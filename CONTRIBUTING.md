# Contributing

Thanks for wanting to help! Bug reports, ideas and pull requests are welcome.

## Reporting a bug

Open an [issue](https://github.com/SebastianYauri/clawdy/issues) with:

- your operating system and desktop (for example *Ubuntu 24.04, GNOME on Wayland*),
- how you installed Clawdy (installer, `.deb`, `install.py`, git checkout),
- what you expected and what happened,
- if it's about the widget's window or hover behaviour, a `debug.log` made with
  `CLAWDY_DEBUG=1` (see [How it works](docs/how-it-works.md#files-it-touches)
  for where it's saved).

Please don't paste the contents of `~/.claude/.credentials.json` or anything
else that contains your Claude session.

## Making changes

1. Fork the repo and create a branch.
2. Run it with `python3 clawdy.py --demo` to see every state with fake data.
3. Keep it dependency-free: the standard library and tkinter only.
4. User-facing text goes in `clawdy_i18n.py`, in English and Spanish.
5. Test on the platforms you can. CI builds and tests Windows, Linux and macOS
   on every pull request.

Some lessons that shaped the code, in case you touch the windows:

- On GNOME/Wayland (XWayland), resizing or reshaping a window every frame
  flickers. Move windows and change their opacity instead.
- `winfo_pointerxy` goes stale when the pointer leaves the window under
  XWayland; rely on `<Enter>`/`<Leave>` events.
- Test on a real display, not only under Xvfb.

## Adding a costume

Costumes live in `clawdy_gui.py`: draw it in `draw_costume`, give it a palette
in `PALETTES`, a special move in the `act == "special"` branch of `draw_clawd`, a trick in `TRICKS`, optional themed props in `THEMED`, a hat
height in `HAT_TOP` if it adds one, and a name in `clawdy_i18n.py`
(`costume.<name>`). Then add it to `PopupMenu.COSTUMES`.
