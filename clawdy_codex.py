"""OpenAI Codex CLI as a second source: usage and activity, from the session
files Codex already writes (~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl).

No network and no API key: every `token_count` event carries the plan's rate
limits (5-hour and weekly windows), and the rest of the events say what the
agent is doing. Nothing has to be configured in Codex.
"""
import glob
import json
import os
import time
from datetime import datetime, timezone

HOME = os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")
SESSIONS = os.path.join(HOME, "sessions")
TAIL = 256 * 1024                 # only the end of a session file is read
ACTIVE = 15 * 60                  # files touched this recently count as open sessions

_cache = {}                       # path -> (mtime, size, parsed)


def installed():
    return os.path.isdir(SESSIONS)


_listed = [0.0, []]


def _files(limit=40):
    """Newest session files first. Listing is cached for a few seconds: it's polled often."""
    now = time.time()
    if now - _listed[0] > 3:
        paths = glob.glob(os.path.join(SESSIONS, "*", "*", "*", "*.jsonl"))
        try:
            paths.sort(key=os.path.getmtime, reverse=True)
        except OSError:
            pass
        _listed[:] = [now, paths[:40]]
    return _listed[1][:limit]


def _ts(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _kind(name):
    """What a tool call looks like, in Clawdy's states."""
    n = (name or "").lower()
    if any(w in n for w in ("patch", "edit", "write", "create")):
        return "typing"
    if any(w in n for w in ("exec", "shell", "run", "command", "bash")):
        return "building"
    if any(w in n for w in ("read", "search", "find", "grep", "web", "view", "list", "fetch")):
        return "reading"
    return "thinking"


def _parse(path):
    """The useful marks of one session file (cached until it changes)."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    hit = _cache.get(path)
    if hit and hit[0] == st.st_mtime and hit[1] == st.st_size:
        return hit[2]
    out = {"limits": None, "limits_ts": 0, "state": None, "ts": 0, "started": 0, "done": 0,
           "ask": 0, "cwd": None, "id": os.path.basename(path)[:-6]}
    try:
        with open(path, "rb") as f:
            if st.st_size > TAIL:
                f.seek(st.st_size - TAIL)
                f.readline()                     # skip the cut line
            data = f.read().decode("utf-8", "replace")
    except OSError:
        return None
    for line in data.splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        t, p = d.get("type"), d.get("payload") or {}
        pt = p.get("type")
        ts = _ts(d.get("timestamp"))
        state = None
        if t == "turn_context" and p.get("cwd"):
            out["cwd"] = p["cwd"]
        elif t == "session_meta" and p.get("cwd") and not out["cwd"]:
            out["cwd"] = p["cwd"]
        elif t == "event_msg":
            if pt == "token_count" and p.get("rate_limits"):
                out["limits"], out["limits_ts"] = p["rate_limits"], ts
            elif pt == "task_started":
                out["started"], state = ts, "thinking"
            elif pt == "task_complete":
                out["done"], state = ts, "happy"
            elif pt and "approval" in pt:
                out["ask"], state = ts, "notification"
            elif pt in ("error", "stream_error"):
                state = "error"
        elif t == "response_item":
            if pt in ("function_call", "custom_tool_call", "local_shell_call"):
                state = _kind(p.get("name") or pt)
            elif pt == "reasoning":
                state = "thinking"
        if state:
            out["state"], out["ts"] = state, ts
    _cache[path] = (st.st_mtime, st.st_size, out)
    return out


def usage():
    """Usage in the same shape Clawdy gets from Claude, or None if Codex never reported any."""
    best = None
    for path in _files(12):
        s = _parse(path)
        if s and s["limits"] and (not best or s["limits_ts"] > best["limits_ts"]):
            best = s
            break                                # newest file with limits is enough
    if not best:
        return None
    rl, limits = best["limits"], []
    for key, kind in (("primary", "session"), ("secondary", "weekly_all")):
        w = rl.get(key) or {}
        if "used_percent" not in w:
            continue
        reset = w.get("resets_at")
        if reset is None and w.get("resets_in_seconds") is not None:
            reset = best["limits_ts"] + float(w["resets_in_seconds"])
        iso = datetime.fromtimestamp(float(reset), timezone.utc).isoformat() if reset else None
        if (w.get("window_minutes") or 0) > 1440:
            kind = "weekly_all"
        limits.append({"kind": kind, "percent": float(w["used_percent"]), "resets_at": iso})
    return {"limits": limits, "source": "codex", "plan": rl.get("plan_type"),
            "updated": best["limits_ts"]} if limits else None


def sessions(now=None):
    """{id: {...}} for Codex sessions active in the last minutes, in the hook's format."""
    now = now or time.time()
    out = {}
    for path in _files(8):
        try:
            if now - os.path.getmtime(path) > ACTIVE:
                break
        except OSError:
            continue
        s = _parse(path)
        if s:
            out["codex-" + s["id"]] = {"state": s["state"], "ts": s["ts"], "started": s["started"],
                                       "done": s["done"], "took": max(0, s["done"] - s["started"]),
                                       "ask": s["ask"], "ask_kind": "permission" if s["ask"] else None,
                                       "cwd": s["cwd"]}
    return out
