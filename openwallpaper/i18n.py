"""Übersetzungen über gettext. Die Quellsprache ist Englisch."""
import gettext
import json
import os
from pathlib import Path

DOMAIN = "openwallpaper"
NAMES = {"en": "English", "de": "Deutsch"}


def _localedir():
    here = Path(__file__).resolve().parent
    env = os.environ.get("OPENWALLPAPER_LOCALEDIR")
    for d in (env, "/app/share/locale", "/usr/share/locale", "/usr/local/share/locale",
              here.parent / "locale"):
        if d and any(Path(d).glob(f"*/LC_MESSAGES/{DOMAIN}.mo")):
            return Path(d)
    return None


def _saved_language():
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    try:
        return json.loads((base / "openwallpaper" / "config.json").read_text()).get("language", "")
    except (OSError, ValueError):
        return ""


def available():
    found = {"en"}
    d = _localedir()
    if d:
        found |= {p.parent.parent.name for p in d.glob(f"*/LC_MESSAGES/{DOMAIN}.mo")}
    return sorted(found)


_pref = os.environ.get("OPENWALLPAPER_LANG") or _saved_language()
_trans = gettext.translation(DOMAIN, str(_localedir() or "/nonexistent"),
                             languages=[_pref] if _pref else None, fallback=True)

tr = _trans.gettext
ntr = _trans.ngettext


def lang():
    return (_trans.info().get("language") or "en").split("_")[0]


def num(n):
    text = f"{n:,}"
    return text.replace(",", ".") if lang() == "de" else text
