# Macast PotPlayer renderer with Lanerc HLS compatibility.
#
# Macast Metadata
# <macast.title>Lanerc PotPlayer Renderer</macast.title>
# <macast.renderer>LanercPotPlayerRenderer</macast.renderer>
# <macast.platform>win32</macast.platform>
# <macast.version>0.1.0</macast.version>
# <macast.host_version>0.7</macast.host_version>
# <macast.author>Asern-l</macast.author>
# <macast.desc>Play Lanerc HLS streams with PotPlayer.</macast.desc>

import logging
import os
import subprocess
import threading
import time
import winreg
from urllib.parse import urlsplit

import cherrypy

from macast.renderer import Renderer
from renderer.lanerc_proxy import _HLSBridge


logger = logging.getLogger("LanercPotPlayerRenderer")
logger.setLevel(logging.INFO)


def _find_potplayer():
    registry_keys = (
        r"Software\DAUM\PotPlayer64",
        r"Software\DAUM\PotPlayer",
    )
    for key_name in registry_keys:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_name) as key:
                path = winreg.QueryValueEx(key, "ProgramPath")[0]
                if os.path.isfile(path):
                    return path
        except OSError:
            pass

    candidates = (
        r"D:\PotPlayer\PotPlayerMini64.exe",
        r"D:\PotPlayer\PotPlayerMini.exe",
        r"C:\Program Files\DAUM\PotPlayer\PotPlayerMini64.exe",
        r"C:\Program Files (x86)\DAUM\PotPlayer\PotPlayerMini.exe",
        r"C:\Program Files\PotPlayer\PotPlayerMini64.exe",
    )
    return next((path for path in candidates if os.path.isfile(path)), None)


class LanercPotPlayerRenderer(Renderer):
    def __init__(self):
        super(LanercPotPlayerRenderer, self).__init__()
        self.hls_bridge = _HLSBridge()
        self.player_path = _find_potplayer()
        self.proc = None
        self.position = 0
        self.playing = False
        self.position_thread = threading.Thread(
            target=self._position_tick,
            name="POTPLAYER_POSITION",
            daemon=True,
        )
        self.position_thread.start()

    def _position_tick(self):
        while True:
            time.sleep(1)
            if self.playing:
                self.position += 1
                sec = self.position
                self.set_state_position(
                    "%d:%02d:%02d" % (sec // 3600, (sec % 3600) // 60, sec % 60)
                )

    def _start_player(self, url):
        if not self.player_path:
            cherrypy.engine.publish(
                "app_notify",
                "PotPlayer not found",
                "Select Lanerc MPV Renderer or install PotPlayer.",
            )
            self.set_state_transport_error()
            return
        try:
            proc = subprocess.Popen(
                [self.player_path, url, "/autoplay", "/new"],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self.proc = proc
            proc.wait()
            if self.proc is proc:
                self.proc = None
                self.playing = False
                self.set_state_stop()
        except Exception as exc:
            logger.exception("Cannot start PotPlayer")
            self.playing = False
            self.set_state_transport_error()
            cherrypy.engine.publish("app_notify", "PotPlayer error", str(exc))

    def set_media_url(self, url, start="0"):
        self.set_media_stop()
        path = urlsplit(url).path.lower()
        if urlsplit(url).scheme in ("http", "https") and path.endswith(".m3u8"):
            url = self.hls_bridge.local_url(url, "playlist")
        self.position = 0
        self.playing = True
        threading.Thread(
            target=self._start_player,
            args=(url,),
            name="POTPLAYER_START",
            daemon=True,
        ).start()
        self.set_state_play()
        cherrypy.engine.publish("renderer_av_uri", url)

    def set_media_stop(self):
        proc = self.proc
        self.proc = None
        self.playing = False
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
        self.set_state_stop()
        cherrypy.engine.publish("renderer_av_stop")

    def set_media_pause(self):
        self.set_state_pause()

    def set_media_resume(self):
        if self.playing:
            self.set_state_play()

    def start(self):
        super(LanercPotPlayerRenderer, self).start()
        logger.info("Using PotPlayer at %s", self.player_path)

    def stop(self):
        try:
            self.set_media_stop()
            super(LanercPotPlayerRenderer, self).stop()
        finally:
            self.hls_bridge.close()
