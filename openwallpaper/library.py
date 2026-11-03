"""Bibliothek, Einstellungen und Steuerung des Renderers."""
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import time
import uuid
import zipfile
from pathlib import Path

from . import APP_ID
from .i18n import tr

HOME = Path.home()
DATA = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share")) / "openwallpaper"
CONF = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config")) / "openwallpaper"
CACHE = Path(os.environ.get("XDG_CACHE_HOME", HOME / ".cache")) / "openwallpaper"
MEDIA = DATA / "media"
LIB_FILE = DATA / "library.json"
CONF_FILE = CONF / "config.json"
CTL_FILE = CACHE / "renderer.ctl"
HB_FILE = CACHE / "renderer.hb"
PLAYLIST = CACHE / "playlist.json"
LOG_FILE = CACHE / "renderer.log"
KEEP_IN_CACHE = {CTL_FILE.name, HB_FILE.name, HB_FILE.with_suffix(".tmp").name,
                 PLAYLIST.name, LOG_FILE.name}
AUTOSTART = HOME / ".config" / "autostart" / f"{APP_ID}.desktop"
IN_FLATPAK = Path("/.flatpak-info").exists()

VIDEO_EXT = {".mp4", ".webm", ".mkv", ".mov", ".avi", ".ogv", ".gif", ".m4v"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
STEAM_WORKSHOP = [
    HOME / ".local/share/Steam/steamapps/workshop/content/431960",
    HOME / ".steam/steam/steamapps/workshop/content/431960",
    HOME / ".var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/workshop/content/431960",
]

for p in (DATA, CONF, CACHE, MEDIA):
    p.mkdir(parents=True, exist_ok=True)

DEFAULTS = {
    "fit": "fill", "current": None, "sync_system": True,
    "pause_fullscreen": True, "pause_battery": True,
    "fps_limit": 0, "volume": 0,
    "slideshow": False, "interval": 15, "slideshow_pool": "all",
    "schedule": False, "day_id": None, "night_id": None,
    "day_start": 7, "night_start": 19,
    "monitors": {},
    "pixabay_key": "", "wallhaven_key": "", "source": "Wallhaven", "paused": False,
    "wh_purity": "100", "wh_categories": "111", "wh_atleast": "", "wh_ratio": "",
    "adult_ok": False, "language": "",
}


def _read(path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def _write(path, obj):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False))
    tmp.replace(path)


def load_items():
    return _read(LIB_FILE, [])


def save_items(items):
    _write(LIB_FILE, items)


def load_config():
    return {**DEFAULTS, **_read(CONF_FILE, {})}


def save_config(cfg):
    _write(CONF_FILE, cfg)


def set_config(**kw):
    cfg = load_config()
    cfg.update(kw)
    save_config(cfg)
    return cfg


def kind_of(path):
    ext = Path(path).suffix.lower()
    if ext in IMAGE_EXT:
        return "image"
    return "video" if ext in VIDEO_EXT else None


def file_sig(path):
    p = Path(path)
    size = p.stat().st_size
    h = hashlib.sha1()
    with open(p, "rb") as f:
        h.update(f.read(1 << 20))
        if size > (1 << 20):
            f.seek(-min(size, 1 << 16), 2)
            h.update(f.read())
    return f"{size}-{h.hexdigest()[:16]}"


def snapshot(path, out, width=None):
    import gi
    gi.require_version("Gst", "1.0")
    gi.require_version("GstApp", "1.0")
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf, GLib, Gst, GstApp  # noqa: F401
    Gst.init(None)
    caps = "video/x-raw,format=RGB" + (f",width={width}" if width else "")
    pipe = Gst.parse_launch(
        "filesrc name=src ! decodebin ! videoconvert ! videoscale ! "
        "capsfilter name=cf ! appsink name=sink max-buffers=1 sync=false")
    pipe.get_by_name("src").set_property("location", str(path))
    pipe.get_by_name("cf").set_property("caps", Gst.Caps.from_string(caps))
    sink = pipe.get_by_name("sink")
    try:
        pipe.set_state(Gst.State.PAUSED)
        ret, _s, _p = pipe.get_state(20 * Gst.SECOND)
        if ret == Gst.StateChangeReturn.FAILURE:
            return False
        ok, dur = pipe.query_duration(Gst.Format.TIME)
        if ok and dur > 0:
            pipe.seek_simple(Gst.Format.TIME,
                             Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
                             min(dur // 4, 5 * Gst.SECOND))
            pipe.get_state(20 * Gst.SECOND)
        sample = sink.try_pull_preroll(10 * Gst.SECOND)
        if not sample:
            return False
        st = sample.get_caps().get_structure(0)
        w, h = st.get_value("width"), st.get_value("height")
        buf = sample.get_buffer()
        ok, info = buf.map(Gst.MapFlags.READ)
        if not ok:
            return False
        try:
            data = GLib.Bytes.new(bytes(info.data))
        finally:
            buf.unmap(info)
        pb = GdkPixbuf.Pixbuf.new_from_bytes(
            data, GdkPixbuf.Colorspace.RGB, False, 8, w, h, ((w * 3 + 3) // 4) * 4)
        pb.savev(str(out), "jpeg", ["quality"], ["90"])
        return True
    finally:
        pipe.set_state(Gst.State.NULL)


def make_thumb(path, kind):
    out = CACHE / (hashlib.sha1(str(path).encode()).hexdigest() + ".jpg")
    if out.exists():
        return str(out)
    try:
        if kind == "image":
            import gi
            gi.require_version("GdkPixbuf", "2.0")
            from gi.repository import GdkPixbuf
            GdkPixbuf.Pixbuf.new_from_file_at_scale(
                str(path), 480, -1, True).savev(str(out), "jpeg", [], [])
        else:
            snapshot(path, out, 480)
    except Exception:  # noqa: BLE001
        return None
    return str(out) if out.exists() else None


def _import_copy(path):
    src = Path(path)
    if src.parent == MEDIA:
        return src
    dest = MEDIA / src.name
    if dest.exists() and dest.stat().st_size != src.stat().st_size:
        dest = MEDIA / f"{hashlib.sha1(str(src).encode()).hexdigest()[:8]}-{src.name}"
    if not dest.exists():
        shutil.copyfile(src, dest)
    return dest


def _add(path, title=None, source=tr("Local"), license="", author="", url="",
         copy=True, size="", tags=None):
    kind = kind_of(path)
    if not kind:
        return None, False
    sig = file_sig(path)
    items = load_items()
    dirty = False
    for it in items:
        if not it.get("sig") and Path(it["path"]).exists():
            it["sig"], dirty = file_sig(it["path"]), True
        if it.get("sig") == sig:
            if dirty:
                save_items(items)
            return it, False
    final = str(_import_copy(path) if copy else Path(path).resolve())
    for it in items:
        if it["path"] == final:
            return it, False
    item = {
        "id": hashlib.sha1(final.encode()).hexdigest()[:12],
        "title": title or Path(final).stem,
        "path": final, "kind": kind, "thumb": make_thumb(final, kind),
        "source": source, "license": license, "author": author, "url": url,
        "size": size, "fav": False, "tags": list(tags or []), "sig": sig,
        "added": int(time.time()),
    }
    items.append(item)
    save_items(items)
    return item, True


def add_item(path, title=None, source=tr("Local"), license="", author="", url="",
             copy=True, size="", tags=None):
    return _add(path, title, source, license, author, url, copy, size, tags)[0]


def remove_item(item_id, delete_file=False):
    items = load_items()
    for it in items:
        if it["id"] == item_id and delete_file and Path(it["path"]).parent == MEDIA:
            Path(it["path"]).unlink(missing_ok=True)
    save_items([it for it in items if it["id"] != item_id])
    cfg = load_config()
    if cfg.get("current") == item_id or item_id in cfg["monitors"].values():
        stop_and_restore()


def toggle_fav(item_id):
    items = load_items()
    state = False
    for it in items:
        if it["id"] == item_id:
            it["fav"] = state = not it.get("fav", False)
    save_items(items)
    return state


def set_tags(item_id, text):
    tags = []
    for t in text.split(","):
        t = t.strip()
        if t and t.lower() not in [x.lower() for x in tags]:
            tags.append(t[:30])
    items = load_items()
    for it in items:
        if it["id"] == item_id:
            it["tags"] = tags
    save_items(items)
    return tags


def all_tags(limit=12):
    names, count = {}, {}
    for it in load_items():
        for t in it.get("tags", []):
            names.setdefault(t.lower(), t)
            count[t.lower()] = count.get(t.lower(), 0) + 1
    top = sorted(count, key=lambda k: (-count[k], k))[:limit]
    return sorted((names[k] for k in top), key=str.lower)


def find_item(query):
    q = query.lower()
    items = load_items()
    for it in items:
        if it["id"] == query:
            return it
    for it in items:
        if q in it["title"].lower():
            return it
    return None


def import_paths(paths):
    new = dup = 0
    for p in map(Path, paths):
        files = [f for f in p.rglob("*") if f.is_file()] if p.is_dir() else [p]
        for f in files:
            if not kind_of(f) or f.name == "preview.gif":
                continue
            item, is_new = _add(f)
            if item:
                new, dup = new + is_new, dup + (not is_new)
    return new, dup


def import_steam():
    added, roots = 0, 0
    for root in STEAM_WORKSHOP:
        if not root.is_dir():
            continue
        roots += 1
        for proj in root.glob("*/project.json"):
            meta = _read(proj, {})
            if str(meta.get("type", "")).lower() != "video":
                continue
            media = proj.parent / meta.get("file", "")
            if media.is_file():
                _, is_new = _add(media, meta.get("title"), "Wallpaper Engine",
                                 tr("Rights belong to the authors"), copy=False)
                added += is_new
    return added, roots


def export_backup(dest, with_media=True):
    items = load_items()
    cfg = load_config()
    for k in ("pixabay_key", "wallhaven_key", "orig_bg"):
        cfg.pop(k, None)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_STORED, allowZip64=True) as z:
        z.writestr("library.json", json.dumps(items, indent=2, ensure_ascii=False))
        z.writestr("config.json", json.dumps(cfg, indent=2, ensure_ascii=False))
        if with_media:
            for it in items:
                p = Path(it["path"])
                if p.parent == MEDIA and p.exists():
                    z.write(p, "media/" + p.name)
    return len(items)


def import_backup(src):
    added = 0
    with zipfile.ZipFile(src) as z:
        names = set(z.namelist())
        if "library.json" not in names:
            raise RuntimeError(tr("This is not an OpenWallpaper backup"))
        incoming = json.loads(z.read("library.json"))
        items = load_items()
        ids = {i["id"] for i in items}
        sigs = {i.get("sig") for i in items if i.get("sig")}
        for it in incoming:
            name = Path(it.get("path", "")).name
            arc = "media/" + name
            if not name or it.get("id") in ids or it.get("sig") in sigs or arc not in names:
                continue
            dest = MEDIA / name
            if not dest.exists():
                with z.open(arc) as s, open(dest, "wb") as d:
                    shutil.copyfileobj(s, d)
            it["path"] = str(dest)
            it["thumb"] = make_thumb(dest, it["kind"])
            items.append(it)
            ids.add(it["id"])
            added += 1
        save_items(items)
    return added


BG_SCHEMA = "org.gnome.desktop.background"
BG_KEYS = ("picture-uri", "picture-uri-dark", "picture-options")


def _gs(*args):
    try:
        r = subprocess.run(["gsettings", *args], capture_output=True,
                           text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


SYSTEM_FRAME = DATA / "system-frame.txt"


def _make_frame(item):
    if item["kind"] == "image":
        return item["path"]
    dest = DATA / f"frame-{item['id']}.jpg"
    if not dest.exists() and not snapshot(item["path"], dest):
        return None
    for old in DATA.glob("frame-*.jpg"):
        if old != dest:
            old.unlink(missing_ok=True)
    return str(dest)


def sync_system_background(item):
    cfg = load_config()
    if not cfg.get("sync_system", True):
        return
    frame = _make_frame(item)
    if not frame:
        return
    if IN_FLATPAK:
        SYSTEM_FRAME.write_text(frame)
    elif _gs("list-schemas") is not None:
        if not cfg.get("orig_bg"):
            orig = {k: _gs("get", BG_SCHEMA, k) for k in BG_KEYS}
            if "openwallpaper/frame-" not in (orig.get("picture-uri") or ""):
                cfg["orig_bg"] = orig
                save_config(cfg)
        uri = "file://" + frame
        for k in ("picture-uri", "picture-uri-dark"):
            _gs("set", BG_SCHEMA, k, uri)
        _gs("set", BG_SCHEMA, "picture-options", "zoom")


def restore_system_background():
    if IN_FLATPAK:
        SYSTEM_FRAME.write_text("")
        return
    cfg = load_config()
    orig = cfg.pop("orig_bg", None)
    if orig:
        for k, v in orig.items():
            if v:
                _gs("set", BG_SCHEMA, k, v.strip("'"))
        save_config(cfg)


_children = []


def _reap():
    for c in _children[:]:
        if c.poll() is not None:
            _children.remove(c)


def is_running():
    try:
        return time.time() - float(HB_FILE.read_text()) < 4
    except (OSError, ValueError):
        return False


def stop():
    CTL_FILE.write_text("stop")
    for _ in range(30):
        _reap()
        if not is_running():
            break
        time.sleep(0.1)
    HB_FILE.unlink(missing_ok=True)


def stop_and_restore():
    stop()
    restore_system_background()
    set_config(current=None, monitors={}, schedule=False)


def _existing():
    return {i["id"]: i for i in load_items() if Path(i["path"]).exists()}


def _entry(i):
    return {"path": i["path"], "kind": i["kind"], "id": i["id"]}


def _pool(cfg):
    items = list(_existing().values())
    pool = cfg.get("slideshow_pool", "all")
    if pool == "fav":
        sel = [i for i in items if i.get("fav")]
    elif pool.startswith("tag:"):
        sel = [i for i in items if pool[4:] in i.get("tags", [])]
    else:
        sel = items
    return sel or items


def schedule_items(cfg=None):
    cfg = cfg or load_config()
    by = _existing()
    d, n = by.get(cfg.get("day_id")), by.get(cfg.get("night_id"))
    return (d, n) if d and n else None


def build_playlist(cfg):
    by = _existing()
    mons = {c: [_entry(by[i])] for c, i in cfg["monitors"].items() if i in by}
    sched = schedule_items(cfg) if cfg["schedule"] else None
    if sched:
        return {"default": [_entry(sched[0]), _entry(sched[1])], "monitors": mons,
                "schedule": {"day_start": int(cfg["day_start"]),
                             "night_start": int(cfg["night_start"])}}
    default = []
    cur = by.get(cfg.get("current"))
    if cur:
        default = [_entry(cur)]
        if cfg["slideshow"]:
            rest = [_entry(i) for i in _pool(cfg) if i["id"] != cur["id"]]
            random.shuffle(rest)
            default += rest
    return {"default": default, "monitors": mons, "schedule": None}


class NeedSpawn(Exception):
    pass


NO_SPAWN = False


def _renderer_args(cfg):
    slide = cfg["slideshow"] and not (cfg["schedule"] and schedule_items(cfg))
    a = ["--fit", cfg["fit"],
         "--interval", str(int(cfg["interval"]) * 60 if slide else 0),
         "--fps", str(int(cfg["fps_limit"])), "--volume", str(int(cfg["volume"]))]
    if cfg["pause_fullscreen"]:
        a.append("--pause-fullscreen")
    if cfg["pause_battery"]:
        a.append("--pause-battery")
    return a


def _can_hot_reload(cfg):
    if not is_running():
        return False
    return _read(PLAYLIST, {}).get("args") == _renderer_args(cfg)


def _check_spawn():
    if NO_SPAWN and not _can_hot_reload(load_config()):
        raise NeedSpawn


def start():
    cfg = load_config()
    pl = build_playlist(cfg)
    if not pl["default"] and not pl["monitors"]:
        return False
    rargs = _renderer_args(cfg)
    pl["args"] = rargs
    if _can_hot_reload(cfg):
        _write(PLAYLIST, pl)
        return True
    if NO_SPAWN:
        raise NeedSpawn
    token = uuid.uuid4().hex
    CTL_FILE.write_text(token)
    _write(PLAYLIST, pl)
    args = [sys.executable, "-m", "openwallpaper.renderer", "--token", token, *rargs]
    with open(LOG_FILE, "w") as log:
        proc = subprocess.Popen(
            args, cwd=str(Path(__file__).resolve().parent.parent),
            start_new_session=True, stdin=subprocess.DEVNULL,
            stdout=log, stderr=log)
    _children.append(proc)
    return True


def apply(item, sync=True, monitor=None):
    _check_spawn()
    cfg = load_config()
    if monitor:
        mons = {**cfg["monitors"], monitor: item["id"]}
        set_config(monitors=mons, current=cfg.get("current") or item["id"],
                   paused=False)
    else:
        set_config(current=item["id"], monitors={}, schedule=False, paused=False)
        if sync:
            sync_system_background(item)
    start()


def set_schedule(on):
    if on and not schedule_items():
        return False
    set_config(schedule=on)
    if on:
        start()
    elif is_running():
        if current_item():
            start()
        else:
            stop_and_restore()
    return True


def current_item():
    return _existing().get(load_config().get("current"))


def restore():
    return True if is_running() else start()


def reapply():
    if is_running():
        start()


def random_item():
    cfg = load_config()
    items = _pool(cfg)
    pool = [i for i in items if i["id"] != cfg.get("current")] or items
    return random.choice(pool) if pool else None


def next_item():
    cfg = load_config()
    items = _pool(cfg)
    if not items:
        return None
    ids = [i["id"] for i in items]
    cur = cfg.get("current")
    return items[(ids.index(cur) + 1 if cur in ids else 0) % len(items)]


def set_autostart(on):
    if not on:
        AUTOSTART.unlink(missing_ok=True)
        return
    AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
    cmd = (f"flatpak run {APP_ID} --restore" if IN_FLATPAK
           else f"{sys.executable} -m openwallpaper --restore")
    AUTOSTART.write_text(
        "[Desktop Entry]\nType=Application\nName=OpenWallpaper\n"
        f"Exec={cmd}\nX-GNOME-Autostart-enabled=true\n")


def cache_size():
    return sum(f.stat().st_size for f in CACHE.glob("*") if f.is_file())


def clear_cache():
    for f in CACHE.glob("*"):
        if f.is_file() and f.name not in KEEP_IN_CACHE:
            f.unlink(missing_ok=True)
    items = load_items()
    for it in items:
        it["thumb"] = make_thumb(it["path"], it["kind"])
    save_items(items)
