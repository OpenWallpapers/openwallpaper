import gc
import sys
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Graphene", "1.0")
from gi.repository import Adw, Gdk, Gio, GLib, Graphene, Gtk  # noqa: E402

from . import APP_ID, __version__, cli, library, sources  # noqa: E402
from .i18n import available, lang, NAMES, ntr, num, tr  # noqa: E402

BG, FG = "#0e0e0e", "#f4f4f4"

CSS = f"""
@define-color window_bg_color {BG};
@define-color window_fg_color {FG};
@define-color view_bg_color {BG};
@define-color view_fg_color {FG};
@define-color headerbar_bg_color {BG};
@define-color headerbar_fg_color {FG};
@define-color headerbar_backdrop_color {BG};
@define-color headerbar_shade_color transparent;
@define-color headerbar_border_color transparent;
@define-color sidebar_bg_color {BG};
@define-color sidebar_fg_color {FG};
@define-color sidebar_backdrop_color {BG};
@define-color sidebar_shade_color transparent;
@define-color sidebar_border_color alpha({FG}, 0.10);
@define-color popover_bg_color {BG};
@define-color popover_fg_color {FG};
@define-color dialog_bg_color {BG};
@define-color dialog_fg_color {FG};
@define-color card_bg_color alpha({FG}, 0.06);
@define-color card_fg_color {FG};
@define-color accent_bg_color {FG};
@define-color accent_fg_color {BG};
@define-color accent_color {FG};
@define-color destructive_bg_color {FG};
@define-color destructive_fg_color {BG};
@define-color destructive_color {FG};
@define-color success_color {FG};
@define-color warning_color {FG};
@define-color error_color {FG};

headerbar {{ box-shadow: none; background: {BG}; }}
.tabs button {{ background: transparent; border-radius: 999px;
    padding: 6px 18px; min-height: 0; font-weight: 600; opacity: 0.55; }}
.tabs button:hover {{ opacity: 1; background: transparent; }}
.tabs button:checked {{ opacity: 1; background: {FG}; color: {BG}; }}
.chip {{ background: transparent; border-radius: 999px; padding: 4px 14px;
    min-height: 0; border: 1px solid alpha({FG}, 0.22); }}
.chip:hover {{ border-color: {FG}; background: transparent; }}
.chip:checked {{ background: {FG}; color: {BG}; border-color: {FG}; }}
/* MenuButton = aeusseres Widget + innerer Button. Nur das aeussere zeichnet den Rand. */
menubutton.chip {{ padding: 0; min-height: 0; border-radius: 999px; background: transparent;
    border: 1px solid alpha({FG}, 0.22); }}
menubutton.chip:hover {{ border-color: {FG}; }}
menubutton.chip > button {{ background: transparent; border: none; box-shadow: none;
    border-radius: 999px; padding: 4px 14px; min-height: 0; outline: none; }}
menubutton.chip > button:hover {{ background: transparent; }}
searchentry.big {{ background: alpha({FG}, 0.06); border-radius: 12px;
    padding: 8px 12px; min-height: 0; box-shadow: none; border: none;
    outline: none; }}
searchentry.big:focus-within {{ background: alpha({FG}, 0.10); }}
.thumb {{ border-radius: 14px; background: alpha({FG}, 0.06); }}
flowboxchild {{ padding: 8px; border-radius: 18px; background: transparent; }}
flowboxchild:selected {{ background: transparent; }}
flowboxchild:selected .thumb {{ outline: 2px solid {FG}; outline-offset: 3px; }}
flowboxchild:hover .thumb {{ outline: 2px solid alpha({FG}, 0.35); outline-offset: 3px; }}
flowboxchild:selected:hover .thumb {{ outline-color: {FG}; }}
.cap {{ font-weight: 600; }}
.dim {{ opacity: 0.55; }}
.key {{ opacity: 0.55; }}
.pill-main {{ border-radius: 12px; padding: 12px; font-weight: 700; }}
.pill-sub {{ border-radius: 12px; padding: 10px; background: alpha({FG}, 0.06); }}
.pill-sub:hover {{ background: alpha({FG}, 0.12); }}
.stopbtn {{ border-radius: 999px; padding: 4px 14px; min-height: 0;
    border: 1px solid {FG}; background: transparent; }}
.stopbtn:hover {{ background: {FG}; color: {BG}; }}
progressbar trough, progressbar progress {{ min-height: 3px; border-radius: 3px; }}
scrolledwindow undershoot, scrolledwindow overshoot {{ background: none; }}
.drop {{ outline: 2px dashed {FG}; outline-offset: -12px; }}
entry.tags {{ background: alpha({FG}, 0.06); border-radius: 12px; box-shadow: none;
    border: none; padding: 8px 12px; min-height: 0; }}
"""

CARD_W, CARD_H = 250, 141
SORT_LIB = [(tr("Recently added"), "added"), (tr("Name"), "title"), (tr("Favorites first"), "fav")]
FAV_CHIP = tr("Favorites")


def run_bg(fn, done=None):
    def work():
        try:
            res, err = fn(), None
        except Exception as e:  # noqa: BLE001
            res, err = None, e
        if done:
            GLib.idle_add(done, res, err)
    threading.Thread(target=work, daemon=True).start()


def set_pic(pic, path):
    try:
        pic.set_paintable(Gdk.Texture.new_from_filename(path))
    except GLib.Error:
        pass


def monitor_names():
    out = []
    mons = Gdk.Display.get_default().get_monitors()
    for i in range(mons.get_n_items()):
        c = mons.get_item(i).get_connector()
        if c:
            out.append(c)
    return out


class Thumb(Gtk.Widget):
    __gtype_name__ = "OWThumb"

    def __init__(self, w, h):
        super().__init__()
        self._w, self._h, self._p = w, h, None
        self.set_overflow(Gtk.Overflow.HIDDEN)
        self.set_halign(Gtk.Align.START)
        self.set_hexpand(False)
        self.add_css_class("thumb")

    def set_paintable(self, p):
        self._p = p
        self.queue_draw()

    def get_paintable(self):
        return self._p

    def do_measure(self, orientation, _for_size):
        s = self._w if orientation == Gtk.Orientation.HORIZONTAL else self._h
        return s, s, -1, -1

    def do_snapshot(self, snap):
        p, w, h = self._p, self.get_width(), self.get_height()
        if not p or not w or not h:
            return
        iw, ih = p.get_intrinsic_width(), p.get_intrinsic_height()
        if iw <= 0 or ih <= 0:
            p.snapshot(snap, w, h)
            return
        s = max(w / iw, h / ih)
        dw, dh = iw * s, ih * s
        snap.save()
        snap.translate(Graphene.Point().init((w - dw) / 2, (h - dh) / 2))
        p.snapshot(snap, dw, dh)
        snap.restore()


class Card(Gtk.FlowBoxChild):
    def __init__(self, data, active=False):
        super().__init__()
        self.data = data
        self.set_halign(Gtk.Align.CENTER)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                      halign=Gtk.Align.CENTER)
        ov = Gtk.Overlay()
        self.pic = Thumb(CARD_W, CARD_H)
        ov.set_child(self.pic)
        self.badge = Gtk.Image(icon_name="starred-symbolic", halign=Gtk.Align.END,
                               valign=Gtk.Align.START, margin_top=8, margin_end=8,
                               visible=bool(data.get("fav")))
        ov.add_overlay(self.badge)
        self._active = active
        title = Gtk.Label(label=("● " if active else "") + data["title"], xalign=0,
                          ellipsize=3, max_width_chars=1, hexpand=True)
        title.add_css_class("cap")
        self.title_lbl = title
        sub = " · ".join(x for x in (data.get("source"), data.get("size") or data.get("license")) if x)
        sub_l = Gtk.Label(label=sub, xalign=0, ellipsize=3, max_width_chars=1)
        sub_l.add_css_class("dim")
        sub_l.add_css_class("caption")
        for w in (ov, title, sub_l):
            box.append(w)
        box.set_size_request(CARD_W, -1)
        self.set_child(box)
        if data.get("thumb"):
            set_pic(self.pic, data["thumb"])

    def set_title(self, text):
        self.title_lbl.set_text(("● " if self._active else "") + text)


class Window(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="OpenWallpaper")
        self.set_default_size(1320, 820)
        self.view = "library"
        self.selected = None
        self.cards = []
        self.page = 0
        self.query = ""
        self.tag_filter = None
        self.gen = 0
        self.busy = False
        self.exhausted = False
        self._sorts = SORT_LIB
        self._empty_mode = "lib"
        self.cfg = library.load_config()
        self.src = next((s for s in sources.SOURCES if s.name == self.cfg["source"]),
                        sources.SOURCES[0])
        self.sort = self.src.sorts[0][1]

        self.toasts = Adw.ToastOverlay()
        self.set_content(self.toasts)
        tv = Adw.ToolbarView()
        self.toasts.set_child(tv)
        tv.add_top_bar(self._build_header())
        self.split = Adw.OverlaySplitView(sidebar_position=Gtk.PackType.END,
                                          show_sidebar=False, min_sidebar_width=320,
                                          max_sidebar_width=340,
                                          sidebar_width_fraction=0.28)
        tv.set_content(self.split)
        self.split.set_content(self._build_main())
        self.split.set_sidebar(self._build_panel())

        drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop.connect("drop", self._on_drop)
        drop.connect("enter", lambda *_: (self.add_css_class("drop"), Gdk.DragAction.COPY)[1])
        drop.connect("leave", lambda *_: self.remove_css_class("drop"))
        self.add_controller(drop)

        self.connect("close-request", self._on_close)
        GLib.timeout_add_seconds(2, self._poll_running)
        self._poll_running()
        self._show("library")

    def _build_header(self):
        hb = Adw.HeaderBar()
        tabs = Gtk.Box(spacing=4)
        tabs.add_css_class("tabs")
        self.tab_lib = Gtk.ToggleButton(label=tr("Library"))
        self.tab_dis = Gtk.ToggleButton(label=tr("Discover"), group=self.tab_lib)
        self.tab_lib.set_active(True)
        self.tab_lib.connect("toggled", lambda b: b.get_active() and self._show("library"))
        self.tab_dis.connect("toggled", lambda b: b.get_active() and self._show("discover"))
        tabs.append(self.tab_lib)
        tabs.append(self.tab_dis)
        hb.set_title_widget(tabs)

        add = Gtk.MenuButton(icon_name="list-add-symbolic", tooltip_text=tr("Add"))
        m = Gio.Menu()
        m.append(tr("Add files …"), "win.add-files")
        m.append(tr("Import folder …"), "win.add-folder")
        m.append(tr("Import from Steam"), "win.steam")
        add.set_menu_model(m)
        hb.pack_start(add)
        self._action("add-files", self._add_files)
        self._action("add-folder", self._add_folder)
        self._action("steam", self._import_steam)

        mon = Gio.SimpleAction.new("mon", GLib.VariantType.new("s"))
        mon.connect("activate", lambda _a, p: self._apply_monitor(p.get_string()))
        self.add_action(mon)

        self.stop_btn = Gtk.Button(label=tr("Stop"), visible=False)
        self.stop_btn.add_css_class("stopbtn")
        self.stop_btn.connect("clicked", lambda _b: self._stop())
        hb.pack_start(self.stop_btn)
        self.pause_btn = Gtk.Button(icon_name="media-playback-pause-symbolic",
                                    tooltip_text=tr("Pause"), visible=False)
        self.pause_btn.connect("clicked", lambda _b: self._toggle_pause())
        hb.pack_start(self.pause_btn)

        gear = Gtk.Button(icon_name="emblem-system-symbolic", tooltip_text=tr("Settings"))
        gear.connect("clicked", lambda _b: self._settings())
        hb.pack_end(gear)
        nxt = Gtk.Button(icon_name="media-skip-forward-symbolic",
                         tooltip_text=tr("Next wallpaper"))
        nxt.connect("clicked", lambda _b: self._next())
        hb.pack_end(nxt)
        shuffle = Gtk.Button(icon_name="media-playlist-shuffle-symbolic",
                             tooltip_text=tr("Random wallpaper"))
        shuffle.connect("clicked", lambda _b: self._random())
        hb.pack_end(shuffle)
        return hb

    def _action(self, name, fn):
        a = Gio.SimpleAction.new(name, None)
        a.connect("activate", lambda *_: fn())
        self.add_action(a)

    def _build_main(self):
        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                      margin_start=24, margin_end=24, margin_top=8, margin_bottom=8)
        row = Gtk.Box(spacing=10)
        self.search = Gtk.SearchEntry(hexpand=True)
        self.search.add_css_class("big")
        self.search.connect("activate", self._on_search)
        self.search.connect("search-changed", self._on_filter)
        row.append(self.search)
        self.count_lbl = Gtk.Label(xalign=1, valign=Gtk.Align.CENTER)
        self.count_lbl.add_css_class("dim")
        row.append(self.count_lbl)
        self.filter_btn = Gtk.MenuButton(label=tr("Filter"), valign=Gtk.Align.CENTER)
        self.filter_btn.add_css_class("chip")
        self.filter_btn.set_popover(self._build_filters())
        row.append(self.filter_btn)
        self.sort_dd = Gtk.DropDown(valign=Gtk.Align.CENTER)
        self.sort_dd.connect("notify::selected", self._on_sort)
        row.append(self.sort_dd)
        top.append(row)

        self.src_box = Gtk.Box(spacing=8)
        grp = None
        for s in sources.SOURCES:
            b = Gtk.ToggleButton(label=f"{s.name} · {s.media}", group=grp)
            grp = grp or b
            b.add_css_class("chip")
            b.set_active(s is self.src)
            b.connect("toggled", self._on_source, s)
            self.src_box.append(b)
        top.append(self.src_box)
        self.chips = Gtk.Box(spacing=8)
        self.chip_scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.EXTERNAL,
                                              vscrollbar_policy=Gtk.PolicyType.NEVER,
                                              propagate_natural_width=False,
                                              propagate_natural_height=True)
        self.chip_scroll.set_child(self.chips)
        wheel = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.VERTICAL)
        wheel.connect("scroll", self._on_chip_wheel)
        self.chip_scroll.add_controller(wheel)
        top.append(self.chip_scroll)
        main.append(top)

        self.flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.SINGLE,
                                homogeneous=True, min_children_per_line=1,
                                max_children_per_line=10, valign=Gtk.Align.START,
                                halign=Gtk.Align.FILL, column_spacing=4, row_spacing=4,
                                margin_start=16, margin_end=16, margin_top=8,
                                margin_bottom=24, activate_on_single_click=True)
        self.flow.connect("child-activated", self._on_pick)
        self.scroll = Gtk.ScrolledWindow(vexpand=True)
        self.scroll.set_child(self.flow)
        self.scroll.get_vadjustment().connect("value-changed", self._on_scroll)

        self.empty = Adw.StatusPage(vexpand=True)
        self.empty_btn = Gtk.Button(halign=Gtk.Align.CENTER)
        self.empty_btn.add_css_class("pill")
        self.empty_btn.add_css_class("suggested-action")
        self.empty.set_child(self.empty_btn)
        self.empty_btn.connect("clicked", lambda _b: self._empty_action())

        self.stack = Gtk.Stack(vexpand=True)
        self.stack.add_named(self.scroll, "grid")
        self.stack.add_named(self.empty, "empty")
        self.stack.add_named(Adw.Spinner(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
                                         width_request=32, height_request=32), "load")
        main.append(self.stack)
        return main

    RATIOS = [(tr("All"), ""), ("16:9", "16x9"), ("16:10", "16x10"), ("21:9", "21x9"),
              ("32:9", "32x9"), (tr("Portrait 9:16"), "9x16")]
    RESOLUTIONS = [(tr("All"), ""), (tr("At least 1920×1080"), "1920x1080"), (tr("At least 2560×1440"), "2560x1440"),
                   (tr("At least 3840×2160"), "3840x2160")]

    def _filter_chip(self, label, active, cb, tip=None):
        b = Gtk.ToggleButton(label=label, active=active)
        b.add_css_class("chip")
        if tip:
            b.set_tooltip_text(tip)
        b.connect("toggled", cb)
        return b

    def _build_filters(self):
        cfg = library.load_config()
        pop = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=14,
                      margin_bottom=14, margin_start=16, margin_end=16)
        box.set_size_request(340, -1)

        def head(t):
            lbl = Gtk.Label(label=t, xalign=0)
            lbl.add_css_class("cap")
            return lbl

        box.append(head(tr("Content")))
        row = Gtk.Box(spacing=6)
        self.f_purity = []
        for i, (name, tip) in enumerate([
                (tr("Safe"), None), (tr("Sketchy"), None),
                (tr("NSFW"), tr("Needs a Wallhaven API key (Settings)"))]):
            b = self._filter_chip(name, cfg["wh_purity"][i] == "1",
                                  lambda btn, i=i: self._on_purity(btn, i), tip)
            self.f_purity.append(b)
            row.append(b)
        box.append(row)

        box.append(head(tr("Category")))
        row = Gtk.Box(spacing=6)
        self.f_cats = []
        for i, name in enumerate([tr("General"), tr("Anime"), tr("People")]):
            b = self._filter_chip(name, cfg["wh_categories"][i] == "1",
                                  lambda btn, i=i: self._on_cat(btn, i))
            self.f_cats.append(b)
            row.append(b)
        box.append(row)

        def dropdown(title, pairs, key):
            r = Gtk.Box(spacing=10)
            r.append(Gtk.Label(label=title, xalign=0, hexpand=True))
            dd = Gtk.DropDown.new_from_strings([a for a, _ in pairs])
            vals = [v for _, v in pairs]
            dd.set_selected(vals.index(cfg[key]) if cfg[key] in vals else 0)
            dd.connect("notify::selected", lambda d, _p: self._on_filter_pick(
                key, vals[d.get_selected()]))
            r.append(dd)
            return r
        box.append(dropdown(tr("Resolution"), self.RESOLUTIONS, "wh_atleast"))
        box.append(dropdown(tr("Aspect ratio"), self.RATIOS, "wh_ratio"))
        pop.set_child(box)
        return pop

    def _on_filter_pick(self, key, value):
        if library.load_config().get(key) == value:
            return
        library.set_config(**{key: value})
        self._discover(reset=True)

    def _bits(self, key, buttons):
        return "".join("1" if b.get_active() else "0" for b in buttons)

    def _on_cat(self, btn, i):
        bits = self._bits("wh_categories", self.f_cats)
        if bits == "000":
            btn.set_active(True)
            return
        self._on_filter_pick("wh_categories", bits)

    def _on_purity(self, btn, i):
        if getattr(self, "_purity_lock", False):
            return
        cfg = library.load_config()
        if i == 2 and btn.get_active():
            if not cfg.get("wallhaven_key"):
                self._set_purity_lock(btn, False)
                self._toast(tr("NSFW content needs a Wallhaven API key (Settings)"))
                return
            if not cfg.get("adult_ok"):
                self._set_purity_lock(btn, False)
                self._confirm_adult()
                return
        bits = self._bits("wh_purity", self.f_purity)
        if bits == "000":
            btn.set_active(True)
            return
        self._on_filter_pick("wh_purity", bits)

    def _set_purity_lock(self, btn, state):
        self._purity_lock = True
        btn.set_active(state)
        self._purity_lock = False

    def _confirm_adult(self):
        dlg = Adw.AlertDialog(heading=tr("NSFW content"),
                              body=tr("These images are for adults only. Confirm that you are at least 18 years old."))
        dlg.add_response("no", tr("Cancel"))
        dlg.add_response("yes", tr("I am 18 or older"))
        dlg.set_default_response("no")

        def answered(d, r):
            if r != "yes":
                return
            library.set_config(adult_ok=True)
            self._set_purity_lock(self.f_purity[2], True)
            self._on_purity(self.f_purity[2], 2)
        dlg.connect("response", answered)
        dlg.present(self)

    def _build_panel(self):
        p = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=16,
                    margin_bottom=20, margin_start=20, margin_end=20)
        self.p_pic = Thumb(280, 170)
        self.p_title = Gtk.Label(xalign=0, wrap=True, selectable=True)
        self.p_title.add_css_class("title-3")
        self.p_grid = Gtk.Grid(column_spacing=16, row_spacing=6)
        self.p_taglbl = Gtk.Label(xalign=0, wrap=True, max_width_chars=30)
        self.p_taglbl.add_css_class("dim")
        self.p_link = Gtk.LinkButton(uri="https://wallhaven.cc", label=tr("Open source page"),
                                     halign=Gtk.Align.START)
        self.p_link.add_css_class("flat")
        self.p_tags = Gtk.Entry(placeholder_text=tr("Tags, separated by commas"))
        self.p_tags.add_css_class("tags")
        self.p_tags.connect("activate", lambda _e: self._save_tags())
        focus = Gtk.EventControllerFocus()
        focus.connect("leave", lambda _c: self._save_tags())
        self.p_tags.add_controller(focus)
        self.p_progress = Gtk.ProgressBar(visible=False)
        self.p_apply = Gtk.Button(label=tr("Set as wallpaper"))
        self.p_apply.add_css_class("suggested-action")
        self.p_apply.add_css_class("pill-main")
        self.p_apply.connect("clicked", lambda _b: self._apply())
        self.p_mon = Gtk.MenuButton(label=tr("Only on one monitor …"))
        self.p_mon.add_css_class("pill-sub")
        self.p_mon.add_css_class("flat")
        self.p_save = Gtk.Button(label=tr("Save to library"))
        self.p_save.add_css_class("pill-sub")
        self.p_save.add_css_class("flat")
        self.p_save.connect("clicked", lambda _b: self._save_only())
        self.p_fav = Gtk.Button()
        self.p_fav.add_css_class("pill-sub")
        self.p_fav.add_css_class("flat")
        self.p_fav.connect("clicked", lambda _b: self._fav())
        self.p_remove = Gtk.Button(label=tr("Remove"))
        self.p_remove.add_css_class("pill-sub")
        self.p_remove.add_css_class("flat")
        self.p_remove.connect("clicked", lambda _b: self._remove())
        for w in (self.p_pic, self.p_title, self.p_grid, self.p_taglbl, self.p_link, self.p_tags,
                  Gtk.Box(vexpand=True), self.p_progress, self.p_apply, self.p_mon,
                  self.p_save, self.p_fav, self.p_remove):
            p.append(w)
        return p

    def _set_sorts(self, pairs):
        self._sorts = pairs
        self._sort_lock = True
        self.sort_dd.set_model(Gtk.StringList.new([a for a, _ in pairs]))
        self.sort_dd.set_selected(0)
        self._sort_lock = False

    def _set_chips(self, names):
        while (c := self.chips.get_first_child()):
            self.chips.remove(c)
        for n in names:
            b = Gtk.ToggleButton(label=n)
            b.add_css_class("chip")
            b.connect("toggled", self._on_chip, n)
            self.chips.append(b)

    def _on_chip_wheel(self, _ctl, _dx, dy):
        adj = self.chip_scroll.get_hadjustment()
        adj.set_value(adj.get_value() + dy * 60)
        return True

    def _chip_buttons(self):
        b = self.chips.get_first_child()
        while b:
            yield b
            b = b.get_next_sibling()

    def _show(self, view):
        self.view = view
        self.gen += 1
        self.query = ""
        self.tag_filter = None
        self.search.set_text("")
        self.src_box.set_visible(view == "discover")
        self.filter_btn.set_visible(view == "discover" and self.src.has_filters)
        self.count_lbl.set_text("")
        self._clear()
        if view == "library":
            self.search.set_placeholder_text(tr("Search library"))
            self._set_sorts(SORT_LIB)
            self._set_chips([FAV_CHIP] + library.all_tags())
            self.chip_scroll.set_visible(True)
            self._fill_library()
        else:
            self.search.set_placeholder_text(self.src.hint)
            self._set_sorts(self.src.sorts)
            self._set_chips(self.src.categories)
            self.chip_scroll.set_visible(True)
            self.sort = self.src.sorts[0][1]
            self._discover(reset=True)

    def _clear(self):
        self.flow.remove_all()
        self.cards = []
        self.selected = None
        self.split.set_show_sidebar(False)

    def _refresh_library(self):
        keep = self.tag_filter
        self._clear()
        self._set_chips([FAV_CHIP] + library.all_tags())
        self.tag_filter = None
        if keep:
            for b in self._chip_buttons():
                if b.get_label() == keep:
                    b.set_active(True)
        self._fill_library()

    def _fill_library(self):
        self.flow.remove_all()
        self.cards = []
        items = library.load_items()
        key = self._sorts[self.sort_dd.get_selected()][1] if self.view == "library" else "added"
        if key == "title":
            items.sort(key=lambda i: i["title"].lower())
        elif key == "fav":
            items.sort(key=lambda i: (not i.get("fav"), -i.get("added", 0)))
        else:
            items.sort(key=lambda i: -i.get("added", 0))
        cur = library.load_config().get("current")
        for it in items:
            self._add_card(it, it["id"] == cur)
        if items:
            self.stack.set_visible_child_name("grid")
            self._on_filter(self.search)
        else:
            self._empty_mode = "lib"
            self.empty.set_title(tr("No wallpapers yet"))
            self.empty.set_description(tr("Add files, drop them into the window or download them from Discover."))
            self.empty_btn.set_label(tr("Open Discover"))
            self.stack.set_visible_child_name("empty")

    def _empty_action(self):
        if self._empty_mode == "lib":
            self.tab_dis.set_active(True)
        else:
            self._discover(reset=True)

    def _add_card(self, data, active=False):
        c = Card(data, active)
        self.flow.append(c)
        self.cards.append(c)
        return c

    def _toast(self, text):
        self.toasts.add_toast(Adw.Toast(title=text, timeout=3))

    def _on_filter(self, entry):
        if self.view != "library":
            return
        q = entry.get_text().lower()
        tf = self.tag_filter

        def ok(d):
            if q and q not in d["title"].lower() and \
                    not any(q in t.lower() for t in d.get("tags", [])):
                return False
            if tf == FAV_CHIP:
                return bool(d.get("fav"))
            if tf:
                return tf.lower() in [t.lower() for t in d.get("tags", [])]
            return True
        for c in self.cards:
            c.set_visible(ok(c.data))

    def _on_sort(self, dd, _p):
        if getattr(self, "_sort_lock", False):
            return
        key = self._sorts[dd.get_selected()][1]
        if self.view == "library":
            self._refresh_library()
        elif key != self.sort:
            self.sort = key
            self._discover(reset=True)

    def _on_source(self, btn, src):
        if not btn.get_active() or src is self.src:
            return
        self.src = src
        library.set_config(source=src.name)
        self.filter_btn.set_visible(src.has_filters)
        self.search.set_placeholder_text(src.hint)
        self._set_sorts(src.sorts)
        self._set_chips(src.categories)
        self.sort = src.sorts[0][1]
        self.search.set_text("")
        self._discover(reset=True)

    def _on_chip(self, btn, name):
        if self.view == "library":
            if btn.get_active():
                for b in self._chip_buttons():
                    if b is not btn:
                        b.set_active(False)
            self.tag_filter = name if btn.get_active() else None
            self._on_filter(self.search)
            return
        if not btn.get_active():
            return
        for b in self._chip_buttons():
            if b is not btn:
                b.set_active(False)
        self.search.set_text(name)
        self._on_search(self.search)

    def _on_search(self, entry):
        if self.view != "discover":
            return
        self.query = entry.get_text().strip()
        self._discover(reset=True)

    def _discover(self, reset=False):
        if reset:
            self.gen += 1
            self.busy = False
            self.page = 0
            self.exhausted = False
            self._clear()
        if self.busy or self.exhausted:
            return
        self.busy = True
        first = not self.cards
        if first:
            self.stack.set_visible_child_name("load")
        gen, page, src, sort = self.gen, self.page, self.src, self.sort
        q = self.query or (src.categories[0] if src.name != "Wallhaven" else "")
        cfg = library.load_config()

        def done(res, err):
            if gen != self.gen:
                return
            self.busy = False
            if err:
                if first:
                    self._empty_mode = "retry"
                    self.empty.set_title(tr("Discover is not reachable"))
                    self.empty.set_description(str(err))
                    self.empty_btn.set_label(tr("Try again"))
                    self.stack.set_visible_child_name("empty")
                else:
                    self._toast(str(err))
                return
            self.stack.set_visible_child_name("grid")
            known = {i["url"] for i in library.load_items() if i.get("url")}
            if page == 0 and res.total is not None:
                self.total = res.total
            for r in res:
                c = self._add_card(r)
                c.data["saved"] = r["url"] in known
                if r.get("thumb_url"):
                    run_bg(lambda u=r["thumb_url"]: sources.fetch_thumb(u),
                           lambda p, e, c=c: p and set_pic(c.pic, p))
            self.page += 1
            tot = getattr(self, "total", None) if page or res.total is None else res.total
            self.count_lbl.set_text(tr("{} of {}").format(len(self.cards), num(tot)) if tot else
                                    ntr("{n} result", "{n} results", len(self.cards)).format(n=len(self.cards)))
            if not res:
                self.exhausted = True
                if first:
                    self._empty_mode = "retry"
                    self.empty.set_title(tr("No results"))
                    self.empty.set_description(tr("Try a different search term."))
                    self.empty_btn.set_label(tr("Reload"))
                    self.stack.set_visible_child_name("empty")
            elif len(self.cards) < 12:
                GLib.idle_add(self._discover)
        run_bg(lambda: src.search(q, page, sort, cfg), done)

    def _on_scroll(self, adj):
        if self.view != "discover":
            return
        if adj.get_value() + adj.get_page_size() > adj.get_upper() - 400:
            self._discover()

    def _on_pick(self, _flow, child):
        self.selected = child
        d = child.data
        self.p_pic.set_paintable(child.pic.get_paintable())
        self._show_details(d)
        if self.view == "discover" and not d.get("detailed") and hasattr(self.src, "details"):
            src, cfg = self.src, library.load_config()
            run_bg(lambda: src.details(d, cfg), lambda r, e: r and self._got_details(child, r))

    def _got_details(self, child, extra):
        child.data.update(extra)
        child.set_title(extra["title"])
        if child is self.selected:
            self._show_details(child.data)

    def _show_details(self, d):
        self.p_title.set_text(d["title"])
        tags = d.get("tags") or []
        self.p_taglbl.set_text(" · ".join(tags) if self.view == "discover" else "")
        self.p_taglbl.set_visible(bool(tags) and self.view == "discover")
        rows = [(tr("Source"), d.get("source")), (tr("License"), d.get("license")),
                (tr("Author"), d.get("author")), (tr("Resolution"), d.get("size"))]
        while (c := self.p_grid.get_first_child()):
            self.p_grid.remove(c)
        r = 0
        for k, v in rows:
            if not v:
                continue
            kl = Gtk.Label(label=k, xalign=0, yalign=0)
            kl.add_css_class("key")
            vl = Gtk.Label(label=v, xalign=0, wrap=True, hexpand=True, max_width_chars=28)
            self.p_grid.attach(kl, 0, r, 1, 1)
            self.p_grid.attach(vl, 1, r, 1, 1)
            r += 1
        if d.get("purity") and d["purity"] != "sfw":
            kl = Gtk.Label(label=tr("Rating"), xalign=0, yalign=0)
            kl.add_css_class("key")
            self.p_grid.attach(kl, 0, r, 1, 1)
            self.p_grid.attach(Gtk.Label(label={"sketchy": tr("Sketchy"), "nsfw": tr("NSFW")}.get(
                d["purity"], d["purity"]), xalign=0), 1, r, 1, 1)
        self.p_link.set_visible(bool(d.get("url")))
        if d.get("url"):
            self.p_link.set_uri(d["url"])
        if self.selected is None:
            return
        local = self.view == "library"
        self.p_apply.set_label(tr("Set as wallpaper") if local else tr("Download and set"))
        self.p_save.set_visible(not local)
        self.p_remove.set_visible(local)
        self.p_fav.set_visible(local)
        self.p_tags.set_visible(local)
        self.p_tags.set_text(", ".join(d.get("tags", [])))
        self.p_fav.set_label(tr("Remove from favorites") if d.get("fav") else tr("Add to favorites"))
        mons = monitor_names()
        self.p_mon.set_visible(local and len(mons) > 1)
        if local and len(mons) > 1:
            menu = Gio.Menu()
            for n in mons:
                item = Gio.MenuItem.new(tr("Only on {}").format(n), None)
                item.set_action_and_target_value("win.mon", GLib.Variant.new_string(n))
                menu.append_item(item)
            self.p_mon.set_menu_model(menu)
        self.p_apply.set_sensitive(True)
        self.split.set_show_sidebar(True)

    def _save_tags(self):
        if not self.selected or self.view != "library":
            return
        d = self.selected.data
        text = self.p_tags.get_text()
        if [t.lower() for t in d.get("tags", [])] == \
                [t.strip().lower() for t in text.split(",") if t.strip()]:
            return
        d["tags"] = library.set_tags(d["id"], text)
        keep = self.tag_filter
        self._set_chips([FAV_CHIP] + library.all_tags())
        self.tag_filter = None
        for b in self._chip_buttons():
            if keep and b.get_label() == keep:
                b.set_active(True)

    def _download(self, d, then):
        self.p_apply.set_sensitive(False)
        self.p_save.set_sensitive(False)
        self.p_progress.set_visible(True)
        self.p_progress.set_fraction(0)
        src = next(s for s in sources.SOURCES if s.name == d["source"])

        cfg = library.load_config()

        def work():
            if hasattr(src, "details") and not d.get("detailed"):
                try:
                    d.update(src.details(d, cfg))
                except RuntimeError:
                    pass
            path = src.download(d, lambda f: GLib.idle_add(self.p_progress.set_fraction, f))
            return library.add_item(path, d["title"], d["source"], d["license"],
                                    d["author"], d["url"], copy=False, size=d.get("size", ""),
                                    tags=d.get("tags"))

        def done(item, err):
            self.p_progress.set_visible(False)
            self.p_apply.set_sensitive(True)
            self.p_save.set_sensitive(True)
            if err or not item:
                self._toast(tr("Error: {}").format(err or tr("File not readable")))
                return
            then(item)
        run_bg(work, done)

    def _set(self, item, monitor=None):
        label = (tr("Active: {} on {}").format(item["title"], monitor) if monitor
                 else tr("Active: {}").format(item["title"]))
        run_bg(lambda: library.apply(item, monitor=monitor), lambda *_: (
            self._toast(label), self._poll_running()))

    def _apply(self):
        if not self.selected:
            return
        d = self.selected.data
        if self.view == "library":
            self._set(d)
        else:
            self._download(d, self._set)

    def _apply_monitor(self, name):
        if self.selected and self.view == "library":
            self._set(self.selected.data, monitor=name)

    def _save_only(self):
        if self.selected:
            self._download(self.selected.data, lambda it: self._toast(
                tr("Saved: {}").format(it["title"])))

    def _fav(self):
        if not self.selected:
            return
        d = self.selected.data
        d["fav"] = library.toggle_fav(d["id"])
        self.selected.badge.set_visible(d["fav"])
        self.p_fav.set_label(tr("Remove from favorites") if d["fav"] else tr("Add to favorites"))

    def _remove(self):
        if not self.selected:
            return
        d = self.selected.data
        run_bg(lambda: library.remove_item(d["id"], delete_file=True), lambda *_: (
            self._refresh_library(), self._poll_running()))

    def _random(self):
        it = library.random_item()
        if not it:
            return self._toast(tr("The library is empty"))
        self._set(it)
        if self.view == "library":
            GLib.timeout_add(600, lambda: self._refresh_library() or False)

    def _next(self):
        it = library.next_item()
        if not it:
            return self._toast(tr("The library is empty"))
        self._set(it)
        if self.view == "library":
            GLib.timeout_add(600, lambda: self._refresh_library() or False)

    def _stop(self):
        self.stop_btn.set_sensitive(False)

        def done(*_):
            self.stop_btn.set_sensitive(True)
            self._poll_running()
            self._toast(tr("Wallpaper stopped"))
            if self.view == "library":
                self._refresh_library()
        run_bg(library.stop_and_restore, done)

    def _toggle_pause(self):
        paused = not library.load_config().get("paused")
        library.set_config(paused=paused)
        self._poll_running()

    def _poll_running(self):
        running = library.is_running()
        self.stop_btn.set_visible(running)
        self.pause_btn.set_visible(running)
        paused = bool(library.load_config().get("paused"))
        self.pause_btn.set_icon_name("media-playback-start-symbolic" if paused
                                     else "media-playback-pause-symbolic")
        self.pause_btn.set_tooltip_text(tr("Resume") if paused else tr("Pause"))
        return True

    def _after_import(self, new, err, kind="added", dup=0):
        self.tab_lib.set_active(True)
        if self.view != "library":
            self._show("library")
        else:
            self._refresh_library()
        if err:
            self._toast(tr("Error: {}").format(err))
        elif new:
            text = {
                "added": ntr("{n} wallpaper added", "{n} wallpapers added", new),
                "steam": ntr("{n} wallpaper imported from Steam", "{n} wallpapers imported from Steam", new),
                "backup": ntr("{n} wallpaper restored from the backup", "{n} wallpapers restored from the backup", new),
            }[kind].format(n=new)
            if dup:
                text += tr(", {} already in the library").format(dup)
            self._toast(text)
        elif dup:
            self._toast(ntr("The wallpaper is already in the library",
                            "All {n} wallpapers are already in the library", dup).format(n=dup))
        else:
            self._toast(tr("Nothing suitable found"))

    def _add_files(self):
        dlg = Gtk.FileDialog(title=tr("Choose videos or images"))
        flt = Gtk.FileFilter(name=tr("Videos and images"))
        for e in sorted(library.VIDEO_EXT | library.IMAGE_EXT):
            flt.add_suffix(e[1:])
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(flt)
        dlg.set_filters(store)
        dlg.open_multiple(self, None, self._files_done)

    def _files_done(self, dlg, res):
        try:
            files = dlg.open_multiple_finish(res)
        except GLib.Error:
            return
        self._import([files.get_item(i).get_path() for i in range(files.get_n_items())])

    def _add_folder(self):
        dlg = Gtk.FileDialog(title=tr("Choose a folder with wallpapers"))
        dlg.select_folder(self, None, self._folder_done)

    def _folder_done(self, dlg, res):
        try:
            f = dlg.select_folder_finish(res)
        except GLib.Error:
            return
        self._import([f.get_path()])

    def _import(self, paths):
        self.stack.set_visible_child_name("load")
        self._toast(tr("Importing …"))
        run_bg(lambda: library.import_paths(paths), lambda r, e: self._after_import(
            r[0] if r else 0, e, dup=r[1] if r else 0))

    def _on_drop(self, _t, value, _x, _y):
        self.remove_css_class("drop")
        paths = [f.get_path() for f in value.get_files() if f.get_path()]
        if paths:
            self._import(paths)
        return True

    def _import_steam(self):
        self._toast(tr("Looking for Wallpaper Engine …"))

        def done(res, err):
            if err:
                return self._after_import(0, err)
            n, roots = res
            if not roots:
                self._toast(tr("No Steam Workshop folder found. Use “Import folder” instead."))
                return
            self._after_import(n, None, "steam")
        run_bg(library.import_steam, done)

    def _spin(self, title, subtitle, lo, hi, value, key, reapply=True):
        row = Adw.SpinRow.new_with_range(lo, hi, 1)
        row.set_title(title)
        if subtitle:
            row.set_subtitle(subtitle)
        row.set_value(value)

        def changed(r, _p):
            library.set_config(**{key: int(r.get_value())})
            if reapply:
                self._debounce_reapply()
        row.connect("notify::value", changed)
        return row

    def _debounce_reapply(self):
        if getattr(self, "_re_id", 0):
            GLib.source_remove(self._re_id)

        def go():
            self._re_id = 0
            run_bg(library.reapply)
            return False
        self._re_id = GLib.timeout_add(700, go)

    def _switch(self, title, subtitle, active, fn):
        row = Adw.SwitchRow(title=title, active=active)
        if subtitle:
            row.set_subtitle(subtitle)
        row.connect("notify::active", lambda r, _p: fn(r.get_active(), r))
        return row

    def _settings(self):
        cfg = library.load_config()
        items = [i for i in library.load_items()]
        titles = [i["title"] for i in items]
        dlg = Adw.PreferencesDialog(title=tr("Settings"))
        page = Adw.PreferencesPage()
        dlg.add(page)

        g = Adw.PreferencesGroup(title=tr("Playback"))
        g.add(self._switch(tr("Fill screen"), tr("Crops the edges instead of showing bars"),
                           cfg["fit"] == "fill", lambda on, _r: (
                               library.set_config(fit="fill" if on else "fit"),
                               run_bg(library.reapply))))
        g.add(self._switch(tr("Pause when fullscreen"), tr("Saves performance in games and videos"),
                           cfg["pause_fullscreen"], lambda on, _r: (
                               library.set_config(pause_fullscreen=on), run_bg(library.reapply))))
        g.add(self._switch(tr("Pause on battery"), tr("Only on devices with a battery"),
                           cfg["pause_battery"], lambda on, _r: (
                               library.set_config(pause_battery=on), run_bg(library.reapply))))
        g.add(self._spin(tr("Limit frame rate"), tr("0 = unlimited. 30 noticeably saves power."),
                         0, 120, cfg["fps_limit"], "fps_limit"))
        g.add(self._spin(tr("Volume"), tr("0 = off. Muted when fullscreen or paused."),
                         0, 100, cfg["volume"], "volume"))
        page.add(g)

        pool_names = [tr("All"), FAV_CHIP] + library.all_tags()
        pool_keys = ["all", "fav"] + [f"tag:{t}" for t in library.all_tags()]
        g = Adw.PreferencesGroup(title=tr("Slideshow"),
                                 description=tr("Switches between wallpapers. Also applies to “Next” and “Random”."))
        g.add(self._switch(tr("Slideshow"), None, cfg["slideshow"], lambda on, _r: (
            library.set_config(slideshow=on), run_bg(library.reapply))))
        g.add(self._spin(tr("Change every … minutes"), None, 1, 240, cfg["interval"], "interval"))
        pool = Adw.ComboRow(title=tr("Selection"), model=Gtk.StringList.new(pool_names))
        if cfg["slideshow_pool"] in pool_keys:
            pool.set_selected(pool_keys.index(cfg["slideshow_pool"]))
        pool.connect("notify::selected", lambda r, _p: (
            library.set_config(slideshow_pool=pool_keys[r.get_selected()]),
            run_bg(library.reapply)))
        g.add(pool)
        page.add(g)

        g = Adw.PreferencesGroup(title=tr("Day and night"),
                                 description=tr("Switches automatically by time of day. Replaces the slideshow."))
        if len(items) >= 2:
            ids = [i["id"] for i in items]
            sw = self._switch(tr("Schedule"), None, cfg["schedule"], lambda on, r: (
                None if library.set_schedule(on) else (
                    r.set_active(False),
                    self._toast(tr("Choose a day and a night wallpaper first")))))
            day = Adw.ComboRow(title=tr("Day"), model=Gtk.StringList.new(titles))
            night = Adw.ComboRow(title=tr("Night"), model=Gtk.StringList.new(titles))
            if cfg["day_id"] in ids:
                day.set_selected(ids.index(cfg["day_id"]))
            if cfg["night_id"] in ids:
                night.set_selected(ids.index(cfg["night_id"]))
            library.set_config(day_id=ids[day.get_selected()], night_id=ids[night.get_selected()])

            def pick(key, row):
                library.set_config(**{key: ids[row.get_selected()]})
                if library.load_config()["schedule"]:
                    self._debounce_reapply()
            day.connect("notify::selected", lambda r, _p: pick("day_id", r))
            night.connect("notify::selected", lambda r, _p: pick("night_id", r))
            g.add(sw)
            g.add(day)
            g.add(night)
            g.add(self._spin(tr("Day starts at (hour)"), None, 0, 23, cfg["day_start"], "day_start"))
            g.add(self._spin(tr("Night starts at (hour)"), None, 0, 23, cfg["night_start"], "night_start"))
        else:
            g.add(Adw.ActionRow(title=tr("At least two wallpapers needed"),
                                subtitle=tr("Add some to the library.")))
        page.add(g)

        mons = monitor_names()
        g = Adw.PreferencesGroup(title=tr("Monitors"),
                                 description=tr("Pick a wallpaper in the library and set it for one monitor only."))
        assigned = library.load_config()["monitors"]
        by = {i["id"]: i["title"] for i in items}
        for n in mons:
            g.add(Adw.ActionRow(title=n, subtitle=by.get(assigned.get(n), tr("Same as the others"))))
        reset = Adw.ActionRow(title=tr("Same on all monitors"), subtitle=tr("Removes individual assignments"))
        b = Gtk.Button(label=tr("Reset"), valign=Gtk.Align.CENTER)
        b.connect("clicked", lambda _b: (library.set_config(monitors={}),
                                         run_bg(library.reapply), self._toast(tr("Reset done"))))
        reset.add_suffix(b)
        g.add(reset)
        page.add(g)

        g = Adw.PreferencesGroup(title=tr("System"))
        codes = [""] + available()
        names = [tr("System default")] + [NAMES.get(c, c) for c in available()]
        langrow = Adw.ComboRow(title=tr("Language"), subtitle=tr("Takes effect after restarting the app"),
                               model=Gtk.StringList.new(names))
        cur = cfg.get("language", "")
        langrow.set_selected(codes.index(cur) if cur in codes else 0)
        langrow.connect("notify::selected", lambda r, _p: library.set_config(
            language=codes[r.get_selected()]))
        g.add(langrow)
        g.add(self._switch(tr("Start at login"), None, library.AUTOSTART.exists(),
                           lambda on, _r: library.set_autostart(on)))
        g.add(self._switch(tr("Set still image in GNOME"),
                           tr("For the overview and lock screen. In the Flatpak this needs the GNOME extension from the gnome-extension folder."),
                           cfg["sync_system"], lambda on, _r: (
                               library.set_config(sync_system=on),
                               None if on else run_bg(library.restore_system_background))))
        page.add(g)

        g = Adw.PreferencesGroup(title=tr("Discover"),
                                 description=tr("Pixabay needs a free key from pixabay.com/api/docs."))
        key = Adw.PasswordEntryRow(title=tr("Pixabay API key"))
        key.set_text(cfg.get("pixabay_key", ""))
        key.connect("changed", lambda r: library.set_config(pixabay_key=r.get_text().strip()))
        g.add(key)
        wkey = Adw.PasswordEntryRow(title=tr("Wallhaven API key (for NSFW content)"))
        wkey.set_text(cfg.get("wallhaven_key", ""))

        def wh_key(r):
            k = r.get_text().strip()
            library.set_config(wallhaven_key=k)
            if not k:
                bits = library.load_config()["wh_purity"][:2] + "0"
                library.set_config(wh_purity=bits, adult_ok=False)
        wkey.connect("changed", wh_key)
        g.add(wkey)
        page.add(g)

        g = Adw.PreferencesGroup(title=tr("Backup"),
                                 description=tr("Backs up the library, tags, favorites and settings. API keys are not included."))
        row = Adw.ActionRow(title=tr("Create backup"), subtitle=tr("ZIP file with all wallpapers"))
        b = Gtk.Button(label=tr("Export"), valign=Gtk.Align.CENTER)
        b.connect("clicked", lambda _b: self._export())
        row.add_suffix(b)
        g.add(row)
        row = Adw.ActionRow(title=tr("Restore backup"), subtitle=tr("Adds missing wallpapers"))
        b = Gtk.Button(label=tr("Import"), valign=Gtk.Align.CENTER)
        b.connect("clicked", lambda _b: self._import_backup())
        row.add_suffix(b)
        g.add(row)
        page.add(g)

        g = Adw.PreferencesGroup(title=tr("Storage"))
        row = Adw.ActionRow(
            title=tr("Clear cache"),
            subtitle=ntr("{mb} MB of thumbnails · {n} wallpaper in the library",
                         "{mb} MB of thumbnails · {n} wallpapers in the library", len(items)).format(
                mb=f"{library.cache_size() / 1048576:.0f}", n=len(items)))
        b = Gtk.Button(label=tr("Clear"), valign=Gtk.Align.CENTER)
        b.connect("clicked", lambda _b: run_bg(library.clear_cache, lambda *_: (
            row.set_subtitle(tr("Cleared")), self._toast(tr("Cache cleared")))))
        row.add_suffix(b)
        g.add(row)
        page.add(g)

        about = Adw.PreferencesGroup()
        about.add(Adw.ActionRow(title="OpenWallpaper",
                                subtitle=tr("Version {} · GPL-3.0-or-later").format(__version__)))
        page.add(about)
        dlg.present(self)

    def _export(self):
        dlg = Gtk.FileDialog(title=tr("Save backup"), initial_name=tr("openwallpaper-backup.zip"))
        dlg.save(self, None, self._export_done)

    def _export_done(self, dlg, res):
        try:
            f = dlg.save_finish(res)
        except GLib.Error:
            return
        self._toast(tr("Creating backup …"))
        run_bg(lambda: library.export_backup(f.get_path()), lambda n, e: self._toast(
            tr("Error: {}").format(e) if e else ntr(
            "Backup with {n} wallpaper created", "Backup with {n} wallpapers created", n).format(n=n)))

    def _import_backup(self):
        dlg = Gtk.FileDialog(title=tr("Choose a backup"))
        flt = Gtk.FileFilter(name=tr("OpenWallpaper backup"))
        flt.add_suffix("zip")
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(flt)
        dlg.set_filters(store)
        dlg.open(self, None, self._backup_done)

    def _backup_done(self, dlg, res):
        try:
            f = dlg.open_finish(res)
        except GLib.Error:
            return
        self._toast(tr("Restoring backup …"))
        run_bg(lambda: library.import_backup(f.get_path()),
               lambda n, e: self._after_import(n or 0, e, "backup"))

    def _on_close(self, _win):
        app = self.get_application()
        if library.is_running():
            app.keep_alive(True)
            app.watch_renderer()
            self.set_visible(False)
            return True
        app.keep_alive(False)
        return False


class App(Adw.Application):

    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self._held = False
        self._watching = False

    def do_command_line(self, cl):
        args = list(cl.get_arguments())[1:]
        if not cli.wants_cli(args):
            self.activate()
            return 0
        code = cli.run(args, out=cl.print_literal)
        if library.is_running():
            self.keep_alive(True)
            self.watch_renderer()
        cl.set_exit_status(code)
        GLib.idle_add(lambda: gc.collect() and False)
        return code

    def keep_alive(self, on):
        if on and not self._held:
            self._held = True
            self.hold()
        elif not on and self._held:
            self._held = False
            self.release()

    def watch_renderer(self):
        if self._watching:
            return
        self._watching = True

        def check():
            win = self.props.active_window
            shown = bool(win and win.get_visible())
            if not library.is_running() and not shown:
                self._watching = False
                self.keep_alive(False)
                return False
            return True
        GLib.timeout_add_seconds(3, check)

    def do_startup(self):
        Adw.Application.do_startup(self)
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        css = Gtk.CssProvider()
        css.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self):
        (self.props.active_window or Window(self)).present()


def main():
    return App().run(sys.argv)
