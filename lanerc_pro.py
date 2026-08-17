# Unified local-player and TV-relay renderer for Macast.
#
# Macast Metadata
# <macast.title>Lanerc Cast</macast.title>
# <macast.renderer>LanercProRenderer</macast.renderer>
# <macast.platform>win32</macast.platform>
# <macast.version>2.1.0</macast.version>
# <macast.host_version>0.7</macast.host_version>
# <macast.author>Asern-l</macast.author>
# <macast.desc>Reliable local playback and optional DLNA TV compatibility relay.</macast.desc>

import json
import logging
import os
import threading
import time
import webbrowser
from enum import Enum
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import cherrypy

from macast import Setting
from macast.gui import MenuItem
from macast.renderer import Renderer, RendererSetting
from macast.utils import SETTING_DIR
from renderer.lanerc_potplayer import LanercPotPlayerRenderer, _find_potplayer
from renderer.lanerc_proxy import LanercHLSRenderer
from renderer.lanerc_tv import DLNAController, LanercTVRenderer, TVSetting, _find_ffmpeg


logger = logging.getLogger("LanercProRenderer")
logger.setLevel(logging.INFO)
if not any(isinstance(handler, logging.FileHandler) for handler in logger.handlers):
    file_handler = logging.FileHandler(
        os.path.join(SETTING_DIR, "lanerc_cast.log"), encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(file_handler)

APP_NAME = "Lanerc Cast"
APP_VERSION = "2.1.0"
ASSET_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml; charset=utf-8",
}


class ProSetting(Enum):
    LanercOutputMode = 9101
    LanercLocalPlayer = 9102
    LanercControlPort = 9103
    LanercTVAudio = 9104
    LanercAudioDelay = 9105
    LanercAutoSync = 9106


class _ControlHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    server_version = "LanercCast/2.1.0"

    def _json(self, data, status=200):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _error(self, status, code, message):
        self._json({"ok": False, "error": {"code": code, "message": message}}, status)

    def _serve_file(self, path, content_type):
        try:
            with open(path, "rb") as handle:
                payload = handle.read()
        except OSError:
            self._error(404, "asset_not_found", "请求的资源不存在")
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        request_path = urlsplit(self.path).path
        if request_path == "/":
            page_path = os.path.join(os.path.dirname(__file__), "lanerc_pro.html")
            self._serve_file(page_path, "text/html; charset=utf-8")
            return
        if request_path.startswith("/assets/"):
            name = os.path.basename(request_path)
            extension = os.path.splitext(name)[1].lower()
            if extension not in ASSET_TYPES or name != request_path.rsplit("/", 1)[-1]:
                self._error(404, "asset_not_found", "请求的资源不存在")
                return
            asset_path = os.path.join(os.path.dirname(__file__), "lanerc_assets", name)
            self._serve_file(asset_path, ASSET_TYPES[extension])
            return
        if request_path == "/api/status":
            self._json({"ok": True, "data": self.server.renderer.status()})
            return
        if request_path == "/api/devices":
            try:
                self._json({"ok": True, "data": self.server.renderer.discover_devices()})
            except Exception:
                logger.exception("TV discovery from control panel failed")
                self._error(500, "discovery_failed", "无法扫描局域网中的电视")
            return
        self._error(404, "not_found", "接口不存在")

    def do_POST(self):
        if urlsplit(self.path).path != "/api/settings":
            self._error(404, "not_found", "接口不存在")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 64 * 1024:
                raise ValueError("请求内容无效")
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            self.server.renderer.update_settings(data)
            self._json({
                "ok": True,
                "data": self.server.renderer.status(),
                "message": "设置已保存，将用于下一次播放",
            })
        except (ValueError, TypeError) as exc:
            self._error(400, "invalid_settings", str(exc))
        except Exception:
            logger.exception("Cannot update settings")
            self._error(500, "settings_failed", "保存设置失败")

    def log_message(self, fmt, *args):
        logger.debug(fmt, *args)


class _ControlServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class ProRendererSetting(RendererSetting):
    def __init__(self, renderer):
        self.renderer = renderer

    def build_menu(self):
        return [
            MenuItem("Lanerc Cast", enabled=False),
            MenuItem("打开控制中心", lambda _: self.renderer.open_control_panel()),
        ]


class LanercProRenderer(Renderer):
    def __init__(self):
        super(LanercProRenderer, self).__init__()
        self.controller = DLNAController()
        self.backend = None
        self.backend_key = ""
        self.audio_backend = None
        self.backend_lock = threading.RLock()
        self.devices_lock = threading.Lock()
        self.devices = []
        self.last_discovery_at = None
        self.last_discovery_error = ""
        self.title = "Lanerc"
        self.media_generation = 0
        self.control_server = None
        self.control_thread = None
        self.control_port = 0
        self.renderer_setting = ProRendererSetting(self)

    def _mode(self):
        mode = str(Setting.get(ProSetting.LanercOutputMode, "local") or "local")
        return mode if mode in ("local", "tv") else "local"

    def _player(self):
        configured = str(
            Setting.get(ProSetting.LanercLocalPlayer, "potplayer") or "potplayer"
        )
        if configured == "potplayer" and _find_potplayer():
            return "potplayer"
        return "mpv"

    def _desired_backend(self):
        return "tv" if self._mode() == "tv" else self._player()

    def _tv_audio(self):
        output = str(Setting.get(ProSetting.LanercTVAudio, "tv") or "tv")
        return output if output in ("tv", "computer") else "tv"

    def _audio_delay(self):
        try:
            return min(8.0, max(0.0, float(Setting.get(ProSetting.LanercAudioDelay, 2.0))))
        except (TypeError, ValueError):
            return 2.0

    def _auto_sync(self):
        return bool(Setting.get(ProSetting.LanercAutoSync, False))

    def _new_backend(self, key):
        if key == "tv":
            return LanercTVRenderer(
                controller=self.controller,
                include_audio=self._tv_audio() == "tv",
            )
        if key == "potplayer":
            return LanercPotPlayerRenderer()
        return LanercHLSRenderer()

    def _ensure_backend(self):
        key = self._desired_backend()
        with self.backend_lock:
            if self.backend is not None and self.backend_key == key:
                return self.backend
            if self.backend is not None:
                self.backend.stop()
            self.backend = self._new_backend(key)
            self.backend_key = key
            self.backend.start()
            if self.title:
                self.backend.set_media_title(self.title)
            logger.info("Pro output backend changed to %s", key)
            return self.backend

    def _ensure_audio_backend(self):
        needs_computer_audio = self._mode() == "tv" and self._tv_audio() == "computer"
        with self.backend_lock:
            if not needs_computer_audio:
                if self.audio_backend is not None:
                    self.audio_backend.stop()
                    self.audio_backend = None
                return None
            if self.audio_backend is None:
                self.audio_backend = LanercPotPlayerRenderer(hidden=True)
                self.audio_backend.start()
                if self.title:
                    self.audio_backend.set_media_title(self.title)
                logger.info("Computer audio output enabled through PotPlayer")
            return self.audio_backend

    def _start_control_server(self):
        configured_port = int(Setting.get(ProSetting.LanercControlPort, 4380) or 4380)
        try:
            server = _ControlServer(("127.0.0.1", configured_port), _ControlHandler)
        except OSError:
            server = _ControlServer(("127.0.0.1", 0), _ControlHandler)
        server.renderer = self
        self.control_server = server
        self.control_port = server.server_address[1]
        self.control_thread = threading.Thread(
            target=server.serve_forever,
            name="LANERC_PRO_CONTROL",
            daemon=True,
        )
        self.control_thread.start()
        logger.info("Control panel: http://127.0.0.1:%s", self.control_port)

    def open_control_panel(self):
        webbrowser.open("http://127.0.0.1:{}/".format(self.control_port))

    def status(self):
        selected_ip = str(Setting.get(TVSetting.LanercTVIP, "") or "")
        with self.devices_lock:
            devices = [dict(item) for item in self.devices]
        selected_device = next(
            (item for item in devices if item["host"] == selected_ip), None
        )
        potplayer_path = _find_potplayer()
        ffmpeg_path = _find_ffmpeg()
        warnings = []
        if self._mode() == "tv" and not ffmpeg_path:
            warnings.append("电视播放需要 FFmpeg，请重新运行安装程序或配置路径。")
        if self._tv_audio() == "computer":
            warnings.append("电脑声音输出属于实验性功能，不同电视的缓冲时间可能导致音画偏差。")
        return {
            "app": {"name": APP_NAME, "version": APP_VERSION},
            "service": {
                "state": "ready" if self.running else "starting",
                "control_port": self.control_port,
                "active_backend": self.backend_key or None,
            },
            "mode": self._mode(),
            "player": self._player(),
            "selected_tv": selected_ip,
            "selected_tv_name": selected_device["name"] if selected_device else "",
            "tv_audio": self._tv_audio(),
            "audio_delay": self._audio_delay(),
            "auto_sync": self._auto_sync(),
            "devices": devices,
            "availability": {
                "potplayer": bool(potplayer_path),
                "potplayer_path": potplayer_path or "",
                "ffmpeg": bool(ffmpeg_path),
                "ffmpeg_path": ffmpeg_path or "",
            },
            "discovery": {
                "last_scan": self.last_discovery_at,
                "error": self.last_discovery_error,
            },
            "warnings": warnings,
        }

    def discover_devices(self):
        preferred_location = str(
            Setting.get(TVSetting.LanercTVLocation, "") or ""
        ).strip()
        try:
            devices = self.controller.discover(
                preferred_location=preferred_location,
                timeout=2,
            )
            self.last_discovery_error = ""
        except Exception as exc:
            self.last_discovery_error = str(exc)
            raise
        result = [
            {"name": device.name, "host": device.host, "location": device.location}
            for device in devices
        ]
        with self.devices_lock:
            self.devices = result
        self.last_discovery_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        status = self.status()
        status["devices"] = result
        return status

    def update_settings(self, data):
        mode = data.get("mode", self._mode())
        player = data.get("player", self._player())
        tv_audio = data.get("tv_audio", self._tv_audio())
        try:
            audio_delay = min(8.0, max(0.0, float(data.get("audio_delay", self._audio_delay()))))
        except (TypeError, ValueError):
            raise ValueError("声音延迟无效")
        auto_sync = bool(data.get("auto_sync", self._auto_sync()))
        selected_tv = str(data.get("selected_tv", "") or "").strip()
        if mode not in ("local", "tv"):
            raise ValueError("输出方式无效")
        if player not in ("potplayer", "mpv"):
            raise ValueError("本机播放器无效")
        if tv_audio not in ("tv", "computer"):
            raise ValueError("声音输出方式无效")
        if tv_audio == "computer" and not _find_potplayer():
            raise ValueError("电脑输出声音需要安装 PotPlayer")
        if mode == "tv" and not selected_tv:
            raise ValueError("启用电视播放前，请先选择电视")

        old_signature = (self._desired_backend(), self._tv_audio())
        Setting.set(ProSetting.LanercOutputMode, mode)
        Setting.set(ProSetting.LanercLocalPlayer, player)
        Setting.set(ProSetting.LanercTVAudio, tv_audio)
        Setting.set(ProSetting.LanercAudioDelay, audio_delay)
        Setting.set(ProSetting.LanercAutoSync, auto_sync)
        Setting.set(TVSetting.LanercTVIP, selected_tv)
        with self.devices_lock:
            selected_device = next(
                (item for item in self.devices if item["host"] == selected_tv), None
            )
        if selected_device is not None:
            Setting.set(TVSetting.LanercTVLocation, selected_device["location"])
        if old_signature != (self._desired_backend(), self._tv_audio()):
            with self.backend_lock:
                self.media_generation += 1
                if self.backend is not None:
                    self.backend.stop()
                    self.backend = None
                    self.backend_key = ""
                if self.audio_backend is not None:
                    self.audio_backend.stop()
                    self.audio_backend = None
            self.set_state_stop()
        cherrypy.engine.publish(
            "app_notify",
            APP_NAME,
            "已切换到电视播放" if mode == "tv" else "已切换到本机播放",
        )

    def start(self):
        super(LanercProRenderer, self).start()
        self._start_control_server()
        threading.Thread(
            target=self.discover_devices,
            name="LANERC_PRO_INITIAL_DISCOVERY",
            daemon=True,
        ).start()

    def set_media_url(self, url, start="0"):
        backend = self._ensure_backend()
        backend.set_media_url(url, start)
        audio_backend = self._ensure_audio_backend()
        if audio_backend is not None:
            with self.backend_lock:
                self.media_generation += 1
                generation = self.media_generation
            threading.Thread(
                target=self._start_computer_audio,
                args=(
                    generation,
                    backend,
                    audio_backend,
                    url,
                    start,
                    self._audio_delay(),
                    self._auto_sync(),
                ),
                name="LANERC_PRO_SPLIT_AUDIO",
                daemon=True,
            ).start()

    def _start_computer_audio(
        self, generation, backend, audio_backend, url, start, delay, auto_sync
    ):
        if not backend.wait_until_streaming(timeout=10):
            logger.warning("TV did not request video; computer audio was not started")
            return
        audio_start = start
        position = (
            backend.wait_for_playback_position(timeout=delay)
            if auto_sync and delay > 0
            else None
        )
        if not auto_sync and delay:
            deadline = time.monotonic() + delay
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                with self.backend_lock:
                    if generation != self.media_generation:
                        return
                time.sleep(min(0.1, remaining))
        if position is not None:
            latest_position = backend.playback_position()
            audio_start = "{:.3f}".format(latest_position or position)
            logger.info("Auto-syncing computer audio at TV position %ss", audio_start)
        with self.backend_lock:
            if (
                generation != self.media_generation
                or audio_backend is not self.audio_backend
                or self._mode() != "tv"
                or self._tv_audio() != "computer"
            ):
                return
        audio_backend.set_media_url(url, audio_start)

    def set_media_title(self, title):
        self.title = title or "Lanerc"
        with self.backend_lock:
            if self.backend is not None:
                self.backend.set_media_title(self.title)
            if self.audio_backend is not None:
                self.audio_backend.set_media_title(self.title)

    def set_media_stop(self):
        with self.backend_lock:
            self.media_generation += 1
            if self.backend is not None:
                self.backend.set_media_stop()
            if self.audio_backend is not None:
                self.audio_backend.set_media_stop()
        self.set_state_stop()

    def set_media_pause(self):
        with self.backend_lock:
            if self.backend is not None:
                self.backend.set_media_pause()
            if self.audio_backend is not None:
                self.audio_backend.set_media_pause()

    def set_media_resume(self):
        with self.backend_lock:
            if self.backend is not None:
                self.backend.set_media_resume()
            if self.audio_backend is not None:
                self.audio_backend.set_media_resume()

    def set_media_position(self, data):
        with self.backend_lock:
            if self.backend is not None:
                self.backend.set_media_position(data)
            if self.audio_backend is not None:
                self.audio_backend.set_media_position(data)

    def set_media_volume(self, data):
        with self.backend_lock:
            if self.backend is not None:
                self.backend.set_media_volume(data)
            if self.audio_backend is not None:
                self.audio_backend.set_media_volume(data)

    def set_media_mute(self, data):
        with self.backend_lock:
            if self.backend is not None:
                self.backend.set_media_mute(data)
            if self.audio_backend is not None:
                self.audio_backend.set_media_mute(data)

    def stop(self):
        try:
            with self.backend_lock:
                if self.backend is not None:
                    self.backend.stop()
                    self.backend = None
                if self.audio_backend is not None:
                    self.audio_backend.stop()
                    self.audio_backend = None
            if self.control_server is not None:
                self.control_server.shutdown()
                self.control_server.server_close()
            if self.control_thread is not None:
                self.control_thread.join(timeout=3)
            self.controller.close()
        finally:
            super(LanercProRenderer, self).stop()
