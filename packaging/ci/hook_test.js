// Runs our hook exactly like Claude Code would, from settings.json.
//   node hook_test.js <settings.json> <sessions dir>
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const [settingsPath, sessions] = process.argv.slice(2);
const settings = JSON.parse(fs.readFileSync(settingsPath, "utf8").replace(/^﻿/, ""));
const ours = (settings.hooks.PreToolUse || [])
  .flatMap((g) => g.hooks)
  .find((h) => /clawdy\.py|clawdy\.exe|clawdy\.app\//i.test(h.command + " " + (h.args || []).join(" ")));
if (!ours) { console.error("our hook was not found"); process.exit(1); }
console.log("hook:", JSON.stringify(ours));

const child = ours.args
  ? spawn(ours.command, ours.args, { stdio: ["pipe", "ignore", "inherit"], windowsHide: true })
  : spawn(ours.command, { shell: true, stdio: ["pipe", "ignore", "inherit"] });
child.stdin.end(JSON.stringify({ hook_event_name: "PreToolUse", session_id: "ci-node", tool_name: "Edit" }));

const timer = setTimeout(() => { console.error("the hook did not finish within 15 s"); process.exit(1); }, 15000);
child.on("exit", (code) => {
  clearTimeout(timer);
  const f = path.join(sessions, "ci-node.json");
  const state = fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, "utf8")).state : null;
  console.log("exit:", code, "| state written:", state);
  process.exit(code === 0 && state === "typing" ? 0 : 1);
});
