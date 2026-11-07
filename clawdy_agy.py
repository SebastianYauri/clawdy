"""Google's Antigravity CLI (`agy`, the successor of Gemini CLI) as a source.

Activity comes from its hooks (~/.gemini/config/hooks.json): every event runs
`clawdy --hook-agy <Event>` with a JSON on stdin, which is turned into the same
per-session state files the Claude Code hook writes. Quota comes from its status
line (~/.gemini/antigravity-cli/settings.json): after every turn agy runs
`clawdy --statusline-agy` with its whole state as JSON on stdin, quota buckets
included, and shows the line it prints in its own bar. Fallbacks: the desktop
app's language server while it runs, and the CLI log's "quota reached … Resets
in …", which becomes a full bar until then.
"""
import glob
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime, timezone

import clawdy_system as cs

HOME = os.environ.get("CLAWDY_AGY_HOME") or os.path.join(os.path.expanduser("~"), ".gemini")
CLI_DIR = os.path.join(HOME, "antigravity-cli")
HOOKS = os.path.join(HOME, "config", "hooks.json")
HISTORY = os.path.join(CLI_DIR, "history.jsonl")
EVENTS = ("SessionStart", "PreToolUse", "PostToolUse", "PreInvocation", "PostInvocation", "Stop")
WEB = "https://antigravity.google/cli"


def cli_path():
    found = shutil.which("agy")
    if found:
        return found
    for d in (os.path.join(cs.HOME, ".local", "bin"), "/opt/homebrew/bin", "/usr/local/bin"):
        p = os.path.join(d, "agy.exe" if cs.WIN else "agy")
        if os.path.isfile(p):
            return p
    return None


def installed():
    return os.path.isdir(CLI_DIR) or cli_path() is not None


# ---------------------------------------------------------------- hooks

def _command(flag="--hook-agy"):
    return cs.hook_command_prefix() + " " + flag


def _read():
    try:
        return json.load(open(HOOKS, encoding="utf-8-sig"))
    except Exception:
        return {}


def hooks_installed():
    return "clawdy" in _read()


def set_hooks(on):
    """Add or remove Clawdy's named hook, leaving everyone else's alone."""
    data = _read()
    if not isinstance(data, dict):
        data = {}
    if on:
        h = lambda ev: {"type": "command", "timeout": 5,
                        "command": ("%s %s" % (_command(), ev)) + ("" if cs.WIN else " || true")}
        entry = {"enabled": True}
        for ev in EVENTS:
            if ev in ("PreToolUse", "PostToolUse"):
                entry[ev] = [{"matcher": "*", "hooks": [h(ev)]}]
            else:
                entry[ev] = [h(ev)]
        data["clawdy"] = entry
    else:
        data.pop("clawdy", None)
    try:
        if data or os.path.exists(HOOKS):
            cs.write_json(HOOKS, data)
    except OSError as e:
        return str(e)
    set_statusline(on)                       # the quota comes this way; a foreign status line is left alone
    return None


# ---------------------------------------------------------------- status line

SETTINGS = os.path.join(CLI_DIR, "settings.json")
STATUS_FLAG = "--statusline-agy"
BUCKETS = {"gemini-5h": ("session", "Gemini"), "gemini-weekly": ("weekly_all", "Gemini"),
           "3p-5h": ("session", "Claude/GPT"), "3p-weekly": ("weekly_all", "Claude/GPT")}


def _settings():
    try:
        return json.load(open(SETTINGS, encoding="utf-8-sig"))
    except Exception:
        return {}


def _statusline_ours(sl):
    return isinstance(sl, dict) and STATUS_FLAG in str(sl.get("command", ""))


def statusline_installed():
    return _statusline_ours(_settings().get("statusLine"))


def set_statusline(on):
    """agy runs the status line command after every turn (through a shell, with its whole
    state as JSON on stdin: quota included). Clawdy's prints a short line for agy's bar
    and keeps the numbers. A status line someone else set up is left alone."""
    data = _settings()
    if not isinstance(data, dict):
        data = {}
    sl = data.get("statusLine")
    if on:
        if _statusline_ours(sl):
            return None
        if isinstance(sl, dict) and sl.get("command"):
            return "statusline taken"
        data["statusLine"] = {"type": "command", "enabled": True,
                              "command": _command(STATUS_FLAG) + ("" if cs.WIN else " || true")}
    elif _statusline_ours(sl):
        data.pop("statusLine")
    else:
        return None
    try:
        cs.write_json(SETTINGS, data)
    except OSError as e:
        return str(e)
    return None


def parse_statusline(payload):
    """Rows like parse_summary's, from the `quota` of the status line payload: buckets by id,
    each with remaining_fraction, reset_time or reset_in_seconds, maybe disabled."""
    quota = payload.get("quota") if isinstance(payload, dict) else None
    out, now = [], time.time()
    for bid, bucket in (quota or {}).items() if isinstance(quota, dict) else []:
        if not isinstance(bucket, dict) or bucket.get("disabled") is True:
            continue
        name = str(bid).lower()
        kind, scope = BUCKETS.get(name) or (
            "weekly_all" if "week" in name else "session" if "5h" in name else None, str(bid))
        frac = _fraction(bucket.get("remaining_fraction"))
        if kind is None or frac is None:
            continue
        reset = _reset(bucket.get("reset_time"))
        secs = bucket.get("reset_in_seconds")
        if reset is None and isinstance(secs, (int, float)) and secs > 0:
            reset = _reset(round((now + float(secs)) / 60) * 60)   # to the minute: steady across turns
        out.append((kind, scope, round((1 - frac) * 100, 1), reset))
    return out


def statusline(payload):
    """One turn of agy: keep its quota (written only when it changed) and return the line for its bar."""
    rows = parse_statusline(payload)
    if rows:
        try:
            old = json.load(open(QUOTA_FILE))
            same = [tuple(r) for r in old.get("rows", [])] == rows and time.time() - old.get("updated", 0) < 600
        except Exception:
            same = False
        if not same:
            cs.write_json(QUOTA_FILE, {"updated": time.time(), "rows": rows})
    return statusline_text(payload, rows)


def statusline_text(payload, rows):
    model = payload.get("model") if isinstance(payload.get("model"), dict) else {}
    label = str(model.get("display_name") or model.get("id") or "").split(" (")[0].strip()
    group = "Gemini" if "gemini" in label.lower() or not label else "Claude/GPT"
    mine = [r for r in rows if r[1] == group] or rows
    parts = [label] if label else []
    for kind, _, pct, _ in sorted(mine, key=lambda r: r[0] != "session"):
        parts.append("%s %d%%" % ("5h" if kind == "session" else "7d", round(pct)))
    ctx = payload.get("context_window") if isinstance(payload.get("context_window"), dict) else {}
    try:
        parts.append("ctx %d%%" % round(float(ctx.get("used_percentage"))))
    except (TypeError, ValueError):
        pass
    return " \u00b7 ".join(parts) or "Clawdy"


def state_for(ev, tool):
    n = (tool or "").lower().replace("_", "")
    if ev == "PreInvocation":
        return "thinking"
    if ev == "PreToolUse":
        if any(k in n for k in ("runcommand", "shell", "terminal", "execute")):
            return "building"
        if any(k in n for k in ("write", "edit", "replace", "create", "patch", "multiedit")):
            return "typing"
        if any(k in n for k in ("read", "view", "grep", "find", "list", "search", "web", "fetch")):
            return "reading"
        return "typing"
    if ev in ("PostToolUse", "PostInvocation"):
        return "thinking"
    if ev == "Stop":
        return "happy"
    if ev == "SessionStart":
        return "idle"
    return None


QUOTA_FILE = os.path.join(cs.cache_dir(), "agy-quota.json")
SERVICE = "/exa.language_server_pb.LanguageServerService"
METADATA = {"metadata": {"ideName": "antigravity", "extensionName": "antigravity", "ideVersion": "unknown", "locale": "en"}}


def endpoints_from_processes():
    """The Antigravity desktop app runs a language server whose command line carries
    `--csrf_token` and `--extension_server_port`: that's how every quota tracker finds it."""
    import subprocess
    out = []
    try:
        if cs.WIN:
            text = subprocess.run(["wmic", "process", "get", "CommandLine"], capture_output=True, text=True, timeout=5).stdout
        else:
            text = subprocess.run(["ps", "-axww", "-o", "command="], capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return out
    for line in text.splitlines():
        if "language_server" not in line or "csrf_token" not in line:
            continue
        m_tok = re.search(r"--csrf_token[= ]\"?([A-Za-z0-9-]+)", line)
        m_port = re.search(r"--extension_server_port[= ](\d+)", line)
        if m_tok and m_port:
            out.append(("http", "127.0.0.1", int(m_port.group(1)), m_tok.group(1)))
    return out


def call(endpoint, method, timeout=4):
    import ssl
    import urllib.request
    scheme, host, port, token = endpoint
    url = "%s://%s:%d%s/%s" % (scheme, host, port, SERVICE, method)
    req = urllib.request.Request(url, data=json.dumps(METADATA).encode(), method="POST", headers={
        "Content-Type": "application/json", "X-Codeium-Csrf-Token": token})
    ctx = ssl._create_unverified_context() if scheme == "https" else None
    body = urllib.request.urlopen(req, timeout=timeout, context=ctx).read()
    return json.loads(body.decode("utf-8", "replace"))


def _fraction(raw):
    if isinstance(raw, dict):
        if raw.get("case") == "remainingFraction":
            raw = raw.get("value")
        else:
            raw = raw.get("remainingFraction")
    try:
        return None if raw is None else max(0.0, min(1.0, float(raw)))
    except (TypeError, ValueError):
        return None


def _reset(value):
    if isinstance(value, (int, float)) and value > 0:
        return datetime.fromtimestamp(float(value), timezone.utc).isoformat()
    return value if isinstance(value, str) and value else None


def parse_summary(body):
    """[(kind, model group, percent used, resets_at)] from RetrieveUserQuotaSummary."""
    root = body.get("response") if isinstance(body.get("response"), dict) else body
    out = []
    for group in root.get("groups") or []:
        if not isinstance(group, dict):
            continue
        scope = group.get("displayName") or ""
        for bucket in group.get("buckets") or []:
            if not isinstance(bucket, dict) or bucket.get("disabled") is True:
                continue
            name = ("%s %s" % (bucket.get("bucketId") or "", bucket.get("displayName") or "")).lower()
            kind = "weekly_all" if "week" in name else ("session" if re.search(r"\b5h\b|5-hour|five[ -]hour|session", name) else None)
            frac = _fraction(bucket.get("remaining") if "remaining" in bucket else bucket)
            if kind is None or frac is None:
                continue
            out.append((kind, scope, round((1 - frac) * 100, 1), _reset(bucket.get("resetTime"))))
    return out


def refresh_quota(endpoint):
    """Ask the local server and save the numbers. Raises on failure."""
    rows = parse_summary(call(endpoint, "RetrieveUserQuotaSummary"))
    if rows:
        cs.write_json(QUOTA_FILE, {"updated": time.time(), "rows": rows})
    return rows


def handle(ev, data):
    """Called by the hook: one Antigravity event → the session's state file."""
    sid = "agy-" + "".join(c for c in str(data.get("conversationId") or "x") if c.isalnum() or c in "-_")[:72]
    os.makedirs(cs.SESSIONS, exist_ok=True)
    path = os.path.join(cs.SESSIONS, sid + ".json")
    try:
        s = json.load(open(path))
    except Exception:
        s = {"subagents": 0}
    now = time.time()
    if ev == "PreInvocation" and s.get("done", 0) >= s.get("started", 0):
        s["started"] = now                                # a new task began
    elif ev == "Stop":
        s["done"] = now
        s["took"] = round(now - s.get("started", now))
    tool = ((data.get("toolCall") or {}).get("name")) if isinstance(data.get("toolCall"), dict) else None
    new = state_for(ev, tool)
    if new:
        s["state"] = new
    s["ts"] = now
    ws = data.get("workspacePaths") or []
    if ws:
        s["cwd"] = str(ws[0])[:400]
    s.update(cs.session_anchor())
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w") as f:
        json.dump(s, f)
    os.replace(tmp, path)


# ---------------------------------------------------------------- usage

def _logs():
    try:
        return sorted(glob.glob(os.path.join(CLI_DIR, "log", "cli-*.log")), key=os.path.getmtime)[-3:]
    except OSError:
        return []


def usage():
    """Numbers the CLI handed its status line (fresh within a day), else the desktop app's
    language server, else a full bar while the CLI log says the quota is out."""
    rows, updated = None, 0
    try:
        q = json.load(open(QUOTA_FILE))
        if time.time() - q.get("updated", 0) < 24 * 3600 and q.get("rows"):
            rows, updated = [tuple(r) for r in q["rows"]], q["updated"]
    except Exception:
        pass
    if rows is None or time.time() - updated > 120:
        for endpoint in endpoints_from_processes():        # the desktop app, if it's running
            try:
                live = refresh_quota(endpoint)
            except Exception:
                continue
            if live:
                rows, updated = live, time.time()
                break
    if rows:
        limits = []
        for kind, scope, pct, reset in rows:
            lim = {"kind": kind, "percent": pct, "resets_at": reset}
            if scope:
                lim["scope"] = {"model": {"display_name": scope}}
            limits.append(lim)
        return {"limits": limits, "source": "agy", "updated": updated}
    return usage_from_log()


def usage_from_log():
    """{"limits": [...]} with a full bar while the CLI reports its quota exhausted, else None."""
    pat = re.compile(r"^[A-Z](\d{2})(\d{2}) (\d{2}):(\d{2}):(\d{2})\.\d+.*quota reached.*?Resets in (?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?",
                     re.I)
    latest = None
    for path in _logs():
        year = int(re.search(r"cli-(\d{4})", os.path.basename(path)).group(1)) if re.search(r"cli-(\d{4})", path) else datetime.now().year
        try:
            with open(path, "rb") as f:
                f.seek(max(0, os.path.getsize(path) - 512 * 1024))
                for raw in f.read().decode("utf-8", "replace").splitlines():
                    line = raw.split("google.Init: ", 1)[-1]
                    m = pat.search(line)
                    if m:
                        mo, d, hh, mi, ss, rh, rm, rs = m.groups()
                        when = datetime(year, int(mo), int(d), int(hh), int(mi), int(ss)).timestamp()
                        wait = int(rh or 0) * 3600 + int(rm or 0) * 60 + int(rs or 0)
                        latest = (when, when + wait)
        except OSError:
            continue
    if not latest or latest[1] <= time.time():
        return None
    iso = datetime.fromtimestamp(latest[1], timezone.utc).isoformat()
    kind = "weekly_all" if latest[1] - latest[0] > 6 * 3600 else "session"
    return {"limits": [{"kind": kind, "percent": 100.0, "resets_at": iso}], "source": "agy", "updated": latest[0]}


# ---------------------------------------------------------------- chats

def recent(limit=6, exclude=()):
    """[{id, cwd, project, title, ts}] from the CLI's prompt history, newest first."""
    out, seen = [], set(exclude)
    try:
        lines = open(HISTORY, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        return out
    for line in reversed(lines[-400:]):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        cid, text, ws = d.get("conversationId"), d.get("display") or "", d.get("workspace")
        if not cid or cid in seen or d.get("type") == "slash_command" or not text.strip() or not ws:
            continue
        seen.add(cid)
        out.append({"id": cid, "cwd": ws, "project": os.path.basename(os.path.normpath(ws)),
                    "title": " ".join(text.split())[:120], "ts": (d.get("timestamp") or 0) / 1000.0})
        if len(out) >= limit:
            break
    return out


def _in(cwd, args=""):
    path = cli_path() or "agy"
    if cs.WIN:
        return "Set-Location -LiteralPath '%s'; & '%s' %s" % (cwd.replace("'", "''"), path, args)
    q = lambda s: "'%s'" % s.replace("'", "'\\''")
    return "cd %s && %s %s" % (q(cwd), q(path), args)


def resume(session):
    return cs.open_terminal(_in(session["cwd"], "--conversation " + session["id"]))


def new_chat_in(cwd):
    return cs.open_terminal(_in(cwd))


def open_new_chat():
    cli = cli_path()
    if cli and cs.open_terminal(('& "%s"' % cli) if cs.WIN else "'%s'" % cli.replace("'", "'\\''")):
        return True
    import webbrowser
    webbrowser.open(WEB)
    return False
