import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ProPackageTests(unittest.TestCase):
    def test_renderer_metadata_and_control_panel_are_packaged(self):
        plugin = (ROOT / "lanerc_pro.py").read_text(encoding="utf-8")
        panel = (ROOT / "lanerc_pro.html").read_text(encoding="utf-8")

        self.assertIn("<macast.title>Lanerc Cast Pro</macast.title>", plugin)
        self.assertIn('id="mode-local"', panel)
        self.assertIn('id="mode-tv"', panel)
        self.assertIn('id="devices"', panel)
        self.assertIn('id="tv-audio"', panel)
        self.assertIn("/api/devices", panel)
        self.assertIn("setInterval", panel)

    def test_installer_selects_unified_renderer(self):
        installer = (ROOT / "install.ps1").read_text(encoding="utf-8")

        self.assertIn("$selectedRenderer = 'Lanerc Cast Pro'", installer)
        self.assertIn("lanerc_pro.html", installer)


if __name__ == "__main__":
    unittest.main()
