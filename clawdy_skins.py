"""Costume art from PNG files, so costumes can be drawn in a pixel art editor
(Pixelorama, Aseprite, LibreSprite, Piskel…) instead of in code.

A costume image is 32×32 pixels; each pixel is half of one of Clawdy's pixels,
so details can be finer than the body. Clawdy's body sits in the middle (see
the reference image) and the art keeps moving with it: jumps, spins, squashes.

    <config>/skins/witch.png         drawn in front of Clawdy
    <config>/skins/vampire_back.png  drawn behind it (capes)
    <config>/skins/templates/        today's costumes, exported to start from

Files are read with Tk itself (PNG support is built in), so no image library
is needed, and they are reloaded when they change.
"""
import os

import clawdy_system as cs

CELL = 3                  # scene units per image pixel (a Clawdy pixel is 6)
X0, Y0 = -48, -63         # the scene point at the image's top-left corner
SIZE = 32


def folder():
    return os.path.join(cs.config_dir(), "skins")


class Recorder:
    """Stands in for the widget while a costume draws itself: remembers the shapes."""

    def __init__(self):
        self.shapes = []

    def px_rect(self, xf, x, y, color, w, h):
        self.shapes.append(("rect", (x, y, w, h), color))

    def poly(self, pts, color):
        self.shapes.append(("poly", pts, color))

    def oval(self, cx, cy, rx, ry, color):
        self.shapes.append(("oval", (cx, cy, rx, ry), color))

    def color_at(self, x, y):
        hit = None
        for kind, g, color in self.shapes:          # the last shape drawn wins
            if kind == "rect":
                inside = g[0] <= x < g[0] + g[2] and g[1] <= y < g[1] + g[3]
            elif kind == "oval":
                inside = ((x - g[0]) / g[2]) ** 2 + ((y - g[1]) / g[3]) ** 2 <= 1
            else:
                inside = _in_poly(x, y, g)
            if inside:
                hit = color
        return hit


def _in_poly(x, y, pts):
    inside, j = False, len(pts) - 1
    for i in range(len(pts)):
        (xi, yi), (xj, yj) = pts[i], pts[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def rasterize(rec, tk_module):
    img = tk_module.PhotoImage(width=SIZE, height=SIZE)
    for py in range(SIZE):
        for px in range(SIZE):
            col = rec.color_at(X0 + (px + 0.5) * CELL, Y0 + (py + 0.5) * CELL)
            if col:
                img.put(col, (px, py))
            else:
                img.transparency_set(px, py, True)
    return img


def export_templates(widget, costumes, tk_module, sprite, colors):
    """Write today's costumes (and Clawdy itself, for reference) as editable PNGs."""
    from clawdy_gui import Xform
    out = os.path.join(folder(), "templates")
    os.makedirs(out, exist_ok=True)
    ident = Xform(0, 0)
    import shutil
    for c in costumes:
        for layer in ("back", "front"):
            name = c + ("_back" if layer == "back" else "") + ".png"
            built_in = cs.resource("assets", "skins", name)
            if os.path.exists(built_in):             # drawn as a PNG already: start from that
                shutil.copy2(built_in, os.path.join(out, name))
                continue
            rec = Recorder()
            type(widget).draw_costume(_Proxy(widget, rec), ident, c, layer, 0.0, 1.0, "open", 0.0)
            if rec.shapes:
                name = c + ("_back" if layer == "back" else "") + ".png"
                rasterize(rec, tk_module).write(os.path.join(out, name), format="png")
    rec = Recorder()                                     # the plain body, as a guide
    h, w = len(sprite), len(sprite[0])
    for r, row in enumerate(sprite):
        for col, ch in enumerate(row):
            if ch in colors:
                rec.px_rect(None, (col - w / 2) * 6, (r - h / 2) * 6, colors[ch], 6, 6)
    rasterize(rec, tk_module).write(os.path.join(out, "_clawdy-reference.png"), format="png")
    with open(os.path.join(folder(), "LEEME - README.txt"), "w", encoding="utf-8") as f:
        f.write(README)
    return out


README = """Clawdy costume art / Diseños de disfraces de Clawdy

EN: Copy a file from "templates" into this folder (e.g. witch.png), open it in a
pixel art editor such as Pixelorama (free), edit it and save. Clawdy picks it
up within seconds. Images are 32x32; each pixel is half a Clawdy pixel. Use
_clawdy-reference.png as a guide layer to see where the body is. Files named
<costume>_back.png are drawn behind Clawdy. Delete a file to go back to the
built-in costume. Names: witch, pumpkin, ghost, vampire, frank, santa, none.

ES: Copia un archivo de "templates" a esta carpeta (por ejemplo witch.png),
ábrelo en un editor de pixel art como Pixelorama (gratis), edítalo y guarda.
Clawdy lo usa en unos segundos. Las imágenes son de 32x32; cada pixel es medio
pixel de Clawdy. Usa _clawdy-reference.png como capa guía para ver dónde está
el cuerpo. Los archivos <disfraz>_back.png se dibujan detrás de Clawdy. Borra
un archivo para volver al disfraz original. Nombres: witch (bruja), pumpkin
(calabaza), ghost (fantasma), vampire (vampiro), frank (Frankenstein),
santa (Noel), none (sin disfraz).
"""


class _Proxy:
    """The widget, except that drawing goes to a Recorder."""

    def __init__(self, widget, rec):
        self._w, self._rec = widget, rec

    def __getattr__(self, name):
        if name in ("px_rect", "poly", "oval"):
            return getattr(self._rec, name)
        if name == "skins":                # export the costumes as coded, not a user's drawing
            return _NoSkins
        return getattr(self._w, name)


class _NoSkins:
    @staticmethod
    def runs(costume, layer):
        return None


class Skins:
    """Loads costume PNGs on demand and notices when they are edited."""

    def __init__(self, tk_module):
        self.tk = tk_module
        self.cache = {}                    # path -> (mtime, runs)

    def runs(self, costume, layer):
        name = costume + ("_back" if layer == "back" else "") + ".png"
        for path in (os.path.join(folder(), name), cs.resource("assets", "skins", name)):
            try:
                mtime = os.path.getmtime(path)       # the user's drawing first, then the built-in one
                break
            except OSError:
                self.cache.pop(path, None)
        else:
            return None
        hit = self.cache.get(path)
        if hit and hit[0] == mtime:
            return hit[1]
        try:
            runs = self.load(path)
        except Exception:
            runs = None                    # half-saved or not a PNG: keep the code costume
        self.cache[path] = (mtime, runs)
        return runs

    def load(self, path):
        """[(x, y, w, h, '#rrggbb')] in scene units: runs of same-color pixels per row."""
        img = self.tk.PhotoImage(file=path)
        w, h = min(img.width(), 64), min(img.height(), 64)
        out = []
        for py in range(h):
            run = None
            for px in range(w + 1):
                col = None
                if px < w and not img.transparency_get(px, py):
                    r, g, b = img.get(px, py)[:3]
                    col = "#%02x%02x%02x" % (r, g, b)
                if run and col == run[1]:
                    run[2] += 1
                    continue
                if run:
                    out.append((run[0], py, run[2], 1, run[1]))
                run = [px, col, 1] if col else None
        merged = []                        # identical runs in consecutive rows become one block
        for x, y, n, _, col in out:
            for m in merged:
                if m[0] == x and m[2] == n and m[4] == col and m[1] + m[3] == y:
                    m[3] += 1
                    break
            else:
                merged.append([x, y, n, 1, col])
        return [(X0 + x * CELL, Y0 + y * CELL, n * CELL, h * CELL, col) for x, y, n, h, col in merged]
