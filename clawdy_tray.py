"""Tray / menu bar icon, so Clawdy can live in the background.

Uses pystray when it's available (bundled in the Windows and macOS builds,
a recommended package on Debian/Ubuntu). Without it Clawdy simply has no tray
icon and keeps working as before.
"""
import os
import queue
import sys
import threading

import clawdy_system as cs
from clawdy_i18n import t as tr

MAC = sys.platform == "darwin"


class Tray:
    def __init__(self, widget, icon_path):
        self.w = widget
        self.icon = None
        self.calls = queue.Queue()          # pystray calls back from its own thread
        if os.environ.get("CLAWDY_NO_TRAY"):
            return
        try:
            import pystray
            from PIL import Image
        except Exception:
            return
        self.pystray = pystray
        try:
            image = Image.open(icon_path)
            self.icon = pystray.Icon("clawdy", image, "Clawdy", menu=self.menu())
            if MAC:
                self.icon.run_detached()    # macOS: Tk already runs the app's event loop
            else:
                threading.Thread(target=self.icon.run, daemon=True).start()
        except Exception:
            self.icon = None
            return
        self.w.root.after(150, self.pump)

    @property
    def active(self):
        return self.icon is not None

    def menu(self):
        P, w = self.pystray, self.w
        Item = P.MenuItem

        def call(fn):
            return lambda icon, item: self.calls.put(fn)

        # pystray asks for check marks from its own thread: read plain values, never Tk variables
        def cfg(key, default=True):
            return lambda item: bool(cs.load_config().get(key, default))

        def switch(var, apply, checked):
            return Item(var[0], call(lambda: w.flip(var[1], apply)), checked=checked)

        def choice(options, get, set_):
            return P.Menu(*[Item(text, call(lambda v=value: (set_(v), self.refresh())),
                                 checked=lambda item, v=value: get() == v, radio=True)
                            for value, text in options])

        from clawdy_gui import DONE_AFTER, SIZES, PopupMenu
        settings = P.Menu(
            switch((tr("menu.hooks"), w.v_hooks), w.toggle_hooks, lambda item: cs.hooks_installed()),
            switch((tr("menu.autostart"), w.v_start), w.toggle_start, lambda item: cs.autostart_enabled()),
            switch((tr("menu.pin"), w.v_pin), w.toggle_pin, cfg("expanded", False)),
            switch((tr("menu.walks"), w.v_walks), w.toggle_walks, cfg("walks")),
            switch((tr("menu.alerts"), w.v_alerts), w.toggle_alerts, cfg("alerts")),
            switch((tr("menu.tasks"), w.v_tasks), w.toggle_tasks, cfg("tasks")),
            switch((tr("menu.sounds"), w.v_sounds), w.toggle_sounds, cfg("sounds")),
            P.Menu.SEPARATOR,
            Item(tr("menu.done_after"), choice(DONE_AFTER, lambda: w.done_after, w.set_done_after)),
            Item(tr("menu.size"), choice([(v, tr(l)) for v, l in SIZES], lambda: w.scale, w.set_scale)),
            Item(tr("menu.costume"), choice([(c, tr("costume." + c)) for c in PopupMenu.COSTUMES],
                                            lambda: w.costume_pref, w.set_costume)),
        )
        return P.Menu(
            Item(lambda item: tr("tray.hide") if w.visible() else tr("tray.show"),
                 call(w.toggle_visible), default=True),
            Item(tr("menu.chat_app" if w.has_app else "menu.chat_web"), call(w.new_chat)),
            Item(tr("menu.share"), call(w.share)),
            Item(tr("menu.refresh"), call(w.refresh)),
            Item(tr("menu.updates"), call(lambda: w.check_updates(True))),
            P.Menu.SEPARATOR,
            Item(tr("menu.settings"), settings),
            P.Menu.SEPARATOR,
            Item(tr("menu.quit"), call(w.root.destroy)),
        )

    def pump(self):
        """Run tray actions on the Tk thread."""
        try:
            while True:
                self.calls.get_nowait()()
        except queue.Empty:
            pass
        except Exception:
            pass
        try:
            self.w.root.after(150, self.pump)
        except Exception:
            pass

    def refresh(self):
        if self.icon:
            try:
                self.icon.update_menu()
            except Exception:
                pass

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
