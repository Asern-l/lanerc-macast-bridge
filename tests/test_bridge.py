import importlib.util
import pathlib
import sys
import threading
import types
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_plugin_module():
    macast = types.ModuleType("macast")
    macast.Setting = type("Setting", (), {"mpv_default_path": "mpv"})
    sys.modules["macast"] = macast

    renderer_package = types.ModuleType("macast_renderer")
    renderer_package.__path__ = []
    sys.modules["macast_renderer"] = renderer_package
    mpv_module = types.ModuleType("macast_renderer.mpv")
    mpv_module.MPVRenderer = type("MPVRenderer", (), {})
    sys.modules["macast_renderer.mpv"] = mpv_module

    spec = importlib.util.spec_from_file_location(
        "lanerc_proxy_under_test", ROOT / "lanerc_proxy.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


plugin = load_plugin_module()


class PayloadDetectionTests(unittest.TestCase):
    def test_finds_mpeg_ts_after_jpeg(self):
        jpeg = b"\xff\xd8header\xff\xd9"
        packet = b"\x47" + (b"x" * 187)
        self.assertEqual(plugin._ts_payload_offset(jpeg + packet * 3), len(jpeg))

    def test_rejects_plain_jpeg(self):
        self.assertEqual(plugin._ts_payload_offset(b"\xff\xd8image\xff\xd9"), 0)

    def test_rejects_plain_transport_stream(self):
        packet = b"\x47" + (b"x" * 187)
        self.assertEqual(plugin._ts_payload_offset(packet * 3), 0)


class PlaylistRewriteTests(unittest.TestCase):
    def setUp(self):
        self.bridge = plugin._HLSBridge.__new__(plugin._HLSBridge)
        self.bridge.port = 12345
        self.bridge.targets = {}
        self.bridge.targets_lock = threading.Lock()

    def test_segment_url_is_anonymous_and_ends_in_ts(self):
        body = self.bridge._rewrite_playlist(
            "#EXTM3U\n#EXTINF:10,\nclips/video.jpg\n",
            "https://example.test/path/index.m3u8",
        ).decode()
        media_line = body.splitlines()[-1]

        self.assertTrue(media_line.endswith("/segment.ts"))
        self.assertNotIn("video.jpg", media_line)
        self.assertEqual(
            list(self.bridge.targets.values()),
            ["https://example.test/path/clips/video.jpg"],
        )

    def test_nested_playlist_keeps_m3u8_hint(self):
        body = self.bridge._rewrite_playlist(
            "#EXTM3U\nvariant/index.m3u8\n",
            "https://example.test/master.m3u8",
        ).decode()
        self.assertTrue(body.splitlines()[-1].endswith("/playlist.m3u8"))


if __name__ == "__main__":
    unittest.main()
