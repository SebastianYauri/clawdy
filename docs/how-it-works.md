# How Clawdy works

## Usage data

Clawdy shows the same numbers as `/usage` in Claude Code. It asks Anthropic's
usage endpoint (`GET https://api.anthropic.com/api/oauth/usage`) with the OAuth
session that Claude Code already keeps on your computer:

| System | Where the session is read from |
|---|---|
| Windows, Linux | `~/.claude/.credentials.json` |
| macOS | the login Keychain, item *Claude Code-credentials* |

This is your Claude subscription session, **not an API key**, so checking your
usage is free and doesn't count against your plan. Clawdy never writes or
refreshes the token; if it expires, open Claude Code once and it renews it.

Clawdy asks at most once every 5 minutes and caches the answer on disk, so
restarting the widget doesn't trigger another request. Right after start-up or waking from sleep it
refreshes immediately. If Claude Code's session has expired, Clawdy waits
without making a request and refreshes the moment Claude Code renews it; if the
network isn't up yet, it retries after 5, 10, 20… seconds. Cached limits whose
reset time has passed are shown as 0 %. If the endpoint answers
`429 Too Many Requests`, Clawdy waits as long as the server asks (5 minutes at
least) and remembers that across restarts.

Every account gets whatever limits it has: usually the 5-hour session and the
weekly limit, sometimes a per-model weekly limit (for example Opus), and the
monthly spend when paid extra usage is enabled. The rings show up to three; the
panel shows up to four.

## Reacting to Claude Code

When you allow *React to Claude Code*, Clawdy adds an asynchronous
[hook](https://docs.claude.com/en/docs/claude-code/hooks) to
`~/.claude/settings.json` for these events:

`UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `Stop`,
`StopFailure`, `SubagentStart`, `SubagentStop`, `Notification`,
`PermissionRequest`, `PreCompact`, `PostCompact`, `SessionStart`, `SessionEnd`.

The hook (`clawdy --hook`) reads the event from stdin, writes a tiny JSON state
file per session into Clawdy's cache folder and exits. It never blocks Claude
Code, never prints anything, and ignores every error. The widget reads those
files a few times per second and picks the most relevant state across all your
open sessions:

| Claude Code is… | Clawdy… |
|---|---|
| thinking about your prompt | shows a thought bubble, lights up an *aha!* bulb or paces around |
| editing or writing files | types on a laptop, takes coffee breaks or goes turbo with the keyboard on fire |
| running shell commands | hammers or watches a terminal scroll by |
| reading, searching, fetching | reads a book or inspects it with a magnifying glass |
| running one subagent / several | grooves with headphones / juggles |
| waiting for you (permission, notification) | raises an alert |
| hitting an error | gets X eyes and a puff of smoke |
| compacting context | sweeps |
| done | throws confetti, dances or sets off fireworks |

States with several animations rotate every few seconds while Claude Code stays
in that state. After 15 minutes without any Claude Code activity, Clawdy naps.

Hooks that belong to other tools are never touched: Clawdy only adds or removes
entries that point at its own program, and keeps a backup of the previous file
in `~/.claude/settings.json.clawdy-backup`. On Linux and macOS the hook command
checks that Clawdy still exists before running it, so removing the app without
disconnecting first leaves a harmless no-op.

## Files it touches

| What | Windows | macOS | Linux |
|---|---|---|---|
| Settings (size, costume…) | `%APPDATA%\clawdy\config.json` | `~/Library/Application Support/clawdy/config.json` | `~/.config/clawdy/config.json` |
| Cache (usage, session states, logs) | `%LOCALAPPDATA%\clawdy\` | `~/Library/Caches/clawdy/` | `~/.cache/clawdy/` |
| Open at login | `HKCU\…\CurrentVersion\Run` → `Clawdy` | `~/Library/LaunchAgents/com.clawdy.app.plist` | `~/.config/autostart/clawdy.desktop` |
| Claude Code hooks | `~/.claude/settings.json` | same | same |

`clawdy --uninstall` (run automatically by the Windows uninstaller) removes the
hooks, the login item and both folders.

## Network

Clawdy talks to exactly two places:

1. `api.anthropic.com`, for your usage, as described above.
2. `api.github.com` / `github.com`, to look for a newer release of Clawdy and
   download it.

There is no telemetry, analytics or server of its own.

## Updates

On start-up and every 6 hours Clawdy asks GitHub for the latest release. When
there is a newer one:

| Installed with | What happens |
|---|---|
| Windows installer | Downloads `Clawdy-Setup.exe` and runs it silently; the installer closes Clawdy, updates it and reopens it. |
| macOS app | Downloads `Clawdy-mac.zip`, swaps the app bundle and reopens it. |
| `.deb` package | Shows *click to update*; clicking downloads the package and installs it through the system password prompt (`pkexec`). |
| `install.py` | Downloads the new source files for that release and restarts. |
| a git checkout | Never touches your working tree; it only shows that an update exists. |

If an update fails, the same version isn't retried for 24 hours, and the
details are written to `update.log` in the cache folder.

## Windows on screen

The widget is two borderless windows: a fixed column with Clawdy and the rings,
and a panel that slides out from behind it. Compositors (especially GNOME on
Wayland) handle moving and fading windows smoothly, but flicker when a window
is resized or reshaped every frame, so the panel never changes size. Rounded
corners come from a color key on Windows, real transparency on macOS and the X
SHAPE extension on Linux.

Tk doesn't antialias arcs, so the rings and the **+** button are rasterized
pixel by pixel into images, and only redrawn when their values change.
Everything else that doesn't animate is cached in a static layer; at 30 fps the
widget stays at a few percent of one CPU core.

Set `CLAWDY_DEBUG=1` to write a `debug.log` with window and hover events to the
cache folder, and `CLAWDY_LANG=en` or `CLAWDY_LANG=es` to force a language.
