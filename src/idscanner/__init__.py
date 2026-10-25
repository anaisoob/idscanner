"""A small, local-only desktop interface for scanning ID cards."""

import sys

from . import i18n, settings
from .i18n import _


def main():
    i18n.use(settings.language() or i18n.system_language())
    # Tk is not installable from PyPI, so explain how to get it instead of showing a traceback.
    try:
        import tkinter  # noqa: F401
    except ImportError:
        from .system_info import tk_install_help

        sys.exit(
            _("ID Scanner needs Tk, the graphical toolkit for Python, which is missing.") + f"\n\n{tk_install_help()}"
        )

    from .app import main as run

    run()
