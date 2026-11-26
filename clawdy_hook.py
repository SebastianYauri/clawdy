"""Claude Code hook: records what each session is doing so Clawdy can act it out.

Claude Code runs it on every event with a JSON object on stdin.
It never blocks and never fails: any problem is silently ignored.
"""
import json
import os
import sys
import time

import clawdy_system as cs

SESSIONS = cs.SESSIONS

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
READ_TOOLS = {"Read", "Grep", "Glob", "WebFetch", "WebSearch", "LS"}


RATE_FILE = os.path.join(os.path.dirname(cs.USAGE_CACHE), "claude-rate.json")


def statusline(payload):
    """Claude Code's status line: keep the session's model, context use and cost next to the
    hook's state (same file, keyed by session_id) and answer with one short line for the bar."""
    if not isinstance(payload, dict):
        payload = {}
    sid = str(payload.get("session_id") or "")
    model = (payload.get("model") or {}).get("display_name") if isinstance(payload.get("model"), dict) else None
    cw = payload.get("context_window") if isinstance(payload.get("context_window"), dict) else {}
    ctx = cw.get("used_percentage")
    if ctx is None and isinstance(cw.get("current_usage"), dict) and cw.get("context_window_size"):
        u = cw["current_usage"]
        used = sum(u.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
        ctx = 100.0 * used / cw["context_window_size"]
    cost = payload.get("cost") if isinstance(payload.get("cost"), dict) else {}
    now = time.time()
    if sid and sid.replace("-", "").isalnum():
        path = os.path.join(SESSIONS, sid + ".json")
        try:
            s = json.load(open(path))
        except Exception:
            s = {}
        if model:
            s["model"] = str(model)[:40]
        if ctx is not None:
            s["ctx"] = round(float(ctx), 1)
        if cost.get("total_cost_usd") is not None:
            s["cost"] = round(float(cost["total_cost_usd"]), 3)
        s["lines"] = [int(cost.get("total_lines_added") or 0), int(cost.get("total_lines_removed") or 0)]
        if payload.get("cwd"):
            s["cwd"] = str(payload["cwd"])[:400]
        s["ts_sl"] = now
        os.makedirs(SESSIONS, exist_ok=True)
        tmp = "%s.%d.tmp" % (path, os.getpid())
        with open(tmp, "w") as f:
            json.dump(s, f)
        os.replace(tmp, path)
    rl = payload.get("rate_limits") if isinstance(payload.get("rate_limits"), dict) else None
    if rl:
        try:
            with open(RATE_FILE, "w") as f:
                json.dump({"ts": now, "rate_limits": rl}, f)
        except OSError:
            pass
    return statusline_text(model, ctx, rl)


def statusline_text(model, ctx, rl):
    """`Clawdy · Opus 5.5 · ctx 16% · 5h 32% · 7d 37%` (the plan from the payload, else cached)."""
    parts = ["Clawdy"]
    if model:
        parts.append(str(model))
    if ctx is not None:
        parts.append("ctx %d%%" % round(float(ctx)))
    plan = []
    if rl:
        for key, label in (("five_hour", "5h"), ("seven_day", "7d")):
            w = rl.get(key)
            if isinstance(w, dict) and w.get("used_percentage") is not None:
                plan.append("%s %d%%" % (label, round(float(w["used_percentage"]))))
    if not plan:
        try:
            data = json.load(open(cs.USAGE_CACHE)).get("data") or {}
            for lim in data.get("limits") or []:
                label = {"session": "5h", "weekly_all": "7d"}.get(lim.get("kind"))
                if label and lim.get("percent") is not None:
                    plan.append("%s %d%%" % (label, round(float(lim["percent"]))))
        except Exception:
            pass
    return " · ".join(parts + plan)


def ask_text(data, kind):
    """A few words on what Claude is waiting for: the tool and its target for a permission,
    else the notification's message."""
    tool = str(data.get("tool_name") or "")
    inp = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    if tool:
        target = inp.get("command") or inp.get("file_path") or inp.get("path") or inp.get("url") or inp.get("pattern") or ""
        target = " ".join(str(target).split())
        if target:
            target = target[:52] + ("…" if len(target) > 52 else "")
        return ("%s %s" % (tool, target)).strip()[:80]
    msg = str(data.get("message") or "").strip()
    if msg.lower().startswith("claude "):
        msg = msg[7:]
    return msg[:80]


def state_for(ev, tool):
    if ev == "UserPromptSubmit":
        return "thinking"
    if ev == "PreToolUse":
        if tool in EDIT_TOOLS:
            return "typing"
        if tool in ("Bash", "PowerShell"):
            return "building"
        if tool in READ_TOOLS:
            return "reading"
        return "typing"
    if ev in ("PostToolUse", "SubagentStop"):
        return "thinking"
    if ev in ("PostToolUseFailure", "StopFailure"):
        return "error"
    if ev in ("Notification", "PermissionRequest"):
        return "notification"
    if ev == "PreCompact":
        return "sweeping"
    if ev in ("Stop", "PostCompact"):
        return "happy"
    if ev == "SessionStart":
        return "idle"
    return None


def read_stdin():
    """All of stdin. In a windowed .exe sys.stdin may be None."""
    try:
        if sys.stdin is not None:
            return sys.stdin.buffer.read()
    except Exception:
        pass
    chunks = []
    try:
        while True:
            b = os.read(0, 65536)
            if not b:
                break
            chunks.append(b)
    except OSError:
        pass
    return b"".join(chunks)


def handle(data):
    ev = data.get("hook_event_name", "")
    sid = "".join(c for c in str(data.get("session_id", "x")) if c.isalnum() or c in "-_")[:80]
    tool = data.get("tool_name", "")
    os.makedirs(SESSIONS, exist_ok=True)
    path = os.path.join(SESSIONS, (sid or "x") + ".json")

    if ev == "SessionEnd":
        try:
            os.remove(path)
        except OSError:
            pass
        return

    try:
        s = json.load(open(path))
    except Exception:
        s = {"subagents": 0}
    if ev == "SubagentStart":
        s["subagents"] = s.get("subagents", 0) + 1
    elif ev == "SubagentStop":
        s["subagents"] = max(0, s.get("subagents", 0) - 1)
    elif ev in ("Stop", "UserPromptSubmit", "SessionStart"):
        s["subagents"] = 0
    now = time.time()
    if ev == "UserPromptSubmit":
        s["started"] = now
    elif ev == "Stop":                          # a task finished: Clawdy may announce it
        s["done"] = now
        s["took"] = round(now - s.get("started", now))
    elif ev in ("Notification", "PermissionRequest"):   # Claude is waiting for you
        text = " ".join(str(data.get(k) or "") for k in ("message", "notification_type")).lower()
        kind = "permission" if ev == "PermissionRequest" or "permission" in text else "waiting"
        if not (kind == "waiting" and s.get("ask_kind") == "permission" and now - s.get("ask", 0) < 10):
            s["ask_kind"] = kind                # both events can come for one request
            s["ask_text"] = ask_text(data, kind)   # what it wants, for the sessions list
        s["ask"] = now
    new = state_for(ev, tool)
    if ev == "Notification" and s.get("ask_kind") == "waiting" and s.get("done", 0) >= s.get("started", 0):
        new = None                              # "waiting for your input" after it finished: not urgent
    if new:
        s["state"] = new
    s["ts"] = now
    if data.get("cwd"):
        s["cwd"] = str(data["cwd"])[:400]       # shown in the sessions list
    s.update(cs.session_anchor())               # Claude Code's pid, tty and terminal: to find its window

    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w") as f:
        json.dump(s, f)
    os.replace(tmp, path)


def main():
    try:
        handle(json.loads(read_stdin().decode("utf-8", "replace")))
    except Exception:
        pass


if __name__ == "__main__":
    main()
