# Macast TV relay renderer with Lanerc HLS compatibility.
#
# Macast Metadata
# <macast.title>Lanerc TV Renderer</macast.title>
# <macast.renderer>LanercTVRenderer</macast.renderer>
# <macast.platform>win32</macast.platform>
# <macast.version>0.2.0</macast.version>
# <macast.host_version>0.7</macast.host_version>
# <macast.author>Asern-l</macast.author>
# <macast.desc>Transcode Lanerc streams and relay them to a DLNA TV.</macast.desc>

import logging
import os
import shutil
import socket
import subprocess
import threading
import uuid
from collections import namedtuple
from enum import Enum
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urljoin, urlsplit

import cherrypy
import requests
from lxml import etree as ElementTree

from macast import Setting
from macast.renderer import Renderer
from renderer.lanerc_proxy import _HLSBridge


logger = logging.getLogger("LanercTVRenderer")
logger.setLevel(logging.INFO)

SSDP_ADDRESS = ("239.255.255.250", 1900)
AVTRANSPORT_TYPE = "urn:schemas-upnp-org:service:AVTransport:1"
RENDERING_CONTROL_TYPE = "urn:schemas-upnp-org:service:RenderingControl:1"
SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
SOAP_ENCODING = "http://schemas.xmlsoap.org/soap/encoding/"

MediaRendererDevice = namedtuple(
    "MediaRendererDevice",
    "name host location av_transport_url rendering_control_url",
)


class TVSetting(Enum):
    LanercTVIP = 9001
    LanercFFmpegPath = 9002
    LanercRelayPort = 9003


def _text(element, child_name, default=""):
    for child in element:
        if child.tag.rsplit("}", 1)[-1] == child_name:
            return child.text or default
    return default


def _media_renderer_from_xml(description_url, xml_data):
    root = ElementTree.fromstring(xml_data)
    for device in root.iter():
        if device.tag.rsplit("}", 1)[-1] != "device":
            continue
        if not _text(device, "deviceType").endswith("MediaRenderer:1"):
            continue

        av_transport_url = ""
        rendering_control_url = ""
        for service in device.iter():
            if service.tag.rsplit("}", 1)[-1] != "service":
                continue
            service_type = _text(service, "serviceType")
            control_url = urljoin(description_url, _text(service, "controlURL"))
            if service_type == AVTRANSPORT_TYPE:
                av_transport_url = control_url
            elif service_type == RENDERING_CONTROL_TYPE:
                rendering_control_url = control_url

        if av_transport_url:
            return MediaRendererDevice(
                name=_text(device, "friendlyName", "DLNA TV"),
                host=urlsplit(description_url).hostname or "",
                location=description_url,
                av_transport_url=av_transport_url,
                rendering_control_url=rendering_control_url,
            )
    return None


class DLNAController:
    def __init__(self):
        self.session = requests.Session()
        self.session.trust_env = False

    def discover(self, preferred_ip="", timeout=3):
        request = (
            "M-SEARCH * HTTP/1.1\r\n"
            "HOST: 239.255.255.250:1900\r\n"
            'MAN: "ssdp:discover"\r\n'
            "MX: 2\r\n"
            "ST: urn:schemas-upnp-org:device:MediaRenderer:1\r\n\r\n"
        ).encode("ascii")
        locations = set()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        try:
            sock.settimeout(timeout)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            sock.sendto(request, SSDP_ADDRESS)
            while True:
                try:
                    data, _ = sock.recvfrom(65535)
                except socket.timeout:
                    break
                headers = self._parse_ssdp_headers(data)
                location = headers.get("location", "")
                if urlsplit(location).scheme in ("http", "https"):
                    locations.add(location)
        finally:
            sock.close()

        devices = []
        for location in locations:
            try:
                response = self.session.get(location, timeout=(2, 4))
                response.raise_for_status()
                device = _media_renderer_from_xml(location, response.content)
            except Exception:
                logger.debug("Cannot read DLNA device at %s", location, exc_info=True)
                continue
            if device is None or device.name.lower().startswith("macast"):
                continue
            if preferred_ip and device.host != preferred_ip:
                continue
            devices.append(device)

        devices.sort(key=lambda item: (item.host, item.name))
        return devices

    @staticmethod
    def _parse_ssdp_headers(data):
        headers = {}
        text = data.decode("iso-8859-1", errors="replace")
        for line in text.split("\r\n")[1:]:
            if ":" in line:
                name, value = line.split(":", 1)
                headers[name.strip().lower()] = value.strip()
        return headers

    def action(self, device, action_name, parameters=None):
        parameters = parameters or {}
        body = ElementTree.Element(
            ElementTree.QName(SOAP_NS, "Envelope"),
            {ElementTree.QName(SOAP_NS, "encodingStyle"): SOAP_ENCODING},
        )
        soap_body = ElementTree.SubElement(body, ElementTree.QName(SOAP_NS, "Body"))
        action = ElementTree.SubElement(
            soap_body, ElementTree.QName(AVTRANSPORT_TYPE, action_name)
        )
        for name, value in parameters.items():
            ElementTree.SubElement(action, name).text = str(value)

        response = self.session.post(
            device.av_transport_url,
            data=ElementTree.tostring(body, encoding="utf-8", xml_declaration=True),
            timeout=(3, 8),
            headers={
                "Content-Type": 'text/xml; charset="utf-8"',
                "SOAPACTION": '"{}#{}"'.format(AVTRANSPORT_TYPE, action_name),
            },
        )
        response.raise_for_status()
        return response.content


def _find_ffmpeg():
    configured = Setting.get(TVSetting.LanercFFmpegPath, "")
    candidates = [
        configured,
        shutil.which("ffmpeg") or "",
        r"D:\Macast\tools\ffmpeg\bin\ffmpeg.exe",
        r"D:\ffmpeg\bin\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links\ffmpeg.exe"),
    ]
    return next((path for path in candidates if path and os.path.isfile(path)), None)


def _local_ip_for(remote_host):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect((remote_host, 9))
        return sock.getsockname()[0]
    finally:
        sock.close()


def _xml_escape(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


class _RelayHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    server_version = "LanercTVRelay/0.2"

    def do_HEAD(self):
        if self.path != self.server.relay.stream_path:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "video/mp2t")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def do_GET(self):
        if self.path != self.server.relay.stream_path:
            self.send_error(404)
            return
        self.server.relay.stream(self)

    def log_message(self, fmt, *args):
        logger.debug(fmt, *args)


class _RelayHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class FFmpegTVRelay:
    def __init__(self, port=0):
        try:
            self.httpd = _RelayHTTPServer(("0.0.0.0", port), _RelayHandler)
        except OSError:
            logger.warning("Relay port %s is unavailable; using a random port", port)
            self.httpd = _RelayHTTPServer(("0.0.0.0", 0), _RelayHandler)
        self.httpd.relay = self
        self.port = self.httpd.server_address[1]
        self.stream_path = "/stream/{}.ts".format(uuid.uuid4().hex)
        self.source_url = ""
        self.ffmpeg_path = ""
        self.process = None
        self.process_lock = threading.Lock()
        self.thread = threading.Thread(
            target=self.httpd.serve_forever,
            name="LANERC_TV_HTTP",
            daemon=True,
        )
        self.thread.start()

    def prepare(self, source_url, ffmpeg_path):
        self.stop_process()
        self.source_url = source_url
        self.ffmpeg_path = ffmpeg_path
        self.stream_path = "/stream/{}.ts".format(uuid.uuid4().hex)

    def url_for(self, device):
        return "http://{}:{}{}".format(
            _local_ip_for(device.host), self.port, self.stream_path
        )

    def _command(self):
        return [
            self.ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "warning",
            "-fflags",
            "+genpts+discardcorrupt",
            "-analyzeduration",
            "10000000",
            "-probesize",
            "10000000",
            "-i",
            self.source_url,
            "-map",
            "0:v:0?",
            "-map",
            "0:a:0?",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-tune",
            "zerolatency",
            "-profile:v",
            "main",
            "-level:v",
            "4.1",
            "-pix_fmt",
            "yuv420p",
            "-vf",
            "scale=w='min(1920,iw)':h=-2",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-ac",
            "2",
            "-ar",
            "48000",
            "-muxdelay",
            "0",
            "-muxpreload",
            "0",
            "-f",
            "mpegts",
            "pipe:1",
        ]

    def stream(self, handler):
        with self.process_lock:
            if self.process is not None and self.process.poll() is None:
                handler.send_error(409, "A TV is already reading the stream")
                return
            if not self.source_url or not self.ffmpeg_path:
                handler.send_error(503, "No media is ready")
                return
            process = subprocess.Popen(
                self._command(),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self.process = process

        handler.send_response(200)
        handler.send_header("Content-Type", "video/mp2t")
        handler.send_header("Cache-Control", "no-store")
        handler.end_headers()
        try:
            while True:
                chunk = process.stdout.read(256 * 1024)
                if not chunk:
                    break
                handler.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError):
            logger.info("TV closed the transcoded stream")
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
            with self.process_lock:
                if self.process is process:
                    self.process = None

    def stop_process(self):
        with self.process_lock:
            process = self.process
            self.process = None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()

    def close(self):
        self.stop_process()
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=3)


def _didl_metadata(title, media_url):
    return (
        '<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">'
        '<item id="0" parentID="0" restricted="1">'
        "<dc:title>{}</dc:title>"
        "<upnp:class>object.item.videoItem</upnp:class>"
        '<res protocolInfo="http-get:*:video/mp2t:*">{}</res>'
        "</item></DIDL-Lite>"
    ).format(_xml_escape(title or "Lanerc"), _xml_escape(media_url))


class LanercTVRenderer(Renderer):
    def __init__(self):
        super(LanercTVRenderer, self).__init__()
        self.hls_bridge = _HLSBridge()
        self.controller = DLNAController()
        self.relay = FFmpegTVRelay(
            int(Setting.get(TVSetting.LanercRelayPort, 0) or 0)
        )
        self.device = None
        self.source_url = ""
        self.title = "Lanerc"
        self.worker = None

    def _notify(self, title, message):
        cherrypy.engine.publish("app_notify", title, message)

    def _start_tv(self):
        ffmpeg_path = _find_ffmpeg()
        if ffmpeg_path is None:
            self.set_state_transport_error()
            self._notify(
                "FFmpeg not found",
                "Install FFmpeg or set LanercFFmpegPath in macast_setting.json.",
            )
            return

        preferred_ip = str(Setting.get(TVSetting.LanercTVIP, "") or "").strip()
        devices = self.controller.discover(preferred_ip=preferred_ip)
        if not devices:
            self.set_state_transport_error()
            message = "No DLNA TV found on the local network."
            if preferred_ip:
                message = "No DLNA TV found at {}.".format(preferred_ip)
            self._notify("TV not found", message)
            return

        self.device = devices[0]
        source = self.source_url
        if (
            urlsplit(source).scheme in ("http", "https")
            and urlsplit(source).path.lower().endswith(".m3u8")
        ):
            source = self.hls_bridge.local_url(source, "playlist")
        self.relay.prepare(source, ffmpeg_path)
        media_url = self.relay.url_for(self.device)
        metadata = _didl_metadata(self.title, media_url)
        try:
            self.controller.action(
                self.device,
                "SetAVTransportURI",
                {
                    "InstanceID": 0,
                    "CurrentURI": media_url,
                    "CurrentURIMetaData": metadata,
                },
            )
            self.controller.action(
                self.device, "Play", {"InstanceID": 0, "Speed": 1}
            )
        except Exception as exc:
            logger.exception("Cannot start playback on TV")
            self.set_state_transport_error()
            self._notify("TV playback error", str(exc))
            return

        self.set_state_play()
        self._notify("Casting to TV", self.device.name)

    def set_media_url(self, url, start="0"):
        self.set_media_stop()
        self.source_url = url
        self.set_state_transport("TRANSITIONING")
        self.worker = threading.Thread(
            target=self._start_tv,
            name="LANERC_TV_START",
            daemon=True,
        )
        self.worker.start()

    def set_media_title(self, title):
        self.title = title or "Lanerc"

    def set_media_stop(self):
        self.relay.stop_process()
        if self.device is not None:
            try:
                self.controller.action(self.device, "Stop", {"InstanceID": 0})
            except Exception:
                logger.debug("Cannot stop TV playback", exc_info=True)
        self.set_state_stop()

    def set_media_pause(self):
        if self.device is not None:
            try:
                self.controller.action(self.device, "Pause", {"InstanceID": 0})
                self.set_state_pause()
            except Exception:
                logger.debug("Cannot pause TV playback", exc_info=True)

    def set_media_resume(self):
        if self.device is not None:
            try:
                self.controller.action(
                    self.device, "Play", {"InstanceID": 0, "Speed": 1}
                )
                self.set_state_play()
            except Exception:
                logger.debug("Cannot resume TV playback", exc_info=True)

    def stop(self):
        try:
            self.set_media_stop()
            super(LanercTVRenderer, self).stop()
        finally:
            self.relay.close()
            self.hls_bridge.close()
