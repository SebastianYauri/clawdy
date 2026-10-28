#!/usr/bin/env python3
"""Draws the character parts into assets/parts/<slot>/<name>.png (32×32 PNGs, see
clawdy_character.py). Each pixel is half of a Clawdy pixel.

Clawdy's body is centered at x = 16: head rows at y 12-25, legs at y 26-29,
eyes at x 10-11 and 20-21, y 16-19, arms at x 2-5 and 26-29, y 18-21.
"""
import os
import struct
import zlib

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "parts")
SIZE = 32


class Grid:
    def __init__(self):
        self.g = [["."] * SIZE for _ in range(SIZE)]

    def px(self, x, y, ch):
        if 0 <= x < SIZE and 0 <= y < SIZE:
            self.g[y][x] = ch

    def rect(self, x, y, w, h, ch):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.px(xx, yy, ch)

    def rows(self, rows, top, left=0):
        for j, row in enumerate(rows):
            for i, ch in enumerate(row):
                if ch != ".":
                    self.px(left + i, top + j, ch)

    def mirror(self):
        """Copy the left half onto the right, mirrored."""
        for y in range(SIZE):
            for x in range(SIZE // 2):
                self.g[y][SIZE - 1 - x] = self.g[y][x]
        return self


def png(path, grid, palette):
    px = [[(0, 0, 0, 0)] * SIZE for _ in range(SIZE)]
    for y in range(SIZE):
        for x in range(SIZE):
            ch = grid.g[y][x]
            if ch != ".":
                h = palette[ch].lstrip("#")
                px[y][x] = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)
    raw = b"".join(b"\0" + bytes(c for p in r for c in p) for r in px)

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


# ---------------------------------------------------------------- heads

WITCH = {"o": "#2e1a4a", "p": "#7d45c4", "P": "#b48af0", "d": "#55299a", "b": "#f59428",
         "B": "#b8620f", "y": "#ffd75a", "s": "#fff3b0"}
WITCH_ROWS = [
    "......................oooo......",
    ".....................oPpdo......",
    "....................oPppdo......",
    "...................oPpppo.......",
    ".................ooPppppdo......",
    "................oPPpppsppdo.....",
    "...............oPPppppppppdo....",
    "..............oPPppppppppppdo...",
    ".............oBbbbbbyybbbbbbBo..",
    "............oBbbbbbyyyybbbbbbBo.",
    "..oooooooooodddddddddddddddddooo",
    ".oPPPPPPpppppppppppppppppppppddo",
    "..oooooooooooooooooooooooooooooo",
]

SANTA = {"o": "#2a1212", "R": "#d42a2a", "r": "#9e1b1b", "L": "#ef5b5b", "w": "#f4f4f4", "W": "#c9ccd6"}
SANTA_ROWS = [
    "..........ooooooo...............",
    "........ooRLLRRRRoo.............",
    ".......oRLLRRRRRRRRoo...........",
    "......oRLRRRRRRRRRRRRoo.........",
    ".....orRLRRRRRRRRRRRRRRooo......",
    ".....orRRRRRRRRRRRRRRRRRRRo.....",
    "....orrRRRRRRRRRRRRRRRoooRRo.oo.",
    "....orRRRRRRRRRRRRRRRRo..oRoowwo",
    "..oowwwwwwwwwwwwwwwwwwwwwoowWWwo",
    ".owWwwWWwwwWWwwwWWwwwWWwwWwoowo.",
    ".owwwwwwwwwwwwwwwwwwwwwwwwwo.o..",
    "..ooooooooooooooooooooooooo.....",
]

FRANK = {"o": "#0b090d", "g": "#5b5566", "H": "#1d1a21", "h": "#3b3644"}
FRANK_HAIR = [
    ".....gggggggggggggggggggggg.....",
    ".....oHhHHHhHHHHhHHHHhHHHHo.....",
    ".....oHHHHHHHHHHHHHHHHHHHHo.....",
    ".....oHHhHHHHHhHHHHHHhHHHHo.....",
    ".....oHHHHHHHHHHHHHHHHHHHHo.....",
    ".....oHHHHHHHHHHHHHHHHHHHHo.....",
    ".....oHHoHHHoHHHHoHHHoHHHHo.....",
    "......oo.oHo.ooHo.ooHo.oHo......",
    "..........o.....o.....o.........",
]

SLICK = {"o": "#0c0a0f", "H": "#1f1a26", "h": "#3d3349"}
SLICK_ROWS = [
    "......oooooooooooooooooooo......",
    "......oHhHHHHhHHHHHHhHHHHo......",
    "......oHHHHHHHHHHHHHHHHHHo......",
    "........oHHHHHHoHHHHHHHo........",
    "..............oHo...............",
    "...............o................",
]


def head_cowboy():
    g = Grid()
    P = {"o": "#3b2314", "B": "#8a5a2b", "b": "#a9733a", "k": "#2a1a10", "y": "#e3b341"}
    g.rect(9, 3, 14, 6, "B")                 # crown
    g.rect(10, 3, 12, 1, "b")
    g.rect(14, 3, 4, 1, "B")                 # dent
    g.rect(9, 7, 14, 1, "k")                 # band
    g.rect(15, 7, 2, 1, "y")                 # buckle
    g.rect(2, 9, 28, 2, "b")                 # brim
    g.rect(1, 10, 1, 1, "b"); g.rect(30, 10, 1, 1, "b")
    g.rect(2, 11, 28, 1, "B")
    for x in range(1, 31):                   # outline
        g.px(x, 8, "o") if 9 <= x <= 22 else g.px(x, 9, "o")
    g.rect(8, 3, 1, 5, "o"); g.rect(23, 3, 1, 5, "o"); g.rect(9, 2, 14, 1, "o")
    g.rect(0, 10, 1, 1, "o"); g.rect(31, 10, 1, 1, "o"); g.rect(1, 11, 1, 1, "o"); g.rect(30, 11, 1, 1, "o")
    g.rect(2, 12, 28, 1, "o")
    return g, P


def head_chef():
    g = Grid()
    P = {"o": "#8a8f99", "w": "#fbfbfd", "W": "#dfe2ea", "s": "#c4c8d2"}
    g.rect(7, 2, 18, 6, "w")                 # puff
    g.rect(6, 3, 20, 4, "w")
    g.rect(9, 1, 14, 1, "w")
    g.rect(8, 7, 16, 1, "W")
    for x in (10, 15, 20):                   # folds
        g.rect(x, 3, 1, 4, "W")
    g.rect(9, 8, 14, 3, "s")                 # band
    g.rect(9, 8, 14, 1, "W")
    g.rect(8, 8, 1, 3, "o"); g.rect(23, 8, 1, 3, "o"); g.rect(9, 11, 14, 1, "o")
    g.rect(5, 3, 1, 4, "o"); g.rect(26, 3, 1, 4, "o"); g.rect(6, 2, 1, 1, "o"); g.rect(25, 2, 1, 1, "o")
    g.rect(7, 1, 2, 1, "o"); g.rect(23, 1, 2, 1, "o"); g.rect(9, 0, 14, 1, "o")
    g.rect(6, 7, 1, 1, "o"); g.rect(25, 7, 1, 1, "o"); g.rect(7, 8, 1, 1, "o"); g.rect(24, 8, 1, 1, "o")
    return g, P


def head_pirate():
    g = Grid()
    P = {"o": "#07060a", "k": "#1c1a22", "K": "#2e2b36", "w": "#f4f4f4", "r": "#c0262e"}
    g.rect(8, 4, 16, 5, "k")                 # crown
    g.rect(9, 4, 14, 1, "K")
    g.rect(3, 9, 26, 3, "k")                 # brim
    g.rect(2, 7, 2, 3, "k"); g.rect(28, 7, 2, 3, "k")       # turned-up ends
    g.rect(2, 6, 1, 1, "K"); g.rect(29, 6, 1, 1, "K")
    g.rect(14, 5, 4, 3, "w")                 # skull
    g.rect(15, 6, 1, 1, "k"); g.rect(16, 6, 1, 1, "k")
    g.rect(15, 8, 2, 1, "w")
    g.rect(12, 9, 8, 1, "w")                 # crossbones
    g.rect(3, 12, 26, 1, "r")                # red band under the brim
    g.rect(7, 3, 18, 1, "o"); g.rect(7, 4, 1, 5, "o"); g.rect(24, 4, 1, 5, "o")
    g.rect(1, 6, 1, 4, "o"); g.rect(30, 6, 1, 4, "o"); g.rect(2, 5, 1, 1, "o"); g.rect(29, 5, 1, 1, "o")
    g.rect(2, 10, 1, 2, "o"); g.rect(29, 10, 1, 2, "o"); g.rect(3, 13, 26, 1, "o")
    return g, P


def head_astronaut():
    g = Grid()
    P = {"o": "#6f7480", "w": "#f2f4f8", "W": "#c9cfdb", "b": "#8fd3ff", "r": "#e05252"}
    # helmet rim around the head: a window in the middle, so the face shows through
    for x in range(6, 26):
        g.px(x, 8, "w"); g.px(x, 9, "W")
    g.rect(4, 10, 2, 16, "w"); g.rect(26, 10, 2, 16, "w")
    g.rect(3, 12, 1, 12, "W"); g.rect(28, 12, 1, 12, "W")
    g.rect(5, 26, 22, 2, "w"); g.rect(6, 28, 20, 1, "W")
    g.rect(6, 10, 2, 2, "w"); g.rect(24, 10, 2, 2, "w")
    g.rect(7, 10, 3, 1, "b"); g.rect(22, 10, 3, 1, "b")       # glass glints
    g.rect(15, 5, 2, 3, "o"); g.rect(14, 4, 4, 1, "r")        # antenna
    for x in range(5, 27):
        g.px(x, 7, "o")
    g.rect(3, 10, 1, 2, "o"); g.rect(28, 10, 1, 2, "o"); g.rect(2, 12, 1, 12, "o"); g.rect(29, 12, 1, 12, "o")
    g.rect(3, 24, 1, 2, "o"); g.rect(28, 24, 1, 2, "o"); g.rect(4, 26, 1, 2, "o"); g.rect(27, 26, 1, 2, "o")
    g.rect(5, 28, 1, 1, "o"); g.rect(26, 28, 1, 1, "o"); g.rect(6, 29, 20, 1, "o")
    return g, P


def head_ninja():
    g = Grid()
    P = {"o": "#120d10", "k": "#23202a", "r": "#c0262e", "R": "#e04a4a"}
    g.rect(4, 13, 24, 3, "k")                # band across the forehead
    g.rect(4, 13, 24, 1, "o")
    g.rect(14, 13, 4, 3, "r")                # knot plate
    g.rect(28, 13, 3, 2, "R"); g.rect(29, 15, 3, 2, "r"); g.rect(28, 17, 2, 1, "R")   # tails
    return g, P


# ---------------------------------------------------------------- faces

def face_glasses():
    g = Grid()
    P = {"k": "#1c1a22", "b": "#9ad8ff"}
    for x0 in (8, 18):
        g.rect(x0, 14, 6, 1, "k"); g.rect(x0, 20, 6, 1, "k")
        g.rect(x0, 14, 1, 7, "k"); g.rect(x0 + 5, 14, 1, 7, "k")
        g.rect(x0 + 1, 15, 1, 1, "b")
    g.rect(14, 17, 4, 1, "k")                # bridge
    g.rect(5, 16, 3, 1, "k"); g.rect(24, 16, 3, 1, "k")       # temples
    return g, P


def face_eyepatch():
    g = Grid()
    P = {"k": "#141218", "K": "#2a2630"}
    g.rect(6, 13, 20, 1, "k")                # strap
    g.rect(5, 14, 1, 1, "k"); g.rect(26, 14, 1, 1, "k")
    g.rect(18, 14, 6, 7, "k")                # patch over the right eye
    g.rect(19, 15, 1, 1, "K")
    return g, P


def face_stitches():
    g = Grid()
    P = {"s": "#7a2c25"}
    g.rect(6, 22, 7, 1, "s")
    for x in (7, 9, 11):
        g.rect(x, 21, 1, 3, "s")
    return g, P


def face_fangs():
    g = Grid()
    P = {"w": "#f7f7f7", "W": "#c9ccd6"}
    for x in (13, 18):
        g.rect(x, 22, 1, 2, "w"); g.rect(x, 24, 1, 1, "W")
    return g, P


def face_blush():
    g = Grid()
    P = {"p": "#f0877a"}
    g.rect(6, 21, 3, 2, "p"); g.rect(23, 21, 3, 2, "p")
    return g, P


# ---------------------------------------------------------------- bodies

def body_bolts():
    g = Grid()
    P = {"k": "#4b4f57", "m": "#9da2ab", "M": "#e0e3ea"}
    for x0, flip in ((3, False), (25, True)):
        g.rect(x0, 23, 3, 3, "m")
        g.rect(x0 + (2 if flip else 0), 23, 1, 3, "M" if not flip else "k")
        g.rect(x0 + (0 if flip else 2), 23, 1, 3, "k" if not flip else "M")
    return g, P


def body_scarf():
    g = Grid()
    P = {"r": "#c8323a", "R": "#e8555c", "o": "#7a1c22"}
    g.rect(6, 22, 20, 3, "r")
    for x in range(7, 26, 3):
        g.rect(x, 23, 1, 1, "R")
    g.rect(6, 24, 20, 1, "o")
    g.rect(21, 25, 4, 5, "r"); g.rect(21, 25, 1, 5, "R"); g.rect(21, 29, 4, 1, "o")   # loose end
    return g, P


def body_bandana():
    g = Grid()
    P = {"r": "#c0262e", "w": "#f4f4f4", "o": "#6e1218"}
    for i, (x0, w) in enumerate(((7, 18), (8, 16), (10, 12), (12, 8), (14, 4))):
        g.rect(x0, 22 + i, w, 1, "r")
    for x in (9, 14, 19, 23):
        g.px(x, 23, "w")
    g.rect(7, 22, 18, 1, "o")
    return g, P


def body_sheet():
    g = Grid()
    P = {"w": "#f2f2f8", "W": "#c9cad6", "o": "#9a9bae"}
    g.rect(3, 9, 26, 19, "w")
    g.rect(5, 7, 22, 2, "w"); g.rect(8, 6, 16, 1, "w"); g.rect(11, 5, 10, 1, "w")
    g.rect(2, 11, 1, 15, "W"); g.rect(29, 11, 1, 15, "W")
    for i in range(7):                       # wavy hem
        x = 3 + i * 4
        g.rect(x, 28, 2, 2 if i % 2 == 0 else 1, "w")
        g.rect(x + 2, 28, 2, 1 if i % 2 == 0 else 2, "W")
    g.rect(10, 16, 2, 4, "."); g.rect(20, 16, 2, 4, ".")      # windows for Clawdy's own eyes
    g.rect(9, 15, 4, 1, "W"); g.rect(19, 15, 4, 1, "W")
    g.rect(14, 23, 4, 3, "o")                                  # a small "boo" mouth
    return g, P


def body_pumpkin():
    g = Grid()
    P = {"r": "#c2603f", "g": "#4f8c35", "G": "#7bbf4f", "y": "#ffd75a", "Y": "#ffb43a"}
    g.rect(8, 12, 2, 14, "r"); g.rect(22, 12, 2, 14, "r")     # ribs
    g.rect(15, 9, 2, 3, "g"); g.rect(17, 9, 3, 1, "G"); g.rect(19, 8, 2, 1, "G")   # stem and leaf
    for i, (x0, w) in enumerate(((10, 2), (9, 4), (8, 6))):  # carved eyes (cover Clawdy's)
        g.rect(x0, 16 + i, w, 1, "y"); g.rect(32 - x0 - w, 16 + i, w, 1, "y")
    g.rect(9, 19, 4, 1, "Y"); g.rect(19, 19, 4, 1, "Y")
    for i, (x0, w) in enumerate(((8, 16), (9, 14))):          # jagged grin
        g.rect(x0, 22 + i, w, 1, "y")
    for x in (10, 14, 18, 22):
        g.px(x, 21, "y"); g.px(x + 2, 24, "Y")
    return g, P


CAPE = {"o": "#120d16", "C": "#231a2b", "c": "#3a2c47", "R": "#8e1424", "r": "#5a0c16", "L": "#b3182a"}
CAPE_LEFT = [  # rows 11..31, left half; mirrored
    "...ooooooooooooo",
    "..oCcCCCCCCCCCCC",
    ".oRcCCCCCCCCCCCC",
    ".oRcCCCCCCCCCCCC",
    "oLRcCCCCCCCCCCCC",
    "oLRcCCCCCCCCCCCC",
    "oLRcCCCCCCCCCCCC",
    "oLRcCCCCCCCCCCCC",
    "oLRcCCCCCCCCCCCC",
    "oLRcCCCCCCCCCCCC",
    "oLRcCCCCCCCCCCCC",
    "oLRcCCCCCCCCCCCC",
    "oLRRcCCCCCCCCCCC",
    "orLRRcCCCCCCCCCC",
    ".orLRRcCCCCCCCCC",
    ".orrLRRcCCCCCCCC",
    "..oorLRRRcCCCCCC",
    "....oorrLRRRRRRR",
    "......oooorrrrrr",
    "..........oooooo",
]


def main():
    parts = {}
    g = Grid(); g.rows(WITCH_ROWS, 0); parts["head/witch"] = (g, WITCH)
    g = Grid(); g.rows(SANTA_ROWS, 1); parts["head/santa"] = (g, SANTA)
    g = Grid(); g.rows(FRANK_HAIR, 7); parts["head/frank"] = (g, FRANK)
    g = Grid(); g.rows(SLICK_ROWS, 11); parts["head/slick"] = (g, SLICK)
    for name, fn in (("head/cowboy", head_cowboy), ("head/chef", head_chef), ("head/pirate", head_pirate),
                     ("head/astronaut", head_astronaut), ("head/ninja", head_ninja),
                     ("face/glasses", face_glasses), ("face/eyepatch", face_eyepatch), ("face/stitches", face_stitches),
                     ("face/fangs", face_fangs), ("face/blush", face_blush),
                     ("body/bolts", body_bolts), ("body/scarf", body_scarf), ("body/bandana", body_bandana),
                     ("body/sheet", body_sheet), ("body/pumpkin", body_pumpkin)):
        parts[name] = fn()
    g = Grid(); g.rows(CAPE_LEFT, 11); g.mirror(); parts["body/cape_back"] = (g, CAPE)
    for name, (grid, palette) in parts.items():
        png(os.path.join(OUT, name + ".png"), grid, palette)
    print("%d parts written to %s" % (len(parts), os.path.normpath(OUT)))


if __name__ == "__main__":
    main()
