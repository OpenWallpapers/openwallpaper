#!/bin/sh
set -e
UUID=openwallpaper-bg@openwallpapers.github.io
SRC="$(dirname "$(readlink -f "$0")")/$UUID"
DST="$HOME/.local/share/gnome-shell/extensions/$UUID"
mkdir -p "$DST"
cp "$SRC"/extension.js "$SRC"/metadata.json "$DST"/
echo "Installiert nach $DST"
echo "Danach neu anmelden (X11: Alt+F2, r, Enter) und aktivieren:"
echo "  gnome-extensions enable $UUID"
