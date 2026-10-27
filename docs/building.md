# Building and running from source

Clawdy is plain Python 3.8+ with tkinter. The tray icon optionally uses
[pystray](https://github.com/moses-palmer/pystray) and Pillow; without them Clawdy
runs the same, just without a tray icon. On Ubuntu:
`sudo apt install python3-pystray gir1.2-ayatanaappindicator3-0.1`.

## Run from a checkout

```sh
git clone https://github.com/SebastianYauri/clawdy.git
cd clawdy
python3 clawdy.py            # first run shows the welcome screen
python3 clawdy.py --demo     # cycle through every state with made-up usage
```

On Debian/Ubuntu install tkinter with `sudo apt install python3-tk`; on Fedora
`sudo dnf install python3-tkinter`; on Arch `sudo pacman -S tk`; on macOS with
Homebrew `brew install python-tk`.

A git checkout never updates itself, so it's safe to hack on.

## Install from source

```sh
python3 install.py              # copies Clawdy to ~/.clawdy and opens it
python3 install.py --uninstall  # disconnects it and removes everything
```

An install made this way updates itself from GitHub releases.

## Command line

```
clawdy.py               open the widget
clawdy.py --setup       connect to Claude Code and open at login
clawdy.py --uninstall   disconnect everything and delete its data
clawdy.py --quit        close the running copy
clawdy.py --demo        cycle through every animation with made-up data
clawdy.py --walk        send the running Clawdy for a walk right now
clawdy.py --hook        called by Claude Code on every event
```

| Environment variable | Effect |
|---|---|
| `CLAWDY_LANG=en` / `es` | force the interface language |
| `CLAWDY_DEBUG=1` | write `debug.log` with window and hover events |
| `CLAWDY_FAKE_LATEST='{"tag_name": "v99.0.0", …}'` | pretend a release exists (used by the update tests) |

## Project layout

| File | What it does |
|---|---|
| `clawdy.py` | entry point and command-line flags |
| `clawdy_gui.py` | the widget: drawing, animations, panel, menu, welcome |
| `clawdy_hook.py` | the Claude Code hook |
| `clawdy_system.py` | paths, settings, hooks, start at login, session token, single instance |
| `clawdy_update.py` | update checks and installers |
| `clawdy_i18n.py` | English and Spanish text |
| `clawdy_tray.py` | tray / menu bar icon |
| `clawdy_walk.py` | desktop walks |
| `clawdy_version.py` | version number, replaced by CI from the git tag |
| `packaging/` | `.deb` script, Inno Setup script, CI hook test |

## Installers

The [GitHub Actions workflow](../.github/workflows/build.yml) builds and tests
everything on real Windows, Linux and macOS runners on every push. Pushing a
`v*` tag also publishes a release with all the installers.

### Linux `.deb`

```sh
packaging/linux/build_deb.sh 1.2.3 dist
```

### Windows

```powershell
pip install pyinstaller pystray pillow
pyinstaller --noconfirm --windowed --name Clawdy --icon assets\icon.ico `
  --add-data "assets;assets" --hidden-import clawdy_gui --hidden-import clawdy_hook `
  --hidden-import clawdy_system --hidden-import clawdy_update --hidden-import clawdy_version `
  --hidden-import clawdy_i18n --hidden-import clawdy_tray --hidden-import clawdy_walk --hidden-import pystray._win32 clawdy.py
iscc /DAppVersion=1.2.3 packaging\windows\Clawdy.iss
```

### macOS

```sh
pip install pyinstaller pillow pystray
pyinstaller --noconfirm --windowed --name Clawdy --icon assets/icon.png \
  --osx-bundle-identifier com.clawdy.app --add-data "assets:assets" \
  --hidden-import clawdy_gui --hidden-import clawdy_hook --hidden-import clawdy_system \
  --hidden-import clawdy_update --hidden-import clawdy_version --hidden-import clawdy_i18n \
  --hidden-import clawdy_tray --hidden-import clawdy_walk --hidden-import pystray._darwin clawdy.py
codesign --force --deep -s - dist/Clawdy.app
```

## Releasing

```sh
git tag v1.2.3
git push origin v1.2.3
```

CI writes the version into `clawdy_version.py`, builds the three installers,
runs the tests and publishes the release using `packaging/release-notes.md`.
Every installed copy picks it up within 6 hours.
