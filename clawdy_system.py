"""Everything that touches the operating system: paths, settings, Claude Code
hooks, start at login, the Claude session token and the single-instance lock."""
import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
import time
import zlib

from clawdy_i18n import t

HOME = os.path.expanduser("~")
WIN = sys.platform == "win32"
MAC = sys.platform == "darwin"
FROZEN = getattr(sys, "frozen", False)

APP = "Clawdy"
HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "clawdy.py")
SETTINGS = os.path.join(HOME, ".claude", "settings.json")
CREDENTIALS = os.path.join(HOME, ".claude", ".credentials.json")
KEYCHAIN_SERVICE = "Claude Code-credentials"

EVENTS = ["UserPromptSubmit", "PreToolUse", "PostToolUse", "PostToolUseFailure",
          "Stop", "StopFailure", "SubagentStart", "SubagentStop", "Notification",
          "PermissionRequest", "PreCompact", "PostCompact", "SessionStart", "SessionEnd"]

# How our entries are recognised inside settings.json (the last four are pre-release names).
MARKERS = ("clawdy.py", "clawdy.exe", "clawdy.app/",
           "clawd_usage.py", "clawd_hook.py", "clawdusage.exe", "clawd usage.app/")


# ------------------------------------------------------------------- paths

def _base(kind):
    if WIN:
        env = "LOCALAPPDATA" if kind == "cache" else "APPDATA"
        sub = "Local" if kind == "cache" else "Roaming"
        return os.environ.get(env) or os.path.join(HOME, "AppData", sub)
    if MAC:
        return os.path.join(HOME, "Library", "Caches" if kind == "cache" else "Application Support")
    env = "XDG_CACHE_HOME" if kind == "cache" else "XDG_CONFIG_HOME"
    return os.environ.get(env) or os.path.join(HOME, ".cache" if kind == "cache" else ".config")


def cache_dir():
    return os.path.join(_base("cache"), "clawdy")


def config_dir():
    return os.path.join(_base("config"), "clawdy")


SESSIONS = os.path.join(cache_dir(), "sessions")
USAGE_CACHE = os.path.join(cache_dir(), "usage.json")
CONFIG = os.path.join(config_dir(), "config.json")

# Derived from the config path, so two users logged in on one machine don't block each other.
LOCK_PORT = 40000 + zlib.crc32(config_dir().encode("utf-8")) % 20000


def resource(*parts):
    """A file bundled with the program (works from source and from PyInstaller)."""
    return os.path.join(getattr(sys, "_MEIPASS", HERE), *parts)


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def load_config():
    try:
        return json.load(open(CONFIG, encoding="utf-8-sig"))
    except Exception:
        return {}


def save_config(cfg):
    write_json(CONFIG, cfg)


def update_config(**changes):
    cfg = load_config()
    cfg.update(changes)
    try:
        save_config(cfg)
    except OSError:
        pass


# ------------------------------------------------------------ Claude session

def _keychain(secret):
    """On macOS Claude Code keeps its session in the login Keychain, not in a file."""
    user = os.environ.get("USER") or os.path.basename(HOME)
    cmd = ["security", "find-generic-password", "-a", user, "-s", KEYCHAIN_SERVICE]
    if secret:
        cmd.append("-w")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    raw = r.stdout.strip()
    if secret and raw and len(raw) % 2 == 0 and all(c in "0123456789abcdefABCDEF" for c in raw):
        try:                                        # `security -w` sometimes prints hex
            raw = bytes.fromhex(raw).decode("utf-8")
        except ValueError:
            pass
    return raw if secret else "ok"


def read_session():
    """(access token, expiry in epoch seconds or None). Raises FileNotFoundError when signed out."""
    raw = _keychain(True) if MAC else None
    if raw is None:
        raw = open(CREDENTIALS, encoding="utf-8").read()
    oauth = json.loads(raw)["claudeAiOauth"]
    exp = oauth.get("expiresAt")
    return oauth["accessToken"], (exp / 1000.0 if exp else None)


def read_token():
    return read_session()[0]


def session_stamp():
    """Changes whenever Claude Code renews its session (cheap; None on macOS)."""
    try:
        return os.path.getmtime(CREDENTIALS)
    except OSError:
        return None


def logged_in():
    # Only checks that the Keychain item exists: reading the secret would prompt.
    return os.path.exists(CREDENTIALS) or (MAC and _keychain(False) is not None)


# ------------------------------------------------------------ launching us

def _gui_python():
    exe = sys.executable
    if WIN:
        w = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.exists(w):
            return w
    return exe


def launch_cmd():
    """argv that opens the widget."""
    if FROZEN:
        return [sys.executable]
    return [_gui_python(), MAIN]


def hook_entry():
    """Our entry for Claude Code's settings.json."""
    base = {"type": "command", "async": True, "timeout": 10}
    if WIN:
        # Exec form (no shell), so it behaves the same under PowerShell and Git Bash.
        if FROZEN:
            return dict(base, command=sys.executable, args=["--hook"])
        return dict(base, command=sys.executable, args=[MAIN, "--hook"])
    # Guarded: if the program is removed without disconnecting, the hook is a no-op.
    target = sys.executable if FROZEN else MAIN
    run = "%s --hook" % shlex.quote(sys.executable) if FROZEN else \
          "%s %s --hook" % (shlex.quote(sys.executable), shlex.quote(MAIN))
    return dict(base, command="[ -f %s ] && %s || true" % (shlex.quote(target), run))


# ------------------------------------------------------------ hooks

def _is_ours(h):
    blob = " ".join([str(h.get("command", ""))] + [str(a) for a in h.get("args", [])]).lower()
    return any(m in blob for m in MARKERS)


def _read_settings():
    if not os.path.exists(SETTINGS):
        return {}
    return json.load(open(SETTINGS, encoding="utf-8-sig"))


def hooks_installed():
    try:
        hooks = _read_settings().get("hooks") or {}
    except Exception:
        return False
    return any(_is_ours(h) for groups in hooks.values() for g in groups or []
               for h in g.get("hooks", []))


def set_hooks(on):
    """Add or remove our hooks without touching anyone else's. Returns an error or None."""
    try:
        data = _read_settings()
    except Exception as e:
        return t("system.read_settings", e=e)
    if os.path.exists(SETTINGS):
        try:
            shutil.copy2(SETTINGS, SETTINGS + ".clawdy-backup")
        except OSError:
            pass

    hooks = data.get("hooks") or {}
    for ev in list(hooks):
        groups = []
        for g in hooks.get(ev) or []:
            g = dict(g)
            g["hooks"] = [h for h in g.get("hooks", []) if not _is_ours(h)]
            if g["hooks"]:
                groups.append(g)
        if groups:
            hooks[ev] = groups
        else:
            hooks.pop(ev, None)
    if on:
        entry = hook_entry()
        for ev in EVENTS:
            hooks.setdefault(ev, []).append({"hooks": [dict(entry)]})
    if hooks:
        data["hooks"] = hooks
    else:
        data.pop("hooks", None)
    if not data and not os.path.exists(SETTINGS):
        return None
    try:
        write_json(SETTINGS, data)
    except Exception as e:
        return t("system.save_settings", e=e)
    return None


# ------------------------------------------------------------ start at login

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_MAC_LABEL = "com.clawdy.app"


def _desktop_file():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(HOME, ".config")
    return os.path.join(base, "autostart", "clawdy.desktop")


def _mac_agent():
    return os.path.join(HOME, "Library", "LaunchAgents", _MAC_LABEL + ".plist")


def autostart_enabled():
    if WIN:
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
                winreg.QueryValueEx(k, APP)
            return True
        except OSError:
            return False
    return os.path.exists(_mac_agent() if MAC else _desktop_file())


def set_autostart(on):
    cmd = launch_cmd()
    if WIN:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
            if on:
                winreg.SetValueEx(k, APP, 0, winreg.REG_SZ, " ".join('"%s"' % c for c in cmd))
            else:
                try:
                    winreg.DeleteValue(k, APP)
                except OSError:
                    pass
        return
    if MAC:
        path = _mac_agent()
        if on:
            args = "".join("<string>%s</string>" % c for c in cmd)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w").write(
                '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE plist PUBLIC '
                '"-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                '<plist version="1.0"><dict><key>Label</key><string>%s</string>'
                '<key>ProgramArguments</key><array>%s</array>'
                '<key>RunAtLoad</key><true/></dict></plist>\n' % (_MAC_LABEL, args))
        elif os.path.exists(path):
            os.remove(path)
        return
    path = _desktop_file()
    if on:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        exe = "clawdy" if MAIN.startswith("/usr/lib/clawdy/") else \
            " ".join('"%s"' % c if " " in c else c for c in cmd)
        open(path, "w").write(
            "[Desktop Entry]\nType=Application\nName=%s\nComment=%s\nExec=%s\nIcon=clawdy\n"
            "X-GNOME-Autostart-Delay=10\n" % (APP, t("system.desktop_comment"), exe))
    elif os.path.exists(path):
        os.remove(path)


# ------------------------------------------------------------ new chat

CHAT_APP = "claude://claude.ai/new?surface=chat"     # the link the Claude app itself uses
CHAT_WEB = "https://claude.ai/new"


def claude_app_installed():
    """Is there a Claude desktop app registered for claude:// links?"""
    if WIN:
        import ctypes
        from ctypes import wintypes
        size = wintypes.DWORD(260)
        buf = ctypes.create_unicode_buffer(260)
        try:
            # ASSOCF_IS_PROTOCOL + ASSOCSTR_EXECUTABLE: covers classic and Store apps.
            hr = ctypes.windll.shlwapi.AssocQueryStringW(0x1000, 2, "claude", None, buf, ctypes.byref(size))
            if hr == 0 and buf.value:
                return True
        except Exception:
            pass
        try:
            import winreg
            winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "claude").Close()
            return True
        except OSError:
            return False
    if MAC:
        return any(os.path.isdir(p) for p in ("/Applications/Claude.app",
                                              os.path.join(HOME, "Applications", "Claude.app")))
    try:
        out = subprocess.run(["xdg-mime", "query", "default", "x-scheme-handler/claude"],
                             capture_output=True, text=True, timeout=3).stdout.strip()
    except Exception:
        return False
    return bool(out)


INSTALL_SH = "curl -fsSL https://claude.ai/install.sh | bash"
INSTALL_PS = "irm https://claude.ai/install.ps1 | iex"


def claude_code_path():
    """Where the Claude Code CLI is, or None. GUI apps often get a short PATH, so look around."""
    found = shutil.which("claude")
    if found:
        return found
    exe = "claude.exe" if WIN else "claude"
    for d in (os.path.join(HOME, ".local", "bin"), os.path.join(HOME, ".claude", "local"),
              "/opt/homebrew/bin", "/usr/local/bin", os.path.join(HOME, ".npm-global", "bin"),
              os.path.join(os.environ.get("APPDATA", ""), "npm")):
        p = os.path.join(d, exe)
        if os.path.isfile(p):
            return p
    return None


def _terminal(cmd):
    """Run a shell command in a new, visible terminal window."""
    if WIN:
        subprocess.Popen(["powershell", "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                         creationflags=0x00000010)
        return True
    if MAC:
        script = 'tell application "Terminal" to do script "%s"' % cmd.replace("\\", "\\\\").replace('"', '\\"')
        subprocess.Popen(["osascript", "-e", script, "-e", 'tell application "Terminal" to activate'])
        return True
    run = "%s; echo; read -p 'Press Enter to close…' _" % cmd
    for term, args in (("ptyxis", ["--new-window", "--", "bash", "-lc", run]),
                       ("kgx", ["--", "bash", "-lc", run]), ("gnome-terminal", ["--", "bash", "-lc", run]),
                       ("konsole", ["-e", "bash", "-lc", run]), ("x-terminal-emulator", ["-e", "bash", "-lc", run]),
                       ("xfce4-terminal", ["-x", "bash", "-lc", run]), ("xterm", ["-e", "bash", "-lc", run])):
        if shutil.which(term):
            subprocess.Popen([term] + args, start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
    return False


def connect_claude_code():
    """Install Claude Code if needed and sign in, in a terminal the user can see.
    Falls back to the setup page when no terminal can be opened."""
    path = claude_code_path()
    if WIN:
        cmd = ('& "%s" auth login' % path) if path else \
            '%s; & "$env:USERPROFILE\\.local\\bin\\claude.exe" auth login' % INSTALL_PS
    else:
        cmd = ("'%s' auth login" % path) if path else "%s && ~/.local/bin/claude auth login" % INSTALL_SH
    try:
        if _terminal(cmd):
            return True
    except Exception:
        pass
    import webbrowser
    webbrowser.open("https://docs.claude.com/en/docs/claude-code/setup")
    return False


def claude_running():
    """Is the Claude desktop app or Claude Code running? Cheap enough to call every ~30 s."""
    names = {"claude", "claude-desktop", "claude.exe"}
    try:
        if WIN:
            out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True,
                                 timeout=5, creationflags=0x08000000).stdout
            return any(line.split(",")[0].strip('"').lower() in names for line in out.splitlines())
        if MAC:
            out = subprocess.run(["ps", "-axco", "comm"], capture_output=True, text=True, timeout=5).stdout
            return any(line.strip().lower() in names for line in out.splitlines())
        for pid in os.listdir("/proc"):
            if pid.isdigit():
                try:
                    with open("/proc/%s/comm" % pid) as f:
                        if f.read().strip().lower() in names:
                            return True
                except OSError:
                    pass
    except Exception:
        pass
    return False


def open_new_chat(use_app):
    if use_app:
        try:
            if WIN:
                os.startfile(CHAT_APP)
            elif MAC:
                subprocess.Popen(["open", CHAT_APP])
            else:
                subprocess.Popen(["xdg-open", CHAT_APP], stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, start_new_session=True)
            return
        except Exception:
            pass
    import webbrowser
    webbrowser.open(CHAT_WEB)


# ------------------------------------------------------------ single instance

def single_instance():
    """Claim the local port. Returns the listening socket, or None if another copy runs."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if WIN:
            s.setsockopt(socket.SOL_SOCKET, getattr(socket, "SO_EXCLUSIVEADDRUSE", 0x4), 1)
        s.bind(("127.0.0.1", LOCK_PORT))
        s.listen(1)
        s.setblocking(False)
        return s
    except OSError:
        s.close()
        return None


def send_to_running(message):
    try:
        with socket.create_connection(("127.0.0.1", LOCK_PORT), timeout=1) as c:
            c.sendall(message)
        return True
    except OSError:
        return False


def ask_running_to_quit(wait=3.0):
    """Ask the running copy to quit and wait until it has let go of its files."""
    if not send_to_running(b"quit"):
        return False
    end = time.time() + wait
    while time.time() < end:
        time.sleep(0.2)
        try:
            socket.create_connection(("127.0.0.1", LOCK_PORT), timeout=0.3).close()
        except OSError:
            return True
    return True


# ------------------------------------------------------------ install / uninstall

def setup(hooks=True, autostart=True):
    err = set_hooks(hooks)
    try:
        set_autostart(autostart)
    except Exception as e:
        err = err or t("system.autostart", e=e)
    update_config(setup_done=True)
    return err


def uninstall():
    ask_running_to_quit()
    set_hooks(False)
    try:
        set_autostart(False)
    except Exception:
        pass
    for d in (config_dir(), cache_dir()):
        shutil.rmtree(d, ignore_errors=True)
