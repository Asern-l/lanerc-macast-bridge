# Unified local-player and TV-relay renderer for Macast.
#
# Macast Metadata
# <macast.title>Lanerc Cast Pro</macast.title>
# <macast.renderer>LanercProRenderer</macast.renderer>
# <macast.platform>win32</macast.platform>
# <macast.version>1.0.0</macast.version>
# <macast.host_version>0.7</macast.host_version>
# <macast.author>Asern-l</macast.author>
# <macast.desc>Local playback and selectable DLNA TV relay in one renderer.</macast.desc>

import json
import logging
import os
import threading
import webbrowser
from enum import Enum
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cherrypy

from macast import Setting
from macast.gui import MenuItem
from macast.renderer import Renderer, RendererSetting
from renderer.lanerc_potplayer import LanercPotPlayerRenderer, _find_potplayer
from renderer.lanerc_proxy import LanercHLSRenderer
from renderer.lanerc_tv import DLNAController, LanercTVRenderer, TVSetting, _find_ffmpeg


logger = logging.getLogger("LanercProRenderer")
logger.setLevel(logging.INFO)


class ProSetting(Enum):
    LanercOutputMode = 9101
    LanercLocalPlayer = 9102
    LanercControlPort = 9103


class _ControlHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    server_version = "LanercCastPro/1.0"

    def _json(self, data, status=200):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/":
            path = os.path.join(os.path.dirname(__file__), "lanerc_pro.html")
            try:
                with open(path, "rb") as handle:
                    payload = handle.read()
            except OSError:
                self.send_error(500, "Control panel is missing")
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path == "/api/status":
            self._json(self.server.renderer.status())
            return
        if self.path == "/api/devices":
            try:
                self._json(self.server.renderer.discover_devices())
            except Exception as exc:
                logger.exception("TV discovery from control panel failed")
                self._json({"error": str(exc)}, status=500)
            return
        self.send_error(404)

    def do_POST(self):
        if self.path != "/api/settings":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            self.server.renderer.update_settings(data)
            self._json(self.server.renderer.status())
        except (ValueError, TypeError) as exc:
            self._json({"error": str(exc)}, status=400)
        except Exception as exc:
            logger.exception("Cannot update Pro settings")
            self._json({"error": str(exc)}, status=500)

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
            MenuItem("Lanerc Cast Pro", enabled=False),
            MenuItem("Open Control Panel", lambda _: self.renderer.open_control_panel()),
        ]


class LanercProRenderer(Renderer):
    def __init__(self):
        super(LanercProRenderer, self).__init__()
        self.controller = DLNAController()
        self.backend = None
        self.backend_key = ""
        self.backend_lock = threading.RLock()
        self.devices_lock = threading.Lock()
        self.devices = []
        self.title = "Lanerc"
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

    def _new_backend(self, key):
        if key == "tv":
            return LanercTVRenderer(controller=self.controller)
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
        return {
            "mode": self._mode(),
            "player": self._player(),
            "selected_tv": selected_ip,
            "devices": devices,
            "availability": {
                "potplayer": bool(_find_potplayer()),
                "ffmpeg": bool(_find_ffmpeg()),
            },
            "control_port": self.control_port,
        }

    def discover_devices(self):
        devices = self.controller.discover(timeout=2)
        result = [
            {"name": device.name, "host": device.host, "location": device.location}
            for device in devices
        ]
        with self.devices_lock:
            self.devices = result
        status = self.status()
        status["devices"] = result
        return status

    def update_settings(self, data):
        mode = data.get("mode", self._mode())
        player = data.get("player", self._player())
        selected_tv = str(data.get("selected_tv", "") or "").strip()
        if mode not in ("local", "tv"):
            raise ValueError("Invalid output mode")
        if player not in ("potplayer", "mpv"):
            raise ValueError("Invalid local player")
        if mode == "tv" and not selected_tv:
            raise ValueError("Select a TV before enabling relay")

        old_key = self._desired_backend()
        Setting.set(ProSetting.LanercOutputMode, mode)
        Setting.set(ProSetting.LanercLocalPlayer, player)
        Setting.set(TVSetting.LanercTVIP, selected_tv)
        if old_key != self._desired_backend():
            with self.backend_lock:
                if self.backend is not None:
                    self.backend.stop()
                    self.backend = None
                    self.backend_key = ""
            self.set_state_stop()
        cherrypy.engine.publish(
            "app_notify",
            "Lanerc Cast Pro",
            "TV relay enabled" if mode == "tv" else "Local playback enabled",
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
        self._ensure_backend().set_media_url(url, start)

    def set_media_title(self, title):
        self.title = title or "Lanerc"
        with self.backend_lock:
            if self.backend is not None:
                self.backend.set_media_title(self.title)

    def set_media_stop(self):
        with self.backend_lock:
            if self.backend is not None:
                self.backend.set_media_stop()
        self.set_state_stop()

    def set_media_pause(self):
        with self.backend_lock:
            if self.backend is not None:
                self.backend.set_media_pause()

    def set_media_resume(self):
        with self.backend_lock:
            if self.backend is not None:
                self.backend.set_media_resume()

    def set_media_position(self, data):
        with self.backend_lock:
            if self.backend is not None:
                self.backend.set_media_position(data)

    def set_media_volume(self, data):
        with self.backend_lock:
            if self.backend is not None:
                self.backend.set_media_volume(data)

    def set_media_mute(self, data):
        with self.backend_lock:
            if self.backend is not None:
                self.backend.set_media_mute(data)

    def stop(self):
        try:
            with self.backend_lock:
                if self.backend is not None:
                    self.backend.stop()
                    self.backend = None
            if self.control_server is not None:
                self.control_server.shutdown()
                self.control_server.server_close()
            if self.control_thread is not None:
                self.control_thread.join(timeout=3)
            self.controller.close()
        finally:
            super(LanercProRenderer, self).stop()
