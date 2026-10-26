#!/usr/bin/env python3
"""Clawdy: an animated Clawd that shows your Claude usage and acts out what Claude Code is doing.

    clawdy.py               open the widget (with a welcome screen the first time)
    clawdy.py --hook        called by Claude Code on every event
    clawdy.py --setup       connect to Claude Code and open at login
    clawdy.py --uninstall   disconnect everything and delete its data
    clawdy.py --quit        close the running copy
    clawdy.py --demo        cycle through every animation with made-up data
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main(argv):
    if "--hook" in argv:                 # hot path: fast and windowless
        import clawdy_hook
        clawdy_hook.main()
        return 0

    import clawdy_system
    if "--quit" in argv:                 # used by the installers when updating
        clawdy_system.ask_running_to_quit()
        return 0
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
