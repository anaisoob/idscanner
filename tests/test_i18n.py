import ast
import contextlib
import gettext
import io
import os
import string
import sys
import unittest
from unittest.mock import patch

import idscanner
from idscanner import i18n, scan_worker

TEMPLATE = i18n.LOCALE_DIR / "idscanner.pot"


def template_messages():
    messages, parts = [], None
    for line in TEMPLATE.read_text(encoding="utf-8").splitlines():
        if line.startswith("msgid "):
            parts = [ast.literal_eval(line[6:])]
        elif line.startswith('"') and parts is not None:
            parts.append(ast.literal_eval(line))
        elif line.startswith("msgstr") and parts is not None:
            messages.append("".join(parts))
            parts = None
    return [message for message in messages if message]


def fields(message):
    return {field for _, field, _, _ in string.Formatter().parse(message) if field is not None}


class TranslationTests(unittest.TestCase):
    def tearDown(self):
        i18n.use("en")

    def test_every_language_has_every_message_with_the_same_fields(self):
        self.assertEqual(
            sorted(path.name for path in i18n.LOCALE_DIR.iterdir() if path.is_dir()),
            sorted(set(i18n.LANGUAGES) - {"en"}),
        )
        for language in set(i18n.LANGUAGES) - {"en"}:
            # Reads the compiled .mo, so a translation that was not compiled fails too.
            catalog = gettext.translation("idscanner", i18n.LOCALE_DIR, languages=[language])._catalog
            for message in template_messages():
                with self.subTest(language=language, message=message):
                    self.assertTrue(catalog.get(message), "not translated")
                    self.assertEqual(fields(catalog[message]), fields(message))

    def test_language_from_environment(self):
        cases = [
            ({"LANG": "de_DE.UTF-8"}, "de"),
            ({"LANGUAGE": "pt:fr_FR", "LANG": "de_DE.UTF-8"}, "fr"),
            ({"LC_ALL": "it_IT.UTF-8", "LANG": "de_DE.UTF-8"}, "it"),
            ({"LANG": "es_ES@euro"}, "es"),
            ({"LANG": "pt_BR.UTF-8"}, "en"),
            ({"LANG": "C.UTF-8"}, "en"),
        ]
        for environment, language in cases:
            with self.subTest(environment=environment), patch.dict(os.environ, environment, clear=True):
                self.assertEqual(i18n.system_language(), language)

    @patch.dict(sys.modules, {"tkinter": None})
    @patch("idscanner.system_info.tk_install_help", return_value="")
    @patch("idscanner.settings.language", return_value="fr")
    def test_saved_language_wins_over_the_system(self, language, help):
        with patch.dict(os.environ, {"LANG": "de_DE.UTF-8"}), self.assertRaises(SystemExit) as exit:
            idscanner.main()
        self.assertIn("a besoin de Tk", exit.exception.code)

    def test_scan_worker_reports_in_the_language_it_is_given(self):
        def scan(device, front, wait):
            wait("first")
            wait("second")

        stderr = io.StringIO()
        with (
            patch.object(sys, "argv", ["scan_worker", "test", "front", "de"]),
            patch("idscanner.scan_worker.id2pdf.scan_card_side", side_effect=scan),
            contextlib.redirect_stderr(stderr),
        ):
            self.assertEqual(scan_worker.main(), 1)
        self.assertIn("second\nLegen Sie die Karte zurecht", stderr.getvalue())
