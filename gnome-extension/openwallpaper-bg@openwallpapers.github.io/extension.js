import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const APP_ID = 'io.github.openwallpapers.OpenWallpaper';
const KEYS = ['picture-uri', 'picture-uri-dark', 'picture-options'];

export default class OpenWallpaperBg extends Extension {
    enable() {
        this._settings = new Gio.Settings({schema_id: 'org.gnome.desktop.background'});
        this._saved = null;
        const candidates = [
            GLib.build_filenamev([GLib.get_home_dir(), '.var', 'app', APP_ID,
                'data', 'openwallpaper', 'system-frame.txt']),
            GLib.build_filenamev([GLib.get_user_data_dir(), 'openwallpaper',
                'system-frame.txt']),
        ];
        this._monitors = [];
        for (const path of candidates) {
            const file = Gio.File.new_for_path(path);
            const mon = file.monitor_file(Gio.FileMonitorFlags.NONE, null);
            mon.connect('changed', () => this._apply(file));
            this._monitors.push(mon);
        }
        this._files = candidates.map(p => Gio.File.new_for_path(p));
        this._timeout = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 2, () => {
            this._files.forEach(f => this._apply(f));
            return GLib.SOURCE_CONTINUE;
        });
    }

    _apply(file) {
        let path;
        try {
            const [ok, bytes] = file.load_contents(null);
            if (!ok)
                return;
            path = new TextDecoder().decode(bytes).trim();
        } catch (e) {
            return;
        }
        if (path) {
            const uri = `file://${path}`;
            if (this._settings.get_string('picture-uri') === uri)
                return;
            if (!this._saved) {
                this._saved = {};
                for (const k of KEYS)
                    this._saved[k] = this._settings.get_string(k);
            }
            this._settings.set_string('picture-uri', uri);
            this._settings.set_string('picture-uri-dark', uri);
            this._settings.set_string('picture-options', 'zoom');
        } else if (this._saved) {
            for (const k of KEYS)
                this._settings.set_string(k, this._saved[k]);
            this._saved = null;
        }
    }

    disable() {
        if (this._timeout) {
            GLib.source_remove(this._timeout);
            this._timeout = null;
        }
        this._monitors?.forEach(m => m.cancel());
        this._monitors = null;
        this._files = null;
        this._settings = null;
        this._saved = null;
    }
}
