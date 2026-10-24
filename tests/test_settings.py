import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from idscanner import settings


class SettingsTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "idscanner" / "settings.json"
        patcher = patch("idscanner.settings.settings_path", return_value=self.path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_default_theme_without_file(self):
        self.assertEqual(settings.theme(), "System")

    def test_saved_theme_is_kept_with_other_settings(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(json.dumps({"other": 1}))
        settings.save(theme="Dark")
        self.assertEqual(settings.theme(), "Dark")
        self.assertEqual(settings.load(), {"other": 1, "theme": "Dark"})

    def test_damaged_file_or_unknown_theme_falls_back(self):
        self.path.parent.mkdir(parents=True)
        for content in ("not json", "[]", json.dumps({"theme": "Purple"})):
            with self.subTest(content=content):
                self.path.write_text(content)
                self.assertEqual(settings.theme(), "System")

    def test_unwritable_location_is_ignored(self):
        with patch("idscanner.settings.settings_path", return_value=Path(os.devnull) / "settings.json"):
            settings.save(theme="Light")


class SettingsPathTests(unittest.TestCase):
    def test_xdg_config_home_on_linux(self):
        with patch("idscanner.settings.sys.platform", "linux"), patch.dict(os.environ, {"XDG_CONFIG_HOME": "/cfg"}):
            self.assertEqual(settings.settings_path(), Path("/cfg/idscanner/settings.json"))

    def test_appdata_on_windows(self):
        with patch("idscanner.settings.sys.platform", "win32"), patch.dict(os.environ, {"APPDATA": "/appdata"}):
            self.assertEqual(settings.settings_path(), Path("/appdata/idscanner/settings.json"))
