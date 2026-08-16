import importlib.util
import pathlib
import sys
import types
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class FakeSetting:
    mpv_default_path = "mpv"

    @staticmethod
    def get(_property, default=None):
        return default


def load_tv_module():
    cherrypy = types.ModuleType("cherrypy")
    cherrypy.engine = types.SimpleNamespace(publish=lambda *args, **kwargs: None)
    sys.modules["cherrypy"] = cherrypy

    macast = types.ModuleType("macast")
    macast.__path__ = []
    macast.Setting = FakeSetting
    sys.modules["macast"] = macast
    renderer_module = types.ModuleType("macast.renderer")
    renderer_module.Renderer = type("Renderer", (), {})
    sys.modules["macast.renderer"] = renderer_module

    renderer_package = types.ModuleType("renderer")
    renderer_package.__path__ = []
    sys.modules["renderer"] = renderer_package
    bridge_module = types.ModuleType("renderer.lanerc_proxy")
    bridge_module._HLSBridge = type("_HLSBridge", (), {})
    sys.modules["renderer.lanerc_proxy"] = bridge_module

    spec = importlib.util.spec_from_file_location(
        "lanerc_tv_under_test", ROOT / "lanerc_tv.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tv = load_tv_module()


DESCRIPTION = b"""<?xml version="1.0"?>
<root xmlns="urn:schemas-upnp-org:device-1-0">
  <device>
    <deviceType>urn:schemas-upnp-org:device:MediaRenderer:1</deviceType>
    <friendlyName>Living Room TV</friendlyName>
    <serviceList>
      <service>
        <serviceType>urn:schemas-upnp-org:service:AVTransport:1</serviceType>
        <controlURL>/upnp/control/avtransport</controlURL>
      </service>
      <service>
        <serviceType>urn:schemas-upnp-org:service:RenderingControl:1</serviceType>
        <controlURL>/upnp/control/rendering</controlURL>
      </service>
    </serviceList>
  </device>
</root>
"""


class DeviceDescriptionTests(unittest.TestCase):
    def test_extracts_renderer_and_resolves_control_urls(self):
        device = tv._media_renderer_from_xml(
            "http://192.168.1.20:8000/description.xml", DESCRIPTION
        )

        self.assertEqual(device.name, "Living Room TV")
        self.assertEqual(device.host, "192.168.1.20")
        self.assertEqual(
            device.av_transport_url,
            "http://192.168.1.20:8000/upnp/control/avtransport",
        )
        self.assertEqual(
            device.rendering_control_url,
            "http://192.168.1.20:8000/upnp/control/rendering",
        )


class FakeResponse:
    content = b"ok"

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self):
        self.request = None

    def post(self, url, **kwargs):
        self.request = (url, kwargs)
        return FakeResponse()


class SoapTests(unittest.TestCase):
    def test_set_uri_soap_escapes_media_url(self):
        controller = tv.DLNAController()
        controller.session = FakeSession()
        device = tv.MediaRendererDevice(
            "TV",
            "192.168.1.20",
            "http://192.168.1.20/device.xml",
            "http://192.168.1.20/avtransport",
            "",
        )

        controller.action(
            device,
            "SetAVTransportURI",
            {
                "InstanceID": 0,
                "CurrentURI": "http://192.168.1.10/stream.ts?a=1&b=2",
                "CurrentURIMetaData": "",
            },
        )

        url, kwargs = controller.session.request
        body = kwargs["data"].decode()
        self.assertEqual(url, device.av_transport_url)
        self.assertIn("SetAVTransportURI", body)
        self.assertIn("a=1&amp;b=2", body)
        self.assertEqual(
            kwargs["headers"]["SOAPACTION"],
            '"urn:schemas-upnp-org:service:AVTransport:1#SetAVTransportURI"',
        )

    def test_didl_declares_mpeg_ts(self):
        metadata = tv._didl_metadata("Title & Episode", "http://host/stream.ts")
        self.assertIn("video/mp2t", metadata)
        self.assertIn("Title &amp; Episode", metadata)


class FFmpegCommandTests(unittest.TestCase):
    def test_transcodes_to_h264_aac_mpeg_ts(self):
        relay = tv.FFmpegTVRelay.__new__(tv.FFmpegTVRelay)
        relay.ffmpeg_path = "ffmpeg.exe"
        relay.source_url = "http://127.0.0.1/input.m3u8"
        command = relay._command()

        self.assertIn("libx264", command)
        self.assertIn("aac", command)
        self.assertEqual(command[-2:], ["mpegts", "pipe:1"])


if __name__ == "__main__":
    unittest.main()
