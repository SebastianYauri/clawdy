"""Claude Code hook: records what each session is doing so Clawdy can act it out.

Claude Code runs it on every event with a JSON object on stdin.
It never blocks and never fails: any problem is silently ignored.
"""
import json
import os
import sys
import time

from clawdy_system import SESSIONS

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
READ_TOOLS = {"Read", "Grep", "Glob", "WebFetch", "WebSearch", "LS"}


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
        s["ask"] = now
    new = state_for(ev, tool)
    if new:
        s["state"] = new
    s["ts"] = now
    if data.get("cwd"):
        s["cwd"] = str(data["cwd"])[:400]       # shown in the sessions list
    s["pid"] = os.getppid()                     # Claude Code (or its shell): to find its window

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
