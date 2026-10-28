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
ROWS = ["idle", "running-right", "running-left", "waving", "jumping", "failed", "waiting", "working", "review"]
FRAME_DT = 0.125                          # the pet plays at about 8 frames per second


def poses(w, cx, feet):
    """Eight designed keyframes per Codex row: (row name, [pose dicts])."""
    import math
    SH = 54
    H = lambda i: math.sin(math.pi * i / 8)          # 0 → 1 → 0 across the row

    def base(**kw):
        p = dict(dy=0.0, dx=0.0, sx=1.0, sy=1.0, rot=0.0, arm_l=0.0, arm_r=0.0, eye="open", eye_dx=0.0,
                 eye_dy=0.0, step=None, tuck=False, props=[], fx=[], part_fx={})
        p.update(kw)
        return p

    def run(d):
        out = []
        for i in range(8):
            bob = [0, 2, 4, 2, 0, 2, 4, 2][i]
            fx = []
            if i % 2 == 0:
                fx.append(("dust", cx - d * 36, feet - 3, 0.8))
            if i % 4 == 1:
                fx.append(("speed", cx - d * 44, feet - 28, 0.9))
            out.append(base(dy=-bob, rot=0.14 * d, step=i % 2, eye_dx=2.5 * d, eye_dy=0.5, arm_l=-2, arm_r=-2,
                            part_fx={"head": (-d * 2.5, 1.0, -d * 0.12)}, fx=fx))
        return out

    idle = [base(sy=1 + 0.025 * math.sin(2 * math.pi * i / 8), eye="closed" if i == 6 else "open",
                 eye_dx=[0, 0, -2, -2, 0, 2, 2, 0][i], arm_l=math.sin(i) * 0.5, arm_r=-math.sin(i) * 0.5) for i in range(8)]
    wave = [base(arm_r=-10 + 4 * math.sin(math.pi * i / 2), arm_l=1, eye="happy", eye_dx=1,
                 dy=-abs(math.sin(math.pi * i / 4)) * 1.5,
                 fx=([("heart", cx + 30, feet - 62 - (i - 2) * 5, 0.8)] if i >= 2 else [])
                    + ([("heart", cx + 44, feet - 50 - (i - 5) * 6, 0.6)] if i >= 5 else [])) for i in range(8)]
    jump = []
    for i in range(8):
        h = [0, .35, .75, 1, 1, .75, .35, 0][i]
        p = base(dy=-h * 40, tuck=h > 0.5, eye="happy" if h > 0.3 else "open",
                 sy=0.85 if i == 0 else (0.88 if i == 7 else (1.08 if i in (1, 2) else 1.0)),
                 sx=1.12 if i == 0 else (1.1 if i == 7 else (0.95 if i in (1, 2) else 1.0)),
                 arm_l=-9 if h > 0.3 else 0, arm_r=-9 if h > 0.3 else 0)
        if i in (3, 4):
            p["fx"] = [("star", cx - 30, feet - 76, 0.7), ("star", cx + 30, feet - 70, 0.7), ("spark", cx, feet - 84, 0.6)]
        if i == 7:
            p["fx"] = [("dust", cx - 30, feet - 2, 0.7), ("dust", cx + 30, feet - 2, 0.7)]
        jump.append(p)
    failed = [base(dx=[-2, 2, -2, 2, -1, 1, 0, 0][i], eye="x", sy=0.95, arm_l=-3, arm_r=-3, props=["err"],
                   fx=[("smoke", cx - 8, feet - SH - 16 - (i % 4) * 4, 0.7 + (i % 4) * 0.08),
                       ("smoke", cx + 10, feet - SH - 8 - ((i + 2) % 4) * 4, 0.55 + ((i + 2) % 4) * 0.08)]) for i in range(8)]
    waiting = [base(dy=-abs(math.sin(math.pi * i / 4)) * 6, eye="scared", arm_l=-8 + math.sin(i * 1.5) * 2,
                    arm_r=-8 - math.sin(i * 1.5) * 2, props=["bang"],
                    fx=[("sweat", cx + 24, feet - 46 + (i % 4) * 3, 0.7)]) for i in range(8)]
    working = [base(arm_l=-4 if i % 2 else 0, arm_r=0 if i % 2 else -4, eye_dy=2, props=["laptop"],
                    fx=[("code", cx + 28 - (i % 2) * 56, feet - 60 - i * 3, 0.55)] + ([("spark", cx + 34, feet - 40, 0.45)] if i == 5 else []))
               for i in range(8)]
    review = [base(rot=0.06 * math.sin(math.pi * i / 4), eye_dx=[-2, -2, -1, 0, 1, 2, 2, 0][i], arm_r=-5, arm_l=1,
                   props=["magnifier"], fx=([("spark", cx + 32, feet - 58, 0.5)] if i == 4 else [])) for i in range(8)]
    return [("idle", idle), ("running-right", run(1)), ("running-left", run(-1)), ("waving", wave),
            ("jumping", jump), ("failed", failed), ("waiting", waiting), ("working", working), ("review", review)]


def render(costume, bg, out_dir):
    """One pass: all frames on a flat background, saved as PNGs."""
    import time as _time
    clock = [1_000_000.0]
    _time.time = lambda: clock[0]
    _time.perf_counter = lambda: clock[0]
    import tkinter as tk
    from PIL import ImageGrab
    import clawdy_gui as g
    import clawdy_character as character

    g.tk = tk
    g.CARD = (0.0, 0.0, 0.0) if bg == "black" else (1.0, 1.0, 1.0)
    g.DEMO_STATES = [None]
    root = tk.Tk()
    root.withdraw()
    w = g.Widget(root, demo=True)
    w.draw = w.update_view = lambda *a: None          # the widget's own loop stays quiet
    w.set_costume(costume)
    w.ready, w.intro_t0 = True, None
    win = tk.Toplevel(root)
    win.overrideredirect(True)
    win.geometry("%dx%d+100+100" % (CELL_W, CELL_H))
    canvas = tk.Canvas(win, width=CELL_W, height=CELL_H, bg="black" if bg == "black" else "white",
                       highlightthickness=0, bd=0)
    canvas.pack()
    w.canvas = canvas
    win.update()
    skins = w.skins

    def fx(name, x, y, s):
        """A pixel-art effect sprite (assets/parts/fx), centered at (x, y) in scene units."""
        path = character.part_path("fx", name)
        xf = g.Xform(x, y + 15 * s, s, s)             # the 32×32 image is centered at sprite (0, -15)
        for rx, ry, rw, rh, col in skins.runs(path) or []:
            w.px_rect(xf, rx, ry, col, rw, rh)

    cx, feet = CELL_W / K / 2, 118
    n = 0
    for name, frames in poses(w, cx, feet):
        for i, p in enumerate(frames):
            clock[0] += FRAME_DT
            w.parts, w.part_fx = [], p["part_fx"]
            canvas.delete("all")
            bx = cx + p["dx"]
            xf = g.Xform(bx, feet + p["dy"] - g.SH / 2 * p["sy"], p["sx"], p["sy"], p["rot"])
            for fname, x, y, s in p["fx"]:
                if fname in ("dust", "smoke", "speed"):           # behind
                    fx(fname, x, y, s)
            w.draw_costume(xf, None, "back", 0.0, 0.6, p["eye"], p["eye_dx"])
            w.draw_sprite(xf, p["arm_l"], p["arm_r"], p["eye"], p["eye_dx"], p["eye_dy"], p["step"], p["tuck"])
            w.draw_costume(xf, None, "front", 0.0, 0.6, p["eye"], p["eye_dx"])
            w.pos, w.dir = 0.0, 1
            w.draw_props(p["props"], bx, feet + p["dy"], feet + p["dy"] - g.SH * p["sy"], clock[0] - 1_000_000.0, p["arm_r"])
            for fname, x, y, s in p["fx"]:
                if fname not in ("dust", "smoke", "speed"):       # in front
                    fx(fname, x, y, s)
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
