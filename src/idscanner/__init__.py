"""A small, local-only desktop interface for scanning ID cards."""

import sys


def main():
    # Tk is not installable from PyPI, so explain how to get it instead of showing a traceback.
    try:
        import tkinter  # noqa: F401
    except ImportError:
        from .system_info import tk_install_help

        sys.exit(f"ID Scanner needs Tk, the graphical toolkit for Python, which is missing.\n\n{tk_install_help()}")

    from .app import main as run

    run()
