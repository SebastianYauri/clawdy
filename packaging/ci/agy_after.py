"""CI, after `--uninstall`: Clawdy's Antigravity hooks and status line are gone, the rest stays."""
import json
import os

HOME = os.path.expanduser("~")
hooks = json.load(open(os.path.join(HOME, ".gemini", "config", "hooks.json"), encoding="utf-8-sig"))
assert "clawdy" not in hooks, hooks
settings = json.load(open(os.path.join(HOME, ".gemini", "antigravity-cli", "settings.json"), encoding="utf-8-sig"))
assert "statusLine" not in settings and settings.get("colorScheme") == "keep me", settings
print("agy disconnected; settings intact")
