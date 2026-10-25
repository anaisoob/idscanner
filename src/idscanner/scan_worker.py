"""Scanner subprocess: send only the finished PNG over stdout."""

import contextlib
import sys

import id2pdf

from . import i18n
from .i18n import _


def main():
    # argv: device, "front" or "back", language
    i18n.use(sys.argv[3])
    id2pdf.set_language(sys.argv[3])
    prompts = 0

    def wait(message):
        nonlocal prompts
        prompts += 1
        if prompts > 1:
            raise id2pdf.ScanError(message + "\n" + _("Adjust the card and click Scan again."))

    try:
        with contextlib.redirect_stdout(sys.stderr):
            image = id2pdf.scan_card_side(sys.argv[1], front=sys.argv[2] == "front", wait=wait)
        image.save(sys.stdout.buffer, format="PNG")
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
