"""Claude Code sessions for the click menu: the ones open right now (from the hook's
state files) and recent chats (from the transcripts Claude Code keeps in
~/.claude/projects), so they can be brought to the front, resumed or started."""
import json
import os
import time

import clawdy_system as cs

PROJECTS = os.path.join(cs.HOME, ".claude", "projects")


def _project(cwd):
    return os.path.basename(os.path.normpath(cwd)) if cwd else "~"


def open_sessions(now=None):
    """[{id, cwd, project, state, ts, pid}] for sessions whose Claude Code is still running."""
    now = now or time.time()
    out = []
    try:
        names = os.listdir(cs.SESSIONS)
    except OSError:
        return out
    for name in names:
        if not name.endswith(".json"):
            continue
        try:
            s = json.load(open(os.path.join(cs.SESSIONS, name)))
        except Exception:
            continue
        pid = s.get("pid")
        if pid and not cs.pid_alive(pid):
            continue
        if not pid and now - s.get("ts", 0) > 3600:
            continue
        out.append({"id": name[:-5], "cwd": s.get("cwd"), "project": _project(s.get("cwd")),
                    "state": s.get("state") or "idle", "ts": s.get("ts", 0), "pid": pid,
                    "started": s.get("started", 0), "done": s.get("done", 0),
                    "ask": s.get("ask", 0), "ask_kind": s.get("ask_kind")})
    urgent = {"notification": 0, "error": 1}
    out.sort(key=lambda x: (urgent.get(x["state"], 2), -x["ts"]))
    return out


def _title(path):
    """Custom title, AI title or the first prompt of a transcript, plus its working dir."""
    title = first = cwd = None
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i > 300 or (title and cwd):
                    break
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                t = d.get("type")
                if t == "custom-title" and d.get("customTitle"):
                    title = d["customTitle"]
                elif t == "ai-title" and d.get("aiTitle") and not title:
                    title = d["aiTitle"]
                elif t == "summary" and d.get("summary") and not title:
                    title = d["summary"]
                elif t == "user":
                    cwd = cwd or d.get("cwd")
                    if first is None:
                        c = (d.get("message") or {}).get("content")
                        if isinstance(c, list):
                            c = " ".join(p.get("text", "") for p in c if isinstance(p, dict))
                        if isinstance(c, str) and c.strip() and not c.lstrip().startswith("<"):
                            first = " ".join(c.split())
    except OSError:
        return None, None
    return (title or first), cwd


def recent_sessions(exclude=(), limit=6):
    """[{id, cwd, project, title, ts}] of the latest chats, newest first."""
    files = []
    try:
        for proj in os.listdir(PROJECTS):
            d = os.path.join(PROJECTS, proj)
            try:
                for name in os.listdir(d):
                    if name.endswith(".jsonl") and name[:-6] not in exclude:
                        p = os.path.join(d, name)
                        files.append((os.path.getmtime(p), p, name[:-6]))
            except OSError:
                continue
    except OSError:
        return []
    out = []
    for ts, path, sid in sorted(files, reverse=True):
        title, cwd = _title(path)
        if not title or not cwd:
            continue                         # empty or tool-only sessions
        out.append({"id": sid, "cwd": cwd, "project": _project(cwd), "title": title, "ts": ts})
        if len(out) >= limit:
            break
    return out


def recent_projects(sessions, opened, limit=3):
    seen, out = set(), []
    for s in list(opened) + list(sessions):
        if s.get("cwd") and s["cwd"] not in seen and os.path.isdir(s["cwd"]):
            seen.add(s["cwd"])
            out.append(s["cwd"])
        if len(out) >= limit:
            break
    return out


def _claude_in(cwd, args=""):
    path = cs.claude_code_path() or "claude"
    if cs.WIN:
        return "Set-Location -LiteralPath '%s'; & '%s' %s" % (cwd.replace("'", "''"), path, args)
    q = lambda s: "'%s'" % s.replace("'", "'\\''")
    return "cd %s && %s %s" % (q(cwd), q(path), args)


def resume(session):
    """Reopen a past chat in a new terminal."""
    return cs.open_terminal(_claude_in(session["cwd"], "--resume " + session["id"]))


def new_chat_in(cwd):
    return cs.open_terminal(_claude_in(cwd))
