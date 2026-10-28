#!/usr/bin/env python3
"""Renders Clawdy as a Codex Pet: the spritesheet OpenAI's Codex app and CLI load
from ~/.codex/pets/<id>/ (8 columns × 9 rows of 192×208 px, one row per state).

Frames come straight from Clawdy's own drawing code, so the pet moves exactly
like the widget. Run it under a virtual display:

    xvfb-run -a python3 packaging/make_codex_pet.py [costume] [out dir]

Transparency: every frame is drawn twice, on black and on white, and the
alpha is recovered from the difference (Tk canvases have no alpha).
"""
import json
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

CELL_W, CELL_H, COLS = 192, 208, 8
K = 1.5                                   # scene units → sheet pixels: one Clawdy pixel = 9 px
# Codex's v1 rows, in order, as Clawdy states: (work state or None, forced act, walking direction)
ROWS = [("idle", None, "look", 1), ("running-right", None, "walk", 1), ("running-left", None, "walk", -1),
        ("waving", None, "wave", 1), ("jumping", None, "jump", 1), ("failed", "error", None, 1),
        ("waiting", "notification", None, 1), ("working", "typing", None, 1), ("review", "reading", None, 1)]
FRAME_DT = 0.125                          # the pet plays at about 8 frames per second


def render(costume, bg, out_dir):
    """One pass: all frames on a flat background, saved as PNGs."""
    import time as _time
    clock = [1_000_000.0]
    _time.time = lambda: clock[0]
    _time.perf_counter = lambda: clock[0]
    import tkinter as tk
    from PIL import ImageGrab
    import clawdy_gui as g

    g.tk = tk
    g.CARD = (0.0, 0.0, 0.0) if bg == "black" else (1.0, 1.0, 1.0)
    g.DEMO_STATES = [None]
    g.HOP = 1.0                                       # room to jump: no rings around it here
    root = tk.Tk()
    root.withdraw()
    w = g.Widget(root, demo=True)
    w.draw = w.update_view = lambda *a: None          # the widget's own loop stays quiet
    w.set_costume(costume)
    w.ready, w.intro_t0 = True, None
    for lim in w.st.data["limits"]:
        lim["percent"] = 12                           # calm pace: energy ≈ 1
    win = tk.Toplevel(root)
    win.overrideredirect(True)
    win.geometry("%dx%d+100+100" % (CELL_W, CELL_H))
    canvas = tk.Canvas(win, width=CELL_W, height=CELL_H, bg="black" if bg == "black" else "white",
                       highlightthickness=0, bd=0)
    canvas.pack()
    w.canvas = canvas
    win.update()

    n = 0
    for row, (name, work, act, direction) in enumerate(ROWS):
        g.DEMO_STATES = [work]
        w.work, w._work_prev, w._work_t, w._work_seed = None, None, 0.0, 1 if name == "review" else 0
        w.parts, w.emit, w.hammer = [], 0.0, 0.0
        w.dir, w.pos = direction, 0.0
        w.force, w.act_t = act, 0.0
        clock[0] += 10                                # a fresh moment for every row
        w._last = clock[0]
        random.seed(row)
        for f in range(COLS):
            clock[0] += FRAME_DT
            if act:
                w.force = act
                w.act_t = f / COLS * 3.6              # one full cycle of the act across the row
            w.pos = 0.0                               # Codex moves the pet; the sprite stays centered
            canvas.delete("all")
            w.draw_clawd(CELL_W / K / 2, 118, 12)
            canvas.scale("all", 0, 0, K, K)
            win.update()
            x, y = win.winfo_rootx(), win.winfo_rooty()
            img = ImageGrab.grab(bbox=(x, y, x + CELL_W, y + CELL_H), xdisplay=os.environ.get("DISPLAY"))
            img.save(os.path.join(out_dir, "%s_%02d.png" % (bg, n)))
            n += 1
    root.destroy()


def compose(costume, work_dir, out_dir):
    from PIL import Image
    sheet = Image.new("RGBA", (CELL_W * COLS, CELL_H * len(ROWS)), (0, 0, 0, 0))
    n = 0
    for row in range(len(ROWS)):
        for col in range(COLS):
            b = Image.open(os.path.join(work_dir, "black_%02d.png" % n)).convert("RGB")
            wht = Image.open(os.path.join(work_dir, "white_%02d.png" % n)).convert("RGB")
            cell = Image.new("RGBA", (CELL_W, CELL_H))
            bp, wp, cp = b.load(), wht.load(), cell.load()
            for y in range(CELL_H):
                for x in range(CELL_W):
                    br, bg_, bb = bp[x, y]
                    wr, wg, wb = wp[x, y]
                    a = 255 - round(((wr - br) + (wg - bg_) + (wb - bb)) / 3)
                    a = max(0, min(255, a))
                    if a == 0:
                        continue
                    cp[x, y] = (min(255, round(br * 255 / a)), min(255, round(bg_ * 255 / a)),
                                min(255, round(bb * 255 / a)), a)
            sheet.paste(cell, (col * CELL_W, row * CELL_H))
            n += 1
    pet_id = "clawdy" if costume == "none" else "clawdy-" + costume
    pet_dir = os.path.join(out_dir, pet_id)
    os.makedirs(pet_dir, exist_ok=True)
    sheet.save(os.path.join(pet_dir, "spritesheet.webp"), lossless=True)
    sheet.crop((0, 0, CELL_W, CELL_H)).save(os.path.join(pet_dir, "preview.png"))
    names = {"none": "Clawdy", "witch": "Clawdy (witch)", "santa": "Clawdy (Santa)", "frank": "Clawdy (Frankenstein)",
             "vampire": "Clawdy (vampire)", "ghost": "Clawdy (ghost)", "pumpkin": "Clawdy (pumpkin)"}
    meta = {"id": pet_id, "displayName": names.get(costume, "Clawdy"),
            "description": "Clawdy, the pixel buddy that shows your Claude and Codex usage "
                           "(github.com/SebastianYauri/clawdy). It thinks, types, hammers away at commands, "
                           "reads with a magnifying glass and throws confetti when the job is done.",
            "spriteVersionNumber": 1, "spritesheetPath": "spritesheet.webp", "kind": "animal"}
    with open(os.path.join(pet_dir, "pet.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(os.path.join(pet_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write("# %s · a Codex Pet\n\nClawdy is a free, open-source desktop buddy that shows how much of your "
                "Claude or Codex plan you've used and acts out what the agent is doing: "
                "https://github.com/SebastianYauri/clawdy\n\n"
                "## Install\n\nCopy this folder to `~/.codex/pets/%s/` (Windows: `%%USERPROFILE%%\\.codex\\pets\\%s\\`), "
                "then in Codex type `/pet` and pick **%s**.\n\nMIT license. Fan art inspired by Clawd, "
                "the Claude Code mascot; not affiliated with Anthropic or OpenAI.\n" % (meta["displayName"], pet_id, pet_id, meta["displayName"]))
    return pet_dir


def main():
    costume = sys.argv[1] if len(sys.argv) > 1 else "none"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "codex-pet")
    if len(sys.argv) > 3 and sys.argv[3] in ("black", "white"):      # a render pass, in its own process
        render(costume, sys.argv[3], out_dir)
        return
    import tempfile
    work = tempfile.mkdtemp(prefix="clawdy-pet-")
    env = dict(os.environ, CLAWDY_NO_TRAY="1", CLAWDY_LANG="en",
               XDG_CONFIG_HOME=os.path.join(work, "cfg"), XDG_CACHE_HOME=os.path.join(work, "cache"))
    for bg in ("black", "white"):
        subprocess.run([sys.executable, os.path.abspath(__file__), costume, work, bg], check=True, env=env)
    print(compose(costume, work, out_dir))


if __name__ == "__main__":
    main()
