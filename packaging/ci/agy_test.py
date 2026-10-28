"""CI: with a (fake) Antigravity CLI around, `--setup` must register Clawdy's hooks and status
line, the status line command must answer a payload with the quota, and `--uninstall` must
take both away again. Usage: agy_test.py <sessions dir> (HOME already points at the profile)."""
import json
import os
import platform
import subprocess
import sys
import time

HOME = os.path.expanduser("~")
HOOKS = os.path.join(HOME, ".gemini", "config", "hooks.json")
SETTINGS = os.path.join(HOME, ".gemini", "antigravity-cli", "settings.json")
PAYLOAD = {"cwd": HOME, "conversation_id": "ci-conv-1", "agent_state": "idle",
           "model": {"id": "gemini-3-pro", "display_name": "Gemini 3 Pro"},
           "context_window": {"used_percentage": 12.5, "context_window_size": 1048576},
           "quota": {"gemini-5h": {"remaining_fraction": 0.75, "reset_in_seconds": 1800},
                     "gemini-weekly": {"remaining_fraction": 0.9, "reset_time": "2099-01-01T00:00:00Z"},
                     "3p-5h": {"remaining_fraction": 0.2, "reset_in_seconds": 600},
                     "3p-weekly": {"remaining_fraction": 0.5, "reset_in_seconds": 90000}}}


def run(command, stdin):
    shell = ["cmd", "/c", command] if platform.system() == "Windows" else ["sh", "-c", command]
    return subprocess.run(shell, input=stdin, capture_output=True, text=True, timeout=20)


def main(quota_file):
    hooks = json.load(open(HOOKS, encoding="utf-8-sig"))
    assert "clawdy" in hooks and hooks["clawdy"]["Stop"], hooks
    settings = json.load(open(SETTINGS, encoding="utf-8-sig"))
    sl = settings["statusLine"]
    assert sl["type"] == "command" and sl["enabled"] and "--statusline-agy" in sl["command"], settings
    assert settings.get("colorScheme") == "keep me", settings       # the user's own keys survive

    t = time.time()
    r = run(sl["command"], json.dumps(PAYLOAD))
    took = time.time() - t
    print("status line (%.1fs): %r" % (took, r.stdout.strip()), r.stderr.strip()[-300:])
    assert r.returncode == 0, r.returncode
    assert took < 5, "agy kills status lines slower than 5 s"
    assert "Gemini 3 Pro" in r.stdout and "5h 25%" in r.stdout and "7d 10%" in r.stdout and "ctx 12%" in r.stdout, r.stdout
    q = json.load(open(quota_file))
    rows = sorted(tuple(x) for x in q["rows"])
    print("quota rows:", rows)
    assert len(rows) == 4 and ("session", "Claude/GPT", 80.0) in [r[:3] for r in rows], rows
    r = run(sl["command"], "")                              # nothing on stdin: still fine, still quick
    assert r.returncode == 0 and r.stdout.strip() == "Clawdy", (r.returncode, r.stdout)
    print("agy status line OK")


if __name__ == "__main__":
    main(sys.argv[1])
