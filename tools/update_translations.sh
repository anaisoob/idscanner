#!/bin/sh
# Extract the messages, merge them into the translations and compile them.
# Needs gettext (xgettext, msgmerge, msgfmt).
set -eu
cd "$(dirname "$0")/.."
locale=src/idscanner/locale
mkdir -p "$locale"
xgettext --language=Python --keyword=_ --keyword=N_ --from-code=UTF-8 --package-name=idscanner \
    --output="$locale/idscanner.pot" src/idscanner/*.py
for po in "$locale"/*/LC_MESSAGES/idscanner.po; do
    [ -e "$po" ] || continue
    msgmerge --quiet --update --backup=none "$po" "$locale/idscanner.pot"
    msgfmt --check --output-file="${po%.po}.mo" "$po"
done
