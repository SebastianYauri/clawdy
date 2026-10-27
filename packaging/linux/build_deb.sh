#!/bin/sh
# Builds the .deb package (Ubuntu, Debian, Mint…).  Usage: build_deb.sh [version] [output dir]
set -eu
umask 022
VER="${1:-1.0.0}"
OUT="${2:-dist}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="$(mktemp -d)"
PKG="$WORK/clawdy"
trap 'rm -rf "$WORK"' EXIT

install -d "$PKG/DEBIAN" "$PKG/usr/bin" "$PKG/usr/lib/clawdy/assets" \
           "$PKG/usr/share/applications" "$PKG/usr/share/icons/hicolor/256x256/apps" \
           "$PKG/usr/share/doc/clawdy"

install -m 644 "$ROOT"/clawdy.py "$ROOT"/clawdy_gui.py "$ROOT"/clawdy_hook.py \
               "$ROOT"/clawdy_system.py "$ROOT"/clawdy_update.py "$ROOT"/clawdy_version.py \
               "$ROOT"/clawdy_i18n.py "$ROOT"/clawdy_tray.py "$ROOT"/clawdy_walk.py \
               "$PKG/usr/lib/clawdy/"
install -m 644 "$ROOT/assets/icon.png" "$PKG/usr/lib/clawdy/assets/icon.png"
install -m 644 "$ROOT/assets/icon.png" "$PKG/usr/share/icons/hicolor/256x256/apps/clawdy.png"
install -m 644 "$ROOT/LICENSE" "$PKG/usr/share/doc/clawdy/copyright"

cat > "$PKG/usr/bin/clawdy" <<'SH'
#!/bin/sh
exec python3 /usr/lib/clawdy/clawdy.py "$@"
SH
chmod 755 "$PKG/usr/bin/clawdy"

cat > "$PKG/usr/share/applications/clawdy.desktop" <<'DESK'
[Desktop Entry]
Type=Application
Name=Clawdy
GenericName=Claude usage
GenericName[es]=Uso de Claude
Comment=Your Claude usage, with an animated buddy
Comment[es]=Tu uso de Claude, con un compañero animado
Exec=clawdy
Icon=clawdy
Terminal=false
Categories=Utility;
Keywords=claude;clawd;usage;uso;
DESK

SIZE=$(du -sk "$PKG/usr" | cut -f1)
cat > "$PKG/DEBIAN/control" <<CTRL
Package: clawdy
Version: $VER
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.8), python3-tk
Recommends: python3-pystray, gir1.2-ayatanaappindicator3-0.1
Installed-Size: $SIZE
Maintainer: SebastianYauri <77989694+SebastianYauri@users.noreply.github.com>
Homepage: https://github.com/SebastianYauri/clawdy
Description: Animated desktop buddy that shows your Claude usage
 A small desktop widget with a pixel mascot that shows how much of your
 Claude plan you have used and acts out what Claude Code is doing.
CTRL

# On removal, close the widget in every session where it is running.
cat > "$PKG/DEBIAN/prerm" <<'PRERM'
#!/bin/sh
set -e
if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    pkill -f /usr/lib/clawdy/clawdy.py 2>/dev/null || true
fi
PRERM
chmod 755 "$PKG/DEBIAN/prerm"

mkdir -p "$OUT"
dpkg-deb --build --root-owner-group "$PKG" "$OUT/clawdy_${VER}_all.deb" >/dev/null
echo "$OUT/clawdy_${VER}_all.deb"
