"""Pixel art layers for the character: 32×32 PNGs read with Tk itself (no image
library needed), turned into rectangles in Clawdy's sprite units.

Each image pixel is half of one of Clawdy's pixels. Clawdy's body sits in the
middle: its head starts at row 12, the eyes are at columns 10-11 and 20-21,
rows 16-19, the legs end at row 29. The built-in parts live in assets/parts/,
the user's own whole skins in <config>/skins/ (see clawdy_character.py).
"""
import os
import time

CELL = 3                  # sprite units per image pixel (a Clawdy pixel is 6)
X0, Y0 = -48, -63         # the sprite point at the image's top-left corner
SIZE = 32


class Skins:
    """Loads PNGs on demand as runs of rectangles and notices when they change."""

    def __init__(self, tk_module):
        self.tk = tk_module
        self.cache = {}                    # path -> (mtime, runs)
        self.last = {}                     # path -> (checked at, runs): the disk is asked once a second

    def runs(self, path):
        hit = self.last.get(path)
        if hit and time.time() - hit[0] < 1.0:
            return hit[1]
        runs = self._runs(path)
        self.last[path] = (time.time(), runs)
        return runs

    def _runs(self, path):
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            self.cache.pop(path, None)
            return None
        hit = self.cache.get(path)
        if hit and hit[0] == mtime:
            return hit[1]
        try:
            runs = self.load(path)
        except Exception:
            runs = None                    # half-saved or not a PNG: draw nothing
        self.cache[path] = (mtime, runs)
        return runs

    def pixels(self, path):
        """{(px, py): '#rrggbb'} of an image, for previews and flattening."""
        img = self.tk.PhotoImage(file=path)
        w, h = min(img.width(), SIZE), min(img.height(), SIZE)
        out = {}
        for py in range(h):
            for px in range(w):
                if not img.transparency_get(px, py):
                    r, g, b = img.get(px, py)[:3]
                    out[(px, py)] = "#%02x%02x%02x" % (r, g, b)
        return out

    def load(self, path):
        """[(x, y, w, h, '#rrggbb')] in sprite units: same-color pixels merged into blocks."""
        pix = self.pixels(path)
        runs = []
        for py in range(SIZE):
            run = None
            for px in range(SIZE + 1):
                col = pix.get((px, py))
                if run and col == run[1]:
                    run[2] += 1
                    continue
                if run:
                    runs.append((run[0], py, run[2], 1, run[1]))
                run = [px, col, 1] if col else None
        merged = []                        # identical runs in consecutive rows become one block
        for x, y, n, _, col in runs:
            for m in merged:
                if m[0] == x and m[2] == n and m[4] == col and m[1] + m[3] == y:
                    m[3] += 1
                    break
            else:
                merged.append([x, y, n, 1, col])
        return [(X0 + x * CELL, Y0 + y * CELL, n * CELL, h * CELL, col) for x, y, n, h, col in merged]


def write_png(tk_module, path, pix):
    """A 32×32 PNG from {(px, py): '#rrggbb'}; everything else transparent."""
    img = tk_module.PhotoImage(width=SIZE, height=SIZE)
    for py in range(SIZE):
        for px in range(SIZE):
            col = pix.get((px, py))
            if col:
                img.put(col, (px, py))
            else:
                img.transparency_set(px, py, True)
    img.write(path, format="png")


def export_templates(widget, tk_module, sprite, colors, layer_paths, skins):
    """Into the skins folder: a reference of Clawdy's body and the current look
    flattened, so they can be opened in a pixel art editor and drawn over."""
    import clawdy_character as character
    out = character.skins_folder()
    os.makedirs(out, exist_ok=True)
    body = {}
    for r, row in enumerate(sprite):
        for c, ch in enumerate(row):
            if ch in colors:
                for dy in (0, 1):
                    for dx in (0, 1):
                        body[(2 + c * 2 + dx, 12 + r * 2 + dy)] = colors[ch]
    write_png(tk_module, os.path.join(out, "_clawdy-reference.png"), body)
    look = {}
    for path in layer_paths:
        try:
            look.update(skins.pixels(path))
        except Exception:
            pass
    write_png(tk_module, os.path.join(out, "_current-look.png"), look)
    with open(os.path.join(out, "LEEME - README.txt"), "w", encoding="utf-8") as f:
        f.write(README)
    return out


README = """Clawdy skins / Skins de Clawdy

EN: Draw a 32x32 PNG in a pixel art editor such as Pixelorama (free) and save it
in this folder, e.g. my-skin.png. It appears under "My skins" in Clawdy's
Customize skin window and is drawn over Clawdy, moving with it. Each pixel is
half a Clawdy pixel; use _clawdy-reference.png as a guide layer to see where
the body is (leave the eyes clear so they stay alive), and _current-look.png
is what you're wearing now, flattened, to start from. A file named
my-skin_back.png is drawn behind Clawdy (capes). Files starting with _ are
ignored.

ES: Dibuja un PNG de 32x32 en un editor de pixel art como Pixelorama (gratis) y
guardalo en esta carpeta, por ejemplo mi-skin.png. Aparece en "Mis skins" en la
ventana Personalizar skin de Clawdy y se dibuja sobre Clawdy, moviendose con el.
Cada pixel es medio pixel de Clawdy; usa _clawdy-reference.png como capa guia
para ver donde esta el cuerpo (deja los ojos libres para que sigan vivos), y
_current-look.png es lo que llevas puesto ahora, aplanado, para partir de ahi.
Un archivo mi-skin_back.png se dibuja detras de Clawdy (capas). Los archivos
que empiezan con _ se ignoran.
"""
