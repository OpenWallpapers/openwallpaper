#!/bin/sh
cd "$(dirname "$(readlink -f "$0")")" || exit 1
exec env PYTHONPATH="$PWD" python3 -m openwallpaper "$@"
