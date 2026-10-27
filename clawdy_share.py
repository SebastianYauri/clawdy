"""Share card: a pixel-art image of Clawdy with your usage, ready to post.

Pure Python (zlib + struct), so it needs no image library. Everything is drawn
on a grid of square cells, like the mascot itself.
"""
import math
import os
import shutil
import struct
import subprocess
import sys
import unicodedata
import webbrowser
import zlib
from urllib.parse import quote

W, H = 1200, 630
BG = (28, 25, 23)
PANEL = (38, 34, 31)
ORANGE = (217, 119, 87)
EYE = (26, 20, 18)
TXT = (245, 237, 224)
DIM = (158, 150, 140)
TRACK = (58, 52, 47)
LINK = "github.com/SebastianYauri/clawdy"

# 5x7 pixel font: what the card needs (labels are upper-cased, accents dropped)
FONT = {
    "A": ".###.#...##...#######...##...##...#", "B": "####.#...#####.#...##...##...#####.",
    "C": ".###.#...##....#....#....#...#.###.", "D": "####.#...##...##...##...##...#####.",
    "E": "######....####.#....#....#....#####", "F": "######....####.#....#....#....#....",
    "G": ".###.#...##....#.####...##...#.####", "H": "#...##...#######...##...##...##...#",
    "I": ".###...#....#....#....#....#...###.", "J": "..###...#....#....#....#.#..#..##..",
    "K": "#...##..#.###..#..#.#...##...##...#", "L": "#....#....#....#....#....#....#####",
    "M": "#...###.###.#.##...##...##...##...#", "N": "#...###..##.#.##..###...##...##...#",
    "O": ".###.#...##...##...##...##...#.###.", "P": "####.#...##...#####.#....#....#....",
    "Q": ".###.#...##...##...##.#.##..#..##.#", "R": "####.#...##...#####.#.#..#..#.#...#",
    "S": ".#####....#.....###.....#....#####.", "T": "#####..#....#....#....#....#....#..",
    "U": "#...##...##...##...##...##...#.###.", "V": "#...##...##...##...##...#.#.#...#..",
    "W": "#...##...##...##.#.##.#.##.#.#.#.#.", "X": "#...##...#.#.#...#...#.#.#...##...#",
    "Y": "#...##...#.#.#...#....#....#....#..", "Z": "#####....#...#...#...#...#....#####",
    "0": ".###.#...##..###.#.###..##...#.###.", "1": "..#...##....#....#....#....#...###.",
    "2": ".###.#...#....#...#...#...#...#####", "3": "#####...#...#.....#.....##...#.###.",
    "4": "...#...##..#.#.#..#.#####...#....#.", "5": "######....####.....#....##...#.###.",
    "6": "..##..#...#....####.#...##...#.###.", "7": "#####....#...#...#...#....#....#...",
    "8": ".###.#...##...#.###.#...##...#.###.", "9": ".###.#...##...#.####....#...#..##..",
    "%": "##...##..#...#...#...#...#..##...##", "(": "...#...#...#....#....#.....#.....#.",
    ")": ".#.....#.....#....#....#...#...#...", ".": "..........................##...##..",
    "-": "................###................", "/": "....#....#...#...#...#...#....#....",
    ":": ".......##...##.........##...##.....", "!": "..#....#....#....#....#.........#..",
    "?": ".###.#...#....#...#...#.........#..", ",": ".....................##...##..#....",
    "'": "..#....#...#.......................", "+": ".......#....#..#####..#....#.......",
    "·": "...............##...##.............",
}
SPRITE = [
    "..XXXXXXXXXX..",
    "..XXXXXXXXXX..",
    "..XXEXXXXEXX..",
    "AAXXEXXXXEXXAA",
    "AAXXXXXXXXXXAA",
    "..XXXXXXXXXX..",
    "..XXXXXXXXXX..",
    "...L.L..L.L...",
    "...L.L..L.L...",
]


class Image:
    def __init__(self, w, h, color):
        self.w, self.h = w, h
        self.px = bytearray(bytes(color) * (w * h))

    def rect(self, x, y, w, h, color):
        x0, y0 = max(0, int(x)), max(0, int(y))
        x1, y1 = min(self.w, int(x + w)), min(self.h, int(y + h))
        if x1 <= x0:
            return
        line = bytes(color) * (x1 - x0)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            self.px[i:i + len(line)] = line

    def png(self):
        raw = b"".join(b"\0" + bytes(self.px[y * self.w * 3:(y + 1) * self.w * 3]) for y in range(self.h))

        def chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", self.w, self.h, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def plain(text):
    """Upper case without accents, so the pixel font can draw it."""
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).upper()


def text_width(text, scale):
    return max(0, len(plain(text)) * 6 * scale - scale)


def draw_text(img, x, y, text, scale, color, align="left"):
    text = plain(text)
    if align == "right":
        x -= text_width(text, scale)
    elif align == "center":
        x -= text_width(text, scale) / 2
    for ch in text:
        g = FONT.get(ch)
        if g:
            g = g.ljust(35, ".")
            for i, bit in enumerate(g[:35]):
                if bit == "#":
                    img.rect(x + (i % 5) * scale, y + (i // 5) * scale, scale, scale, color)
        x += 6 * scale


def draw_ring(img, cx, cy, radius, width, p, color, cell=6):
    """A chunky pixel ring, filled clockwise from the top up to p percent."""
    r0, r1 = radius - width / 2, radius + width / 2
    n = int(r1 // cell) + 1
    for j in range(-n, n + 1):
        for i in range(-n, n + 1):
            dx, dy = (i + 0.5) * cell, (j + 0.5) * cell
            d = math.hypot(dx, dy)
            if r0 <= d <= r1:
                frac = (math.atan2(dx, -dy) % (2 * math.pi)) / (2 * math.pi)
                img.rect(cx + i * cell, cy + j * cell, cell, cell, color if frac * 100 < p else TRACK)


def draw_mascot(img, cx, cy, px):
    x0, y0 = cx - len(SPRITE[0]) * px / 2, cy - len(SPRITE) * px / 2
    for r, row in enumerate(SPRITE):
        for c, ch in enumerate(row):
            if ch != ".":
                img.rect(x0 + c * px, y0 + r * px, px, px, EYE if ch == "E" else ORANGE)


def make_card(rows, title):
    """rows: [(label, percent, rgb 0-1, reset text)]. Returns PNG bytes."""
    img = Image(W, H, BG)
    img.rect(0, 0, W, 12, ORANGE)                       # top stripe
    cx, cy = 300, 306
    img.rect(cx - 270, cy - 270, 540, 540, PANEL)
    radii = (246, 210, 174)
    for (label, p, col, _), rad in zip(rows, radii):
        draw_ring(img, cx, cy, rad, 24, p, tuple(round(v * 255) for v in col))
    for rad in radii[len(rows):]:
        draw_ring(img, cx, cy, rad, 24, 0, TRACK)
    draw_mascot(img, cx, cy, 18)

    x, right = 620, 1150
    draw_text(img, x, 60, title, 5, TXT)
    y = 140
    step = 104 if len(rows) <= 3 else 100
    for label, p, col, reset in rows[:4]:
        color = tuple(round(v * 255) for v in col)
        pct = "%d%%" % round(p)
        room = right - x - text_width(pct, 6) - 24
        scale = 4 if text_width(label, 4) <= room else 3
        while text_width(label, scale) > room:
            label = label[:-1]
        draw_text(img, x, y + (4 - scale) * 7, label, scale, DIM)
        draw_text(img, right, y - 6, pct, 6, color, "right")
        bar_y = y + 44
        img.rect(x, bar_y, right - x, 18, TRACK)
        img.rect(x, bar_y, (right - x) * max(0.0, min(1.0, p / 100)), 18, color)
        if reset:
            draw_text(img, x, bar_y + 26, reset, 2, DIM)
        y += step
    draw_text(img, 30, 590, "CLAWDY", 4, ORANGE)
    draw_text(img, 1170, 594, LINK, 3, DIM, "right")
    return img.png()


def pictures_dir():
    home = os.path.expanduser("~")
    if sys.platform.startswith("linux") and shutil.which("xdg-user-dir"):
        try:
            d = subprocess.run(["xdg-user-dir", "PICTURES"], capture_output=True, text=True, timeout=3).stdout.strip()
            if d and os.path.isdir(d) and d != home:
                return d
        except Exception:
            pass
    d = os.path.join(home, "Pictures")
    return d if os.path.isdir(d) else home


def save_card(png, folder=None):
    import time
    folder = folder or pictures_dir()
    path = os.path.join(folder, time.strftime("clawdy-usage-%Y%m%d-%H%M%S.png"))
    with open(path, "wb") as f:
        f.write(png)
    return path


def reveal(path):
    """Show the file in the file manager, so it can be dragged into a post."""
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", path])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
        else:
            subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
    except Exception:
        pass


def open_post(text):
    """A new post on X with the text filled in; the user attaches the image."""
    webbrowser.open("https://x.com/intent/post?text=" + quote(text))
