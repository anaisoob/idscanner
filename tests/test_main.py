import sys
import unittest
from unittest.mock import patch

import idscanner
from idscanner import i18n


class MainTests(unittest.TestCase):
    def tearDown(self):
        i18n.use("en")

    @patch.dict(sys.modules, {"tkinter": None})
    @patch("idscanner.system_info.tk_install_help", return_value="install Tk like this")
    @patch("idscanner.settings.language", return_value="en")
    def test_missing_tk_explains_instead_of_traceback(self, language, help):
        with self.assertRaises(SystemExit) as exit:
            idscanner.main()
        self.assertIn("needs Tk", exit.exception.code)
        self.assertIn("install Tk like this", exit.exception.code)
