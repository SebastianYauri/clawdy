#!/bin/sh
# Installs Clawdy on macOS or Linux:
#   curl -fsSL https://raw.githubusercontent.com/SebastianYauri/clawdy/main/get.sh | sh
# CLAWDY_VERSION=1.4.1 picks a specific release instead of the latest one.
set -eu

REPO="SebastianYauri/clawdy"
say() { printf '\033[1;38;5;173m›\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "$1 is required"; }

need curl
TAG="${CLAWDY_VERSION:-}"
if [ -z "$TAG" ]; then
    TAG=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" |
          sed -n 's/.*"tag_name": *"v\{0,1\}\([^"]*\)".*/\1/p' | head -n 1)
    [ -n "$TAG" ] || die "could not find the latest release"
fi
TAG="${TAG#v}"
URL="https://github.com/$REPO/releases/download/v$TAG"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

from_source() {
    need python3
    python3 -c "import tkinter" 2>/dev/null ||
        die "Python's tkinter is missing (macOS: brew install python-tk · Fedora: sudo dnf install python3-tkinter · Arch: sudo pacman -S tk)"
    say "Downloading Clawdy $TAG (source)…"
    curl -fsSL "https://github.com/$REPO/archive/refs/tags/v$TAG.tar.gz" | tar -xz -C "$TMP"
    python3 "$TMP/clawdy-$TAG/install.py"
}

case "$(uname -s)" in
Darwin)
    if [ "$(uname -m)" != "arm64" ]; then
        from_source                                     # the app is built for Apple silicon
        exit 0
    fi
    say "Downloading Clawdy $TAG for macOS…"
    curl -fL --progress-bar "$URL/Clawdy-mac.zip" -o "$TMP/Clawdy.zip"
    DEST=/Applications
    [ -w "$DEST" ] || { DEST="$HOME/Applications"; mkdir -p "$DEST"; }
    pkill -f "Clawdy.app/Contents/MacOS" 2>/dev/null || true
    rm -rf "$DEST/Clawdy.app"
    ditto -x -k "$TMP/Clawdy.zip" "$DEST"
    say "Installed in $DEST/Clawdy.app"
    open "$DEST/Clawdy.app"
    ;;
Linux)
    if command -v apt-get >/dev/null 2>&1 && command -v dpkg >/dev/null 2>&1; then
        say "Downloading Clawdy $TAG (.deb)…"
        curl -fL --progress-bar "$URL/clawdy_${TAG}_all.deb" -o "$TMP/clawdy.deb"
        chmod 644 "$TMP/clawdy.deb"; chmod 755 "$TMP"
        SUDO=""
        [ "$(id -u)" = 0 ] || SUDO="sudo"
        say "Installing (your password may be asked)…"
        $SUDO apt-get install -y "$TMP/clawdy.deb"
        if [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] && [ "$(id -u)" != 0 ]; then
            (setsid clawdy >/dev/null 2>&1 &) || true
        fi
    else
        from_source
    fi
    ;;
*)
    die "unsupported system; on Windows run: irm https://raw.githubusercontent.com/$REPO/main/get.ps1 | iex"
    ;;
esac
say "Done! Clawdy is in the corner of your screen. 👾"
