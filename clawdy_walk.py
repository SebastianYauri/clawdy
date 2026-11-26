"""Desktop walks: now and then Clawdy leaves its porthole for a little trip.

Windows: rappels down a rope to the taskbar, strolls along it, throws the rope
back up and climbs home. Linux and macOS: jumps up and hangs from the top of
the screen (below the top bar / menu bar), swings along it hand over hand, then
slides down a rope back into the porthole.

In costume it goes out its own way: the vampire flies off as a bat, the ghost
floats around (and says boo), the witch rides her broom, the pumpkin bounces,
Frankenstein stomps with its arms out, and Santa and the reindeer take the sleigh: it
lifts off from the porthole, crosses the top of the screen, comes round from the other
side and lands back home (frames pre-rendered in 3D, assets/anim/sleigh).

Clawdy travels in its own small borderless window (color key on Windows, real
transparency on macOS, the X SHAPE extension on Linux) and the rope is a thin
window of its own, so nothing ever has to be resized smoothly but the rope.
"""
import math
import random
import re
import subprocess
import sys

WIN = sys.platform == "win32"
MAC = sys.platform == "darwin"

ORANGE, ORANGE_D, DARK = "#d97757", "#b35c42", "#1a1412"
ROPE = "#c08b52"
GW, GH = 16, 16                       # the sprite grid, in sprite pixels (one = one Clawdy pixel)
OX, OY = 1, 7                         # where the 14x9 sprite sits in the grid (room for hats above)


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


# ---------------------------------------------------------------- screen edges

def _monitor_windows(x, y):
    import ctypes
    from ctypes import wintypes

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]
    user32 = ctypes.windll.user32
    user32.MonitorFromPoint.restype = wintypes.HANDLE
    mon = user32.MonitorFromPoint(wintypes.POINT(int(x), int(y)), 2)
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    user32.GetMonitorInfoW(mon, ctypes.byref(info))
    m, wk = info.rcMonitor, info.rcWork
    floor = wk.bottom if wk.bottom < m.bottom else m.bottom
    return (m.left, m.top, m.right, m.bottom), floor


def _monitors_linux():
    """[(rect, is_primary)] from xrandr (XWayland answers too)."""
    mons = []
    out = subprocess.run(["xrandr", "--listmonitors"], capture_output=True, text=True, timeout=3).stdout
    for line in out.splitlines():
        m = re.search(r"(\*?)\S*\s+(\d+)/\d+x(\d+)/\d+\+(\d+)\+(\d+)", line)
        if m:
            w, h, mx, my = map(int, m.groups()[1:])
            mons.append(((mx, my, mx + w, my + h), "*" in line.split()[1]))
    return mons


def _monitors_mac():
    from AppKit import NSScreen
    screens = NSScreen.screens()
    h0 = screens[0].frame().size.height
    mons = []
    for i, s in enumerate(screens):
        f = s.frame()
        left, top = f.origin.x, h0 - (f.origin.y + f.size.height)
        mons.append(((left, top, left + f.size.width, top + f.size.height), i == 0))
    return mons


def _monitors_windows():
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    proc = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HMONITOR, wintypes.HDC,
                              ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
    mons = []

    def cb(hmon, hdc, lprc, lparam):
        r = lprc.contents
        mons.append(((r.left, r.top, r.right, r.bottom), r.left == 0 and r.top == 0))
        return 1
    user32.EnumDisplayMonitors(None, None, proc(cb), 0)
    return mons


def monitors(sw, sh):
    """Every monitor as (rect, is_primary); the whole screen when the system won't say."""
    try:
        mons = (_monitors_windows if WIN else _monitors_mac if MAC else _monitors_linux)()
    except Exception:
        mons = []
    return mons or [((0, 0, sw, sh), True)]


def nearest_monitor(mons, x, y):
    """The monitor under a point, else the closest one: a point left in the void when a
    screen was unplugged or moved still gets a real monitor."""
    for rect, _ in mons:
        if rect[0] <= x < rect[2] and rect[1] <= y < rect[3]:
            return rect
    def dist(rect):
        dx = max(rect[0] - x, 0, x - rect[2] + 1)
        dy = max(rect[1] - y, 0, y - rect[3] + 1)
        return dx * dx + dy * dy
    return min((rect for rect, _ in mons), key=dist)


def _monitor_linux(x, y, sw, sh):
    mons = monitors(sw, sh)
    rect = nearest_monitor(mons, x, y)
    is_primary = next((p for r, p in mons if r == rect), False)
    panel = 0
    try:
        out = subprocess.run(["xprop", "-root", "_NET_WORKAREA"], capture_output=True, text=True, timeout=3).stdout
        vals = [int(v) for v in re.findall(r"\d+", out.split("=", 1)[1])][:4]
        primary = next((r for r, p in mons if p), None)
        if primary and 0 < vals[1] - primary[1] < 120:
            panel = vals[1] - primary[1]          # GNOME's top bar on the primary monitor
    except Exception:
        pass
    return rect, rect[1] + (panel if is_primary else 0)


def _monitor_mac(x, y, sw, sh):
    try:
        from AppKit import NSScreen
        screens = NSScreen.screens()
        h0 = screens[0].frame().size.height
        rects = []
        for s in screens:
            f, v = s.frame(), s.visibleFrame()
            left, top = f.origin.x, h0 - (f.origin.y + f.size.height)
            inset = (f.origin.y + f.size.height) - (v.origin.y + v.size.height)
            rects.append(((left, top, left + f.size.width, top + f.size.height), top + inset))
        rect = nearest_monitor([(r, False) for r, _ in rects], x, y)
        return rect, next(t for r, t in rects if r == rect)
    except Exception:
        pass
    return (0, 0, sw, sh), 30


# ---------------------------------------------------------------- the sprite

FLIERS = ("vampire", "ghost", "witch", "pumpkin")   # these leave by air instead of the rope
SLEIGH = ("santa", "reindeer")                      # these take the sleigh
FLOORED = ("frank", "snowman", "tree", "gingerbread")   # these go along the bottom of the screen, each its way
SLEIGH_FRAMES = 12
SLEIGH_SEAT = (51, 14)                              # where Clawdy sits in a sleigh frame (grid units)
SLEIGH_PX = 0.5                                     # a sleigh image pixel is half a grid unit (fine detail)


def sleigh_frames(widget):
    """The sleigh's frames as rect runs, or None if the files aren't there."""
    import clawdy_system as cs
    from clawdy_skins import frame_runs
    out = []
    try:
        for i in range(SLEIGH_FRAMES):
            runs, w, h = frame_runs(widget.skins.tk, cs.resource("assets", "anim", "sleigh", "%d.png" % i))
            out.append(runs)
        return out, w, h
    except Exception:
        return None


def bat(frame, blink=False):
    body, wing, rim, eye = "#2a1d33", "#4a3260", "#7a5a96", "#ff4a4a"
    R = [(OX + 5, OY + 3, 4, 4, body), (OX + 5, OY + 2, 1, 1, body), (OX + 8, OY + 2, 1, 1, body)]
    if frame % 2:                                       # wings up
        for d, x in ((-1, OX + 1), (1, OX + 9)):
            R += [(x, OY + 2, 4, 2, wing), (x + (0 if d < 0 else 3), OY, 1, 2, rim),
                  (x + (1 if d < 0 else 2), OY + 1, 1, 1, wing)]
    else:                                               # wings down
        for d, x in ((-1, OX + 1), (1, OX + 9)):
            R += [(x, OY + 4, 4, 2, wing), (x + (0 if d < 0 else 3), OY + 6, 1, 2, rim),
                  (x + (1 if d < 0 else 2), OY + 6, 1, 1, wing)]
    if not blink:
        R += [(OX + 6, OY + 4, 1, 1, eye), (OX + 7, OY + 4, 1, 1, eye)]
    return R


def ghost(frame, boo=False, blink=False, look=0):
    white, shade, dark = "#f2f2f8", "#c9cad6", "#151217"
    R = [(OX + 3, OY - 1, 8, 1, white), (OX + 2, OY, 10, 7, white), (OX + 1, OY + 3, 1, 2, white),
         (OX + 12, OY + 3 - (2 if boo else 0), 1, 2, white), (OX + 1, OY + 3 - (2 if boo else 0), 1, 2, white)]
    for i in range(5):                                  # wavy hem
        R.append((OX + 2 + i * 2, OY + 7, 2, 1 + (i + frame) % 2, white if i % 2 else shade))
    if boo:
        R += [(OX + 4, OY + 1, 2, 3, dark), (OX + 8, OY + 1, 2, 3, dark), (OX + 6, OY + 4, 2, 2, dark)]
    elif not blink:
        R += [(OX + 4 + look, OY + 2, 1, 2, dark), (OX + 9 + look, OY + 2, 1, 2, dark)]
    return R


def pose(kind, frame=0, look=0, blink=False, costume="none", col=None, wear=((), ())):
    """Rectangles (x, y, w, h, color) in sprite pixels on the GW x GH grid.
    `wear` is (behind, in front): the character's parts, from wear_from()."""
    if kind == "bat":
        return bat(frame, blink)
    if kind in ("ghost", "boo"):
        return ghost(frame, kind == "boo", blink, look)
    back, front = wear[0], wear[1]
    paint = wear[2] if len(wear) > 2 else None
    return (list(back) + painted(plain(kind, frame, look, blink, col), paint, col) + list(front)
            + (broom() if kind == "broom" else []))


def painted(rects, paint, col=None):
    """Body, arm and leg rectangles take the costume's colours cell by cell (looked up at the
    limb's rest position, so a raised arm keeps its sleeve)."""
    if not paint:
        return rects
    body, body_d = (col or (ORANGE, ORANGE_D))[:2]
    out = []
    for x, y, w, h, c in rects:
        if c == body_d and w == 1:                                                         # a leg
            rest_y = lambda cy: min(max(cy, OY + 7), OY + 8)
            rest_x = lambda cx: cx
        elif c == body and (w, h) != (10, 7):                                              # an arm
            left = x < OX + 6
            rest_x = (lambda cx: min(max(cx, OX), OX + 1)) if left else (lambda cx: min(max(cx, OX + 12), OX + 13))
            rest_y = lambda cy: min(max(cy, OY + 3), OY + 4)
        elif c == body:                                                                    # the body
            rest_x = lambda cx: cx
            rest_y = lambda cy: cy
        else:
            out.append((x, y, w, h, c))
            continue
        for cy in range(y, y + h):
            for cx in range(x, x + w):
                out.append((cx, cy, 1, 1, paint.get((rest_x(cx), rest_y(cy)), c)))
    return out


def wear_from(widget):
    """The character's parts as grid rectangles: every 2×2 block of a 32×32 part
    image is one Clawdy pixel, so they land exactly on the walking sprite."""
    import clawdy_character as character
    from clawdy_gui import BODY_CELLS
    cells = {(r // 2, c // 2) for r, c in BODY_CELLS}      # the walk's grid is one Clawdy pixel per cell
    ch = widget.character_now()
    skins = widget.skin_paths(ch)
    out, paint = [], {}
    for layer in ("back", "front"):
        rects = []
        for path in character.layers(ch, layer):
            try:
                pix = widget.skins.pixels(path)
            except Exception:
                continue
            on_body = layer == "front" and path in skins
            for (sx, sy), colr in pix.items():
                if sx % 2 or sy % 2:
                    continue                           # one sample per Clawdy pixel
                x, y = OX + (sx - 2) // 2, OY + (sy - 12) // 2
                if not (0 <= x < GW and 0 <= y < GH):
                    continue
                if on_body and (y - OY, x - OX) in cells:
                    paint[(x, y)] = colr               # moves with the limb
                else:
                    rects.append((x, y, 1, 1, colr))
        out.append(rects)
    out.append(paint)
    return tuple(out)


def broom():
    return [(0, OY + 7, 11, 1, "#8a5a2b"), (11, OY + 6, 3, 3, "#d9b25a"), (14, OY + 6, 2, 3, "#b88a3a")]


def plain(kind, frame=0, look=0, blink=False, col=None):
    ORANGE, ORANGE_D, DARK = col or (globals()["ORANGE"], globals()["ORANGE_D"], globals()["DARK"])
    R = [(OX + 2, OY, 10, 7, ORANGE)]                                   # body
    ey, eh = (OY + 3, 1) if blink else (OY + 2, 2)
    eyes = [(OX + 4 + look, ey, 1, eh, DARK), (OX + 9 + look, ey, 1, eh, DARK)]
    legs_x = [OX + 3, OX + 5, OX + 8, OX + 10]
    legs = [(lx, OY + 7, 1, 2, ORANGE_D) for lx in legs_x]
    arms = [(OX, OY + 3, 2, 2, ORANGE), (OX + 12, OY + 3, 2, 2, ORANGE)]
    if kind in ("walk", "stomp"):
        # a four-frame cycle: contact (all feet down, body low), pass (one pair up, body bobs
        # up, arms swing), contact, pass with the other pair
        f = frame % 4
        passing = f % 2 == 1
        up = () if not passing else ((0, 2) if f == 1 else (1, 3))
        legs = [(lx, OY + 6 if passing else OY + 7, 1, (1 if i in up else 3) if passing else 2, ORANGE_D)
                for i, lx in enumerate(legs_x)]
        if passing:
            R = [(OX + 2, OY - 1, 10, 7, ORANGE)]
            eyes = [(x, y - 1, w, h, c) for x, y, w, h, c in eyes]
        if kind == "walk":
            swing = (0 if not passing else (-1 if f == 1 else 1))
            arms = [(OX, OY + 3 + swing - (1 if passing else 0), 2, 2, ORANGE),
                    (OX + 12, OY + 3 - swing - (1 if passing else 0), 2, 2, ORANGE)]
        else:                                    # Frankenstein: stiff legs, arms straight out front
            arms = [(OX, OY + (0 if passing else 1), 2, 3, ORANGE), (OX + 12, OY + (0 if passing else 1), 2, 3, ORANGE)]
    elif kind == "wave":
        arms = [arms[0], (OX + 12, OY + (0 if frame % 2 else 1), 2, 2, ORANGE)]
    elif kind == "hang":                      # both hands on the edge above
        a = frame % 2
        arms = [(OX, a, 2, OY + 5 - a, ORANGE), (OX + 12, 1 - a, 2, OY + 4 + a, ORANGE)]
    elif kind == "hang1":                     # one hand on the edge, waving with the other
        arms = [(OX, 0, 2, OY + 5, ORANGE), (OX + 12, OY + (0 if frame % 2 else 1), 2, 2, ORANGE)]
    elif kind == "broom":                     # riding: legs tucked, hands on the stick
        legs = [(lx, OY + 7, 1, 1, ORANGE_D) for lx in legs_x]
        arms = [(OX + 1, OY + 5, 2, 2, ORANGE), (OX + 11, OY + 5, 2, 2, ORANGE)]
    elif kind == "hop":                       # 0: crouch, 1: in the air (legs tucked), 2: landing squash
        if frame in (0, 2):
            R = [(OX + 1, OY + 1, 12, 6, ORANGE)]
            eyes = [(x, y + 1, w, h, c) for x, y, w, h, c in eyes]
            arms = [(OX - 1, OY + 4, 2, 2, ORANGE), (OX + 13, OY + 4, 2, 2, ORANGE)]
            legs = [(lx, OY + 7, 1, 2, ORANGE_D) for lx in legs_x]
        else:
            legs = [(lx, OY + 7, 1, 1, ORANGE_D) for lx in legs_x]
            arms = [(OX, OY + 2, 2, 2, ORANGE), (OX + 12, OY + 2, 2, 2, ORANGE)]
    elif kind in ("climb", "slide"):          # holding the rope in the middle
        a = frame % 2 if kind == "climb" else 0
        arms = [(OX + 5, a, 1, OY - a, ORANGE), (OX + 8, 1 - a if kind == "climb" else 0,
                                                   1, OY - (1 - a if kind == "climb" else 0), ORANGE)]
        legs = [(OX + 5, OY + 7, 1, 2 - (frame % 2 if kind == "climb" else 0), ORANGE_D),
                (OX + 8, OY + 7, 1, 1 + (frame % 2 if kind == "climb" else 1), ORANGE_D)]
    return R + arms + legs + eyes


# ---------------------------------------------------------------- the trip

class Walk:
    def __init__(self, widget):
        self.w = widget
        self.root = widget.root
        k = widget.k
        self.p = p = max(3, round(3.7 * k))
        self.t = 0.0
        self.i = 0
        self.wave_until = 0.0
        self.trail = []
        self.costume = widget.costume()
        self.gw, self.gh, self.frames = GW, GH, None
        self.fs = 1.0                            # grid units per frame pixel
        if self.costume in SLEIGH:
            got = sleigh_frames(widget)
            if got:
                self.frames, fw, fh = got
                self.fs = SLEIGH_PX if fw > 64 else 1.0
                self.gw, self.gh = fw * self.fs, fh * self.fs
        self.pw, self.ph = round(self.gw * p), round(self.gh * p)
        self.colors = widget.body_colors()
        self.wear = wear_from(widget)
        self.shaper = None
        self._last_key = None

        root = self.root
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        cw, h = round(104 * k), round(114 * k)
        wx, wy = root.winfo_rootx(), root.winfo_rooty()
        self.pcx = wx + 52 * k                   # porthole center
        self.pcy = wy + 54 * k
        self.wb = wy + h                         # widget bottom
        if self.frames:                          # the sleigh: across the top of the screen
            self.mon, top = ((_monitor_windows(self.pcx, self.pcy)[0], None) if WIN
                             else (_monitor_mac if MAC else _monitor_linux)(self.pcx, self.pcy, sw, sh))
            self.lane = (top if top is not None else self.mon[1]) + 24 * k
            self.mode = "sleigh"
        elif self.costume in FLIERS:             # by air: no rope, any system
            self.mon = ((_monitor_windows(self.pcx, self.pcy)[0]) if WIN
                        else (_monitor_mac if MAC else _monitor_linux)(self.pcx, self.pcy, sw, sh)[0])
            self.mode = "fly"
        elif WIN:
            self.mon, self.floor = _monitor_windows(self.pcx, self.pcy)
            self.mode = "floor"
        elif self.costume in FLOORED:            # on the floor everywhere: the bottom of the screen
            self.mon = (_monitor_mac if MAC else _monitor_linux)(self.pcx, self.pcy, sw, sh)[0]
            self.floor = self.mon[3] - (70 * k if MAC else 4 * k)     # above the Dock on macOS
            self.mode = "floor"
        else:
            self.mon, self.ceil = (_monitor_mac if MAC else _monitor_linux)(self.pcx, self.pcy, sw, sh)
            self.mode = "ceiling"
        room = self.pcx - self.mon[0] - self.pw
        self.D = max(0.0, min(180 * k, room))
        self.v = {"gingerbread": 170, "snowman": 45, "tree": 60}.get(self.costume, 70) * k

        x0 = self.pcx - self.pw / 2
        if self.mode == "sleigh":
            self.x0, self.y0 = self.pcx - SLEIGH_SEAT[0] * p, self.pcy - SLEIGH_SEAT[1] * p
            self.v = 190 * k
            self.out = min(160 * k, max(0.0, self.mon[2] - self.x0 - self.pw))
            self.phases = [("up", 2.0), ("cross", max(0.5, (self.mon[2] - (self.x0 + self.out)) / self.v)),
                           ("wrap", max(0.5, (self.x0 - self.out - self.mon[0] + self.pw) / self.v)), ("land", 2.2)]
        elif self.mode == "fly":
            self.D = max(0.0, min(320 * k, room))
            self.phases = [("out", 2.4), ("loop", 3.6), ("home", 2.4)]
            self.x0, self.y0 = x0, self.pcy - self.ph / 2
        elif self.mode == "floor":
            stand = self.floor - self.ph
            drop = max(0.0, stand - self.wb)
            self.phases = [("rappel", 1.0 + drop / 420), ("land", 0.4), ("walk", self.D / self.v),
                           ("look", 1.6), ("wave", 1.4), ("back", self.D / self.v),
                           ("throw", 0.6), ("climb", 1.2 + drop / 260)]
            self.x0, self.stand = x0, stand
        else:
            self.phases = [("jump", 0.6), ("swing", self.D / (self.v * 0.9)), ("dangle", 2.0),
                           ("swingback", self.D / (self.v * 0.9)), ("rappel", 1.3)]
            self.x0 = x0

        import tkinter as tk
        self.win = tk.Toplevel(root)
        self.canvas = widget.make_window(self.win, self.pw, self.ph)
        self.canvas.bind("<Button-1>", self.poke)
        self.rope = tk.Toplevel(root)
        self.rope.overrideredirect(True)
        try:
            self.rope.wm_attributes("-topmost", True)
        except tk.TclError:
            pass
        self.rope.config(bg=ROPE)
        self.rope.withdraw()
        self.rope_shown = False
        self.rope_w = max(2, p // 2 + 1)
        self.win.update_idletasks()
        if not widget.keyed and sys.platform.startswith("linux"):
            try:
                from clawdy_gui import Shaper
                self.shaper = Shaper(self.win)
            except Exception:
                self.shaper = None

    # -------- helpers --------

    def poke(self, ev=None):
        self.wave_until = self.t + 1.2

    def draw(self, kind, x, y, frame=0, look=0, lean=0.0, extra=()):
        if self.t < self.wave_until and kind in ("walk", "stand", "look"):
            kind = "wave"
        blink = (self.t % 3.3) < 0.12
        if kind == "walk" and self.costume == "frank":
            kind = "stomp"
        rects = pose(kind, frame, look, blink, self.costume, self.colors, self.wear)
        if lean:                                 # shear: the top drifts one way, the feet the other
            rects = [(rx + round(lean * (OY + 3 - (ry + rh / 2)) / 3), ry, rw, rh, col) for rx, ry, rw, rh, col in rects]
        rects = list(extra) + rects
        key = (kind, frame, look, blink, round(lean, 1), len(extra))
        if key != self._last_key:
            self._last_key = key
            c, p = self.canvas, self.p
            c.delete("all")
            for rx, ry, rw, rh, col in rects:
                c.create_rectangle(rx * p, ry * p, (rx + rw) * p, (ry + rh) * p, fill=col, width=0)
            if self.shaper:
                try:
                    self.shaper.set([(rx * p, ry * p, rw * p, rh * p) for rx, ry, rw, rh, _ in rects
                                     if rw > 0 and rh > 0])
                except Exception:
                    self.shaper = None
        self.win.geometry("+%d+%d" % (round(x), round(y)))

    def rope_span(self, x, top, bottom):
        hgt = round(bottom - top)
        if hgt < 2:
            self.hide_rope()
            return
        self.rope.geometry("%dx%d+%d+%d" % (self.rope_w, hgt, round(x + 8 * self.p - self.rope_w / 2), round(top)))
        if not self.rope_shown:                  # map it once, then only move/resize it
            self.rope_shown = True
            self.rope.deiconify()
            self.win.lift()

    def hide_rope(self):
        if self.rope_shown:
            self.rope_shown = False
            self.rope.withdraw()

    # -------- the timeline --------

    def step(self, dt):
        """Advance the trip. Returns False when Clawdy is back home."""
        self.t += dt
        while self.i < len(self.phases) and self.t >= sum(d for _, d in self.phases[:self.i + 1]):
            self.i += 1
        if self.i >= len(self.phases):
            return False
        name, dur = self.phases[self.i]
        q = (self.t - sum(d for _, d in self.phases[:self.i])) / dur if dur > 0 else 1.0
        frame = int(self.t * 8)
        {"floor": self.floor_step, "ceiling": self.ceiling_step, "fly": self.fly_step,
         "sleigh": self.sleigh_step}[self.mode](name, q, frame)
        return True

    def sleigh_step(self, name, q, frame):
        """Takes off from the porthole in an accelerating arc, crosses the top of the screen with
        a long swoop, comes round from the other side and glides down to land, flaring at the end."""
        x0, y0, lane, out, k = self.x0, self.y0, self.lane, self.out, self.w.k
        gh = self.gh
        if name == "up":                         # ease in: slow at first, then away
            e = q * q * (3 - 2 * q)
            ex = q * q
            x = x0 + out * ex
            y = y0 + (lane - y0) * e - math.sin(q * math.pi) * 10 * k      # a small overshoot above the lane
        elif name == "cross":                    # a swoop: dips a little, then climbs
            x = x0 + out + (self.mon[2] - (x0 + out)) * q
            y = lane + math.sin(q * math.pi) * 34 * k
        elif name == "wrap":
            x = self.mon[0] - self.pw + (x0 - out - self.mon[0] + self.pw) * q
            y = lane + math.sin(q * math.pi) * 22 * k
        else:                                    # ease out: glides in, flares, lands softly
            e = 1 - (1 - q) ** 3
            x = x0 - out + out * e
            y = lane + (y0 - lane) * e + math.sin(q * math.pi) * 8 * k
        bob = math.sin(self.t * 2.4) * 3 * k
        # magic dust streams off the runners and drifts down behind
        self.trail = [(tx, ty + (self.t - born) * 6, col, born) for tx, ty, col, born in self.trail if self.t - born < 0.9]
        if int(self.t * 30) % 2 == 0:
            self.trail.append((random.uniform(0, 14), random.uniform(gh * 0.55, gh * 0.85),
                               random.choice(("#ffd75a", "#ffffff", "#8cd9ff", "#ffb347")), self.t))
        self.draw_frame(int(self.t * 12) % len(self.frames), x, y + bob,
                        extra=[(round(tx), round(ty), 1, 1, col) for tx, ty, col, _ in self.trail if ty < gh])

    def draw_frame(self, i, x, y, extra=()):
        key = ("frame", i, tuple(extra))
        if key != self._last_key:
            self._last_key = key
            c, p, fs = self.canvas, self.p, self.fs
            c.delete("all")
            rects = [(rx * fs, ry * fs, rw * fs, rh * fs, col) for rx, ry, rw, rh, col in self.frames[i]] + list(extra)
            boxes = []
            for rx, ry, rw, rh, col in rects:
                x0, y0, x1, y1 = round(rx * p), round(ry * p), round((rx + rw) * p), round((ry + rh) * p)
                c.create_rectangle(x0, y0, x1, y1, fill=col, width=0)
                boxes.append((x0, y0, x1 - x0, y1 - y0))
            if self.shaper:
                try:
                    self.shaper.set(boxes)
                except Exception:
                    self.shaper = None
        self.win.geometry("+%d+%d" % (round(x), round(y)))

    def fly_step(self, name, q, frame):
        """Out to the left by air, a loop there, and back into the porthole."""
        x0, y0, D, k, c = self.x0, self.y0, self.D, self.w.k, self.costume
        lift = {"witch": 110, "vampire": 80, "ghost": 60, "pumpkin": 0}[c] * k
        cx, cy = x0 - D, y0 - lift
        if name == "out":
            e = ease(q)
            x, y = x0 - D * e, y0 - lift * math.sin(e * math.pi / 2)
        elif name == "loop":                     # a figure eight
            a = q * 2 * math.pi
            x, y = cx + math.sin(a) * 60 * k, cy - math.sin(2 * a) * 26 * k
        else:
            e = ease(q)
            x, y = cx + D * e, cy + lift * (1 - math.cos(e * math.pi / 2))
        if c == "vampire":
            self.draw("bat", x, y + math.sin(self.t * 9) * 4 * k, int(self.t * 9))
        elif c == "ghost":
            boo = name == "loop" and 0.42 < q < 0.62
            self.alpha(1.0 if boo else 0.78 + 0.12 * math.sin(self.t * 4))
            self.draw("boo" if boo else "ghost", x, y + math.sin(self.t * 3) * 5 * k, int(self.t * 4))
        elif c == "witch":
            lean = math.cos(q * 2 * math.pi) if name == "loop" else (-1 if name == "out" else 1) * 0.8
            swoop = math.sin(self.t * 4) * 6 * k
            self.trail = [(tx, ty, col, born) for tx, ty, col, born in self.trail if self.t - born < 0.5]
            if int(self.t * 20) % 2 == 0:
                self.trail.append((random.randint(10, 15), random.randint(OY + 4, OY + 9),
                                   random.choice(("#c77dff", "#ffd75a", "#8cd9ff")), self.t))
            self.draw("broom", x, y + swoop, lean=lean, extra=[(tx, ty, 1, 1, col) for tx, ty, col, _ in self.trail])
        else:                                    # pumpkin: bounces along
            hop = abs(math.sin(self.t * 4.2))
            self.draw("hop" if hop > 0.25 else ("stand" if hop > 0.1 else "hop"), x, y - hop * 46 * k,
                      1 if hop > 0.25 else 2)

    def alpha(self, a):
        try:
            self.win.attributes("-alpha", a)
        except Exception:
            pass

    def floor_step(self, name, q, frame):
        x0, stand, wb, D, ph = self.x0, self.stand, self.wb, self.D, self.ph
        if name == "rappel":
            y = lerp(wb, stand, ease(q))
            self.rope_span(x0, wb, y + self.p)
            self.draw("slide", x0, y)
        elif name == "land":
            self.rope_span(x0, lerp(wb, stand, ease(q)), stand + self.p)
            self.draw("stand", x0, stand)
        elif name == "walk":
            self.hide_rope()
            self.gait(x0 - D * q, stand, frame, -1)
        elif name == "look":
            self.draw("look", x0 - D, stand, look=-1 if q < 0.5 else 1)
        elif name == "wave":
            self.draw("wave", x0 - D, stand, frame)
        elif name == "back":
            self.gait(x0 - D * (1 - q), stand, frame, 1)
        elif name == "throw":
            self.rope_span(x0, lerp(stand, wb, ease(q)), stand + self.p)
            self.draw("slide", x0, stand)
        elif name == "climb":
            y = lerp(stand, wb, ease(q))
            self.rope_span(x0, wb, y + self.p)
            self.draw("climb", x0, y, frame)

    def gait(self, x, stand, frame, d):
        """Along the floor, each costume its own way."""
        c, k = self.costume, self.w.k
        if c == "tree":                          # hops as one piece
            q = (self.t * 2.4) % 1
            air = math.sin(q * math.pi)
            self.draw("hop", x, stand - air * 26 * k, 0 if q < 0.08 else (1 if q < 0.85 else 2))
        elif c == "snowman":                     # slides, rocking, no steps
            self.draw("stand", x, stand - abs(math.sin(self.t * 4)) * 2 * k, lean=math.sin(self.t * 4) * 0.5)
        elif c == "gingerbread":                 # runs for it
            self.draw("walk", x, stand - abs(math.sin(self.t * 18)) * 3 * k, int(self.t * 16), lean=d * 0.6)
        else:
            self.draw("walk", x, stand, frame)

    def ceiling_step(self, name, q, frame):
        x0, ceil, D, k = self.x0, self.ceil, self.D, self.w.k
        start_y = self.pcy - self.ph / 2
        sway = math.sin(self.t * 3.2) * 3 * k
        if name == "jump":
            y = lerp(start_y, ceil, ease(q)) - math.sin(q * math.pi) * 18 * k
            self.draw("hang", x0, y)
        elif name == "swing":
            self.draw("hang", x0 - D * q + sway, ceil, int(self.t * 4))
        elif name == "dangle":
            self.draw("hang1", x0 - D + sway * 0.5, ceil, frame)
        elif name == "swingback":
            self.draw("hang", x0 - D * (1 - q) + sway, ceil, int(self.t * 4))
        elif name == "rappel":
            y = lerp(ceil, start_y + self.ph * 0.2, ease(q))
            self.rope_span(x0, ceil, y + self.p)
            self.draw("slide", x0, y)

    def close(self):
        for win in (self.win, self.rope):
            try:
                win.destroy()
            except Exception:
                pass
