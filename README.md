# ID Scanner

A small English-language desktop interface for [id2pdf](../id2pdf).
Scan the front and back of an ID-1 card, preview both sides on an A4 page,
and save a PDF at the card's real size. Existing images can also be loaded;
id2pdf detects and crops the card when possible, otherwise it uses the whole image.
All image processing happens locally.

## Run on Linux

Requires Python 3.11+, Tk, and the sibling `../id2pdf` project.
For scanning, install SANE and confirm your scanner appears in `scanimage -L`.

```bash
# Debian / Ubuntu system dependencies
sudo apt install python3-tk sane-utils

# From this directory, with uv installed
uv sync
uv run idscanner
```

The local id2pdf dependency is configured in `pyproject.toml`.
The project tells uv to use the system Python only: the Python builds uv downloads
ship a Tk without Xft, so CustomTkinter falls back to unscaled bitmap fonts and draws
empty boxes instead of rounded corners. When installing as a tool, do the same:
`uv tool install --python-preference only-system …`.
Alternatively, use a virtual environment and install both projects:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ../id2pdf -e .
.venv/bin/idscanner
```

## Use

1. Click **Refresh scanners**, select a scanner, place the front of the card face down, and close the lid.
2. Click **Scan front**, turn the card over, then click **Scan back**.
3. Check the preview and choose **Save PDF…**. Either side can be replaced independently.

Use **Choose image…** for photos or scans already on disk. If a whole image appears
instead of a cropped card, choose a clearer image or crop it before importing.
Print the resulting PDF at 100% / actual size to preserve card dimensions.
Scanner discovery runs only when you click **Refresh scanners**. If SANE's
`scanimage` command is missing, the app explains how to install it or use existing
images instead. SANE is not required for image import or PDF export.

Scanner discovery, scanning, image processing, and export run in a background thread.
If detection fails, reposition the card and scan that side again.
Scans have a three-minute timeout. Use **Cancel scan** to stop a scan;
the application waits for cleanup before allowing closure.
PDF export uses a temporary file so a failed export does not overwrite an existing PDF.
**Help** (or F1) shows these instructions in the app; **About** shows the version and license.

## Icon

`src/idscanner/icon.png` and `icon.ico` are drawn by `tools/make_icon.py`;
run `uv run python tools/make_icon.py` after changing it.

## License

GPL-3.0-or-later; see `LICENSE`. The id2pdf library uses the same license.
