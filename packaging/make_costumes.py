#!/usr/bin/env python3
"""Draws the built-in costume art into assets/skins/ (32×32 PNGs, see clawdy_skins.py).

Each pixel is half of a Clawdy pixel. Clawdy's body is centered at x = 16;
its head starts at y = 12, the eyes are at x 10-11 and 20-21, y 16-19, the
arms at y 18-21 and the legs at y 26-29.
"""
import os
import struct
import zlib

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "skins")
SIZE = 32


def png(path, rows, palette, top):
    """rows: strings of palette keys ('.' = transparent), starting at image row `top`."""
    px = [[(0, 0, 0, 0)] * SIZE for _ in range(SIZE)]
    for j, row in enumerate(rows):
        for i, ch in enumerate(row[:SIZE]):
            if ch != ".":
                h = palette[ch].lstrip("#")
                px[top + j][i] = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)
    raw = b"".join(b"\0" + bytes(c for p in r for c in p) for r in px)

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def mirror(rows):
    """Left halves (16 wide) mirrored into full rows."""
    return [r + r[::-1] for r in rows]


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

SANTA = {"o": "#2a1212", "R": "#d42a2a", "r": "#9e1b1b", "L": "#ef5b5b", "w": "#f4f4f4",
         "W": "#c9ccd6"}
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

FRANK = {"o": "#0b090d", "g": "#5b5566", "H": "#1d1a21", "h": "#3b3644", "s": "#7a2c25",
         "m": "#9da2ab", "M": "#e0e3ea", "k": "#4b4f57"}
FRANK_ROWS = [  # starting at row 7
    ".....gggggggggggggggggggggg.....",
    ".....oHhHHHhHHHHhHHHHhHHHHo.....",
    ".....oHHHHHHHHHHHHHHHHHHHHo.....",
    ".....oHHhHHHHHhHHHHHHhHHHHo.....",
    ".....oHHHHHHHHHHHHHHHHHHHHo.....",
    ".....oHHHHHHHHHHHHHHHHHHHHo.....",
    ".....oHHoHHHoHHHHoHHHoHHHHo.....",
    "......oo.oHo.ooHo.ooHo.oHo......",
    "..........o.....o.....o.........",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    ".......s.s.s....................",
    "......sssssss...................",
    "...kmM.s.s.s.............Mmk....",
    "...kmM...................Mmk....",
    "...kmM...................Mmk....",
]

VAMP = {"o": "#0c0a0f", "H": "#1f1a26", "h": "#3d3349", "w": "#f7f7f7", "W": "#c9ccd6"}
VAMP_ROWS = [  # starting at row 11
    "......oooooooooooooooooooo......",
    "......oHhHHHHhHHHHHHhHHHHo......",
    "......oHHHHHHHHHHHHHHHHHHo......",
    "........oHHHHHHoHHHHHHHo........",
    "..............oHo...............",
    "...............o................",
    "................................",
    "................................",
    "................................",
    "................................",
    ".............w....w.............",
    ".............w....w.............",
    ".............W....W.............",
]

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
    os.makedirs(OUT, exist_ok=True)
    png(os.path.join(OUT, "witch.png"), WITCH_ROWS, WITCH, 0)
    png(os.path.join(OUT, "santa.png"), SANTA_ROWS, SANTA, 1)
    png(os.path.join(OUT, "frank.png"), FRANK_ROWS, FRANK, 7)
    png(os.path.join(OUT, "vampire.png"), VAMP_ROWS, VAMP, 11)
    png(os.path.join(OUT, "vampire_back.png"), mirror(CAPE_LEFT), CAPE, 11)
    print("written to", os.path.normpath(OUT))


if __name__ == "__main__":
    main()
