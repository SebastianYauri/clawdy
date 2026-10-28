"""The character creator: a dark window in Clawdy's style with a live preview,
a row of colors, a row of parts per slot, the user's own skins and presets.
Every click applies at once to the widget and is remembered."""
import math
import os
import shutil
import time

import clawdy_character as character
from clawdy_i18n import t as tr

MW, PAD = 400, 12
TILE, GAP = 34, 37
PREVIEW_H = 104


class Creator:
    def __init__(self, w, x_root, y_root):
        import tkinter as tk
        from clawdy_gui import CARD, ORANGE, DIM, TXT, hx, round_rect
        self.tk, self.hx, self.round_rect = tk, hx, round_rect
        self.CARD, self.ORANGE, self.DIM, self.TXT = CARD, ORANGE, DIM, TXT
        self.w, self.k = w, w.k
        self.closed, self.hover, self.hits = False, None, []
        self.flash_text, self.flash_until = "", 0.0
        self.win = tk.Toplevel(w.root)
        self.h = self.layout_height()
        pw, ph = round(MW * self.k), round(self.h * self.k)
        self.canvas = w.make_window(self.win, pw, ph)
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        x = max(4, min(x_root, sw - pw - 4))
        y = max(4, min(y_root, sh - ph - 4))
        self.win.geometry("+%d+%d" % (x, y))
        self.win.update_idletasks()
        w.round_corners(self.win, pw, ph, radius=14)
        c = self.canvas
        c.bind("<Motion>", self.on_motion)
        c.bind("<Enter>", self.on_motion)
        c.bind("<Leave>", lambda e: self.set_hover(None))
        c.bind("<Button-1>", self.on_click)
        self.win.bind("<Escape>", lambda e: self.close())
        self.draw()
        try:
            self.win.focus_force()
        except tk.TclError:
            pass
        self.win.after(120, self.tick)

    # -------- layout --------
    def rows(self):
        """[(kind, label, y)] top to bottom, in units."""
        y = 34 + PREVIEW_H + 12
        out = [("color", tr("creator.color"), y)]
        y += 36
        for slot in character.SLOTS:
            out.append((slot, tr("creator." + slot), y))
            y += 18 + TILE + 10
        if character.user_skins():
            out.append(("skin", tr("creator.mine"), y))
            y += 18 + TILE + 10
        out.append(("presets", tr("creator.presets"), y))
        y += 18 + 3 * 24 + 8
        out.append(("buttons", "", y))
        return out

    def layout_height(self):
        return self.rows()[-1][2] + 26 + PAD

    # -------- drawing --------
    def draw(self):
        c, k, w = self.canvas, self.k, self.w
        hx = self.hx
        S = lambda v: v * k
        fam = w.fam
        font = lambda size, bold=False: (fam, max(6, round(size * w.scale)), "bold" if bold else "normal")
        c.delete("all")
        self.hits = []
        self.round_rect(c, 0, 0, S(MW) - 1, S(self.h) - 1, S(14), fill=hx(self.CARD),
                        outline=hx((0.30, 0.27, 0.25)))
        c.create_text(S(PAD), S(14), text=tr("creator.title"), anchor="w", fill=hx(self.ORANGE), font=font(11, True))
        self.button(MW - PAD - 18, 5, 18, 18, "×", self.close, plain=True)

        # preview
        px0, py0, px1, py1 = PAD, 34, MW - PAD, 34 + PREVIEW_H
        self.round_rect(c, S(px0), S(py0), S(px1), S(py1), S(10), fill=hx((0.15, 0.135, 0.125)), outline="")
        ch = w.character_now()
        bob = math.sin(time.time() * 2.2) * 1.5
        blink = (time.time() % 3.7) < 0.14
        w.draw_still(c, S(MW / 2), S(py0 + PREVIEW_H / 2 + 6 + bob), 1.3 * k, ch, "closed" if blink else "open")
        name = next((tr("costume." + p) for p in character.PRESET_ORDER if character.matches(ch, p)), None)
        if w.costume_pref == "auto":
            name = tr("costume.auto") + " · " + tr("costume." + w.costume())
        c.create_text(S(px0 + 10), S(py0 + 11), text=name or tr("creator.custom"), anchor="w", fill=hx(self.DIM), font=font(7))
        if time.time() < self.flash_until:
            c.create_text(S(px1 - 10), S(py0 + 11), text=self.flash_text, anchor="e", fill=hx(self.ORANGE), font=font(7, True))

        for kind, label, y in self.rows():
            if kind == "buttons":
                labels = [(tr("creator.random"), self.random), (tr("creator.import"), self.import_png),
                          (tr("creator.draw"), self.draw_own), (tr("creator.close"), self.close)]
                bw = (MW - 2 * PAD - 3 * 6) / 4
                for i, (text, fn) in enumerate(labels):
                    self.button(PAD + i * (bw + 6), y, bw, 22, text, fn)
                continue
            c.create_text(S(PAD), S(y + 6), text=label, anchor="w", fill=hx(self.DIM), font=font(7, True))
            if kind == "color":
                for i, (key, rgb) in enumerate(character.COLORS):
                    cx, cy = PAD + 10 + i * 26 + 60, y + 6
                    r = 8 if key == ch["color"] else 6.5
                    if key == ch["color"]:
                        c.create_oval(S(cx - 10), S(cy - 10), S(cx + 10), S(cy + 10), outline=hx(self.ORANGE), width=S(1.5))
                    c.create_oval(S(cx - r), S(cy - r), S(cx + r), S(cy + r), fill=hx(rgb), outline="")
                    self.hits.append(((cx - 11, cy - 11, cx + 11, cy + 11), lambda key=key: self.set("color", key)))
            elif kind == "presets":
                names = ["auto"] + character.PRESET_ORDER
                pw = (MW - 2 * PAD - 4 * 5) / 5
                for i, p in enumerate(names):
                    col, row = i % 5, i // 5
                    x1, y1 = PAD + col * (pw + 5), y + 18 + row * 24
                    on = (p == "auto" and w.costume_pref == "auto") or (p != "auto" and w.costume_pref != "auto"
                                                                        and character.matches(ch, p))
                    self.pill(x1, y1, pw, 20, tr("costume." + p), on, lambda p=p: self.preset(p))
            else:
                options = [None] + (character.PARTS[kind] if kind != "skin" else [n for n, _ in character.user_skins()])
                for i, opt in enumerate(options):
                    x1, y1 = PAD + i * GAP, y + 16
                    on = (ch.get(kind) == opt) if kind != "skin" else (ch.get("skin") == opt)
                    hot = self.hover == (kind, opt)
                    fill = (0.30, 0.22, 0.19) if on else ((0.22, 0.20, 0.19) if hot else (0.17, 0.155, 0.145))
                    self.round_rect(c, S(x1), S(y1), S(x1 + TILE), S(y1 + TILE), S(6), fill=hx(fill),
                                    outline=hx(self.ORANGE) if on else "")
                    if opt is None:
                        c.create_line(S(x1 + 9), S(y1 + TILE / 2), S(x1 + TILE - 9), S(y1 + TILE / 2),
                                      fill=hx(self.DIM), width=S(1.5))
                    else:
                        self.tile(kind, opt, x1, y1)
                    self.hits.append(((x1, y1, x1 + TILE, y1 + TILE), lambda kind=kind, opt=opt: self.set(kind, opt)))
                    self.hits[-1] = (self.hits[-1][0], self.hits[-1][1], (kind, opt))

    def tile(self, slot, name, x1, y1):
        """A part by itself, small, over a faint body."""
        c, k, w = self.canvas, self.k, self.w
        s = 0.34 * k
        cx, cy = (x1 + TILE / 2) * k, (y1 + TILE / 2 + 8) * k
        body = self.hx(character.color_rgb(w.character_now()), 0.25)
        c.create_rectangle(cx - 21 * s, cy - 27 * s, cx + 21 * s, cy + 15 * s, fill=body, outline="")
        if slot == "skin":
            paths = character.layers({"skin": name}, "front")
        else:
            paths = character.layers({slot: name}, "back") + character.layers({slot: name}, "front")
        for path in paths:
            for x, y, ww, hh, col in w.skins.runs(path) or []:
                c.create_rectangle(round(cx + x * s), round(cy + y * s), round(cx + (x + ww) * s),
                                   round(cy + (y + hh) * s), fill=col, outline="")

    def pill(self, x, y, w_, h, text, on, fn):
        c, k = self.canvas, self.k
        S = lambda v: v * k
        hot = self.hover == text
        fill = self.ORANGE if on else ((0.26, 0.23, 0.22) if hot else (0.19, 0.17, 0.16))
        self.round_rect(c, S(x), S(y), S(x + w_), S(y + h), S(8), fill=self.hx(fill), outline="")
        c.create_text(S(x + w_ / 2), S(y + h / 2), text=text, fill=self.hx((0.12, 0.09, 0.08) if on else self.TXT),
                      font=(self.w.fam, max(6, round(6.5 * self.w.scale)), "bold" if on else "normal"))
        self.hits.append(((x, y, x + w_, y + h), fn, text))

    def button(self, x, y, w_, h, text, fn, plain=False):
        c, k = self.canvas, self.k
        S = lambda v: v * k
        hot = self.hover == text
        if not plain:
            self.round_rect(c, S(x), S(y), S(x + w_), S(y + h), S(8),
                            fill=self.hx((0.28, 0.24, 0.22) if hot else (0.21, 0.19, 0.18)), outline="")
        c.create_text(S(x + w_ / 2), S(y + h / 2), text=text,
                      fill=self.hx(self.ORANGE if (hot or plain) else self.TXT),
                      font=(self.w.fam, max(6, round((9 if plain else 6.5) * self.w.scale)), "bold"))
        self.hits.append(((x, y, x + w_, y + h), fn, text))

    # -------- behaviour --------
    def find(self, ev):
        x, y = ev.x / self.k, ev.y / self.k
        for box, fn, *tag in self.hits:
            if box[0] <= x <= box[2] and box[1] <= y <= box[3]:
                return fn, (tag[0] if tag else None)
        return None, None

    def set_hover(self, tag):
        if tag != self.hover:
            self.hover = tag
            self.draw()

    def on_motion(self, ev):
        fn, tag = self.find(ev)
        self.set_hover(tag if fn else None)

    def on_click(self, ev):
        fn, _ = self.find(ev)
        if fn:
            fn()

    def set(self, slot, value):
        ch = dict(self.w.character_now())
        if slot == "skin":
            ch["skin"] = None if ch.get("skin") == value else value
        elif slot == "color":
            ch["color"] = value
        else:
            ch["skin"] = None
            ch[slot] = value
        self.apply(ch)

    def preset(self, name):
        if name == "auto":
            self.w.set_costume("auto")
        else:
            self.apply(character.preset(name, self.w.character["color"]))
        self.refit()

    def random(self):
        self.apply(character.shuffle(self.w.character_now()))

    def apply(self, ch):
        self.w.set_character(ch)
        self.draw()

    def import_png(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(parent=self.win, title=tr("creator.import"),
                                          filetypes=[("PNG", "*.png")])
        if not path:
            return
        try:
            img = self.tk.PhotoImage(file=path)
            ok = img.width() == 32 and img.height() == 32
        except Exception:
            ok = False
        if not ok:
            self.say(tr("creator.bad_png"))
            return
        name = os.path.splitext(os.path.basename(path))[0].replace(" ", "-")
        os.makedirs(character.skins_folder(), exist_ok=True)
        shutil.copy2(path, os.path.join(character.skins_folder(), name + ".png"))
        ch = dict(self.w.character_now())
        ch["skin"] = name
        self.apply(ch)
        self.refit()

    def draw_own(self):
        self.w.design_costumes()

    def say(self, text):
        self.flash_text, self.flash_until = text, time.time() + 3
        self.draw()

    def refit(self):
        """Rows may have appeared or gone (user skins): resize the window."""
        h = self.layout_height()
        if h != self.h:
            self.h = h
            pw, ph = round(MW * self.k), round(h * self.k)
            self.canvas.config(width=pw, height=ph)
            self.win.geometry("%dx%d" % (pw, ph))
            self.win.update_idletasks()
            self.w.round_corners(self.win, pw, ph, radius=14)
        self.draw()

    def tick(self):
        if self.closed:
            return
        self.draw()                                    # the preview breathes and blinks
        self.win.after(120, self.tick)

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.w.popup_menu is self:
            self.w.popup_menu = None
        try:
            self.win.destroy()
        except Exception:
            pass
