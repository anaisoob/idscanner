# Changelog

## Unreleased

- Ctrl+C in the terminal closes the app like its close button, asking first when a document
  is open, instead of printing a traceback and running on.

## 0.1.0

- First version: scan the front and back of an ID card with SANE, or choose existing images,
  and save both sides on one A4 page as a PDF at the card's real size.
- Remembers the chosen scanner and the theme (system, light or dark); looks for scanners
  without blocking the app, and a scan can be cancelled.
- Warns when no card is found in a chosen image.
