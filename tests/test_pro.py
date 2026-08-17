import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ProPackageTests(unittest.TestCase):
    def test_renderer_metadata_and_control_panel_are_packaged(self):
        plugin = (ROOT / "lanerc_pro.py").read_text(encoding="utf-8")
        panel = (ROOT / "lanerc_pro.html").read_text(encoding="utf-8")
        script = (ROOT / "lanerc_assets" / "app.js").read_text(encoding="utf-8")
        style = (ROOT / "lanerc_assets" / "app.css").read_text(encoding="utf-8")

        self.assertIn("<macast.title>Lanerc Cast</macast.title>", plugin)
        self.assertIn("APP_VERSION = \"2.1.0\"", plugin)
        self.assertIn('id="mode-local"', panel)
        self.assertIn('id="mode-tv"', panel)
        self.assertIn('id="devices"', panel)
        self.assertIn('id="audio-delay"', panel)
        self.assertIn('id="auto-sync"', panel)
        self.assertIn("/api/devices", script)
        self.assertIn("setInterval", script)
        self.assertIn("@media (max-width: 720px)", style)
        self.assertTrue((ROOT / "lanerc_assets" / "brand.svg").is_file())

    def test_installer_selects_unified_renderer(self):
        installer = (ROOT / "install.ps1").read_text(encoding="utf-8")

        self.assertIn("'Lanerc Cast'", installer)
        self.assertIn("lanerc_pro.html", installer)
        self.assertIn("Add-DefaultSetting", installer)
        self.assertNotIn("EscapeHandling", installer)


if __name__ == "__main__":
    unittest.main()
