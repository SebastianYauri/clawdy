// Clawdy Focus: a D-Bus door into GNOME Shell so Clawdy can raise the window that hosts a
// Claude Code session. On Wayland no application may focus another's window; the Shell may.
import Gio from 'gi://Gio';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const IFACE = `<node>
  <interface name="app.clawdy.Focus">
    <method name="ActivateByPid"><arg type="u" name="pid" direction="in"/><arg type="b" name="ok" direction="out"/></method>
    <method name="ActivateByTitle"><arg type="s" name="needle" direction="in"/><arg type="b" name="ok" direction="out"/></method>
    <method name="Version"><arg type="u" name="version" direction="out"/></method>
  </interface>
</node>`;

export default class ClawdyFocus extends Extension {
    enable() {
        this._dbus = Gio.DBusExportedObject.wrapJSObject(IFACE, this);
        this._dbus.export(Gio.DBus.session, '/app/clawdy/Focus');
    }

    disable() {
        this._dbus?.flush();
        this._dbus?.unexport();
        this._dbus = null;
    }

    _windows() {
        return global.get_window_actors().map(a => a.meta_window).filter(w => w && !w.skip_taskbar)
            .sort((a, b) => b.get_user_time() - a.get_user_time());   // most recently used first
    }

    _activate(win) {
        if (!win)
            return false;
        win.activate(global.get_current_time());
        return true;
    }

    ActivateByPid(pid) {
        return this._activate(this._windows().find(w => w.get_pid() === pid));
    }

    ActivateByTitle(needle) {
        return this._activate(this._windows().find(w => (w.get_title() || '').includes(needle)));
    }

    Version() {
        return 1;
    }
}
