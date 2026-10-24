"""User settings, kept as JSON in the system's configuration directory."""

import json
import os
import sys
from pathlib import Path

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
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(load() | changes, indent=2), encoding="utf-8")
    except OSError:
        pass  # not being able to remember a preference should never stop the app


def theme() -> str:
    value = load().get("theme")
    return value if value in THEMES else "System"
