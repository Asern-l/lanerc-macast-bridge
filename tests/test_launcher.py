import json
import os
import pathlib
import tempfile
import unittest
from unittest import mock

import launcher


ROOT = pathlib.Path(__file__).resolve().parents[1]


class LauncherInstallTests(unittest.TestCase):
    def test_install_location_rejects_nonempty_unowned_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = pathlib.Path(temp_dir)
            (path / "user-file.txt").write_text("keep", encoding="utf-8")
            with self.assertRaises(ValueError):
                launcher.validate_install_location(path)

    def test_install_location_requires_marker_for_existing_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = pathlib.Path(temp_dir)
            (path / "engine").mkdir()
            (path / "config").mkdir()
            with self.assertRaises(ValueError):
                launcher.validate_install_location(path)

    def test_bundled_runtime_is_extracted_to_user_directory(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as local_dir:
            source_root = pathlib.Path(source_dir)
            for index, source_name in enumerate(launcher.RUNTIME_FILES):
                path = source_root / source_name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(("runtime-{}".format(index)).encode())
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": local_dir}), mock.patch.object(
                launcher, "resource_root", return_value=source_root
            ):
                executable = launcher.ensure_bundled_runtime()
                self.assertTrue(executable.is_file())
                for source_name, target_name in launcher.RUNTIME_FILES.items():
                    self.assertEqual(
                        (source_root / source_name).read_bytes(),
                        (pathlib.Path(local_dir) / "LanercCast" / target_name).read_bytes(),
                    )

    def test_bundled_runtime_uses_saved_custom_directory(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as local_dir, tempfile.TemporaryDirectory() as custom_dir:
            source_root = pathlib.Path(source_dir)
            for index, source_name in enumerate(launcher.RUNTIME_FILES):
                path = source_root / source_name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(("runtime-{}".format(index)).encode())
            location_file = pathlib.Path(local_dir) / launcher.INSTALL_LOCATION_FILE
            location_file.write_text(json.dumps({"path": custom_dir}), encoding="utf-8")
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": local_dir}), mock.patch.object(
                launcher, "resource_root", return_value=source_root
            ):
                executable = launcher.ensure_bundled_runtime()
                self.assertTrue(executable.is_file())
                self.assertEqual(executable.parent.parent, pathlib.Path(custom_dir))

    def test_fresh_install_creates_current_plugin_and_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.dict(
            os.environ, {"LOCALAPPDATA": temp_dir}
        ), mock.patch.object(launcher, "resource_root", return_value=ROOT):
            launcher.install_plugin()

            settings_path = pathlib.Path(temp_dir) / "xfangfang" / "Macast" / "macast_setting.json"
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(settings["Macast_Renderer"], "Lanerc Cast")
            self.assertEqual(settings["LanercOutputMode"], "local")
            self.assertEqual(settings["LanercPotPlayerPath"], "")
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
