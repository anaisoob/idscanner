import unittest
from unittest.mock import Mock, patch

from idscanner.system_info import sane_install_help, tk_install_help, tk_lacks_xft


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

    @patch("idscanner.system_info.platform.system", return_value="Linux")
    def test_tk_commands(self, system):
        cases = [
            ({"ID": "linuxmint", "ID_LIKE": "ubuntu debian"}, "sudo apt install python3-tk"),
            ({"ID": "fedora"}, "sudo dnf install python3-tkinter"),
            ({"ID": "endeavouros", "ID_LIKE": "arch"}, "sudo pacman -S tk"),
            ({"ID": "unknown"}, "often called python3-tk"),
        ]
        for release, expected in cases:
            with self.subTest(release=release):
                with patch("idscanner.system_info.platform.freedesktop_os_release", return_value=release):
                    self.assertIn(expected, tk_install_help())

    def test_tk_other_systems(self):
        for system, expected in (("Windows", "tcl/tk and IDLE"), ("Darwin", "brew install python-tk")):
            with self.subTest(system=system):
                with patch("idscanner.system_info.platform.system", return_value=system):
                    self.assertIn(expected, tk_install_help())

    def test_tk_lacks_xft(self):
        def tk(windowing, fontsystem):
            return Mock(call=lambda *args: windowing if args == ("tk", "windowingsystem") else fontsystem)

        self.assertTrue(tk_lacks_xft(tk("x11", "x11")))
        self.assertFalse(tk_lacks_xft(tk("x11", "xft")))
        self.assertFalse(tk_lacks_xft(tk("win32", "")))
        self.assertFalse(tk_lacks_xft(Mock(call=Mock(side_effect=RuntimeError))))
