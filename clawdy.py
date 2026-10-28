#!/usr/bin/env python3
"""Clawdy: an animated Clawd that shows your Claude usage and acts out what Claude Code is doing.

    clawdy.py               open the widget (with a welcome screen the first time)
    clawdy.py --hook        called by Claude Code on every event
    clawdy.py --setup       connect to Claude Code and open at login
    clawdy.py --uninstall   disconnect everything and delete its data
    clawdy.py --quit        close the running copy
    clawdy.py --demo        cycle through every animation with made-up data
    clawdy.py --walk        send the running Clawdy for a walk right now
    clawdy.py --hook-agy    called by the Antigravity CLI on every event
    clawdy.py --statusline-agy   the Antigravity CLI's status line (its quota comes this way)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if sys.platform.startswith("linux"):
    os.environ.setdefault("GDK_BACKEND", "x11")   # GTK (tray, pet window) alongside Tk, placeable


def read_stdin(timeout):
    """All of stdin, or whatever arrived within `timeout` seconds (never hang agy's bar)."""
    if sys.platform == "win32":
        return sys.stdin.read()
    import select
    import time
    chunks, end = [], time.time() + timeout
    while True:
        ready, _, _ = select.select([sys.stdin], [], [], max(0.0, end - time.time()))
        if not ready:
            break
        chunk = os.read(sys.stdin.fileno(), 65536)
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks).decode("utf-8", "replace")


def main(argv):
    if "--hook" in argv:                 # hot path: fast and windowless
        import clawdy_hook
        clawdy_hook.main()
        return 0
    if "--statusline-agy" in argv:       # Antigravity CLI status line: its state (quota included) on stdin
        line = ""
        try:
            import json
            import clawdy_agy
            raw = read_stdin(1.5)
            line = clawdy_agy.statusline(json.loads(raw) if raw.strip() else {})
        except Exception:
            pass
        sys.stdout.write((line or "Clawdy") + "\n")
        return 0
    if "--hook-agy" in argv:             # Antigravity CLI: the event name comes as an argument
        try:
            import json
            import clawdy_agy
            i = argv.index("--hook-agy")
            ev = argv[i + 1] if i + 1 < len(argv) else ""
            raw = sys.stdin.read() if sys.stdin else ""
            clawdy_agy.handle(ev, json.loads(raw) if raw.strip() else {})
        except Exception:
            pass
        return 0

    import clawdy_system
    if "--quit" in argv:                 # used by the installers when updating
        clawdy_system.ask_running_to_quit()
        return 0
    if "--walk" in argv:
        return 0 if clawdy_system.send_to_running(b"walk") else 1
    if "--skin" in argv:
        return 0 if clawdy_system.send_to_running(b"creator") else 1
    if "--uninstall" in argv:
        clawdy_system.uninstall()
        return 0
    if "--setup" in argv:
        err = clawdy_system.setup()
        if err and sys.stdout:          # a windowed .exe has no stdout
            print(err)
        return 1 if err else 0

    import clawdy_gui
    selftest = 0
    if "--selftest" in argv:
        i = argv.index("--selftest")
        selftest = int(argv[i + 1]) if i + 1 < len(argv) and argv[i + 1].isdigit() else 5
    return clawdy_gui.run(demo="--demo" in argv, selftest=selftest)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
