# Changelog

## 0.4.0

- Save… writes a JPEG or PNG image too, for forms that only accept images: A4 at 300 dpi,
  chosen with the file type or the name's extension.

## 0.3.0

- The app is in German, French, Italian, Spanish and Croatian too, following the system
  language; About lets you choose another one, used from the next start (id2pdf 0.2.1).
- The README gives one install command per Linux distribution, with pipx, Tk and SANE.

## 0.2.0

- Choose image… finds the card in phone photos too, also taken at a slant or on a busy
  background, and straightens it (id2pdf 0.2.0).
- Adding a side after Clear document no longer fails with 'image "pyimage…" doesn't exist'.
- Ctrl+C in the terminal closes the app like its close button, asking first when a document
  is open, instead of printing a traceback and running on.

## 0.1.0

- First version: scan the front and back of an ID card with SANE, or choose existing images,
  and save both sides on one A4 page as a PDF at the card's real size.
- Remembers the chosen scanner and the theme (system, light or dark); looks for scanners
  without blocking the app, and a scan can be cancelled.
- Warns when no card is found in a chosen image.
