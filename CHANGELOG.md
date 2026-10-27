# Changelog

All notable changes to Clawdy are listed here. Versions follow
[Semantic Versioning](https://semver.org/).

## 1.3.0

- Works without Claude Code: with only the Claude desktop app, Clawdy keeps its
  animations, chat button and walks, with empty rings and a **Click to see your
  usage** prompt that installs Claude Code and signs you in, in a terminal you
  can see. When Claude Code is installed but signed out, the click just signs in.

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
