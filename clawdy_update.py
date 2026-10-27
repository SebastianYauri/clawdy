"""Updates: look for a newer release on GitHub and install it.

- Windows (.exe): download the installer and run it silently; it closes the
  widget, updates it and opens it again.
- Mac (.app): download the zip, swap the bundle and relaunch.
- Linux (.deb): installing a system package needs a password, so it happens
  when the user clicks the notice, through the system prompt (pkexec).
- Installed from source (install.py): download the files and restart.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

import clawdy_system as cs
from clawdy_i18n import t
from clawdy_version import VERSION

REPO = "SebastianYauri/clawdy"
RELEASES = "https://github.com/%s/releases/latest" % REPO
API = "https://api.github.com/repos/%s/releases/latest" % REPO
RAW = "https://raw.githubusercontent.com/%s/%s/%s"
SOURCE_FILES = ["clawdy.py", "clawdy_gui.py", "clawdy_hook.py", "clawdy_system.py",
                "clawdy_update.py", "clawdy_version.py", "clawdy_i18n.py", "clawdy_tray.py", "clawdy_walk.py", "clawdy_sessions.py",
                "clawdy_share.py", "assets/icon.png", "assets/alert.wav", "assets/done.wav", "assets/ask.wav"]
RETRY_AFTER = 24 * 3600             # don't retry a failed version for a day


def parse(v):
    parts = []
    for x in str(v).strip().lstrip("vV").split(".")[:3]:
        digits = "".join(ch for ch in x if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts + [0] * (3 - len(parts)))


def newer(a, b):
    return parse(a) > parse(b)


def mac_bundle():
    """The "Clawdy.app" folder we are running from."""
    path = os.path.abspath(sys.executable)
    for _ in range(3):
        path = os.path.dirname(path)
    return path if path.endswith(".app") else None


def install_kind():
    if cs.FROZEN and cs.WIN and "\\scoop\\apps\\" in sys.executable.lower():
        return "scoop"                  # Scoop owns the files: `scoop update clawdy`
    if cs.FROZEN and cs.WIN:
        return "exe"
    if cs.FROZEN and cs.MAC:
        b = mac_bundle()
        return "app" if b and os.access(os.path.dirname(b), os.W_OK) else "manual"
    if cs.MAIN.startswith("/usr/lib/clawdy/"):
        return "deb"
    if os.path.isdir(os.path.join(cs.HERE, ".git")):
        return "dev"                    # a git checkout: never overwrite it
    if not cs.FROZEN and os.access(cs.HERE, os.W_OK):
        return "source"
    return "manual"


def log(msg):
    try:
        os.makedirs(cs.cache_dir(), exist_ok=True)
        with open(os.path.join(cs.cache_dir(), "update.log"), "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except OSError:
        pass


def _open(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "clawdy/" + VERSION,
                                               "Accept": "application/vnd.github+json"})
    return urllib.request.urlopen(req, timeout=timeout)


def check():
    """The latest release if it is newer than us, else None."""
    fake = os.environ.get("CLAWDY_FAKE_LATEST")         # tests only
    if fake:
        rel = json.loads(fake)
    else:
        try:
            rel = json.loads(_open(API).read())
        except urllib.error.HTTPError as e:
            if e.code == 404:                           # nothing released yet
                return None
            raise
    tag = rel.get("tag_name") or ""
    if not tag or not newer(tag, VERSION):
        return None
    return {"version": tag.lstrip("vV"), "tag": tag, "ref": rel.get("ref") or tag,
            "assets": rel.get("assets") or [], "url": rel.get("html_url") or RELEASES}


def should_auto_apply(info):
    """Don't keep retrying a version we already tried to install."""
    tried = cs.load_config().get("update_tried") or {}
    return not (tried.get("version") == info["version"] and time.time() - tried.get("at", 0) < RETRY_AFTER)


def _remember_try(info):
    cfg = cs.load_config()
    cfg["update_tried"] = {"version": info["version"], "at": time.time()}
    try:
        cs.save_config(cfg)
    except OSError:
        pass


def _download(url, dest, digest=None):
    h = hashlib.sha256()
    with _open(url, timeout=180) as r, open(dest + ".part", "wb") as f:
        while True:
            b = r.read(65536)
            if not b:
                break
            f.write(b)
            h.update(b)
    if digest and digest.startswith("sha256:") and h.hexdigest() != digest.split(":", 1)[1]:
        os.remove(dest + ".part")
        raise IOError("download checksum mismatch")
    os.replace(dest + ".part", dest)


def _asset(info, suffix):
    for a in info["assets"]:
        if a.get("name", "").lower().endswith(suffix):
            return a
    return None


def _relaunch(cmd):
    """Reopen the widget once this one has exited."""
    if cs.WIN:
        return
    subprocess.Popen(["sh", "-c", 'sleep 1.5; exec "$@"', "sh"] + list(cmd),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def apply(info):
    """Install the new version.

    Returns "restart" when the widget must exit (another process reopens it),
    None when the installer takes care of everything, or a message on failure."""
    kind = install_kind()
    log("updating from %s to %s (%s)" % (VERSION, info["version"], kind))
    _remember_try(info)
    work = os.path.join(cs.cache_dir(), "update")
    os.makedirs(work, exist_ok=True)

    if kind == "scoop":
        return t("update.scoop")

    if kind == "exe":
        a = _asset(info, ".exe")
        if not a:
            return t("update.no_installer")
        dest = os.path.join(work, "Clawdy-Setup-%s.exe" % info["version"])
        _download(a["browser_download_url"], dest, a.get("digest"))
        subprocess.Popen([dest, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/autoupdate=1"],
                         creationflags=0x00000008 | 0x00000200, close_fds=True)
        log("installer started")
        return None

    if kind == "app":
        a = _asset(info, "-mac.zip")
        if not a:
            return t("update.no_mac")
        dest = os.path.join(work, a["name"])
        _download(a["browser_download_url"], dest, a.get("digest"))
        bundle = mac_bundle()
        tmp = tempfile.mkdtemp(dir=work)
        try:
            subprocess.run(["ditto", "-x", "-k", dest, tmp], check=True)
            new = os.path.join(tmp, os.path.basename(bundle))
            if not os.path.isdir(new):
                return t("update.bad_zip")
            old = bundle + ".old"
            shutil.rmtree(old, ignore_errors=True)
            os.rename(bundle, old)              # the running app keeps working
            shutil.move(new, bundle)
            shutil.rmtree(old, ignore_errors=True)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        log("app replaced")
        _relaunch(["open", "-n", bundle])
        return "restart"

    if kind == "deb":
        a = _asset(info, ".deb")
        if not a:
            return t("update.no_package")
        dest = os.path.join(work, a["name"])
        _download(a["browser_download_url"], dest, a.get("digest"))
        if shutil.which("pkexec"):
            r = subprocess.run(["pkexec", "apt-get", "install", "-y", dest],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            log("pkexec exited with %d" % r.returncode)
            if r.returncode == 0:
                _relaunch(["clawdy"])
                return "restart"
            if r.returncode in (126, 127):
                return t("update.cancelled")
        subprocess.Popen(["xdg-open", dest], start_new_session=True)
        return t("update.finish")

    if kind == "source":
        tmp = tempfile.mkdtemp(dir=work)
        try:
            for f in SOURCE_FILES:
                d = os.path.join(tmp, f)
                os.makedirs(os.path.dirname(d), exist_ok=True)
                _download(RAW % (REPO, info["ref"], f), d)
            for f in SOURCE_FILES:                      # everything downloaded: now replace
                dst = os.path.join(cs.HERE, f)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.move(os.path.join(tmp, f), dst)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        log("files updated")
        _relaunch(cs.launch_cmd())
        return "restart"

    return t("update.manual")
