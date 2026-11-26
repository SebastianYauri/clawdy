"""CI: `--setup` must register Clawdy's status line in Claude Code's settings (next to the
hooks), the command must answer a payload with model, context and plan use and keep the
session's numbers; after `--uninstall` the status line must be gone.
Usage: claude_sl_test.py <sessions dir>   |   claude_sl_test.py after"""
import json
import os
import platform
import subprocess
import sys
import time

SETTINGS = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
PAYLOAD = {"session_id": "ci-sl-1", "cwd": os.path.expanduser("~"), "version": "2.1.90",
           "model": {"id": "claude-opus-5-5", "display_name": "Opus 5.5"},
           "context_window": {"total_input_tokens": 156000, "context_window_size": 1000000,
                              "used_percentage": 16.4, "remaining_percentage": 83.6,
                              "current_usage": {"input_tokens": 1000, "cache_creation_input_tokens": 5000,
                                                "cache_read_input_tokens": 150000}},
           "cost": {"total_cost_usd": 1.2345, "total_duration_ms": 100, "total_lines_added": 12,
                    "total_lines_removed": 3},
           "rate_limits": {"five_hour": {"used_percentage": 32, "resets_at": 1800000000},
                           "seven_day": {"used_percentage": 37.4, "resets_at": 1800000000}}}


def run(command, stdin):
    if platform.system() == "Windows":
        shell = 'cmd /d /s /c "%s"' % command
    else:
        shell = ["sh", "-c", command]
    return subprocess.run(shell, input=stdin, capture_output=True, text=True, timeout=20)


def main(arg):
    settings = json.load(open(SETTINGS, encoding="utf-8-sig"))
    sl = settings.get("statusLine")
    if arg == "after":
        assert not sl, "status line left behind: %r" % (sl,)
        print("claude status line gone")
        return
    assert isinstance(sl, dict) and sl.get("type") == "command" and "--statusline-claude" in sl["command"], settings
    t = time.time()
    r = run(sl["command"], json.dumps(PAYLOAD))
    took = time.time() - t
    print("status line (%.1fs): %r" % (took, r.stdout.strip()), r.stderr.strip()[-300:])
    assert r.returncode == 0, r.returncode
    assert took < 5, "too slow for a status line"
    out = r.stdout
    assert "Opus 5.5" in out and "ctx 16%" in out and "5h 32%" in out and "7d 37%" in out, out
    s = json.load(open(os.path.join(arg, "ci-sl-1.json")))
    assert s["model"] == "Opus 5.5" and round(s["ctx"]) == 16 and s["lines"] == [12, 3] and s["cost"] == 1.234, s
    r = run(sl["command"], "")
    assert r.returncode == 0 and r.stdout.strip() == "Clawdy", (r.returncode, r.stdout)
    print("claude status line OK")


if __name__ == "__main__":
    main(sys.argv[1])
