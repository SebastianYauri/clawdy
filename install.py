#!/usr/bin/env python3
"""Install from source (Intel Macs, Fedora, Arch and other systems).

On Windows, Ubuntu/Debian and Apple Silicon Macs the installers on the
Releases page are easier.

    python3 install.py              copy to ~/.clawdy and open it
    python3 install.py --uninstall  remove everything
"""
import os
import shutil
import subprocess
import sys

SRC = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(os.path.expanduser("~"), ".clawdy")
HOME = os.path.expanduser("~")
DATA = os.environ.get("XDG_DATA_HOME") or os.path.join(HOME, ".local", "share")
MENU = os.path.join(DATA, "applications", "clawdy.desktop")
ICON = os.path.join(DATA, "icons", "hicolor", "256x256", "apps", "clawdy.png")
FILES = ["clawdy.py", "clawdy_gui.py", "clawdy_hook.py", "clawdy_system.py",
         "clawdy_update.py", "clawdy_version.py", "clawdy_i18n.py", "clawdy_tray.py", "clawdy_walk.py"]


def add_to_menu(main_py):
    """Linux: an entry in the applications menu, so Clawdy can be found and reopened."""
    if not sys.platform.startswith("linux"):
        return
    os.makedirs(os.path.dirname(ICON), exist_ok=True)
    shutil.copy2(os.path.join(SRC, "assets", "icon.png"), ICON)
    os.makedirs(os.path.dirname(MENU), exist_ok=True)
    with open(MENU, "w") as f:
        f.write("[Desktop Entry]\nType=Application\nName=Clawdy\nGenericName=Claude usage\n"
                "Comment=Your Claude usage, with an animated buddy\n"
                "Exec=%s %s\nIcon=clawdy\nTerminal=false\nCategories=Utility;\n"
                "Keywords=claude;clawd;usage;uso;\n" % (sys.executable, main_py))
    subprocess.call(["update-desktop-database", os.path.dirname(MENU)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) if shutil.which("update-desktop-database") else None


def main():
    main_py = os.path.join(DEST, "clawdy.py")
    if "--uninstall" in sys.argv:
        if os.path.exists(main_py):
            subprocess.call([sys.executable, main_py, "--uninstall"])
        shutil.rmtree(DEST, ignore_errors=True)
        for f in (MENU, ICON):
            if os.path.exists(f):
                os.remove(f)
        print("Clawdy was removed.")
        return
    try:
        import tkinter  # noqa: F401
    except ImportError:
        sys.exit("tkinter is missing. macOS: brew install python-tk · Fedora: sudo dnf install python3-tkinter"
                 " · Arch: sudo pacman -S tk · Debian/Ubuntu: sudo apt install python3-tk")
    if os.path.exists(main_py):
        subprocess.call([sys.executable, main_py, "--quit"])
    os.makedirs(os.path.join(DEST, "assets"), exist_ok=True)
    for f in FILES:
        shutil.copy2(os.path.join(SRC, f), os.path.join(DEST, f))
    shutil.copy2(os.path.join(SRC, "assets", "icon.png"), os.path.join(DEST, "assets", "icon.png"))
    add_to_menu(main_py)
    subprocess.Popen([sys.executable, main_py], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Done: Clawdy is open. The first time it asks what to connect.")


if __name__ == "__main__":
    main()
