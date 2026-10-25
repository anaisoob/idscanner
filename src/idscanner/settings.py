"""User settings, kept as JSON in the system's configuration directory."""

import json
import os
import sys
import tempfile
from pathlib import Path

from .i18n import LANGUAGES

THEMES = ("System", "Light", "Dark")


def settings_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "idscanner" / "settings.json"


def load() -> dict:
    # A missing or damaged file only means the defaults are used.
    try:
        settings = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return settings if isinstance(settings, dict) else {}


def save(**changes) -> None:
    path = settings_path()
    # Write a temporary file and swap it in, so an interrupted save keeps the old settings.
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".settings-", suffix=".json", dir=path.parent)
    except OSError:
        return  # not being able to remember a preference should never stop the app
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(load() | changes, indent=2))
        os.replace(temporary, path)
    except OSError:
        pass
    finally:
        temporary.unlink(missing_ok=True)


def theme() -> str:
    value = load().get("theme")
    return value if value in THEMES else "System"


def language() -> str | None:
    """The language chosen in About, or None to follow the system."""
    value = load().get("language")
    return value if value in LANGUAGES else None
