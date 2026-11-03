"""Der Prozess, der das Wallpaper zeichnet."""
import argparse
import ctypes
import datetime
import json
import signal
import sys
from pathlib import Path

import gi

gi.require_version("Gst", "1.0")
gi.require_version("GstVideo", "1.0")
from gi.repository import GLib, Gst, GstVideo  # noqa: E402

from . import library  # noqa: E402
from .i18n import tr  # noqa: E402

X = ctypes.CDLL("libX11.so.6")
XEXT = ctypes.CDLL("libXext.so.6")
XRR = ctypes.CDLL("libXrandr.so.2")


class XRRMonitorInfo(ctypes.Structure):
    _fields_ = [("name", ctypes.c_ulong), ("primary", ctypes.c_int),
                ("automatic", ctypes.c_int), ("noutput", ctypes.c_int),
                ("x", ctypes.c_int), ("y", ctypes.c_int),
                ("width", ctypes.c_int), ("height", ctypes.c_int),
                ("mwidth", ctypes.c_int), ("mheight", ctypes.c_int),
                ("outputs", ctypes.c_void_p)]


X.XOpenDisplay.restype = ctypes.c_void_p
X.XOpenDisplay.argtypes = [ctypes.c_char_p]
X.XDefaultScreen.argtypes = [ctypes.c_void_p]
X.XRootWindow.restype = ctypes.c_ulong
X.XRootWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
X.XDisplayWidth.argtypes = [ctypes.c_void_p, ctypes.c_int]
X.XDisplayHeight.argtypes = [ctypes.c_void_p, ctypes.c_int]
X.XBlackPixel.restype = ctypes.c_ulong
X.XBlackPixel.argtypes = [ctypes.c_void_p, ctypes.c_int]
X.XCreateSimpleWindow.restype = ctypes.c_ulong
X.XCreateSimpleWindow.argtypes = [
    ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int,
    ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_ulong, ctypes.c_ulong,
]
X.XInternAtom.restype = ctypes.c_ulong
X.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
X.XGetAtomName.restype = ctypes.c_void_p
X.XGetAtomName.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
X.XChangeProperty.argtypes = [
    ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong,
    ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int,
]
X.XGetWindowProperty.argtypes = [
    ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_long, ctypes.c_long,
    ctypes.c_int, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
    ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_ulong),
    ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
]
X.XStoreName.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_char_p]
X.XMapWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
X.XLowerWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
X.XFlush.argtypes = [ctypes.c_void_p]
X.XFree.argtypes = [ctypes.c_void_p]
X.XDestroyWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
X.XCloseDisplay.argtypes = [ctypes.c_void_p]
X.XQueryTree.argtypes = [
    ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
    ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)),
    ctypes.POINTER(ctypes.c_uint),
]
XEXT.XShapeCombineRectangles.argtypes = [
    ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
]
XRR.XRRGetMonitors.restype = ctypes.POINTER(XRRMonitorInfo)
XRR.XRRGetMonitors.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int,
                               ctypes.POINTER(ctypes.c_int)]
XRR.XRRFreeMonitors.argtypes = [ctypes.POINTER(XRRMonitorInfo)]

XA_ATOM, XA_WINDOW = 4, 33
SHAPE_INPUT, SHAPE_SET = 2, 0


def _atom(d, name):
    return X.XInternAtom(d, name.encode(), 0)


def _set_atoms(d, win, prop, names):
    atoms = (ctypes.c_ulong * len(names))(*[_atom(d, n) for n in names])
    X.XChangeProperty(d, win, _atom(d, prop), XA_ATOM, 32, 0, atoms, len(names))


def _get_longs(d, win, prop, typ):
    actual, fmt = ctypes.c_ulong(), ctypes.c_int()
    n, after = ctypes.c_ulong(), ctypes.c_ulong()
    data = ctypes.POINTER(ctypes.c_ubyte)()
    if X.XGetWindowProperty(d, win, _atom(d, prop), 0, 1024, 0, typ,
                            ctypes.byref(actual), ctypes.byref(fmt),
                            ctypes.byref(n), ctypes.byref(after),
                            ctypes.byref(data)) != 0 or not data:
        return []
    vals = list(ctypes.cast(data, ctypes.POINTER(ctypes.c_ulong))[:n.value])
    X.XFree(data)
    return vals


def list_monitors(d):
    root = X.XRootWindow(d, X.XDefaultScreen(d))
    n = ctypes.c_int()
    arr = XRR.XRRGetMonitors(d, root, 1, ctypes.byref(n))
    mons = []
    if arr:
        for i in range(n.value):
            m = arr[i]
            raw = X.XGetAtomName(d, m.name)
            name = ctypes.string_at(raw).decode() if raw else f"monitor{i}"
            if raw:
                X.XFree(raw)
            mons.append((name, m.x, m.y, m.width, m.height))
        XRR.XRRFreeMonitors(arr)
    if not mons:
        s = X.XDefaultScreen(d)
        mons = [("screen", 0, 0, X.XDisplayWidth(d, s), X.XDisplayHeight(d, s))]
    return mons


def make_click_through(d, win):
    XEXT.XShapeCombineRectangles(d, win, SHAPE_INPUT, 0, 0, None, 0, SHAPE_SET, 0)
    root, parent = ctypes.c_ulong(), ctypes.c_ulong()
    kids = ctypes.POINTER(ctypes.c_ulong)()
    n = ctypes.c_uint()
    if X.XQueryTree(d, win, ctypes.byref(root), ctypes.byref(parent),
                    ctypes.byref(kids), ctypes.byref(n)) and kids:
        for i in range(n.value):
            XEXT.XShapeCombineRectangles(d, kids[i], SHAPE_INPUT, 0, 0, None, 0,
                                         SHAPE_SET, 0)
        X.XFree(kids)


def fullscreen_active(d):
    root = X.XRootWindow(d, X.XDefaultScreen(d))
    act = _get_longs(d, root, "_NET_ACTIVE_WINDOW", XA_WINDOW)
    if not act or not act[0]:
        return False
    return _atom(d, "_NET_WM_STATE_FULLSCREEN") in _get_longs(
        d, act[0], "_NET_WM_STATE", XA_ATOM)


def on_battery():
    base = Path("/sys/class/power_supply")
    try:
        supplies = list(base.iterdir())
    except OSError:
        return False
    has_bat, ac_online = False, False
    for s in supplies:
        try:
            kind = (s / "type").read_text().strip()
            if kind == "Battery":
                has_bat = True
            elif kind in ("Mains", "USB") and (s / "online").read_text().strip() == "1":
                ac_online = True
        except OSError:
            continue
    return has_bat and not ac_online


def create_desktop_window(d, x, y, w, h):
    win = X.XCreateSimpleWindow(d, X.XRootWindow(d, X.XDefaultScreen(d)), x, y, w, h,
                                0, 0, X.XBlackPixel(d, X.XDefaultScreen(d)))
    X.XStoreName(d, win, b"OpenWallpaper")
    _set_atoms(d, win, "_NET_WM_WINDOW_TYPE", ["_NET_WM_WINDOW_TYPE_DESKTOP"])
    _set_atoms(d, win, "_NET_WM_STATE", [
        "_NET_WM_STATE_BELOW", "_NET_WM_STATE_STICKY",
        "_NET_WM_STATE_SKIP_TASKBAR", "_NET_WM_STATE_SKIP_PAGER"])
    make_click_through(d, win)
    X.XMapWindow(d, win)
    X.XLowerWindow(d, win)
    return win


def _gst_video_filter(chain):
    try:
        return Gst.parse_bin_from_description(" ! ".join(chain), True)
    except GLib.Error as e:
        print("Filter:", e, file=sys.stderr)
        return None


class Output:

    def __init__(self, ctl, name, geo, win):
        self.ctl, self.name, self.geo, self.win = ctl, name, geo, win
        self.items, self.index = [], 0
        self.pipe = None
        self.sink_name = None
        self.sinks = ["glimagesink", "ximagesink"]
        self.paused = False

    def set_items(self, items):
        key = [i["path"] for i in items]
        if key == [i["path"] for i in self.items] and self.pipe:
            return
        self.items, self.index = items, 0
        self.play()

    def play(self):
        self.teardown()
        if not self.items:
            return
        item = self.items[self.index]
        if not self.sink_name:
            if not self.sinks:
                print(tr("No video sink available"), file=sys.stderr)
                return
            self.sink_name = self.sinks.pop(0)
        sink = Gst.ElementFactory.make(self.sink_name, None)
        if sink is None:
            self.sink_name = None
            return self.play()
        pipe = Gst.ElementFactory.make("playbin", None)
        a = self.ctl.args
        flags = "video+audio" if a.volume > 0 and item["kind"] == "video" else "video"
        Gst.util_set_object_arg(pipe, "flags", flags)
        pipe.set_property("volume", a.volume / 100.0)
        pipe.set_property("uri", GLib.filename_to_uri(item["path"], None))
        pipe.set_property("video-sink", sink)
        chain = []
        if item["kind"] == "image":
            chain.append('imagefreeze ! capsfilter caps="video/x-raw,framerate=1/1"')
        elif a.fps > 0:
            chain.append("videorate drop-only=true ! capsfilter "
                         f'caps="video/x-raw,framerate=0/1,max-framerate={a.fps}/1"')
        if a.fit == "fill":
            _x, _y, w, h = self.geo
            chain.append(f"aspectratiocrop aspect-ratio={w}/{h}")
        if chain:
            flt = _gst_video_filter(chain)
            if flt:
                pipe.set_property("video-filter", flt)
        GstVideo.VideoOverlay.set_window_handle(sink, self.win)
        GstVideo.VideoOverlay.handle_events(sink, False)
        bus = pipe.get_bus()
        bus.add_signal_watch()
        bus.connect("message::eos", self._on_eos)
        bus.connect("message::error", self._on_error)
        self.pipe = pipe
        pipe.set_state(Gst.State.PAUSED if self.paused else Gst.State.PLAYING)

    def teardown(self):
        if self.pipe:
            self.pipe.get_bus().remove_signal_watch()
            self.pipe.set_state(Gst.State.NULL)
            self.pipe = None

    def pause(self, on):
        self.paused = on
        if self.pipe:
            self.pipe.set_state(Gst.State.PAUSED if on else Gst.State.PLAYING)

    def _on_eos(self, *_):
        if self.items[self.index]["kind"] == "image" or not self.pipe:
            return
        self.pipe.seek_simple(Gst.Format.TIME,
                              Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, 0)

    def _on_error(self, _bus, msg):
        err, dbg = msg.parse_error()
        print(tr("Error ({}):").format(self.name), err.message, dbg, file=sys.stderr)
        if self.sinks:
            self.sink_name = None
            return self.play()
        if len(self.items) > 1:
            self.next()

    def next(self):
        if len(self.items) > 1:
            self.index = (self.index + 1) % len(self.items)
            self.play()


class Controller:
    def __init__(self, args, d):
        self.args, self.d = args, d
        self.loop = GLib.MainLoop()
        self.outputs = {}
        self.layout = None
        self.fs = False
        self.bat = False
        self.manual = bool(library.load_config().get("paused"))
        self.tick_n = 0
        self.scheduled = None
        self.pl_mtime = library.PLAYLIST.stat().st_mtime_ns
        self.sync_outputs()

    def sync_outputs(self):
        mons = list_monitors(self.d)
        layout = [(n, x, y, w, h) for n, x, y, w, h in mons]
        if layout == self.layout:
            return
        self.layout = layout
        for o in self.outputs.values():
            o.teardown()
            X.XDestroyWindow(self.d, o.win)
        self.outputs = {}
        for name, x, y, w, h in layout:
            win = create_desktop_window(self.d, x, y, w, h)
            self.outputs[name] = Output(self, name, (x, y, w, h), win)
        X.XFlush(self.d)
        self.assign()

    def _plan(self):
        pl = json.loads(library.PLAYLIST.read_text())
        default = pl["default"]
        if pl.get("schedule"):
            s = pl["schedule"]
            hour = datetime.datetime.now().hour
            day = s["day_start"] <= hour < s["night_start"] if s["day_start"] < s["night_start"] \
                else not (s["night_start"] <= hour < s["day_start"])
            default = [default[0] if day else default[1]]
            self.scheduled = day
        return default, pl["monitors"]

    def assign(self):
        default, per_mon = self._plan()
        for name, o in self.outputs.items():
            o.set_items(per_mon.get(name) or default)
            o.pause(self.fs or self.bat or self.manual)

    def tick(self):
        try:
            if library.CTL_FILE.read_text() != self.args.token:
                self.stop()
                return False
        except OSError:
            self.stop()
            return False
        self.tick_n += 1
        tmp = library.HB_FILE.with_suffix(".tmp")
        tmp.write_text(str(__import__("time").time()))
        tmp.replace(library.HB_FILE)
        try:
            m = library.PLAYLIST.stat().st_mtime_ns
            if m != self.pl_mtime:
                self.pl_mtime = m
                self.assign()
        except (OSError, ValueError):
            pass
        self.sync_outputs()
        for o in self.outputs.values():
            make_click_through(self.d, o.win)
            X.XLowerWindow(self.d, o.win)
        changed = False
        if self.tick_n % 2 == 0:
            manual = bool(library.load_config().get("paused"))
            changed |= manual != self.manual
            self.manual = manual
        if self.args.pause_fullscreen:
            fs = fullscreen_active(self.d)
            changed |= fs != self.fs
            self.fs = fs
        if self.args.pause_battery and self.tick_n % 10 == 0:
            bat = on_battery()
            changed |= bat != self.bat
            self.bat = bat
        if self.tick_n % 20 == 0:
            pl_sched = json.loads(library.PLAYLIST.read_text()).get("schedule")
            if pl_sched:
                before = self.scheduled
                self._plan()
                if self.scheduled != before:
                    self.assign()
        if changed:
            for o in self.outputs.values():
                o.pause(self.fs or self.bat or self.manual)
        X.XFlush(self.d)
        return True

    def slide(self):
        for o in self.outputs.values():
            o.next()
        return True

    def stop(self):
        for o in self.outputs.values():
            o.teardown()
        self.loop.quit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", required=True)
    ap.add_argument("--fit", choices=["fill", "fit"], default="fill")
    ap.add_argument("--interval", type=int, default=0)
    ap.add_argument("--fps", type=int, default=0)
    ap.add_argument("--volume", type=int, default=0)
    ap.add_argument("--pause-fullscreen", action="store_true")
    ap.add_argument("--pause-battery", action="store_true")
    args = ap.parse_args()

    Gst.init(None)
    d = X.XOpenDisplay(None)
    if not d:
        sys.exit(tr("No X11 display (Wayland is not supported yet)"))
    ctl = Controller(args, d)
    for sig in (signal.SIGTERM, signal.SIGINT):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: ctl.stop() or False)
    GLib.timeout_add(500, ctl.tick)
    if args.interval > 0:
        GLib.timeout_add_seconds(args.interval, ctl.slide)
    try:
        ctl.loop.run()
    finally:
        try:
            if library.CTL_FILE.read_text() in (args.token, "stop"):
                library.HB_FILE.unlink(missing_ok=True)
        except OSError:
            pass
        for o in ctl.outputs.values():
            X.XDestroyWindow(d, o.win)
        X.XCloseDisplay(d)


if __name__ == "__main__":
    main()
