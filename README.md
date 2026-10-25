# ID Scanner

Scan the front and back of an ID card and save both sides on one A4 page as a PDF,
at the card's real size, like a photocopy. Photos or scans you already have work too:
the card is found, straightened and cut out of the image.

| Light | Dark |
|---|---|
| ![ID Scanner with both sides of a sample card on an A4 page](https://raw.githubusercontent.com/anaisoob/idscanner/main/docs/screenshot-light.png) | ![The same window in dark mode](https://raw.githubusercontent.com/anaisoob/idscanner/main/docs/screenshot-dark.png) |

It works with any card of ID-1 size (85.6 × 54 mm): ID cards, driving licences, health
insurance cards, residence permits. Everything happens on your computer; nothing is uploaded.
The card detection comes from [id2pdf](https://github.com/anaisoob/id2pdf).

| | Scan with a scanner | Use existing images |
|---|---|---|
| Linux | yes, with SANE | yes |
| Windows, macOS | no | yes |

## Install

### Linux

One command installs pipx, Tk and SANE from your distribution, then ID Scanner:

| Distribution | Command |
|---|---|
| Fedora | `sudo dnf install pipx python3-tkinter sane-backends sane-airscan && pipx install idscanner` |
| Debian, Ubuntu, Mint | `sudo apt install pipx python3-tk sane-utils sane-airscan && pipx install idscanner` |
| Arch, Manjaro | `sudo pacman -S python-pipx tk sane sane-airscan && pipx install idscanner` |
| openSUSE | `sudo zypper install python3-pipx python3-tk sane-backends sane-airscan && pipx install idscanner` |

If `idscanner` is not found afterwards, run `pipx ensurepath` and open a new terminal.
SANE is only needed for scanning; sane-airscan adds network scanners and most newer USB
scanners. Check that your scanner shows up with `scanimage -L`. Without SANE the app still
opens and works with image files; **Refresh scanners** explains what to install.

### Windows, macOS

Scanning is not supported there; image files work. You need Python 3.11 or newer with Tk:

- **Windows:** install Python from [python.org](https://www.python.org/downloads/); Tk is included.
  Then run `py -m pip install --user pipx`, `py -m pipx ensurepath` and, in a new terminal,
  `pipx install idscanner`.
- **macOS:** the [python.org](https://www.python.org/downloads/) installer includes Tk.
  With Homebrew: `brew install python-tk pipx && pipx install idscanner`.

### Other ways

[pipx](https://pipx.pypa.io/) keeps the app in its own environment and uses your system's
Python and its Tk. [uv](https://docs.astral.sh/uv/) works too: `uv tool install idscanner`;
on Linux add `--python-preference only-system`, because the Python builds that uv downloads
come with a Tk that cannot draw smooth fonts or rounded corners there.

Without either, use a virtual environment:

```
python3 -m venv idscanner-env                     # Windows: py -m venv idscanner-env
idscanner-env/bin/pip install idscanner           # Windows: idscanner-env\Scripts\pip
```

Then start it with `idscanner` (or `idscanner-env/bin/idscanner`, on Windows
`idscanner-env\Scripts\idscanner`).

## Use

1. Choose your scanner. The app looks for scanners when it starts and remembers your choice;
   click **Refresh scanners** after connecting or switching on a scanner.
2. Put the card face down on the glass, anywhere and with its text upright, and close the lid.
3. Click **Scan front**, turn the card over, then click **Scan back**.
4. Check the preview and click **Save PDF…**.

Either side can be scanned again or replaced on its own. **Choose image…** loads a phone photo
or a scan from disk instead; a card photographed at a slant is straightened. If no card is
found in it, the whole image is added and the side is marked **card not found**: take the photo
on a plain background, away from printed pages, or crop it first.

Print the PDF at 100 % / "actual size", not "fit to page", so the card keeps its real size.

**Cancel scan** stops a running scan; a scan also gives up after three minutes. The app can be
closed while an image is being opened, but not during a scan or while a PDF is being saved.
A failed save never overwrites an existing PDF. **Help** (F1) shows these steps in the app.
**About** lets you choose a light or dark theme, or follow the system; the choice is remembered.

The app is in English, German, French, Italian, Spanish and Croatian and follows the system
language; **About** lets you choose another one, which is used from the next start.

## Development

uv takes id2pdf from a checkout next to this one, so changes to both can be tested together:

```
git clone https://github.com/anaisoob/id2pdf.git
git clone https://github.com/anaisoob/idscanner.git
cd idscanner
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

`src/idscanner/icon.png` and `icon.ico` are drawn by `tools/make_icon.py`;
run `uv run python tools/make_icon.py` after changing it.

Translations are in `src/idscanner/locale/<language>/LC_MESSAGES/idscanner.po`; run
`./tools/update_translations.sh` (needs gettext) after changing a message. A new language also
goes into `LANGUAGES` in `src/idscanner/i18n.py`, and into id2pdf, whose scanning messages the
app shows.

## License

GPL-3.0-or-later; see `LICENSE`. id2pdf uses the same license.
