import sys
import unittest
from unittest.mock import patch

import idscanner


class MainTests(unittest.TestCase):
    @patch.dict(sys.modules, {"tkinter": None})
    @patch("idscanner.system_info.tk_install_help", return_value="install Tk like this")
    def test_missing_tk_explains_instead_of_traceback(self, help):
        with self.assertRaises(SystemExit) as exit:
            idscanner.main()
        self.assertIn("needs Tk", exit.exception.code)
        self.assertIn("install Tk like this", exit.exception.code)
