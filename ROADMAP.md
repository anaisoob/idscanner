# Roadmap

Goal: installing ID Scanner should take one command, or one click, especially on Linux.
Today it needs a Python with Tk, SANE for scanning, and local copies of `id2pdf` and
`idscanner` side by side.

## 1. Public repositories

Publish `id2pdf` and `idscanner` (Codeberg or GitHub). Everything below needs real URLs:
the README still links to `../id2pdf`, and PyPI pages should point to the source.

## 2. PyPI

Publish both projects, `id2pdf` first because `idscanner` depends on it. Both names are free.

- Add `readme`, `urls`, `classifiers` and `keywords` to both `pyproject.toml` files.
- Publish from CI with PyPI trusted publishing, triggered by a version tag.
- Check that a wheel contains everything: id2pdf's translations, the icons.
- README: `pipx install idscanner` as the main way. On Linux, prefer pipx over
  `uv tool install`: pipx uses the system Python and its Tk, while uv may pick a Python
  build whose Tk cannot draw smooth fonts or rounded corners (no Xft).

pipx installs all Python dependencies (CustomTkinter, id2pdf, OpenCV, NumPy, Pillow) in an
isolated environment. It cannot install system packages: Tk and, for scanning, SANE still
come from the distribution. When Tk is missing, `idscanner` already prints the command for
the user's system instead of a traceback, and a Tk without Xft is reported in the status line.

## 3. AUR

A `PKGBUILD` for Arch is short once the package is on PyPI: depends on `python`, `tk`, `sane`,
`python-numpy`, `python-opencv`, `python-pillow` and `python-customtkinter` (AUR), plus
id2pdf as its own AUR package. One command, with Tk and SANE included.

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

## Not planned

- **AppImage, Snap:** the same SANE bundling work as Flatpak, with fewer users reached.
- **Debian, Fedora packages:** slow to get into the distributions; PyPI, AUR and Flatpak
  cover these users.
- **A Windows installer** (PyInstaller): only image import works on Windows, so
  `pipx install idscanner` is enough for now.
