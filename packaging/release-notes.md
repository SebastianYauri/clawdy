## Install with one command

- **Windows** (PowerShell): `irm https://raw.githubusercontent.com/SebastianYauri/clawdy/main/get.ps1 | iex`
- **macOS / Linux**: `curl -fsSL https://raw.githubusercontent.com/SebastianYauri/clawdy/main/get.sh | sh`
- **Scoop**: `scoop bucket add sebastianyauri https://github.com/SebastianYauri/scoop-bucket` then `scoop install clawdy`
- **Homebrew**: `brew install --cask sebastianyauri/tap/clawdy`

## Or download the installer

| Your computer | File | How to install |
|---|---|---|
| **Windows 10 / 11** | `Clawdy-Setup.exe` | Double-click it and follow the steps. |
| **Ubuntu, Debian, Mint** | `clawdy_…_all.deb` | Double-click it → **Install**. |
| **Mac (Apple silicon)** | `Clawdy-mac.dmg` | Open it and drag *Clawdy* into *Applications*. |

Clawdy reads your usage from [Claude Code](https://claude.com/claude-code); with only the Claude
desktop app, one click sets it up. Already have Clawdy? It updates itself.

**Edge blocks the download?** Press **Ctrl + J**, click **⋯** next to `Clawdy-Setup.exe` → **Keep**,
then **Show more** → **Keep anyway**. New apps aren't "commonly downloaded" yet.

**Windows says "Windows protected your PC"?** Click **More info** → **Run anyway**.
That's normal for apps without a paid signing certificate, and only happens once.

**macOS says "Apple could not verify Clawdy is free of malware"?** Click **Done**, then open
**System Settings → Privacy & Security**, scroll down and click **Open Anyway** (only the first
time). When asked about *Claude Code-credentials*, click **Always Allow**: it's your Claude Code
session, needed to read your usage.

See the [changelog](https://github.com/SebastianYauri/clawdy/blob/main/CHANGELOG.md) for what's new.
