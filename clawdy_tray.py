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
        return P.Menu(
            Item(lambda item: tr("tray.hide") if w.visible() else tr("tray.show"),
                 call(w.toggle_visible), default=True),
            Item(tr("menu.chat_app" if w.has_app else "menu.chat_web"), call(w.new_chat)),
            Item(tr("menu.share"), call(w.share)),
            Item(tr("menu.refresh"), call(w.refresh)),
            P.Menu.SEPARATOR,
            Item(tr("menu.hooks"), call(lambda: w.flip(w.v_hooks, w.toggle_hooks)),
                 checked=lambda item: cs.hooks_installed()),
            Item(tr("menu.autostart"), call(lambda: w.flip(w.v_start, w.toggle_start)),
                 checked=lambda item: cs.autostart_enabled()),
            Item(tr("menu.updates"), call(lambda: w.check_updates(True))),
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
