import unittest
from unittest.mock import patch

from idscanner.system_info import sane_install_help


class SystemInfoTests(unittest.TestCase):
    @patch("idscanner.system_info.platform.system", return_value="Linux")
    def test_distribution_commands_and_parent_fallback(self, system):
        cases = [
            ({"ID": "ubuntu"}, "sudo apt install sane-utils"),
            ({"ID": "linuxmint", "ID_LIKE": "ubuntu debian"}, "sudo apt install sane-utils"),
            ({"ID": "fedora"}, "sudo dnf install sane-backends"),
            ({"ID": "arch"}, "sudo pacman -S sane"),
            ({"ID": "manjaro", "ID_LIKE": "arch"}, "sudo pacman -S sane"),
            ({"ID": "opensuse-tumbleweed"}, "sudo zypper install sane-backends"),
            ({"ID": "unknown", "PRETTY_NAME": "Unknown Linux"}, "package providing scanimage"),
        ]
        for release, expected in cases:
            with self.subTest(release=release):
                with patch("idscanner.system_info.platform.freedesktop_os_release", return_value=release):
                    self.assertIn(expected, sane_install_help())

    @patch("idscanner.system_info.platform.system", return_value="Linux")
    @patch("idscanner.system_info.platform.freedesktop_os_release", side_effect=OSError)
    def test_missing_os_release(self, release, system):
        self.assertIn("package providing scanimage", sane_install_help())

    @patch("idscanner.system_info.platform.system", return_value="Windows")
    def test_other_system(self, system):
        self.assertIn("requires Linux", sane_install_help())
