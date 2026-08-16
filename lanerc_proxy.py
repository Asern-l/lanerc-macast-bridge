# Macast renderer for HLS segments disguised with a JPEG prefix.
#
# Macast Metadata
# <macast.title>Lanerc MPV Renderer</macast.title>
# <macast.renderer>LanercHLSRenderer</macast.renderer>
# <macast.platform>win32</macast.platform>
# <macast.version>0.1.0</macast.version>
# <macast.host_version>0.7</macast.host_version>
# <macast.author>Asern-l</macast.author>
# <macast.desc>Play Lanerc HLS streams with Macast's bundled mpv.</macast.desc>

import hashlib
import logging
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urljoin, urlsplit

import requests

from macast import Setting
from macast_renderer.mpv import MPVRenderer


logger = logging.getLogger("LanercHLSRenderer")
logger.setLevel(logging.INFO)

_PLAYLIST_TYPES = {
    "application/mpegurl",
    "application/vnd.apple.mpegurl",
    "audio/mpegurl",
    "audio/x-mpegurl",
}
_URI_ATTRIBUTE = re.compile(r'URI=("|\')(.*?)(\1)', re.IGNORECASE)


def _ts_payload_offset(data):
    """Return the MPEG-TS offset after a tiny JPEG, or zero if not disguised."""
    if not data.startswith(b"\xff\xd8"):
        return 0

    search_from = 2
    while True:
        eoi = data.find(b"\xff\xd9", search_from)
        if eoi < 0:
            return 0
        offset = eoi + 2
        if (
            len(data) > offset + 376
            and data[offset] == 0x47
            and data[offset + 188] == 0x47
            and data[offset + 376] == 0x47
        ):
            return offset
        search_from = offset


class _ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    server_version = "LanercHLSBridge/0.1"

    def do_GET(self):
        parts = urlsplit(self.path).path.strip("/").split("/")
        token = parts[1] if len(parts) == 3 and parts[0] == "fetch" else ""
        target = self.server.bridge.resolve(token)
        if target is None:
            self.send_error(404, "Unknown media token")
            return
        self.server.bridge.serve(self, target)

    def log_message(self, fmt, *args):
        logger.debug(fmt, *args)


class _ThreadingServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class _HLSBridge:
    def __init__(self):
        self.session = requests.Session()
        # Macast may inherit unrelated HTTP(S)_PROXY variables. Media URLs
        # must use the PC's direct network route, matching mpv's behavior.
        self.session.trust_env = False
        self.targets = {}
        self.targets_lock = threading.Lock()
        self.httpd = _ThreadingServer(("127.0.0.1", 0), _ProxyHandler)
        self.httpd.bridge = self
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(
            target=self.httpd.serve_forever,
            name="LANERC_HLS_PROXY",
            daemon=True,
        )
        self.thread.start()
        logger.info("Lanerc HLS bridge listening on 127.0.0.1:%s", self.port)

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=3)

    def local_url(self, upstream_url, media_kind="asset"):
        names = {
            "playlist": "playlist.m3u8",
            "segment": "segment.ts",
            "asset": "asset.bin",
        }
        token = hashlib.sha256(upstream_url.encode("utf-8")).hexdigest()
        with self.targets_lock:
            self.targets[token] = upstream_url
        return "http://127.0.0.1:{}/fetch/{}/{}".format(
            self.port, token, names[media_kind]
        )

    def resolve(self, token):
        with self.targets_lock:
            return self.targets.get(token)

    def _rewrite_playlist(self, text, base_url):
        output = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                target = urljoin(base_url, stripped)
                kind = "playlist" if urlsplit(target).path.lower().endswith(".m3u8") else "segment"
                line = self.local_url(target, kind)
            elif "URI=" in line.upper():
                line = _URI_ATTRIBUTE.sub(
                    lambda match: 'URI="{}"'.format(
                        self.local_url(urljoin(base_url, match.group(2)))
                    ),
                    line,
                )
            output.append(line)
        return ("\n".join(output) + "\n").encode("utf-8")

    def serve(self, handler, target):
        response = None
        try:
            response = self.session.get(
                target,
                stream=True,
                timeout=(10, 45),
                headers={
                    "Accept": "*/*",
                    "User-Agent": "Mozilla/5.0 LanercHLSBridge/0.1",
                },
            )
            response.raise_for_status()
            response.raw.decode_content = True
            prefix = response.raw.read(1024 * 1024)
            content_type = (
                response.headers.get("Content-Type", "").split(";", 1)[0].lower()
            )

            if prefix.lstrip().startswith(b"#EXTM3U") or content_type in _PLAYLIST_TYPES:
                body = prefix + response.raw.read()
                body = self._rewrite_playlist(
                    body.decode("utf-8-sig"), response.url
                )
                handler.send_response(200)
                handler.send_header("Content-Type", "application/vnd.apple.mpegurl")
                handler.send_header("Content-Length", str(len(body)))
                handler.send_header("Cache-Control", "no-store")
                handler.end_headers()
                handler.wfile.write(body)
                return

            offset = _ts_payload_offset(prefix)
            if offset:
                logger.info("Removed %s-byte JPEG prefix from HLS segment", offset)
                prefix = prefix[offset:]
                content_type = "video/mp2t"

            handler.send_response(200)
            handler.send_header("Content-Type", content_type or "application/octet-stream")
            handler.send_header("Cache-Control", "no-store")
            handler.end_headers()
            handler.wfile.write(prefix)
            while True:
                chunk = response.raw.read(256 * 1024)
                if not chunk:
                    break
                handler.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError):
            logger.debug("Player closed the proxied connection")
        except Exception as exc:
            logger.exception("Proxy request failed")
            try:
                handler.send_error(502, "Upstream media request failed: {}".format(exc))
            except Exception:
                pass
        finally:
            if response is not None:
                response.close()


class LanercHLSRenderer(MPVRenderer):
    def __init__(self, path=Setting.mpv_default_path):
        self.hls_bridge = _HLSBridge()
        super(LanercHLSRenderer, self).__init__(path=path)

    def set_media_url(self, url, start="0"):
        path = urlsplit(url).path.lower()
        if urlsplit(url).scheme in ("http", "https") and path.endswith(".m3u8"):
            logger.info("Routing HLS stream through the Lanerc compatibility bridge")
            url = self.hls_bridge.local_url(url, "playlist")
        super(LanercHLSRenderer, self).set_media_url(url, start)

    def stop(self):
        try:
            super(LanercHLSRenderer, self).stop()
        finally:
            self.hls_bridge.close()
