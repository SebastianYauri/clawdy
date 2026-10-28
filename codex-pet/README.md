# Clawdy as a Codex Pet

[Clawdy](https://github.com/SebastianYauri/clawdy) also lives inside OpenAI's Codex: these folders are
[Codex Pets](https://developers.openai.com/codex) rendered straight from Clawdy's animations, one per costume.

| Folder | Pet |
|---|---|
| `clawdy` | Clawdy |
| `clawdy-witch` · `clawdy-pumpkin` · `clawdy-ghost` · `clawdy-vampire` · `clawdy-frank` · `clawdy-santa` | Clawdy in its classic costumes |
| `clawdy-cowboy` · `clawdy-chef` · `clawdy-pirate` · `clawdy-astronaut` · `clawdy-ninja` | …and the new ones |

## Install

- **From Clawdy:** right-click → **Settings… → Install as a Codex pet** copies `clawdy` into Codex's pets folder.
- **By hand:** copy a folder to `~/.codex/pets/` (Windows: `%USERPROFILE%\.codex\pets\`), then in the Codex app
  or CLI type `/pet` and pick it. The CLI shows pets in iTerm2, Kitty and other terminals with Sixel graphics.

Each pet is a `pet.json` plus a `spritesheet.webp` (8 columns × 9 rows of 192 × 208 px: idle, running right and
left, waving, jumping, failed, waiting, working and review). `packaging/make_codex_pet.py` regenerates them.

Fan art inspired by Clawd, the Claude Code mascot; not affiliated with Anthropic or OpenAI. MIT license.
