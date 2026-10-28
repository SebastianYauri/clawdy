"""Clawdy as an MCP server for Google's Antigravity CLI: the only way in.

Antigravity keeps the token of its local server for its own child processes,
and MCP servers are such children (hooks are not). Register this with
`agy mcp add clawdy <clawdy> --agy-mcp`: it offers no tools at all; it just
asks the server for the quota summary once a minute and saves the numbers
(never the token) where Clawdy reads them. It runs only while agy runs.
"""
import json
import os
import sys
import threading
import time

import clawdy_agy as agy

EVERY = float(os.environ.get("CLAWDY_AGY_EVERY", "60"))


def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def poll():
    endpoints = agy.endpoints_from_env()
    status = {"token": bool(os.environ.get("ANTIGRAVITY_CSRF_TOKEN")),
              "vars": sorted(k for k in os.environ if k.startswith("ANTIGRAVITY_")),
              "endpoints": [(s, h, p) for s, h, p, _ in endpoints], "ok": None, "error": None}
    while True:
        for endpoint in endpoints:
            try:
                rows = agy.refresh_quota(endpoint)
                status["ok"], status["error"], status["rows"] = time.time(), None, len(rows)
                break
            except Exception as e:
                status["error"] = "%s %s: %s" % (endpoint[0], endpoint[2], str(e)[:100])
        try:
            import clawdy_system as cs
            cs.write_json(agy.STATUS_FILE, status)          # names and outcomes only: never the token
        except Exception:
            pass
        time.sleep(EVERY)


def main():
    threading.Thread(target=poll, daemon=True).start()
    for line in sys.stdin:                                  # the MCP handshake, politely answered
        try:
            m = json.loads(line)
        except ValueError:
            continue
        mid, method = m.get("id"), m.get("method", "")
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": (m.get("params") or {}).get("protocolVersion", "2024-11-05"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "clawdy", "version": "1"}}})
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": mid, "result": {"tools": []}})
        elif method in ("resources/list", "prompts/list"):
            send({"jsonrpc": "2.0", "id": mid, "result": {method.split("/")[0]: []}})
        elif mid is not None:
            send({"jsonrpc": "2.0", "id": mid, "result": {}})
    return 0


if __name__ == "__main__":
    sys.exit(main())
