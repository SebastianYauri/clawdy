"""Google's Antigravity CLI (`agy`, the successor of Gemini CLI) as a source.

Activity comes from its hooks (~/.gemini/config/hooks.json): every event runs
`clawdy --hook-agy <Event>` with a JSON on stdin, which is turned into the same
per-session state files the Claude Code hook writes. The CLI doesn't share its
quota with other programs, so usage is only known when it ran out: the CLI log
records "quota reached … Resets in …", which becomes a full bar until then.
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

def _command():
    return cs.hook_command_prefix() + " --hook-agy"


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
    return None


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
QUOTA_EVERY = 60


def ask_server_quota():
    """From inside a hook: the CLI hands its children the address of its local server and a
    one-launch CSRF token; use them (in memory only) to read the quota summary and save just
    the numbers. Any problem is ignored: the hook must never fail or slow the CLI down."""
    token = os.environ.get("ANTIGRAVITY_CSRF_TOKEN")
    port = os.environ.get("ANTIGRAVITY_SIDECAR_WEB_PORT")
    addr = os.environ.get("ANTIGRAVITY_LS_ADDRESS")
    if not token or not (port or addr):
        return
    try:
        if os.path.getmtime(QUOTA_FILE) > time.time() - QUOTA_EVERY:
            return                                          # fresh enough
    except OSError:
        pass
    import urllib.request
    host = addr if addr and "://" in addr else "http://127.0.0.1:%s" % (port or addr.rsplit(":", 1)[-1])
    url = host.rstrip("/") + "/exa.language_server_pb.LanguageServerService/RetrieveUserQuotaSummary"
    req = urllib.request.Request(url, data=b"{}", method="POST", headers={
        "Content-Type": "application/json", "x-codeium-csrf-token": token})
    try:
        body = json.loads(urllib.request.urlopen(req, timeout=3).read().decode("utf-8", "replace"))
    except Exception:
        return
    summary = body.get("quotaSummary") or body
    buckets = summary.get("quotaBuckets") or body.get("quotaBuckets") or []
    limits = []
    for b in buckets:
        try:
            frac = float(b.get("remainingFraction", 1.0))
        except (TypeError, ValueError):
            continue
        reset = b.get("resetTime")
        label = b.get("refreshWindowLabel") or b.get("quotaBucketName") or ""
        limits.append({"kind": "weekly_all" if "week" in str(label).lower() else "session",
                       "percent": round(max(0.0, min(1.0, 1 - frac)) * 100, 1), "resets_at": reset,
                       "name": b.get("quotaBucketName") or label})
    if limits:
        cs.write_json(QUOTA_FILE, {"limits": limits, "updated": time.time(), "raw_keys": sorted(summary.keys())[:20]})


def handle(ev, data):
    """Called by the hook: one Antigravity event → the session's state file."""
    try:
        ask_server_quota()
    except Exception:
        pass
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
    s["pid"] = os.getppid()
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
    """The quota the hook saved from the CLI's own server (fresh within a day), else a full bar
    while the CLI log reports the quota exhausted, else None."""
    try:
        q = json.load(open(QUOTA_FILE))
        if time.time() - q.get("updated", 0) < 24 * 3600 and q.get("limits"):
            limits = []
            for l in q["limits"]:
                reset = l.get("resets_at")
                if isinstance(reset, (int, float)):
                    reset = datetime.fromtimestamp(reset, timezone.utc).isoformat()
                limits.append({"kind": l["kind"], "percent": l["percent"], "resets_at": reset,
                               "scope": {"model": {"display_name": l.get("name")}} if l.get("name") else None})
            return {"limits": limits, "source": "agy", "updated": q["updated"]}
    except Exception:
        pass
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
