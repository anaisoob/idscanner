"""Translations of the interface (gettext, domain "idscanner").

The language is the one chosen in About, otherwise the system's; id2pdf's messages follow it.
"""

import gettext
import locale
import os
import re
import subprocess
import sys
from pathlib import Path

LOCALE_DIR = Path(__file__).parent / "locale"
# Each language in its own name, as it is offered in About.
LANGUAGES = {
    "en": "English",
    "de": "Deutsch",
    "es": "Español",
    "fr": "Français",
    "hr": "Hrvatski",
    "it": "Italiano",
}

_language = "en"
_translation: gettext.NullTranslations = gettext.NullTranslations()


def use(language: str) -> None:
    global _language, _translation
    _language = language
    _translation = translation(language)


def current() -> str:
    return _language


def translation(language: str) -> gettext.NullTranslations:
    return gettext.translation("idscanner", LOCALE_DIR, languages=[language], fallback=True)


def _(message: str) -> str:
    return _translation.gettext(message)


def N_(message: str) -> str:
    """Marks a message for translation where it is defined; _() translates it where it is shown."""
    return message


def system_language() -> str:
    """The first supported language the system asks for, otherwise English."""
    for name in preferred_languages():
        code = re.split(r"[_.@-]", name.strip(), maxsplit=1)[0].lower()
        if code in LANGUAGES:
            return code
        if code in ("c", "posix"):
            break
    return "en"


def preferred_languages() -> list[str]:
    # The same variables gettext reads, in its order; LANGUAGE may list several.
    names = os.environ.get("LANGUAGE", "").split(":")
    names += [next((os.environ[key] for key in ("LC_ALL", "LC_MESSAGES", "LANG") if os.environ.get(key)), "")]
    names = [name for name in names if name]
    # Windows and macOS apps usually get no such variables.
    if not names and sys.platform == "win32":
        import ctypes

        names.append(locale.windows_locale.get(ctypes.windll.kernel32.GetUserDefaultUILanguage(), ""))
    elif not names and sys.platform == "darwin":
        try:
            output = subprocess.run(
                ["defaults", "read", "-g", "AppleLanguages"], capture_output=True, text=True, timeout=2
            ).stdout
        except (OSError, subprocess.SubprocessError):
            output = ""
        names += re.findall(r'"?([A-Za-z]{2,3}(?:-[A-Za-z0-9]+)*)"?,?\s*$', output, re.MULTILINE)
    return names
