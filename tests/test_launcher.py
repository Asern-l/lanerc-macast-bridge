import json
import os
import pathlib
import tempfile
import unittest
from unittest import mock

import launcher


ROOT = pathlib.Path(__file__).resolve().parents[1]


class LauncherInstallTests(unittest.TestCase):
    def test_fresh_install_creates_current_plugin_and_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.dict(
            os.environ, {"LOCALAPPDATA": temp_dir}
        ), mock.patch.object(launcher, "resource_root", return_value=ROOT):
            launcher.install_plugin()

            settings_path = pathlib.Path(temp_dir) / "xfangfang" / "Macast" / "macast_setting.json"
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(settings["Macast_Renderer"], "Lanerc Cast")
            self.assertEqual(settings["LanercOutputMode"], "local")
            self.assertFalse(settings["LanercAutoSync"])
            self.assertTrue(launcher.installation_current())

    def test_upgrade_preserves_output_choices(self):
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.dict(
            os.environ, {"LOCALAPPDATA": temp_dir}
        ), mock.patch.object(launcher, "resource_root", return_value=ROOT):
            settings_path = pathlib.Path(temp_dir) / "xfangfang" / "Macast" / "macast_setting.json"
            settings_path.parent.mkdir(parents=True)
            settings_path.write_text(
                json.dumps(
                    {
                        "Macast_Renderer": "Lanerc Cast Pro",
                        "LanercOutputMode": "tv",
                        "LanercTVAudio": "computer",
                        "LanercTVIP": "192.168.1.50",
                    }
                ),
                encoding="utf-8",
            )

            launcher.install_plugin()
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(settings["Macast_Renderer"], "Lanerc Cast")
            self.assertEqual(settings["LanercOutputMode"], "tv")
            self.assertEqual(settings["LanercTVAudio"], "computer")
            self.assertEqual(settings["LanercTVIP"], "192.168.1.50")
            self.assertEqual(len(list((settings_path.parent / "backup").glob("*.json"))), 1)


if __name__ == "__main__":
    unittest.main()
