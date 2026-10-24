# Roadmap

Goal: installing ID Scanner should take one command, or one click, especially on Linux.
Today it is `pipx install idscanner`, plus Tk and, for scanning, SANE from the distribution.

## 1. Public repositories (done)

[id2pdf](https://github.com/anaisoob/id2pdf) and [idscanner](https://github.com/anaisoob/idscanner)
are on GitHub, and the README installs from there.

## 2. PyPI (done)

[id2pdf](https://pypi.org/project/id2pdf/) and [idscanner](https://pypi.org/project/idscanner/)
are on PyPI (0.2.0 since 2026-10-24). A version tag (`git tag vX.Y.Z && git push origin main --tags`) runs
`.github/workflows/publish.yml`, which tests, builds and uploads with PyPI trusted publishing.
Release `id2pdf` first when `idscanner` needs a new version of it.

pipx installs all Python dependencies (CustomTkinter, id2pdf, OpenCV, NumPy, Pillow) in an
isolated environment. It cannot install system packages: Tk and, for scanning, SANE still
come from the distribution. When Tk is missing, `idscanner` already prints the command for
the user's system instead of a traceback, and a Tk without Xft is reported in the status line.

## 3. AUR

A `PKGBUILD` for Arch is short once the package is on PyPI: depends on `python`, `tk`, `sane`,
`python-numpy`, `python-opencv`, `python-pillow` and `python-customtkinter` (AUR), plus
id2pdf as its own AUR package. One command, with Tk and SANE included.

The package also brings the entry in the app menu: a `.desktop` file and the icon in
`/usr/share/applications` and `/usr/share/icons`. A wheel from PyPI cannot put them there
(pipx keeps everything in its own environment), so ID Scanner has no menu entry until then.

## 4. Flatpak (only if needed)

The best experience for people who never open a terminal: one click in GNOME Software or KDE
Discover, with Python, Tk and SANE bundled. Worth doing once people outside the terminal
audience actually use the app; it takes a few days plus Flathub review.

- Build `sane-backends` and `sane-airscan` inside the Flatpak, otherwise network and most
  newer USB scanners will not work. GNOME Document Scanner and NAPS2 on Flathub do the same.
- Permissions: `--device=all` for USB scanners, `--share=network` for network scanners,
  `--socket=x11` for Tk.
- Python dependencies through `flatpak-pip-generator`; OpenCV makes the package large.
- Flathub needs a metainfo file, a `.desktop` file and the icon (`src/idscanner/icon.png`).
- The runtime has to be updated about once a year.

## Card detection in photos (when needed)

id2pdf finds a card in a photo by its straight sides, its proportions, the colour difference
across each side, the fine print inside and edges ending at its corners. A doubtful card is
reported as not found rather than cut out wrongly. On the ID-card photos of MIDV-2020 (see
`tools/evaluate_midv.py` in id2pdf) that gives 344 of 500 found and 3 wrong: on a plain table
50 of 50, on a printed page 5 of 50, on a white keyboard 26 of 50.

Newspapers, printed pages and keyboards fail because they look like what is looked for: long
straight lines (rows of text, rows of keys) fill the list of candidate sides, they make many
rectangles of a card's proportions, a block of text is as full of fine print as a card, and
a pale card on white paper shows little colour difference across its edge. The best outline
is then weak or has a rival nearly as good, and no card is reported.

The advice to photograph the card on a plain surface (Help, README) covers this. Worth
improving only if people often photograph cards on papers:

- **Colour:** cards are coloured (security print, coat of arms, photo), newspapers and most
  keyboards are black, white or grey. Comparing colour saturation inside and outside an
  outline would likely tell a card from a block of text. A moderate change; measure it on
  MIDV-2020 before and after, judging first by the number of wrong cut-outs.
- **A trained detector** (a neural network for documents) solves this best, but adds a large
  dependency and a model. Not worth it for a helper tool.

## Not planned

- **AppImage, Snap:** the same SANE bundling work as Flatpak, with fewer users reached.
- **Debian, Fedora packages:** slow to get into the distributions; PyPI, AUR and Flatpak
  cover these users.
- **A Windows installer** (PyInstaller): only image import works on Windows, so
  `pipx install idscanner` is enough for now.
