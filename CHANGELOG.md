# Changelog

All notable changes to Clawdy are listed here. Versions follow
[Semantic Versioning](https://semver.org/).

## 1.4.1

- **"Claude finished" / "Claude needs you" notifications.** When a Claude Code
  task that took 5 minutes or more finishes (choose 30 s, 1, 2 or 5 min in the
  menu), or Claude stops to wait for your
  permission or reply, you get a notification with the project name, an 8-bit
  sound and a line under Clawdy (**Done!** / **Needs you!**). Turn it off with
  **Notify when Claude finishes**.
- **Share my usage.** A new menu item (also in the tray) saves a pixel-art card
  with Clawdy and your limits to your Pictures folder, shows it in your file
  manager and opens a new post on X with the text filled in.
- The tray / menu bar icon has a **Settings** submenu with every option of the
  right-click menu: switches, notify threshold, size and costume.
- **Install with one command:** `irm …/get.ps1 | iex` on Windows,
  `curl -fsSL …/get.sh | sh` on macOS and Linux, plus a
  [Scoop bucket](https://github.com/SebastianYauri/scoop-bucket) and a
  [Homebrew tap](https://github.com/SebastianYauri/homebrew-tap). Copies
  installed with Scoop leave updates to `scoop update clawdy`.

## 1.4.0

- Alerts near your limits: when any limit crosses 80 % or 95 %, Clawdy raises
  the alarm and you get a system notification, once per reset window. Turn it
  off from the right-click menu.
- 8-bit alert sound (bip-bip-biiip) with the alerts; mute it with **Sounds**
  in the menu.
- During an alert the bottom line reads, for example, **5h at 82%!** in red.

## 1.3.1

- Windows build goes back to PyInstaller's stock bootloader. The self-compiled
  one in 1.3.0 made Microsoft Defender's machine-learning engine flag the
  installer as a false positive, so 1.3.0 was pulled back to a pre-release.
- New releases are published as pre-releases first and promoted after a
  VirusTotal check.

## 1.3.0

- Works without Claude Code: with only the Claude desktop app, Clawdy keeps its
  animations, chat button and walks, with empty rings and a **Click to see your
  usage** prompt. One click (and one confirmation) installs Claude Code in the
  background and opens the browser: just click Authorize, no terminal or
  commands. When Claude Code is installed but signed out, the click just signs in.
- The welcome screen offers to connect your usage right away when Claude Code
  isn't set up, so the only step left is clicking Authorize in the browser.
- Installing from source on Linux now adds Clawdy to the applications menu, so
  you can find and reopen it after quitting.
- New app icon: a crisp, pixel-perfect Clawdy at every size.
- Click Clawdy for your Claude Code chats: bring an open one to the front,
  resume a recent one in a terminal, or start a new chat in a recent project.

## 1.2.0

- Desktop walks: while you're using Claude Code or the Claude app, now and
  then Clawdy goes for a walk on the taskbar (Windows) or hangs from the top of
  the screen (Linux, macOS) and climbs back home on a rope. Toggle it from the
  right-click menu; `clawdy --walk` sends it out right away.

## 1.1.0

- More animations while you code: each Claude Code state now rotates through
  several of them. Thinking lights an *aha!* bulb or paces around, writing takes
  coffee breaks or goes turbo with the keyboard on fire, commands show a
  scrolling terminal, reading uses a magnifying glass, and finishing a task
  brings a victory dance or fireworks.
- Clawdy takes a nap after 15 minutes without Claude Code activity.
- Usage is up to date right after you turn on your computer: Clawdy no longer
  spends a request on an expired session (it waits for Claude Code to renew it
  and refreshes the moment it does), retries within seconds when the network
  isn't up yet, and refreshes as soon as the computer wakes from sleep.
- Limits that already reset show 0 % instead of yesterday's numbers.
- Tray icon (menu bar on macOS) to show or hide Clawdy, open a new chat,
  refresh, change settings and quit. Hidden, Clawdy keeps running in the
  background.
- New intro: until fresh usage arrives the widget stays empty with a quiet
  loading pulse. Then Clawdy walks in carrying a beach ball, throws it on the
  floor and the rings fill up from 0 as the numbers count up.

## 1.0.0

First public release.

- Compact widget with three antialiased usage rings around an animated Clawdy.
- Side panel that slides out on hover with every limit and its reset time.
- **+** button that opens a new chat in the Claude app, or on claude.ai.
- Live reactions to Claude Code through hooks: thinking, writing, commands,
  reading, subagents, compacting, waiting for you, errors and done.
- Costumes with their own animations and props: witch, pumpkin, ghost, vampire
  and Santa, plus *Auto* by date.
- Custom dark right-click menu: size, costume, pinned panel, hooks, start at login.
- Welcome screen that asks before changing anything.
- Installers for Windows, Ubuntu/Debian and macOS, with automatic updates.
- English and Spanish interface, following the system language.
