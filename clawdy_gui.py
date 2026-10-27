"""Clawdy's window: an animated Clawd with your Claude usage.

Drag with the left button, right-click for the menu.
"""
import json
import math
import os
import random
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import clawdy_system as cs
import clawdy_update as cu
from clawdy_i18n import STRINGS, t as tr
from clawdy_system import SESSIONS
from clawdy_tray import Tray
from clawdy_walk import Walk
from clawdy_version import VERSION

tk = None            # imported in run(): the hook doesn't need tkinter

URL = "https://api.anthropic.com/api/oauth/usage"
POLL = 300          # seconds between usage requests
UPDATE_EVERY = 6 * 3600             # look for new versions every 6 hours
FPS, FPS_FAST = 30, 60             # frames/s when idle and while the panel moves
# Compact view: a vertical column. Expanding opens a side panel (towards the
# free side of the screen); the column itself never moves.
CW, H = 104, 114                    # compact column
PW = 170                            # side panel
SCENE_W = 300                       # the scene is drawn at this width…
SCENE_K = 0.62                      # …and scaled down by this
RING_C = (52, 54)                   # ring center
RING_RS = (48, 43, 38)              # nested, thin, close to the edge
RING_W = 3.5
HAT_TOP = {"witch": -56, "santa": -52, "pumpkin": -38}   # sprite units; the body spans -27..27
HOP = 0.42                          # lower jumps: Clawdy lives inside the rings
REACH = 0.55                        # floating props are pulled closer…
PART_REACH = 0.6                    # …and particles too, so they fit in the porthole
FAR_PROPS = ("bubble", "balls", "bang", "err", "hammer", "broom", "crystal", "cauldron", "bulb")
# Each Claude Code state rotates through a few animations so long sessions stay fun.
VARIANTS = {"thinking": ("bubble", "bulb", "pace"), "typing": ("laptop", "coffee", "turbo"),
            "building": ("hammer", "terminal"), "reading": ("book", "magnifier"),
            "happy": ("confetti", "dance", "fireworks")}
VARIANT_SECS = 7.0
NAP_AFTER = 15 * 60                # no Claude Code activity for this long: take a nap
TRIP_EVERY = (10 * 60, 20 * 60)    # while you use Claude, now and then Clawdy goes for a walk
IN_USE_FOR = 10 * 60               # Claude Code activity this recent counts as "using Claude"
# Intro once fresh usage arrives: walk in carrying a ball, throw it down, rings fill up.
INTRO_WALK, INTRO_WIND, INTRO_FILL, INTRO_END = 1.4, 0.35, 0.9, 4.2
PLUS = (93, 11)                     # new chat button, in the free corner
PLUS_R = 9
INFO_Y = H - 7                      # bottom line: names, or what's going on
SIZES = ((0.8, "size.small"), (1.0, "size.normal"), (1.3, "size.large"))
OPEN_AFTER, CLOSE_AFTER, SPEED = 0.25, 0.4, 3.2    # s, s, views/s


def ease(t):
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def clamp(t):
    return max(0.0, min(1.0, t))

# ---------------------------------------------------------------- colors

CARD = (0.11, 0.10, 0.09)
ORANGE = (0.851, 0.467, 0.341)
ORANGE_D = (0.70, 0.36, 0.26)
DARK = (0.10, 0.08, 0.07)
TXT = (0.96, 0.93, 0.88)
DIM = (0.62, 0.59, 0.55)
KEY = "#ff00ff"      # color Windows makes transparent


def hx(rgb, a=1.0):
    """Tk color. The background is opaque, so alpha is blended against the card."""
    if a < 1.0:
        rgb = tuple(c * a + b * (1 - a) for c, b in zip(rgb, CARD))
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(c * 255))) for c in rgb)


# ---------------------------------------------------------------- Clawd

# X = body, E = eye, L = leg, A = arm
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
PX = 6
SW, SH = len(SPRITE[0]) * PX, len(SPRITE) * PX



def _sprite_blocks():
    """The sprite as a few rectangles: drawing 90 separate pixels per frame is slow.
    Returns [(part, row0, col0, row1, col1)]; eyes are separate."""
    parts = {}
    for r, row in enumerate(SPRITE):
        for c, ch in enumerate(row):
            if ch in "XE":
                key = "body"
            elif ch == "A":
                key = "arm_l" if c < len(row) // 2 else "arm_r"
            elif ch == "L":
                key = "leg%d" % c
            else:
                continue
            parts.setdefault(key, set()).add((r, c))
    blocks = []
    for key, cells in parts.items():
        runs = {}                       # runs per row…
        for r in sorted({r for r, _ in cells}):
            cols = sorted(c for rr, c in cells if rr == r)
            start = prev = cols[0]
            for c in cols[1:] + [None]:
                if c != (prev + 1 if prev is not None else None):
                    runs.setdefault((start, prev), []).append(r)
                    start = c
                prev = c
        for (c0, c1), rows in runs.items():   # …and identical consecutive rows merge
            r0 = prev = rows[0]
            for r in rows[1:] + [None]:
                if r != prev + 1:
                    blocks.append((key, r0, c0, prev, c1))
                    r0 = r
                prev = r
    return blocks


BLOCKS = _sprite_blocks()
EYES = [(r, c) for r, row in enumerate(SPRITE) for c, ch in enumerate(row) if ch == "E"]

# idle routine, when Claude Code isn't doing anything
ACTS = ["walk", "jump", "wave", "walk", "look", "spin", "dance", "special", "walk", "stretch", "flip"]

SPOOKY = ("witch", "pumpkin", "ghost", "vampire")
# In costume the special move shows up more often, plus its own "trick"
COSTUME_ACTS = ["walk", "special", "jump", "look", "trick", "special", "spin", "trick", "stretch", "flip"]
TRICKS = {"witch": "fly", "vampire": "bat", "ghost": "float", "pumpkin": "roll", "santa": "present"}
# Claude Code work props, in costume
THEMED = {("witch", "bubble"): "crystal", ("witch", "laptop"): "spellbook", ("witch", "book"): "spellbook",
          ("witch", "hammer"): "cauldron", ("santa", "laptop"): "gift"}
PALETTES = {
    "witch": [(0.75, 0.45, 0.95), (1.0, 0.85, 0.35), (0.55, 0.85, 1.0)],
    "pumpkin": [(0.95, 0.55, 0.15), (0.60, 0.35, 0.80), (0.45, 0.78, 0.32)],
    "ghost": [(0.95, 0.95, 1.0), (0.72, 0.74, 0.85), (0.60, 0.85, 1.0)],
    "vampire": [(0.88, 0.14, 0.20), (0.62, 0.55, 0.72), (0.95, 0.95, 0.95)],
    "santa": [(0.90, 0.16, 0.16), (0.22, 0.72, 0.32), (1.0, 1.0, 1.0), (1.0, 0.85, 0.35)],
}
MAGIC = [(0.75, 0.45, 0.95), (1.0, 0.85, 0.35), (0.55, 0.85, 1.0)]


def season(today=None):
    """Which holiday it is; picks the automatic costume."""
    d = today or datetime.now()
    md = (d.month, d.day)
    if (10, 15) <= md <= (11, 2):
        return "halloween"
    if md >= (12, 10) or md <= (1, 6):
        return "christmas"
    return None

def label(state, short=False):
    """What Clawdy is doing, in words. `short` fits the narrow column."""
    key = "act." + state
    if short and key + ".short" in STRINGS:
        key += ".short"
    return tr(key)


# how long a state lasts without new events (seconds)
TTL = {"happy": 5, "error": 3, "notification": 300}
PRIO = {"happy": 1, "thinking": 2, "reading": 3, "typing": 3, "building": 3, "sweeping": 3,
        "groove": 4, "juggling": 5, "error": 6, "notification": 7}
CODE = ["{", "}", ";", "<>", "/", "=", "()", "[]", "=>"]
CONFETTI = [(0.95, 0.4, 0.4), (0.4, 0.75, 0.95), (0.95, 0.85, 0.35), (0.5, 0.85, 0.5), (0.85, 0.5, 0.9)]


def read_activity(now):
    """The most relevant state across open Claude Code sessions."""
    best = None
    try:
        names = os.listdir(SESSIONS)
    except OSError:
        return None
    for name in names:
        if not name.endswith(".json"):
            continue
        path = os.path.join(SESSIONS, name)
        try:
            s = json.load(open(path))
        except Exception:
            continue
        state, ts = s.get("state"), s.get("ts", 0)
        if now - ts > 3600:
            try:
                os.remove(path)          # abandoned session
            except OSError:
                pass
            continue
        if not state or state == "idle" or now - ts > TTL.get(state, 300):
            continue
        subs = s.get("subagents", 0)
        if subs and state in ("thinking", "typing", "building", "reading"):
            state = "juggling" if subs >= 2 else "groove"
        if best is None or PRIO[state] > PRIO[best]:
            best = state
    return best


# ---------------------------------------------------------------- usage

class State:
    """The last known usage. Cached on disk so reopening the widget neither
    fires another request nor loses what was shown."""

    def __init__(self):
        self.data = None
        self.error = None
        self.updated = 0.0
        self.retry_at = 0.0
        self.need = None                    # "install" / "login" / "renew": Claude Code isn't ready
        self.load()

    def load(self):
        try:
            c = json.load(open(cs.USAGE_CACHE))
        except Exception:
            return
        self.data = c.get("data")
        self.updated = c.get("updated", 0)
        self.retry_at = c.get("retry_at", 0)
        if self.retry_at > time.time():
            self.error = tr("error.rate_limited")

    def save(self):
        try:
            cs.write_json(cs.USAGE_CACHE, {"data": self.data, "updated": self.updated,
                                           "retry_at": self.retry_at})
        except Exception:
            pass

    def fresh(self):
        return self.data is not None and time.time() - self.updated < POLL


def fetch(st):
    """One usage request. Returns "ok", "expired", "rate", "auth", "offline", "error" or "skip"."""
    if time.time() < st.retry_at or st.fresh():
        return "skip"
    try:
        tok, expires = cs.read_session()
        if expires and expires < time.time() + 20:
            st.error, st.need = tr("error.renew"), "renew"   # don't spend a request on a dead token
            return "expired"
        req = urllib.request.Request(URL, headers={
            "Authorization": "Bearer " + tok,
            "anthropic-beta": "oauth-2025-04-20",
            "User-Agent": "clawdy/" + VERSION})
        st.data = json.loads(urllib.request.urlopen(req, timeout=20).read())
        st.error, st.updated, st.retry_at, st.need = None, time.time(), 0, None
        st.save()
        return "ok"
    except urllib.error.HTTPError as e:
        if e.code == 429:
            try:
                wait = int(e.headers.get("retry-after") or 0)
            except ValueError:
                wait = 0
            st.retry_at = time.time() + max(wait, 300)
            st.error = tr("error.rate_limited")
            st.save()
            return "rate"
        if e.code == 401:
            st.error, st.need = tr("error.renew"), "renew"
            return "auth"
        st.error = "HTTP %d" % e.code
    except (FileNotFoundError, KeyError):
        st.need = "login" if cs.claude_code_path() else "install"   # e.g. only the desktop app
        st.error = tr("need." + st.need)
        return "auth"
    except (urllib.error.URLError, OSError):
        st.error = tr("error.offline")
        return "offline"
    except Exception as e:
        st.error = str(e)[:40]
    return "error"


def demo_data():
    now = datetime.now(timezone.utc)
    iso = lambda h: (now + timedelta(hours=h)).isoformat()
    return {"limits": [
        {"kind": "session", "percent": 34, "resets_at": iso(3.4)},
        {"kind": "weekly_all", "percent": 58, "resets_at": iso(61)},
        {"kind": "weekly_scoped", "percent": 76, "resets_at": iso(61),
         "scope": {"model": {"display_name": "Opus"}}}]}


DEMO_STATES = [None, "thinking", "typing", "building", "reading", "groove",
               "juggling", "notification", "error", "sweeping", "happy"]


def until(iso):
    if not iso:
        return ""
    try:
        s = (datetime.fromisoformat(iso) - datetime.now(timezone.utc)).total_seconds()
    except ValueError:
        return ""
    if s <= 0:
        return tr("time.now")
    d, r = divmod(int(s), 86400)
    h, m = r // 3600, r % 3600 // 60
    return "%dd %dh" % (d, h) if d else ("%dh %dm" % (h, m) if h else "%dm" % m)


ORDER = {"session": 0, "weekly_all": 1, "weekly_scoped": 2, "spend": 3}


def bars(data):
    """[(label, percent, resets_at)] for whatever limits the account has.

    Session and weekly almost always; a per-model weekly limit (Fable, Opus…)
    only on some plans; and the monthly spend if paid extra usage is enabled."""
    found = []
    for lim in data.get("limits") or []:
        kind = lim.get("kind")
        if kind == "session":
            name = tr("limit.session")
        elif kind == "weekly_all":
            name = tr("limit.weekly")
        elif kind == "spend":
            name = tr("limit.extra")
        else:
            model = ((lim.get("scope") or {}).get("model") or {}).get("display_name")
            name = tr("limit.weekly_model", model=model) if model else tr("limit.other")
        pct, reset = float(lim.get("percent") or 0), lim.get("resets_at")
        if _passed(reset):                 # cached data from before a reset: it's 0 now
            pct, reset = 0.0, None
        found.append((ORDER.get(kind, 9), name, pct, reset))
    out = [(n, p, r) for _, n, p, r in sorted(found, key=lambda f: f[0])]
    if not out:
        for key, name in (("five_hour", tr("limit.session")), ("seven_day", tr("limit.weekly"))):
            w = data.get(key)
            if w:
                reset = w.get("resets_at")
                out.append((name, 0.0 if _passed(reset) else float(w.get("utilization") or 0),
                            None if _passed(reset) else reset))
    return out


def _passed(iso):
    try:
        return bool(iso) and datetime.fromisoformat(iso) <= datetime.now(timezone.utc)
    except ValueError:
        return False


def short_name(name):
    """A two or three letter name for the narrow column."""
    known = {tr("limit.session"): tr("short.session"), tr("limit.weekly"): tr("short.weekly"),
             tr("limit.extra"): tr("short.extra")}
    return known.get(name, name.replace(tr("limit.weekly") + " ", "")[:6])


def bar_color(p):
    if p >= 90:
        return (0.90, 0.30, 0.25)
    if p >= 70:
        return (0.95, 0.70, 0.25)
    return (0.45, 0.78, 0.45)


# ---------------------------------------------------------------- drawing

class Xform:
    """Translate + rotate + scale, for drawing the sprite."""

    def __init__(self, tx, ty, sx=1.0, sy=1.0, rot=0.0):
        self.tx, self.ty, self.sx, self.sy, self.rot = tx, ty, sx, sy, rot
        self.co, self.si = math.cos(rot), math.sin(rot)

    def pt(self, x, y):
        x, y = x * self.sx, y * self.sy
        return self.tx + x * self.co - y * self.si, self.ty + x * self.si + y * self.co


def rounded_rects(x, y, w, h, r):
    """A rounded rectangle as a list of rectangles (for SHAPE)."""
    r = int(max(0, min(r, w // 2, h // 2)))
    out = []
    for i in range(r):
        d = r - i - 0.5
        inset = int(round(r - math.sqrt(max(0.0, r * r - d * d))))
        out.append((x + inset, y + i, w - 2 * inset, 1))
        out.append((x + inset, y + h - 1 - i, w - 2 * inset, 1))
    out.append((x, y + r, w, h - 2 * r))
    return out


class Shaper:
    """Clips the visible area of a window (X11 and XWayland) with the SHAPE extension."""

    def __init__(self, root):
        import ctypes
        import ctypes.util
        c = ctypes
        x11 = c.cdll.LoadLibrary(c.util.find_library("X11") or "libX11.so.6")
        xext = c.cdll.LoadLibrary(c.util.find_library("Xext") or "libXext.so.6")
        x11.XOpenDisplay.restype = c.c_void_p
        x11.XOpenDisplay.argtypes = [c.c_char_p]
        x11.XFlush.argtypes = [c.c_void_p]
        xext.XShapeQueryExtension.argtypes = [c.c_void_p, c.POINTER(c.c_int), c.POINTER(c.c_int)]

        class XRect(c.Structure):
            _fields_ = [("x", c.c_short), ("y", c.c_short),
                        ("width", c.c_ushort), ("height", c.c_ushort)]

        xext.XShapeCombineRectangles.argtypes = [c.c_void_p, c.c_ulong, c.c_int, c.c_int, c.c_int,
                                                 c.POINTER(XRect), c.c_int, c.c_int, c.c_int]
        self.dpy = x11.XOpenDisplay(root.winfo_screen().encode())
        if not self.dpy:
            raise OSError("no X display")
        a, b = c.c_int(), c.c_int()
        if not xext.XShapeQueryExtension(self.dpy, c.byref(a), c.byref(b)):
            raise OSError("no SHAPE extension")
        # The outer Tk window must be clipped. For borderless windows "wm frame"
        # returns the inner one, so ask X for the parent.
        x11.XQueryTree.argtypes = [c.c_void_p, c.c_ulong, c.POINTER(c.c_ulong), c.POINTER(c.c_ulong),
                                   c.POINTER(c.POINTER(c.c_ulong)), c.POINTER(c.c_uint)]
        x11.XFree.argtypes = [c.c_void_p]
        inner = root.winfo_id()
        rt, parent, kids, n = c.c_ulong(), c.c_ulong(), c.POINTER(c.c_ulong)(), c.c_uint()
        if not x11.XQueryTree(self.dpy, inner, c.byref(rt), c.byref(parent), c.byref(kids), c.byref(n)):
            raise OSError("XQueryTree failed")
        if kids:
            x11.XFree(kids)
        self.win = parent.value if parent.value and parent.value != rt.value else inner
        self.x11, self.xext, self.XRect = x11, xext, XRect

    def set(self, rects, visible=True, mouse=True):
        arr = (self.XRect * len(rects))(*[self.XRect(int(x), int(y), max(0, int(w)), max(0, int(h)))
                                          for x, y, w, h in rects])
        for kind, on in ((0, visible), (2, mouse)):   # 0: bounding, 2: input
            if on:
                self.xext.XShapeCombineRectangles(self.dpy, self.win, kind, 0, 0, arr, len(rects), 0, 0)
        self.x11.XFlush(self.dpy)


class Widget:
    """The column is a fixed window; the panel is a second window that slides
    out from behind it while fading in. The compositor (Wayland especially) only
    has to move windows and change their opacity: resizing or reshaping them
    mid-animation is what flickers."""

    def __init__(self, root, demo=False):
        self.root = root
        self.demo = demo
        self.st = State()
        if demo:
            self.st.data, self.st.updated, self.st.error = demo_data(), time.time(), None
        self.t0 = time.time()
        self._last = self.t0
        self._act_read = 0.0
        self._work_prev, self._work_t, self._work_seed = None, 0.0, 0
        self._last_work = time.time()
        self.work = None
        self.pos, self.dir, self.act_i, self.act_t = 0.0, 1, 0, 0.0
        self.parts, self.landed, self.emit, self.hammer = [], False, 0.0, 0.0
        self.fscale, self.mouse, self._drag = 1.0, None, False
        self.pinned = bool(cs.load_config().get("expanded"))
        self.e = 0.0                                # 0 = compact, 1 = expanded
        self.target, self.in_since, self.out_since = 0, None, None
        self.panel_left = True                      # the panel opens to the left
        self.col_in = self.panel_in = False
        self.left_at = 0.0
        self._hover_last = time.time()
        self.has_app = cs.claude_app_installed()
        self.plus_hover, self.plus_click, self._plus_last = 0.0, -10.0, time.time()
        self._placed, self._skey, self._pkey = False, None, None
        self._ring_img, self._ring_key = None, None
        self._smooth = {}
        self.ready = False                      # no fresh usage yet: the widget waits empty
        self.intro_t0 = self.fill_t0 = None
        self.ball = None
        self.panel_out, self._ppos, self._palpha = False, None, None
        self.upd_state, self.upd_info, self.upd_msg, self.upd_msg_until = None, None, None, 0.0
        self.upd_quit = False
        self.costume_pref = cs.load_config().get("costume", "auto")
        self.force, self.batform, self._was_bat, self.fly_dy = None, False, False, 0.0
        self._bat_at = 0.0
        self.dbg = None
        if os.environ.get("CLAWDY_DEBUG"):
            os.makedirs(cs.cache_dir(), exist_ok=True)
            self.dbg = open(os.path.join(cs.cache_dir(), "debug.log"), "w", buffering=1)


        self.keyed = False
        self.base_k = max(1.0, min(3.0, root.winfo_fpixels("1i") / 96.0))
        self.scale = float(cs.load_config().get("size", 1.0))
        self.k = self.base_k * self.scale
        k = self.k
        self.canvas = self.make_window(root, round(CW * k), round(H * k))
        self.col_canvas = self.canvas
        self.panel = tk.Toplevel(root)
        self.pcanvas = self.make_window(self.panel, round(PW * k), round(H * k))
        self.panel.withdraw()

        c = self.col_canvas
        c.bind("<Button-1>", self.press)
        c.bind("<B1-Motion>", self.drag)
        c.bind("<ButtonRelease-1>", self.release)
        # Use enter/leave events: under XWayland, querying the pointer returns a
        # stale position once it leaves the window.
        c.bind("<Enter>", self.on_motion)
        c.bind("<Motion>", self.on_motion)
        c.bind("<Leave>", self.on_leave)
        c.bind("<Button-3>", self.popup)
        if cs.MAC:                                   # right-click is button 2 on macOS
            c.bind("<Button-2>", self.popup)
            c.bind("<Control-Button-1>", self.popup)
        p = self.pcanvas
        p.bind("<Enter>", self.on_panel_enter)
        p.bind("<Motion>", self.on_panel_enter)
        p.bind("<Leave>", self.on_panel_leave)
        p.bind("<Button-1>", self.press_panel)
        p.bind("<B1-Motion>", self.drag)
        p.bind("<ButtonRelease-1>", self.release)
        p.bind("<Button-3>", self.popup)
        if cs.MAC:
            p.bind("<Button-2>", self.popup)
            p.bind("<Control-Button-1>", self.popup)

        self.v_hooks = tk.BooleanVar(value=cs.hooks_installed())
        self.v_start = tk.BooleanVar(value=cs.autostart_enabled())
        self.v_pin = tk.BooleanVar(value=self.pinned)
        self.popup_menu = None
        self.hidden = False
        self.v_walks = tk.BooleanVar(value=cs.load_config().get("walks", True))
        self.walk, self.away = None, False
        self.setup_phase = None              # installing Claude Code / waiting for the browser
        soon = os.environ.get("CLAWDY_WALK_IN")
        self.next_trip = time.time() + (float(soon) if soon else random.uniform(*TRIP_EVERY))
        self._walk_clock = time.perf_counter()
        self.tray = Tray(self, cs.resource("assets", "icon.png")) if not demo else None

        self.fam = self.pick_font(["Segoe UI", "DejaVu Sans", "Helvetica Neue", "Helvetica"])
        self.mono = self.pick_font(["Consolas", "DejaVu Sans Mono", "Menlo", "Courier"])

        self._next_fetch, self._backoff, self._fetching = 0.0, 0, False
        self._stamp, self._last_sync = cs.session_stamp(), time.time()
        self.sync()
        if not demo:
            root.after(5000, self.auto_update)
        self.tick()

    def make_window(self, win, w, h):
        win.overrideredirect(True)
        win.title(cs.APP)
        try:
            win.wm_attributes("-topmost", True)
        except tk.TclError:
            pass
        # Rounded corners: a color key on Windows, real transparency on macOS,
        # and SHAPE on Linux (see place()).
        bg = hx(CARD)
        try:
            win.wm_attributes("-transparentcolor", KEY)
            self.keyed, bg = True, KEY
        except tk.TclError:
            if cs.MAC:
                try:
                    win.wm_attributes("-transparent", True)
                    win.config(bg="systemTransparent")
                    self.keyed, bg = True, "systemTransparent"
                except tk.TclError:
                    pass
        canvas = tk.Canvas(win, width=w, height=h, bg=bg, highlightthickness=0, bd=0)
        canvas.pack()
        win.geometry("%dx%d+%d+%d" % (w, h, -10000, -10000))     # off-screen until place()
        return canvas

    def pick_font(self, names):
        try:
            from tkinter import font as tkfont
            have = set(tkfont.families(self.root))
        except Exception:
            return names[-1]
        for n in names:
            if n in have:
                return n
        return names[-1]

    # ------------------------------------------------ windows

    def round_corners(self, win, w, h, radius=16):
        """Fixed rounded-corner clip (Linux), applied once per window."""
        if self.keyed or not sys.platform.startswith("linux"):
            return False
        try:
            win.update_idletasks()
            Shaper(win).set(rounded_rects(0, 0, w, h, round(radius * self.k)))
            return True
        except Exception:
            return False

    def place(self):
        """First frame with the window mapped: corners and position."""
        k = self.k
        cw, pw, h = round(CW * k), round(PW * k), round(H * k)
        self.rounded = self.keyed or self.round_corners(self.root, cw, h)
        # the panel stays mapped but off-screen until needed
        self.panel.deiconify()
        self.panel.update_idletasks()
        self.round_corners(self.panel, pw, h)
        self.set_alpha(0.0)
        x = self.root.winfo_screenwidth() - cw - round(30 * k)
        self.root.geometry("+%d+%d" % (x, round(60 * k)))
        self._placed = True

    # ------------------------------------------------ updates

    def auto_update(self):
        self.check_updates(False)
        self.root.after(UPDATE_EVERY * 1000, self.auto_update)

    def check_updates(self, manual):
        """Look for a new version in the background and install it when possible."""
        self.log("CHECK updates", "kind=%s" % cu.install_kind())

        def work():
            try:
                info = cu.check()
            except Exception as e:
                cu.log("check failed: %s" % e)
                if manual:
                    self.flash(tr("update.offline"))
                return
            if not info:
                if manual:
                    self.flash(tr("update.latest"))
                return
            self.upd_info = info
            kind = cu.install_kind()
            if kind in ("exe", "app", "source") and (manual or cu.should_auto_apply(info)):
                self.install_update()
            else:
                self.upd_state = "available"
        threading.Thread(target=work, daemon=True).start()

    def install_update(self):
        info = self.upd_info
        if not info:
            return
        if cu.install_kind() in ("manual", "dev"):
            import webbrowser
            webbrowser.open(info["url"])
            return
        self.upd_state = "applying"

        def work():
            try:
                r = cu.apply(info)
            except Exception as e:
                cu.log("failed: %s" % e)
                r = tr("update.failed")
            if r == "restart":
                self.upd_quit = True            # tick() exits; another process reopens us
            elif r is None:
                self.upd_state = "installing"   # the installer will close us
            else:
                self.upd_state = "available"
                self.flash(r)
        threading.Thread(target=work, daemon=True).start()

    def flash(self, msg, secs=5):
        self.upd_msg, self.upd_msg_until = msg, time.time() + secs

    def update_label(self):
        if self.upd_msg and time.time() < self.upd_msg_until:
            return self.upd_msg, DIM
        if self.upd_state == "available" and self.upd_info:
            return tr("update.available", v=self.upd_info["version"]), ORANGE
        if self.upd_state in ("applying", "installing"):
            return tr("update.applying"), ORANGE
        return None

    def costume(self):
        if self.costume_pref == "auto":
            return {"halloween": "witch", "christmas": "santa"}.get(season(), "none")
        return self.costume_pref

    def set_costume(self, value):
        self.costume_pref = value
        cfg = cs.load_config()
        cfg["costume"] = value
        try:
            cs.save_config(cfg)
        except OSError:
            pass
        self.force, self.act_t = "special", 0.0                   # show it off right away

    def set_scale(self, scale):
        """Resize the widget now and remember it."""
        self.scale = scale
        cfg = cs.load_config()
        cfg["size"] = scale
        try:
            cs.save_config(cfg)
        except OSError:
            pass
        right = self.root.winfo_x() + self.root.winfo_width()       # keep the right edge in place
        self.k = self.base_k * scale
        k = self.k
        cw, pw, h = round(CW * k), round(PW * k), round(H * k)
        self.col_canvas.config(width=cw, height=h)
        self.pcanvas.config(width=pw, height=h)
        self.root.geometry("%dx%d+%d+%d" % (cw, h, right - cw, self.root.winfo_y()))
        self.panel.geometry("%dx%d" % (pw, h))
        self.root.update_idletasks()
        self.round_corners(self.root, cw, h)
        self.round_corners(self.panel, pw, h)
        self._skey = self._pkey = self._ring_key = self._ppos = None

    def set_alpha(self, a):
        a = round(a, 2)
        if a != self._palpha:
            self._palpha = a
            try:
                self.panel.wm_attributes("-alpha", max(0.0, min(1.0, a)))
            except tk.TclError:
                pass

    def place_panel(self):
        """Slide the panel out from behind the column towards the free side."""
        k = self.k
        if self.e <= 0.0:
            if self.panel_out:
                self.panel_out = False
                self.set_alpha(0.0)
                self.panel.geometry("+%d+%d" % (-10000, -10000))
                self._ppos = None
            return
        rx, ry = self.root.winfo_x(), self.root.winfo_y()
        cw, pw, gap = round(CW * k), round(PW * k), round(6 * k)
        if self.panel_left:
            start, end = rx + cw - pw, rx - pw - gap
        else:
            start, end = rx, rx + cw + gap
        x = round(lerp(start, end, ease(self.e)))
        if not self.panel_out:
            self.panel_out = True
            self.panel.lift()
            self.root.lift()                 # column always above the panel
            if self.popup_menu:              # and the menu above everything
                self.popup_menu.win.lift()
        if (x, ry) != self._ppos:
            self._ppos = (x, ry)
            self.panel.geometry("+%d+%d" % (x, ry))
        self.set_alpha(clamp(self.e * 1.5))

    def plus_at(self):
        return PLUS[0], PLUS[1], PLUS_R

    def on_plus(self, mx, my):
        x, y, r = self.plus_at()
        return math.hypot(mx - x, my - y) < r + 3

    def press(self, ev):
        if self.popup_menu:
            self.popup_menu.close()
        if ev.y / self.k > INFO_Y - 7 and self.upd_state == "available":
            self._drag = False
            self.install_update()
            return
        if ev.y / self.k > INFO_Y - 9 and self.no_usage() and not self.setup_phase:
            self._drag = False
            self.setup_claude_code()
            return
        if self.on_plus(ev.x / self.k, ev.y / self.k):
            self._drag = False
            self.new_chat()
            return
        self.press_panel(ev)

    def press_panel(self, ev):
        self._drag = True
        self._dx, self._dy = ev.x_root - self.root.winfo_x(), ev.y_root - self.root.winfo_y()

    def toggle_pin(self):
        self.pinned = self.v_pin.get()
        cfg = cs.load_config()
        cfg["expanded"] = self.pinned
        try:
            cs.save_config(cfg)
        except OSError:
            pass

    def update_view(self):
        """Expand on hover, collapse when the mouse leaves."""
        now = time.time()
        dt = min(now - self._hover_last, 0.1)
        self._hover_last = now
        # Moving from the column to the panel crosses a gap: leaving for less
        # than 0.15 s doesn't count.
        inside = self.col_in or self.panel_in or now - self.left_at < 0.15
        if not (self.col_in or now - self.left_at < 0.15):
            self.mouse = None
        # Hovering the + while compact doesn't expand, so the button doesn't run away.
        over_plus = self.e < 0.5 and self.mouse is not None and self.on_plus(*self.mouse)
        hot = inside and not over_plus
        if hot:
            self.out_since, self.in_since = None, self.in_since or now
        else:
            self.in_since, self.out_since = None, self.out_since or now

        if self.pinned or (inside and self.e >= 0.5):
            target = 1
        elif hot and now - self.in_since >= OPEN_AFTER:
            target = 1
        elif not inside and self.target == 1 and now - self.out_since < CLOSE_AFTER:
            target = 1
        else:
            target = 0
        if target == 1 and self.target == 0 and self.e == 0.0:
            # towards the free side of the screen
            col = self.root.winfo_x() + round(CW * self.k) / 2
            self.panel_left = col > self.root.winfo_screenwidth() / 2
        if target != self.target:
            self.log("DECIDE", "open" if target else "close", "inside=%s e=%.2f" % (inside, self.e))
        self.target = target
        step = dt * SPEED
        self.e = clamp(self.e + step) if target else clamp(self.e - step)
        self.place_panel()

    def new_chat(self):
        self.plus_click = time.time()
        cs.open_new_chat(self.has_app)
        self.force, self.act_t = "wave", 0.0                 # Clawdy waves
        for i in range(4):
            self.spawn("heart", SCENE_W / 2 + (i - 1.5) * 16, 40, (i - 1.5) * 10, -45, 1.4)

    def release(self, ev):
        self._drag = False

    def log(self, *parts):
        if self.dbg:
            self.dbg.write("%.3f %s\n" % (time.time() % 1000, " ".join(str(p) for p in parts)))

    def on_motion(self, ev):
        if not self.col_in:
            self.log("ENTER column", ev.x, ev.y, "e=%.2f" % self.e)
        self.col_in = True
        self.mouse = (ev.x / self.k, ev.y / self.k)

    def on_leave(self, ev):
        self.log("LEAVE column", "e=%.2f" % self.e)
        self.col_in = False
        self.left_at = time.time()

    def on_panel_enter(self, ev):
        if not self.panel_in:
            self.log("ENTER panel", "e=%.2f" % self.e)
        self.panel_in = True

    def on_panel_leave(self, ev):
        self.log("LEAVE panel", "e=%.2f" % self.e)
        self.panel_in = False
        self.left_at = time.time()

    def drag(self, ev):
        if not self._drag:
            return
        self.root.geometry("+%d+%d" % (ev.x_root - self._dx, ev.y_root - self._dy))

    def popup(self, ev):
        if self.popup_menu:
            self.popup_menu.close()
        self.popup_menu = PopupMenu(self, ev.x_root, ev.y_root)

    def toggle_hooks(self):
        err = cs.set_hooks(self.v_hooks.get())
        if err:
            self.v_hooks.set(cs.hooks_installed())
            self.st.error = err[:60]

    def toggle_start(self):
        try:
            cs.set_autostart(self.v_start.get())
        except Exception:
            self.v_start.set(cs.autostart_enabled())

    def refresh(self):
        """Fetch now (menu, or something worth checking right away)."""
        if self.demo or self._fetching:
            return
        self._fetching = True

        def work():
            try:
                self._after_fetch(fetch(self.st))
            finally:
                self._fetching = False
        threading.Thread(target=work, daemon=True).start()

    def _after_fetch(self, outcome):
        now = time.time()
        if not self.ready and self.st.data and not self.st.error and self.st.fresh():
            self.start_intro()
        if outcome == "offline":                # e.g. right after boot: retry soon, then back off
            self._backoff = min(self._backoff + 1, 6)
            self._next_fetch = now + min(5 * 2 ** (self._backoff - 1), POLL)
            return
        self._backoff = 0
        if outcome in ("expired", "auth"):      # wait for Claude Code to renew the session
            self._next_fetch = now + 60
        elif outcome == "rate":
            self._next_fetch = self.st.retry_at
        elif outcome == "skip":                 # still fresh, or still rate limited
            self._next_fetch = max(self.st.retry_at, self.st.updated + POLL)
        else:
            self._next_fetch = now + POLL

    def setup_claude_code(self):
        """Install Claude Code if needed and sign in, without any terminal: the only
        thing the user does is approve in the browser."""
        from tkinter import messagebox
        login_only = self.st.need == "login"
        if not messagebox.askyesno(tr("need.ask_title"), tr("need.ask_login" if login_only else "need.ask"),
                                   parent=self.root):
            return
        self.setup_phase = "browser" if login_only else "installing"

        def work():
            path = cs.claude_code_path() or cs.install_claude_code()
            if not path:                        # last resort: the visible terminal
                self.setup_phase = None
                cs.connect_claude_code()
                self.flash(tr("need.opened"), 60)
                return
            self.setup_phase = "browser"
            proc = cs.start_claude_login(path)
            try:                                # finishes by itself once the user approves
                proc and proc.wait(timeout=600)
            except Exception:
                try:
                    proc.terminate()
                except Exception:
                    pass
            self.setup_phase = None
            self._stamp = None                  # make sync() look at the new session right away
            self._next_fetch = 0.0
        threading.Thread(target=work, daemon=True).start()

    def no_usage(self):
        """No Claude Code session to read usage from: Clawdy works, the rings stay empty."""
        return self.st.need in ("install", "login")

    def start_intro(self):
        self.ready, self.intro_t0, self.fill_t0, self.ball = True, time.time(), None, None

    def fill(self):
        """0 → 1 while the rings fill up after the ball lands."""
        if not self.ready:
            return 0.0
        if self.intro_t0 is None:
            return 1.0
        if self.fill_t0 is None:
            return 0.0
        return ease(clamp((time.time() - self.fill_t0) / INTRO_FILL))

    def maybe_walk(self, force=False):
        now = time.time()
        if self.walk or (not force and (now < self.next_trip or not self.v_walks.get())):
            return
        if not force and not self.using_claude(now):
            self.next_trip = now + 60          # only while you're using Claude
            return
        busy = (self.work in ("notification", "error") or self.hidden or self.e > 0 or self._drag
                or not (self.ready or self.no_usage()) or self.intro_t0 is not None or self.popup_menu)
        if not force:
            busy = busy or self.col_in or self.panel_in
        if busy:
            self.next_trip = now + 60
            return
        try:
            self.walk = Walk(self)
            self.away = True
        except Exception:
            self.walk = None
        self.next_trip = now + random.uniform(*TRIP_EVERY)

    def using_claude(self, now):
        if now - self._last_work < IN_USE_FOR:
            return True
        if now - getattr(self, "_running_at", 0) > 30:
            self._running_at = now
            self._running = cs.claude_running()
        return self._running

    def end_walk(self, home=True):
        if self.walk:
            self.walk.close()
        self.walk, self.away = None, False
        if home:                               # back in the porthole with a little hop
            self.force, self.act_t = "jump", 0.0
            for i in range(7):
                a = math.pi + i * math.pi / 6
                self.spawn("spark", SCENE_W / 2, 108, math.cos(a) * 60, math.sin(a) * 50, 0.7)

    def toggle_walks(self):
        cs.update_config(walks=self.v_walks.get())
        if not self.v_walks.get() and self.walk:
            self.end_walk()

    def sync(self):
        """Runs every 2 s without touching the network unless a request is due."""
        self.maybe_walk()
        if self.demo and not self.ready and time.time() - self.t0 > 1.5:
            self.start_intro()
        if not self.demo:
            now = time.time()
            if now - self._last_sync > 30:       # woke up from suspend
                self._next_fetch = 0.0
                self.st.updated = 0.0
            self._last_sync = now
            stamp = cs.session_stamp()
            if stamp != self._stamp:            # Claude Code renewed its session
                self._stamp = stamp
                if self.st.error:
                    self._next_fetch, self.st.retry_at = 0.0, 0.0
            if now >= self._next_fetch:
                self.refresh()
        self.root.after(2000, self.sync)

    def visible(self):
        return not self.hidden

    def hide(self):
        """Keep running in the background: still checks usage, draws nothing."""
        if self.popup_menu:
            self.popup_menu.close()
        self.hidden = True
        self.panel.withdraw()
        self.root.withdraw()
        if self.tray:
            self.tray.refresh()

    def show(self):
        if not self.hidden:
            return
        self.hidden = False
        self.root.deiconify()
        self.panel.deiconify()
        self._ppos = self._palpha = None
        self._skey = self._pkey = None
        self.root.lift()
        if self.tray:
            self.tray.refresh()

    def toggle_visible(self):
        self.hide() if not self.hidden else self.show()

    def flip(self, var, apply):
        """Toggle a menu setting from outside the right-click menu (the tray)."""
        var.set(not var.get())
        apply()
        if self.tray:
            self.tray.refresh()

    def greet(self):
        """The program was opened again: wave so the user finds us."""
        self.show()
        self.root.deiconify()
        self.root.lift()
        self.pos, self.emit = 0.0, 0.0
        for i in range(6):
            self.spawn("heart", SCENE_W / 2 + (i - 2.5) * 14, 50, (i - 2.5) * 8, -40, 1.6)

    def tick(self):
        if self.upd_quit:
            self.root.destroy()
            return
        if self.hidden:                     # in the tray: nothing to draw
            if self.walk:
                self.end_walk(home=False)
            self.root.after(500, self.tick)
            return
        now_pc = time.perf_counter()
        wdt, self._walk_clock = min(now_pc - self._walk_clock, 0.1), now_pc
        if self.walk:
            if self.work in ("notification", "error") or self._drag or not self.v_walks.get():
                self.end_walk()                 # Claude Code needs you: hurry home
            elif not self.walk.step(wdt):
                self.end_walk()
        try:
            if not self._placed:
                if not self.root.winfo_ismapped():
                    self.root.after(30, self.tick)
                    return
                self.place()
            self.update_view()
            self.draw()
        except tk.TclError:
            return
        busy = 0.0 < self.e < 1.0 or self.col_in or self.panel_in or self.target != self.e
        period = 1.0 / (FPS_FAST if busy else FPS)
        now = time.perf_counter()
        due = getattr(self, "_due", now) + period
        if due < now:                    # running late: don't try to catch up
            due = now + period / 2
        self._due = due
        self.root.after(max(1, round((due - now) * 1000)), self.tick)

    # ------------------------------------------------ primitives

    def rect(self, x, y, w, h, color):
        self.canvas.create_rectangle(x, y, x + w, y + h, fill=color, width=0)

    def oval(self, cx, cy, rx, ry, color):
        self.canvas.create_oval(cx - rx, cy - ry, cx + rx, cy + ry, fill=color, width=0)

    def poly(self, pts, color):
        self.canvas.create_polygon(pts, fill=color, width=0)

    def text(self, x, y, s, color, size=12, bold=False, anchor="w", mono=False):
        size = max(5, round(size * self.fscale * self.scale))
        self.canvas.create_text(x, y, text=s, fill=color, anchor=anchor,
                                font=(self.mono if mono else self.fam, size,
                                      "bold" if bold else "normal"))

    def lw(self, w):
        return max(1, round(w * self.fscale * self.scale))

    def px_rect(self, xf, x, y, color, w=PX, h=PX):
        """One sprite block, transformed."""
        if xf.rot:
            self.poly([xf.pt(x, y), xf.pt(x + w, y), xf.pt(x + w, y + h), xf.pt(x, y + h)], color)
        else:
            x0, y0 = xf.pt(x, y)
            x1, y1 = xf.pt(x + w, y + h)
            self.canvas.create_rectangle(round(x0), round(y0), round(x1), round(y1), fill=color, width=0)

    # ------------------------------------------------ Clawd

    def spawn(self, kind, x, y, vx=0.0, vy=-20.0, life=1.5, **extra):
        p = {"k": kind, "x": x, "y": y, "vx": vx, "vy": vy, "life": life, "max": life}
        p.update(extra)
        self.parts.append(p)

    def draw_clawd(self, cx, by, top):
        now = time.time()
        t = now - self.t0
        dt = min(now - self._last, 0.1)
        self._last = now

        if not self.ready and not self.no_usage():   # waiting for usage: just a quiet loading pulse
            for i in range(3):
                a = 0.25 + 0.6 * max(0.0, math.sin(t * 4 - i * 0.8))
                self.oval(cx - 14 + i * 14, by - 24, 4, 4, hx(DIM, a))
            return
        if self.away:                          # out for a walk: the porthole is empty
            self.draw_parts(dt, t)
            return
        if self.intro_t0 is not None:
            if self.draw_intro(cx, by, now - self.intro_t0, dt, t):
                return
            self.intro_t0 = None
            self.act_t, self.force = 0.0, "wave"
        if self.demo:
            self.work = DEMO_STATES[int(t / 3.0) % len(DEMO_STATES)]
        elif now - self._act_read > 0.25:
            self._act_read = now
            self.work = read_activity(now)
        work = self.work
        if work != self._work_prev:
            self._work_prev, self._work_t = work, 0.0
            self._work_seed += 1
        self._work_t += dt
        if work:
            self._last_work = now
        vs = VARIANTS.get(work)
        variant = vs[(self._work_seed + int(self._work_t / VARIANT_SECS)) % len(vs)] if vs else None

        energy = 1 + top / 100 * 1.5          # more usage = faster
        panic = top >= 90
        DUR = 3.6
        costume = self.costume()
        acts = COSTUME_ACTS if costume != "none" else ACTS
        self.act_t += dt * energy
        if self.act_t >= DUR:
            self.act_t = 0.0
            self.act_i = (self.act_i + 1) % len(acts)
            self.landed = False
            self.force = None
        act = self.force or acts[self.act_i % len(acts)]
        if act == "trick":
            act = TRICKS.get(costume, "dance")
        if panic and act == "walk" and costume != "ghost":
            act = "run"
        if top < 10 and act == "look":
            act = "sleep"
        if not self.demo and now - self._last_work > NAP_AFTER and act not in ("wave", "special"):
            act = "sleep"
        p = self.act_t / DUR
        if work:
            act = work

        dy = sx = sy = rot = 0.0
        glow = 0.6
        sx = sy = 1.0
        arm_l = arm_r = 0.0
        eye_dx, eye_dy, eye = self.dir * 1.0, 0.0, "open"
        step, tuck, props = None, False, []
        lim = 12                               # scene units
        self.emit -= dt
        if work and work != "sweeping":        # stay centered while working
            self.pos *= 1 - min(1.0, dt * 3)

        self.batform = False
        if act == "walk" and costume == "ghost":    # the ghost doesn't walk, it floats
            self.pos += self.dir * 30 * dt
            if abs(self.pos) > lim:
                self.pos = math.copysign(lim, self.pos)
                self.dir *= -1
            dy = -6 - math.sin(t * 2.5) * 3
            arm_l = arm_r = math.sin(t * 3) * 2
        elif act in ("walk", "run"):
            v = (55 if act == "walk" else 140) * energy
            f = (10 if act == "walk" else 18) * energy
            self.pos += self.dir * v * dt
            if abs(self.pos) > lim:
                self.pos = math.copysign(lim, self.pos)
                self.dir *= -1
            dy = -abs(math.sin(t * f)) * 3
            step = int(t * f / math.pi * 2) % 2
            sw = math.sin(t * f) * 3
            arm_l, arm_r = sw, -sw
            if act == "run":
                arm_l, arm_r = -6 + sw, -6 - sw
                eye = "scared"
                if self.emit <= 0:
                    self.spawn("dust", cx + self.pos - self.dir * SW / 2, by, -self.dir * 25, -6, 0.4)
                    self.emit = 0.08
        elif act in ("jump", "flip"):
            q = (p * 2) % 1 if act == "jump" else p
            if q < 0.2:
                sy, sx = 0.82, 1.12
            elif q < 0.75:
                k = (q - 0.2) / 0.55
                dy = -math.sin(k * math.pi) * (34 if act == "jump" else 30) * HOP
                sy, sx = 1.08, 0.94
                arm_l = arm_r = -6
                tuck = True
                eye = "happy"
                if act == "flip":
                    rot = self.dir * k * 2 * math.pi
                self.landed = False
            elif q < 0.9:
                sy, sx = 0.85, 1.12
                if not self.landed:
                    self.landed = True
                    for i in range(7):
                        a = math.pi + i * math.pi / 6
                        self.spawn("spark", cx + self.pos, by - 4, math.cos(a) * 60, math.sin(a) * 50, 0.7)
        elif act == "wave":
            arm_r = -9 + math.sin(t * 16) * 4
            eye = "happy"
            dy = -abs(math.sin(t * 5)) * 2
            if self.emit <= 0:
                self.spawn("heart", cx + self.pos + SW / 2, by - SH, 15, -30, 1.4)
                self.emit = 0.7
        elif act == "dance":
            rot = math.sin(t * 7) * 0.18
            dy = -abs(math.sin(t * 7)) * 6
            arm_l = -6 if math.sin(t * 7) > 0 else 2
            arm_r = 2 if math.sin(t * 7) > 0 else -6
            step = int(t * 7 / math.pi) % 2
            eye = "happy"
            self.pos += math.sin(t * 3.5) * 25 * dt
            if self.emit <= 0:
                side = 1 if int(t * 2) % 2 else -1
                self.spawn("note", cx + self.pos + side * (SW / 2 + 6), by - SH, side * 15, -35, 1.6)
                self.emit = 0.45
        elif act == "look":
            eye_dx = -2.5 if p < 0.33 else (2.5 if p < 0.66 else 0)
            if 0.66 < p < 0.7 and self.emit <= 0:
                self.spawn("?", cx + self.pos + 10, by - SH - 6, 0, -18, 1.2)
                self.emit = 1.0
        elif act == "sleep":
            sy, sx = 0.93 + math.sin(t * 2) * 0.03, 1.04
            eye = "closed"
            if self.emit <= 0:
                self.spawn("z", cx + self.pos + SW / 2 - 4, by - SH, 12, -18, 2.0)
                self.emit = 0.8

        elif act == "spin":                     # two full turns
            sx = math.cos(p * 4 * math.pi)
            if sx < 0:
                eye = "back"                      # no eyes from behind
            dy = -abs(math.sin(p * 4 * math.pi)) * 3
        elif act == "stretch":                  # stretch and yawn
            q = math.sin(min(p / 0.7, 1.0) * math.pi)
            sy, sx = 1 + 0.16 * q, 1 - 0.08 * q
            arm_l = arm_r = -8 * q
            eye = "closed" if q > 0.3 else "open"
        elif act == "special":                  # each costume's special move
            c = self.costume()
            if c == "witch":                    # spell with sparkles
                arm_r = -9 + math.sin(t * 10) * 2
                eye = "happy"
                if self.emit <= 0:
                    self.spawn("star", cx + self.pos + SW / 2 + 6, by - SH + 12,
                               random.uniform(-30, 40), random.uniform(-70, -30), 1.0,
                               col=random.choice(MAGIC))
                    self.emit = 0.07
            elif c == "ghost":                  # boo!
                q = (p * 2) % 1
                arm_l = arm_r = -9
                eye = "scared"
                sy = 1 + 0.12 * math.sin(q * math.pi)
                if q < 0.08 and self.emit <= 0:
                    self.spawn("boo", cx + self.pos, by - SH - 6, 0, -18, 1.3)
                    self.emit = 0.6
            elif c == "pumpkin":                # the candle inside flares up
                glow = 0.55 + 0.45 * abs(math.sin(t * 7))
                dy = -abs(math.sin(t * 3)) * 3
            elif c == "vampire":                # raise the cape, bats fly out
                arm_l = arm_r = -9
                eye = "scared"
                dy = -abs(math.sin(t * 3)) * 2
                if self.emit <= 0:
                    d = random.choice((-1, 1))
                    self.spawn("bat", cx + self.pos + d * 10, by - SH, d * 70, random.uniform(-40, -15), 1.6,
                               ph=random.uniform(0, 6))
                    self.emit = 0.35
            elif c == "santa":                  # ho ho ho!
                q = (p * 3) % 1
                dy = -math.sin(q * math.pi) * 22 * HOP
                eye = "happy"
                if q < 0.06 and self.emit <= 0:
                    self.spawn("jo", cx + self.pos, by - SH - 16, 0, -16, 1.2)
                    self.emit = 0.4
            else:                               # no costume: wave
                arm_r = -9 + math.sin(t * 16) * 4
                eye = "happy"
                if self.emit <= 0:
                    self.spawn("heart", cx + self.pos + SW / 2, by - SH, 15, -30, 1.4)
                    self.emit = 0.7

        elif act == "fly":                       # witch: broom flight inside the rings
            ang = p * 2 * math.pi
            self.pos = math.sin(ang) * 12
            self.dir = 1 if math.cos(ang) >= 0 else -1
            dy = -5 - math.sin(ang * 2) * 4
            rot = math.cos(ang) * 0.12
            tuck, eye = True, "happy"
            arm_l = arm_r = -2
            props.append("broomfly")
            if self.emit <= 0:
                self.spawn("star", cx + self.pos - self.dir * 46, by + dy - 6,
                           -self.dir * 20, random.uniform(-10, 10), 0.8, col=random.choice(MAGIC))
                self.emit = 0.06
        elif act == "bat":                       # vampire: turns into a bat
            self.batform = 0.12 < p < 0.88
            if self.batform != self._was_bat:    # puff of smoke on transform
                for i in range(10):
                    a = i * math.pi / 5
                    self.spawn("puff", cx + self.pos + math.cos(a) * 12, by - SH / 2 + math.sin(a) * 10,
                               math.cos(a) * 40, math.sin(a) * 30, 0.6)
            self._was_bat = self.batform
            if self.batform:
                self.pos = math.sin(t * 1.6) * 10
                dy = -8 - math.sin(t * 5) * 4
        elif act == "float":                     # ghost: floating loop
            ang = p * 2 * math.pi
            self.pos = math.sin(ang) * 12
            dy = -7 - math.sin(ang * 2) * 6
            arm_l = arm_r = -4 + math.sin(t * 6) * 2
            eye = "happy"
        elif act == "roll":                      # pumpkin: rolls side to side
            q = math.sin(p * 2 * math.pi)
            self.pos = q * 12
            rot = self.pos / 12 * math.pi
            tuck = True
        elif act == "present":                   # Santa: pulls out a present
            props.append("gift")
            dy = -abs(math.sin(t * 4)) * 2
            arm_l = arm_r = -5
            eye = "happy"
            if 0.55 < p < 0.6 and self.emit <= 0:
                for _ in range(8):
                    self.spawn("star", cx + self.pos, by - 24, random.uniform(-50, 50),
                               random.uniform(-80, -30), 1.0, col=random.choice(PALETTES["santa"]))
                self.emit = 0.3

        # --- states coming from Claude Code ---
        elif act == "thinking" and variant == "pace":   # paces around, hand on chin
            self.pos += self.dir * 22 * dt
            if abs(self.pos) > lim * 0.8:
                self.pos = math.copysign(lim * 0.8, self.pos)
                self.dir *= -1
            step = int(t * 6 / math.pi) % 2
            arm_r = -5
            eye_dx, eye_dy = self.dir * 2, -1.5
            if self.emit <= 0:
                self.spawn("dots", cx + self.pos + self.dir * 14, by - SH - 4, 0, -14, 1.2)
                self.emit = 1.1
        elif act == "thinking" and variant == "bulb":   # a light bulb flickers on: aha!
            q = (self._work_t % VARIANT_SECS) / VARIANT_SECS
            self.bulb = 0.0 if q < 0.25 else (1.0 if q > 0.45 else float(int(t * 14) % 2))
            eye_dx, eye_dy = 0.0, -2.5
            eye = "happy" if self.bulb >= 1 else "open"
            arm_r = -9 if self.bulb >= 1 else -3
            dy = -abs(math.sin(t * 6)) * 3 if self.bulb >= 1 else 0
            props.append("bulb")
            if self.bulb >= 1 and self.emit <= 0:
                self.spawn("spark", cx + self.pos + random.uniform(-14, 14), by - SH - 34,
                           random.uniform(-40, 40), random.uniform(-50, -10), 0.6)
                self.emit = 0.2
        elif act == "thinking":
            eye_dx, eye_dy = 1.5, -2
            dy = -abs(math.sin(t * 2)) * 2
            arm_r = -4 + math.sin(t * 3)
            props.append("bubble")
        elif act == "typing" and variant == "coffee":    # types, then sips coffee
            q = t % 3.0
            sip = q > 2.0
            eye_dy = 2 if not sip else -1
            eye = "happy" if sip else "open"
            arm_l = -9 if sip else (2 if int(t * 12) % 2 else -2)
            arm_r = 2 if int(t * 12 + 1) % 2 else -2
            self.sip = sip
            props += ["laptop", "mug"]
            if not sip and self.emit <= 0:
                self.spawn("txt", cx + self.pos + random.uniform(-20, 20), by - 30,
                           random.uniform(-10, 10), -35, 1.1, txt=random.choice(CODE))
                self.emit = 0.3
        elif act == "typing" and variant == "turbo":     # furious typing: the keyboard is on fire
            eye_dy, eye = 2, "scared"
            arm_l = 3 if int(t * 26) % 2 else -3
            arm_r = -arm_l
            self.pos += math.sin(t * 40) * 0.5
            props += ["laptop", "flames"]
            if self.emit <= 0:
                self.spawn("txt", cx + self.pos + random.uniform(-24, 24), by - 30,
                           random.uniform(-30, 30), random.uniform(-60, -35), 0.9, txt=random.choice(CODE))
                if random.random() < 0.3:
                    self.spawn("drop", cx + self.pos + SW / 2 - 6, by - SH + 6, 14, -14, 0.8)
                self.emit = 0.09
        elif act == "typing":
            eye_dy = 2
            arm_l = 2 if int(t * 14) % 2 else -2
            arm_r = -arm_l
            props.append("laptop")
            if self.emit <= 0:
                if costume in ("witch", "santa"):    # sparkles instead of code
                    self.spawn("star", cx + self.pos + random.uniform(-18, 18), by - 30,
                               random.uniform(-10, 10), -35, 1.0, col=random.choice(PALETTES[costume]))
                else:
                    self.spawn("txt", cx + self.pos + random.uniform(-20, 20), by - 30,
                               random.uniform(-10, 10), -35, 1.1, txt=random.choice(CODE))
                self.emit = 0.22
        elif act == "building" and variant == "terminal":   # watches a terminal scroll by
            eye_dx = 2.5
            eye_dy = -1 + ((t * 2) % 1) * 2
            arm_r = -3
            dy = -abs(math.sin(t * 2)) * 1.5
            props.append("terminal")
        elif act == "building":
            ph = (t * 1.8) % 1
            self.hammer = 2.0 - ph / 0.6 * 2.3 if ph < 0.6 else -0.3 + min(1, (ph - 0.6) / 0.1) * 2.3
            arm_r = -6 if ph < 0.6 else 2
            if ph >= 0.7 and not self.landed:
                self.landed = True
                sy, sx = 0.92, 1.05
                for _ in range(5):
                    a = -math.pi / 2 + random.uniform(-1.1, 1.1)
                    if costume == "witch":            # cauldron bubbles
                        self.spawn("bubble", cx + self.pos + SW / 2 + 10 + random.uniform(-10, 10), by - 22,
                                   random.uniform(-8, 8), random.uniform(-45, -25), 1.0)
                    else:
                        self.spawn("spark", cx + self.pos + SW / 2 + 22, by - 10,
                                   math.cos(a) * 70, math.sin(a) * 70, 0.5)
            elif ph < 0.6:
                self.landed = False
            props.append("hammer")
        elif act == "reading" and variant == "magnifier":   # inspects every line with a magnifier
            sweep = math.sin(t * 1.6)
            eye_dx, eye_dy = sweep * 2.5, 1
            arm_r = -4 + sweep * 2
            dy = -abs(math.sin(t * 3)) * 1
            self.lens = sweep
            props.append("magnifier")
        elif act == "reading":
            eye_dy = 2
            eye_dx = -2 + ((t * 0.7) % 1) * 4
            props.append("book")
        elif act == "groove":
            sx = 1 + math.sin(t * 8) * 0.04
            dy = -abs(math.sin(t * 4)) * 5
            eye = "happy"
            step = int(t * 4 / math.pi) % 2
            props.append("headphones")
            if self.emit <= 0:
                side = random.choice((-1, 1))
                self.spawn("note", cx + self.pos + side * (SW / 2 + 4), by - SH, side * 18, -30, 1.5)
                self.emit = 0.5
        elif act == "juggling":
            eye_dy = -2
            arm_l = -5 if math.sin(t * 8) > 0 else 1
            arm_r = 1 if math.sin(t * 8) > 0 else -5
            props.append("balls")
        elif act == "error":
            eye = "x"
            self.pos += math.sin(t * 50) * 1.2
            sy = 0.95
            props.append("err")
            if self.emit <= 0:
                self.spawn("dust", cx + self.pos + random.uniform(-15, 15), by - SH, 0, -25, 1.0)
                self.emit = 0.15
        elif act == "notification":
            dy = -abs(math.sin(t * 7)) * 6
            arm_l = arm_r = -8 + math.sin(t * 14) * 3
            eye = "scared"
            props.append("bang")
        elif act == "sweeping":
            self.pos += self.dir * 35 * dt
            if abs(self.pos) > lim * 0.7:
                self.pos = math.copysign(lim * 0.7, self.pos)
                self.dir *= -1
            step = int(t * 8 / math.pi) % 2
            props.append("broom")
            if self.emit <= 0:
                self.spawn("dust", cx + self.pos + self.dir * (SW / 2 + 14), by, self.dir * 30, -10, 0.6)
                self.emit = 0.12
        elif act == "happy" and variant == "dance":     # victory dance
            rot = math.sin(t * 8) * 0.2
            dy = -abs(math.sin(t * 8)) * 7
            arm_l = -7 if math.sin(t * 8) > 0 else 1
            arm_r = 1 if math.sin(t * 8) > 0 else -7
            step = int(t * 8 / math.pi) % 2
            eye = "happy"
            if self.emit <= 0:
                side = random.choice((-1, 1))
                self.spawn("note", cx + self.pos + side * (SW / 2 + 6), by - SH, side * 18, -35, 1.4)
                self.spawn("conf", cx + self.pos + random.uniform(-40, 40), by - SH - 10,
                           random.uniform(-30, 30), random.uniform(-80, -30), 1.4,
                           col=random.choice(PALETTES.get(costume, CONFETTI)), spin=random.uniform(0, 6))
                self.emit = 0.3
        elif act == "happy" and variant == "fireworks":  # fireworks behind Clawdy
            eye, arm_l, arm_r = "happy", -8, -8
            dy = -abs(math.sin(t * 3)) * 3
            if self.emit <= 0:
                ox, oy = cx + random.uniform(-45, 45), by - SH - random.uniform(10, 30)
                col = random.choice(PALETTES.get(costume, CONFETTI))
                for i in range(14):
                    a = i * math.pi / 7
                    self.spawn("fw", ox, oy, math.cos(a) * 85, math.sin(a) * 85, 1.1, col=col)
                self.emit = 0.45
        elif act == "happy":
            q = (t * 2.2) % 1
            dy = -math.sin(q * math.pi) * 22 * HOP
            arm_l = arm_r = -7
            eye = "happy"
            tuck = q > 0.1
            if self.emit <= 0:
                pal = PALETTES.get(costume, CONFETTI)
                for _ in range(4):
                    kind = "star" if costume in ("witch", "santa") else "conf"
                    self.spawn(kind, cx + self.pos + random.uniform(-40, 40), by - SH - 10,
                               random.uniform(-40, 40), random.uniform(-90, -30), 1.6,
                               col=random.choice(pal), spin=random.uniform(0, 6))
                if costume == "santa":
                    self.spawn("snow", cx + random.uniform(-60, 60), 20, 0, 25, 3.0, ph=random.uniform(0, 6))
                self.emit = 0.15

        if eye == "open" and (t % 3.1) < 0.13:
            eye = "closed"
        if panic and not work:
            self.pos += math.sin(t * 45) * 0.6
        if top >= 70 and not work and self.emit <= 0 and act not in ("dance", "wave", "sleep", "run"):
            self.spawn("drop", cx + self.pos + SW / 2 - 6, by - SH + 6 + dy, 10, -10, 0.9)
            self.emit = 0.5

        props = [THEMED.get((costume, pr), pr) for pr in props]
        self.fly_dy = dy
        if costume in SPOOKY and now - self._bat_at > 7:      # a bat now and then
            self._bat_at = now + random.uniform(0, 4)
            d = random.choice((-1, 1))
            self.spawn("bat", cx - d * 95, random.uniform(28, 60), d * 75, 0, 2.6,
                       ph=random.uniform(0, 6))
        elif costume == "santa" and random.random() < dt * 3:  # snow
            self.spawn("snow", cx + random.uniform(-75, 75), 18, random.uniform(-6, 6), 20, 4.5,
                       ph=random.uniform(0, 6))

        bx = cx + self.pos
        k = max(0.3, 1 + dy / 60)
        self.oval(bx, by + 3, SW / 2 * k, 3.5, hx((0, 0, 0), 0.35 * k))

        xf = Xform(bx, by + dy - SH / 2 * sy, sx, sy, rot)   # anchored at the feet
        if self.batform:
            self.draw_big_bat(bx, by + dy - SH / 2, t)
        else:
            self.draw_costume(xf, costume, "back", t, glow, eye, eye_dx)
            self.draw_sprite(xf, arm_l, arm_r, eye, eye_dx, eye_dy, step, tuck)
            self.draw_costume(xf, costume, "front", t, glow, eye, eye_dx)
        self.draw_props(props, bx, by, by + dy - SH, t, arm_r)
        self._center = (bx, by + dy - SH / 2)
        self.draw_parts(dt, t)

    def draw_intro(self, cx, by, it, dt, t):
        """Clawdy walks in with a ball, throws it on the floor and the rings fill up.
        Returns False once the intro is over."""
        if it > INTRO_END:
            return False
        costume = self.costume()
        sx = sy = 1.0
        dy = rot = 0.0
        arm_l = arm_r = -9.0
        eye, step, tuck = "open", None, False
        throw_at = INTRO_WALK + INTRO_WIND
        if it < INTRO_WALK:                                  # walk in from the left
            k = it / INTRO_WALK
            self.pos = lerp(-58, 0, 1 - (1 - k) ** 2)
            self.dir = 1
            step = int(t * 12 / math.pi) % 2
            dy = -abs(math.sin(t * 12)) * 2.5
        elif it < throw_at:                                  # wind up
            self.pos = 0.0
            q = (it - INTRO_WALK) / INTRO_WIND
            sy, sx = 1 - 0.12 * q, 1 + 0.06 * q
            arm_l = arm_r = -9 - 3 * q
        else:                                                # thrown: arms down, happy
            self.pos = 0.0
            q = min(1.0, (it - throw_at) / 0.15)
            arm_l = arm_r = lerp(-12, 2, q)
            sy = 1 + 0.06 * math.sin(min(1.0, (it - throw_at) / 0.3) * math.pi)
            eye = "happy" if self.fill_t0 else "open"
        bx = cx + self.pos
        self.oval(bx, by + 3, SW / 2, 3.5, hx((0, 0, 0), 0.35))
        xf = Xform(bx, by + dy - SH / 2 * sy, sx, sy, rot)
        self.draw_costume(xf, costume, "back", t, 0.6, eye, 0)
        self.draw_sprite(xf, arm_l, arm_r, eye, 0, -1, step, tuck)
        self.draw_costume(xf, costume, "front", t, 0.6, eye, 0)
        top_y = by + dy - SH * sy
        hat = (-HAT_TOP.get(costume, -27) - 27) * 0.8
        R = 11
        if it < throw_at:                                    # carried above the head
            self.ball = None
            self.draw_ball(bx, top_y - hat - R - 2 + (3 * (it - INTRO_WALK) / INTRO_WIND if it > INTRO_WALK else 0), R, t)
        else:
            b = self.ball
            if b is None:
                b = self.ball = {"x": bx, "y": top_y - hat - R - 2, "vx": 60.0, "vy": 120.0, "hits": 0, "spin": 0.0}
            b["vy"] += 900 * dt
            b["x"] += b["vx"] * dt
            b["y"] += b["vy"] * dt
            b["spin"] += b["vx"] * dt / R
            if b["y"] > by - R and b["vy"] > 0:              # bounce on the floor
                b["y"] = by - R
                b["vy"] *= -0.55
                b["vx"] *= 0.92
                b["hits"] += 1
                if b["hits"] == 1:
                    self.fill_t0 = time.time()
                    for i in range(9):
                        a = math.pi + i * math.pi / 8
                        self.spawn("spark", b["x"], by - 2, math.cos(a) * 80, math.sin(a) * 60, 0.6)
                if abs(b["vy"]) < 40:
                    b["vy"] = 0.0
            fade = clamp((INTRO_END - it) / 0.25)      # it rolls out behind the rings
            self.draw_ball(b["x"], b["y"], R, b["spin"], fade)
        self._center = (bx, by - SH / 2)
        self.draw_parts(dt, t)
        return True

    def draw_ball(self, x, y, r, spin, a=1.0):
        """A beach ball in the usage colors."""
        cols = [(0.45, 0.78, 0.45), (0.95, 0.70, 0.25), (0.90, 0.30, 0.25)]
        self.oval(x, y, r, r, hx((0.97, 0.95, 0.92), a))
        bf = Xform(x, y, 1, 1, spin)
        for i, col in enumerate(cols):
            a0 = i * 2 * math.pi / 3
            pts = [bf.pt(0, 0)] + [bf.pt(math.cos(a0 + j * 0.35) * r * 0.95, math.sin(a0 + j * 0.35) * r * 0.95)
                                   for j in range(4)]
            self.poly(pts, hx(col, a))
        self.oval(x, y, 2.5, 2.5, hx((0.97, 0.95, 0.92), a))
        self.oval(x - r * 0.4, y - r * 0.45, 2.5, 2, hx((1, 1, 1), 0.8 * a))

    def draw_sprite(self, xf, arm_l, arm_r, eye, eye_dx, eye_dy, step, tuck):
        orange, orange_d, dark = hx(ORANGE), hx(ORANGE_D), hx(DARK)
        x0, y0 = -SW / 2, -SH / 2
        for key, r0, c0, r1, c1 in BLOCKS:
            x, y = x0 + c0 * PX, y0 + r0 * PX
            w, h = (c1 - c0 + 1) * PX, (r1 - r0 + 1) * PX
            color = orange
            if key.startswith("leg"):
                if tuck or (step is not None and (c0 in (3, 8)) == bool(step)):
                    y -= 3
                color = orange_d
            elif key == "arm_l":
                y += arm_l
            elif key == "arm_r":
                y += arm_r
            self.px_rect(xf, x, y, color, w, h)

        for r, c in EYES:
            x, y = x0 + c * PX, y0 + r * PX
            ex = x + eye_dx
            if eye == "open":
                self.px_rect(xf, ex, y + eye_dy, dark)
            elif eye == "scared":
                self.poly([xf.pt(ex - 1, y - 2), xf.pt(ex + PX + 1, y - 2),
                           xf.pt(ex + PX + 1, y + PX), xf.pt(ex - 1, y + PX)], dark)
            elif eye == "closed" and r == 3:
                self.poly([xf.pt(x - 1, y + 3), xf.pt(x + PX + 1, y + 3),
                           xf.pt(x + PX + 1, y + 5), xf.pt(x - 1, y + 5)], dark)
            elif eye == "happy" and r == 2:            # ^ ^ eyes
                for ox, oy in ((-2, 5), (1, 2), (5, 5)):
                    self.poly([xf.pt(x + ox, y + oy), xf.pt(x + ox + 3, y + oy),
                               xf.pt(x + ox + 3, y + oy + 3), xf.pt(x + ox, y + oy + 3)], dark)
            elif eye == "x" and r == 2:                 # X eyes
                for ox, oy in ((0, 0), (4, 0), (2, 3), (0, 6), (4, 6)):
                    self.poly([xf.pt(x - 1 + ox, y + 1 + oy), xf.pt(x + 2 + ox, y + 1 + oy),
                               xf.pt(x + 2 + ox, y + 4 + oy), xf.pt(x - 1 + ox, y + 4 + oy)], dark)

    def draw_big_bat(self, x, y, t):
        """The vampire in bat form."""
        f = math.sin(t * 14)
        rim, body = hx((0.62, 0.55, 0.72)), hx((0.22, 0.17, 0.28))
        for c, grow in ((rim, 3), (body, 0)):        # light rim first, then the body
            g = grow
            self.poly([(x - 8, y - 4), (x - 44 - g, y - 12 - 16 * f - g), (x - 34, y + 6 + g),
                       (x - 24, y + 2), (x - 14, y + 10 + g)], c)
            self.poly([(x + 8, y - 4), (x + 44 + g, y - 12 - 16 * f - g), (x + 34, y + 6 + g),
                       (x + 24, y + 2), (x + 14, y + 10 + g)], c)
            self.oval(x, y + 2, 12 + g, 13 + g, c)
            self.poly([(x - 10, y - 8), (x - 9 - g, y - 21 - g), (x - 2, y - 10)], c)    # ears
            self.poly([(x + 10, y - 8), (x + 9 + g, y - 21 - g), (x + 2, y - 10)], c)
        red = hx((1.0, 0.25, 0.25))
        self.rect(x - 6, y - 2, 4, 4, red)
        self.rect(x + 2, y - 2, 4, 4, red)
        white = hx((0.97, 0.97, 0.97))
        self.poly([(x - 4, y + 6), (x - 1, y + 6), (x - 2.5, y + 10)], white)
        self.poly([(x + 1, y + 6), (x + 4, y + 6), (x + 2.5, y + 10)], white)

    def draw_costume(self, xf, c, layer, t, glow, eye, eye_dx):
        """Costumes share Clawdy's transform, so they jump, spin and squash with
        it. Sprite coordinates: body x ±30, y -27..15."""
        if c == "none":
            return

        def b(x, y, w, h, col):
            self.px_rect(xf, x, y, hx(col), w, h)

        def tri(pts, col):
            self.poly([xf.pt(x, y) for x, y in pts], hx(col))

        dark = (0.08, 0.06, 0.07)
        if c == "vampire" and layer == "back":            # cape goes behind
            tri([(-36, -23), (36, -23), (45, 29), (-45, 29)], (0.45, 0.40, 0.52))   # light rim
            tri([(-34, -21), (34, -21), (42, 27), (-42, 27)], (0.09, 0.07, 0.10))
            tri([(-34, -21), (-28, -21), (-34, 27), (-42, 27)], (0.62, 0.10, 0.15))
            tri([(34, -21), (28, -21), (34, 27), (42, 27)], (0.62, 0.10, 0.15))
            return
        if layer == "back":
            return

        if c == "witch":
            # Purple disappears on the dark card: a light rim drawn first peeks
            # out around the silhouette, plus a highlight on the crown.
            hat = [(-36, -31, 72, 4), (-18, -37, 36, 6), (-12, -43, 24, 6),
                   (-6, -49, 15, 6), (2, -54, 12, 5), (10, -52, 8, 4)]
            rim, brim, cone = (0.80, 0.66, 0.98), (0.40, 0.22, 0.62), (0.55, 0.31, 0.82)
            for x, y, w, h in hat:
                b(x - 2, y - 2, w + 4, h + 4, rim)
            b(*hat[0], brim)                              # brim
            for x, y, w, h in hat[1:]:
                b(x, y, w, h, cone)
            b(-12, -43, 4, 6, (0.70, 0.50, 0.95))         # highlight
            b(-6, -49, 3, 6, (0.70, 0.50, 0.95))
            b(-18, -37, 36, 3, (0.98, 0.58, 0.16))        # band
            b(-3, -37, 6, 3, (1.0, 0.88, 0.35))           # buckle
            b(1, -47, 3, 3, (1.0, 0.88, 0.35))            # star
        elif c == "santa":
            red, white = (0.86, 0.16, 0.16), (0.97, 0.97, 0.97)
            b(-24, -39, 48, 6, red)
            b(-16, -45, 34, 6, red)
            b(-4, -50, 26, 5, red)
            b(16, -48, 10, 8, red)                        # droops to the side
            b(-32, -33, 64, 6, white)                     # fur trim
            o = xf.pt(29, -40)
            self.oval(o[0], o[1], 4.5, 4.5, hx(white))    # pompom
        elif c == "pumpkin":
            rib = (0.76, 0.38, 0.26)
            b(-14, -27, 3, 42, rib)                       # ribs
            b(11, -27, 3, 42, rib)
            b(-3, -35, 6, 8, (0.33, 0.55, 0.22))          # stem
            tri([(3, -33), (13, -38), (9, -29)], (0.40, 0.66, 0.28))
            b(-21, -17, 12, 16, ORANGE)                   # cover the usual eyes
            b(9, -17, 12, 16, ORANGE)
            lit = tuple(min(1.0, 0.55 + 0.45 * glow * c2) for c2 in (1.0, 0.85, 0.35))
            tri([(-20, -5), (-10, -5), (-15, -15)], lit)  # carved eyes, lit from inside
            tri([(10, -5), (20, -5), (15, -15)], lit)
            tri([(-16, 2), (16, 2), (12, 9), (6, 5), (0, 10), (-6, 5), (-12, 9)], lit)
        elif c == "ghost":
            white, shade = (0.95, 0.95, 0.98), (0.80, 0.81, 0.87)
            b(-21, -34, 42, 3, white)
            b(-27, -31, 54, 4, white)
            b(-33, -27, 66, 46, white)
            b(-33, 15, 66, 2, shade)
            for i in range(4):                            # wavy hem
                b(-33 + i * 18, 19, 12, 4 + 3 * abs(math.sin(t * 5 + i)), white)
            ex = eye_dx
            if eye in ("closed", "happy", "back"):
                if eye != "back":
                    b(-18 + ex, -9, 7, 2, dark)
                    b(12 + ex, -9, 7, 2, dark)
            else:
                h = 12 if eye == "scared" else 9
                b(-18 + ex, -15, 7, h, dark)
                b(12 + ex, -15, 7, h, dark)
                if eye == "scared":
                    b(-4, 0, 8, 7, dark)                  # "boo" mouth
        elif c == "vampire":
            hair = (0.12, 0.10, 0.14)                     # visible on orange
            b(-30, -27, 60, 5, hair)
            tri([(-8, -22), (8, -22), (0, -15)], hair)    # widow's peak
            if eye != "back":
                tri([(-8, 1), (-3, 1), (-5.5, 7)], (0.97, 0.97, 0.97))      # fangs
                tri([(3, 1), (8, 1), (5.5, 7)], (0.97, 0.97, 0.97))

    def draw_props(self, props, bx, by, bt, t, arm_r):
        """Floating props are pulled towards Clawdy so the whole animation fits in
        the porthole; props it holds stay put."""
        cx, cy = bx, bt + SH / 2
        for pr in props:
            mark = self.canvas.create_line(0, 0, 0, 0)
            self.draw_prop(pr, bx, by, bt, t, arm_r)
            if pr in FAR_PROPS:
                for item in self.canvas.find_all():
                    if item > mark:
                        self.canvas.addtag_withtag("near", item)
                self.canvas.scale("near", cx, cy, REACH, REACH)
                self.canvas.dtag("near", "near")
            self.canvas.delete(mark)

    def draw_prop(self, pr, bx, by, bt, t, arm_r):
        props = (pr,)
        dark = hx((0.12, 0.11, 0.10))
        costume = self.costume()
        if pr == "crystal":                              # crystal ball
            ox, oy = bx + SW / 2 + 18, by - 26
            self.poly([(ox - 9, oy + 14), (ox + 9, oy + 14), (ox + 6, oy + 8), (ox - 6, oy + 8)],
                      hx((0.85, 0.65, 0.25)))
            self.oval(ox, oy - 4, 18, 18, hx((0.80, 0.66, 0.98)))
            self.oval(ox, oy - 4, 15, 15, hx((0.55, 0.38, 0.85)))
            for i in range(3):
                a = t * 3 + i * 2.1
                self.oval(ox + math.cos(a) * 7, oy - 4 + math.sin(a) * 6, 3, 3, hx((0.85, 0.80, 1.0)))
            self.oval(ox - 6, oy - 11, 3.5, 3, hx((1, 1, 1)))
            return
        if pr == "spellbook":                            # spellbook
            for side in (-1, 1):
                x = bx if side > 0 else bx - 20
                self.rect(x - 1, by - 27, 22, 18, hx((0.45, 0.25, 0.65)))
                self.rect(x + 1, by - 25, 18, 14, hx((0.97, 0.93, 0.80)))
                for i in range(3):
                    self.rect(x + 4, by - 22 + i * 4, 12, 1, hx((0.45, 0.25, 0.65), 0.6))
            self.rect(bx - 2, by - 28, 4, 20, hx((1.0, 0.85, 0.35)))      # golden spine
            return
        if pr == "cauldron":                             # bubbling cauldron
            ox, oy = bx + SW / 2 + 10, by - 10
            self.oval(ox, oy, 20, 13, hx((0.45, 0.40, 0.52)))
            self.oval(ox, oy, 18, 11, hx((0.18, 0.16, 0.20)))
            self.oval(ox, oy - 9, 16, 4, hx((0.40, 0.85, 0.35)))
            sx_, sy_ = bx + SW / 2 - 4, bt + 22 + arm_r
            self.canvas.create_line(sx_, sy_, ox - 4 + math.sin(t * 6) * 8, oy - 8,
                                    fill=hx((0.55, 0.36, 0.20)), width=self.lw(3))
            return
        if pr == "gift":                                 # present in hand
            gx, gy = bx, by - 22 + math.sin(t * 4) * 1.5
            self.rect(gx - 16, gy, 32, 20, hx((0.86, 0.16, 0.16)))
            self.rect(gx - 3, gy, 6, 20, hx((0.22, 0.72, 0.32)))
            self.rect(gx - 16, gy + 7, 32, 5, hx((0.22, 0.72, 0.32)))
            self.poly([(gx, gy), (gx - 10, gy - 7), (gx - 8, gy + 1)], hx((0.22, 0.72, 0.32)))
            self.poly([(gx, gy), (gx + 10, gy - 7), (gx + 8, gy + 1)], hx((0.22, 0.72, 0.32)))
            return
        if pr == "broomfly":                             # flying broom, under Clawdy
            d = self.dir
            y = by + self.fly_dy - 2
            self.canvas.create_line(bx + d * 40, y - 6, bx - d * 36, y + 2,
                                    fill=hx((0.62, 0.40, 0.22)), width=self.lw(4))
            self.poly([(bx - d * 34, y - 3), (bx - d * 52, y - 12), (bx - d * 56, y + 4),
                       (bx - d * 52, y + 14), (bx - d * 34, y + 7)], hx((0.92, 0.75, 0.35)))
            return
        for pr in props:
            if pr == "bubble":
                col = hx((0.95, 0.93, 0.90))
                self.oval(bx + SW / 2 - 2, bt - 2, 2.5, 2.5, col)
                self.oval(bx + SW / 2 + 6, bt - 10, 4, 4, col)
                self.oval(bx + SW / 2 + 28, bt - 28, 26, 15, col)
                for i in range(3):
                    on = int(t * 3) % 4 > i
                    self.oval(bx + SW / 2 + 18 + i * 10, bt - 28, 3, 3,
                              dark if on else hx((0.12, 0.11, 0.10), 0.3))
            elif pr == "laptop":
                self.rect(bx - 24, by - 26, 48, 18, hx((0.55, 0.56, 0.60)))
                self.oval(bx, by - 17, 3, 3, hx((0.60, 0.85, 1.0), 0.5 + 0.5 * abs(math.sin(t * 3))))
                self.rect(bx - 28, by - 8, 56, 5, hx((0.40, 0.41, 0.45)))
            elif pr == "hammer":
                self.rect(bx + SW / 2 + 12, by - 8, 20, 8, hx((0.45, 0.45, 0.48)))
                hx0, hy0 = bx + SW / 2 - 4, bt + 22 + arm_r
                th = self.hammer
                ex, ey = hx0 + math.sin(th) * 24, hy0 - math.cos(th) * 24
                self.canvas.create_line(hx0, hy0, ex, ey, fill=hx((0.55, 0.36, 0.20)), width=self.lw(3))
                hd = Xform(ex, ey, 1, 1, th)
                self.poly([hd.pt(-8, -5), hd.pt(8, -5), hd.pt(8, 4), hd.pt(-8, 4)], hx((0.70, 0.70, 0.75)))
            elif pr == "book":
                for side in (-1, 1):
                    x = bx if side > 0 else bx - 20
                    self.rect(x - 1, by - 27, 22, 18, hx((0.55, 0.30, 0.20)))
                    self.rect(x + 1, by - 25, 18, 14, hx((0.97, 0.95, 0.88)))
                    for i in range(4):
                        self.rect(x + 4, by - 22 + i * 3, 12, 1, hx((0.30, 0.30, 0.30), 0.6))
            elif pr == "headphones":
                self.canvas.create_arc(bx - SW / 2 + 10, bt - 4, bx + SW / 2 - 10, bt + 20,
                                       start=0, extent=180, style="arc", outline=dark, width=self.lw(4))
                for x in (bx - SW / 2 + 7, bx + SW / 2 - 15):
                    self.rect(x, bt + 4, 8, 15, hx((0.85, 0.25, 0.30)))
            elif pr == "balls":
                balls = {"pumpkin": [(0.95, 0.55, 0.15)] * 3, "witch": [(0.95, 0.55, 0.15)] * 3,
                         "santa": [(0.86, 0.16, 0.16), (0.22, 0.72, 0.32), (1.0, 0.85, 0.35)],
                         "ghost": [(0.55, 0.85, 1.0), (0.78, 0.62, 1.0), (0.55, 0.85, 1.0)],   # will-o'-the-wisps
                         "vampire": [(0.88, 0.14, 0.20), (0.62, 0.55, 0.72), (0.88, 0.14, 0.20)]
                         }.get(costume, [(0.9, 0.3, 0.3), (0.35, 0.65, 0.95), (0.95, 0.8, 0.3)])
                for i, col in enumerate(balls):
                    a = t * 4.5 + i * 2 * math.pi / 3
                    self.oval(bx + math.cos(a) * 36, bt + 2 - abs(math.sin(a)) * 24, 9, 9, hx(col))
            elif pr in ("bang", "err"):
                col = (0.95, 0.75, 0.20) if pr == "bang" else (0.90, 0.30, 0.25)
                yb = bt - 26 - abs(math.sin(t * 7)) * 4
                self.oval(bx, yb, 13, 13, hx(col))
                self.text(bx, yb, "!", dark, 14, bold=True, anchor="center")
            elif pr == "bulb":
                on = getattr(self, "bulb", 0.0)
                ox, oy = (bx + SW / 2 + 20, bt - 18) if costume in HAT_TOP else (bx, bt - 34)   # beside a hat
                if on:
                    self.oval(ox, oy, 30, 30, hx((1.0, 0.92, 0.45), 0.22))
                    for i in range(8):
                        a = i * math.pi / 4 + t
                        self.canvas.create_line(ox + math.cos(a) * 22, oy + math.sin(a) * 22,
                                                ox + math.cos(a) * 30, oy + math.sin(a) * 30,
                                                fill=hx((1.0, 0.92, 0.45)), width=self.lw(3))
                self.oval(ox, oy, 17, 17, hx((1.0, 0.92, 0.45) if on else (0.55, 0.55, 0.50)))
                self.oval(ox - 5, oy - 6, 4, 4, hx((1, 1, 1), 0.8 if on else 0.3))
                self.rect(ox - 8, oy + 14, 16, 10, hx((0.60, 0.62, 0.66)))
                self.rect(ox - 6, oy + 24, 12, 4, hx((0.40, 0.42, 0.46)))
            elif pr == "mug":
                sip = getattr(self, "sip", False)
                mx, my = (bx - SW / 2 + 2, bt + 18) if sip else (bx - SW / 2 - 10, by - 14)
                self.rect(mx - 6, my, 12, 12, hx((0.95, 0.95, 0.92)))
                self.rect(mx - 4, my + 2, 8, 3, hx((0.45, 0.28, 0.18)))
                self.canvas.create_arc(mx + 3, my + 2, mx + 11, my + 9, start=-90, extent=180,
                                       style="arc", outline=hx((0.95, 0.95, 0.92)), width=self.lw(2))
                for i in range(2):
                    wob = math.sin(t * 4 + i * 2) * 2
                    self.oval(mx - 2 + i * 4 + wob, my - 5 - ((t * 10 + i * 5) % 8), 1.5, 2,
                              hx((0.85, 0.85, 0.85), 0.6))
            elif pr == "flames":
                for i in range(5):
                    fx = bx - 22 + i * 11
                    h = 7 + abs(math.sin(t * 13 + i * 1.7)) * 9
                    self.poly([(fx - 5, by - 8), (fx + 5, by - 8), (fx, by - 8 - h)], hx((0.98, 0.55, 0.15)))
                    self.poly([(fx - 2.5, by - 8), (fx + 2.5, by - 8), (fx, by - 8 - h * 0.55)],
                              hx((1.0, 0.88, 0.35)))
            elif pr == "terminal":
                ox, oy = bx + 26, by - 24                  # in front of Clawdy, inside the porthole
                self.rect(ox - 24, oy - 18, 48, 34, hx((0.30, 0.32, 0.36)))
                self.rect(ox - 21, oy - 15, 42, 25, hx((0.06, 0.07, 0.08)))
                scroll = int(t * 6)
                for i in range(4):
                    w = 10 + ((scroll + i) * 7) % 24
                    self.rect(ox - 18, oy - 12 + i * 5, w, 3, hx((0.45, 0.85, 0.45)))
                prog = (t * 0.35) % 1
                self.rect(ox - 21, oy + 12, 42, 4, hx((0.20, 0.21, 0.24)))
                self.rect(ox - 21, oy + 12, 42 * prog, 4, hx((0.45, 0.85, 0.45)))
                self.rect(ox - 5, oy + 16, 10, 8, hx((0.30, 0.32, 0.36)))
            elif pr == "magnifier":
                lx = bx + getattr(self, "lens", 0.0) * 16
                ly = by - 20
                for side in (-1, 1):                     # an open book underneath
                    x = bx if side > 0 else bx - 20
                    self.rect(x - 1, by - 21, 22, 13, hx((0.55, 0.30, 0.20)))
                    self.rect(x + 1, by - 19, 18, 9, hx((0.97, 0.95, 0.88)))
                self.canvas.create_line(lx + 7, ly + 7, lx + 16, ly + 16,
                                        fill=hx((0.55, 0.36, 0.20)), width=self.lw(4))
                self.oval(lx, ly, 10, 10, hx((0.75, 0.76, 0.80)))
                self.oval(lx, ly, 8, 8, hx((0.70, 0.88, 1.0)))
                self.oval(lx - 3, ly - 3, 2.5, 2, hx((1, 1, 1)))
            elif pr == "broom":
                d = self.dir
                sweep = math.sin(t * 9) * 6
                hx0, hy0 = bx + d * (SW / 2 - 4), bt + 24
                fx, fy = bx + d * (SW / 2 + 16) + sweep, by - 2
                self.canvas.create_line(hx0, hy0, fx, fy - 6, fill=hx((0.55, 0.36, 0.20)), width=self.lw(3))
                self.poly([(fx - 8, fy), (fx + 8, fy), (fx + 4, fy - 8), (fx - 4, fy - 8)],
                          hx((0.85, 0.70, 0.35)))

    def draw_parts(self, dt, t):
        alive = []
        for q in self.parts:
            q["life"] -= dt
            if q["life"] <= 0:
                continue
            alive.append(q)
            q["x"] += q["vx"] * dt
            q["y"] += q["vy"] * dt
            if q["k"] in ("spark", "drop", "conf", "fw"):
                q["vy"] += 120 * dt
            a = q["life"] / q["max"]
            x, y, k = q["x"], q["y"], q["k"]
            ccx, ccy = getattr(self, "_center", (x, y))   # closer to Clawdy, to fit the porthole
            x, y = ccx + (x - ccx) * PART_REACH, ccy + (y - ccy) * PART_REACH
            if k == "spark":
                col = hx((1, 0.85, 0.4), a)
                self.rect(x - 1, y - 4, 2, 8, col)
                self.rect(x - 4, y - 1, 8, 2, col)
            elif k == "conf":
                cf = Xform(x, y, 1, 1, t * 8 + q["spin"])
                self.poly([cf.pt(-3, -1.5), cf.pt(3, -1.5), cf.pt(3, 1.5), cf.pt(-3, 1.5)], hx(q["col"], a))
            elif k == "txt":
                self.text(x, y, q["txt"], hx((0.55, 0.85, 0.60), a), 10, bold=True, mono=True)
            elif k == "dust":
                self.oval(x, y, 2 + (1 - a) * 3, 2 + (1 - a) * 3, hx((0.70, 0.65, 0.60), a * 0.6))
            elif k == "drop":
                self.oval(x, y, 4, 5, hx((0.55, 0.80, 1.0), a))
            elif k == "bat":                                # flapping bat
                f = math.sin(t * 18 + q["ph"])
                y += math.sin(t * 4 + q["ph"]) * 4
                col = hx((0.55, 0.42, 0.68), min(1.0, a * 3))   # violet reads on the dark card
                self.oval(x, y, 3.5, 3.5, col)
                self.poly([(x - 2, y), (x - 14, y - 2 - 7 * f), (x - 9, y + 3)], col)
                self.poly([(x + 2, y), (x + 14, y - 2 - 7 * f), (x + 9, y + 3)], col)
                eye = hx((1.0, 0.85, 0.3), min(1.0, a * 3))
                self.rect(x - 2, y - 1.5, 1.5, 1.5, eye)
                self.rect(x + 0.5, y - 1.5, 1.5, 1.5, eye)
            elif k == "bubble":
                self.oval(x, y, 3, 3, hx((0.45, 0.90, 0.40), a))
            elif k == "fw":
                self.rect(x - 2.5, y - 2.5, 5, 5, hx(q["col"], a))
                self.rect(x - q["vx"] * 0.05 - 1.5, y - q["vy"] * 0.05 - 1.5, 3, 3, hx(q["col"], a * 0.5))
            elif k == "puff":
                r = 4 + (1 - a) * 6
                self.oval(x, y, r, r, hx((0.72, 0.70, 0.78), a * 0.8))
            elif k == "snow":
                x += math.sin(t * 2 + q["ph"]) * 4
                self.rect(x - 1.5, y - 1.5, 3, 3, hx((0.95, 0.97, 1.0), min(1.0, a * 2)))
            elif k == "star":
                col = hx(q["col"], a)
                sf = Xform(x, y, 1, 1, t * 6)
                self.poly([sf.pt(0, -5), sf.pt(1.5, -1.5), sf.pt(5, 0), sf.pt(1.5, 1.5),
                           sf.pt(0, 5), sf.pt(-1.5, 1.5), sf.pt(-5, 0), sf.pt(-1.5, -1.5)], col)
            else:
                glyph, col, size = {"heart": ("♥", (0.95, 0.4, 0.5), 13),
                                    "note": ("♪", (0.95, 0.85, 0.5), 14),
                                    "z": ("z", TXT, int(10 + (1 - a) * 5)),
                                    "?": ("?", TXT, 15),
                                    "dots": ("…", TXT, 15),
                                    "boo": (tr("say.boo"), (0.97, 0.97, 1.0), 16),
                                    "jo": (tr("say.ho"), (1.0, 1.0, 1.0), 13)}[k]
                tx = x + math.sin(t * 4 + y) * 3
                if k in ("boo", "jo"):              # dark outline: readable on anything
                    for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
                        self.text(tx + ox, y + oy, glyph, hx((0.10, 0.08, 0.08), a), size, bold=True,
                                  anchor="center")
                self.text(tx, y, glyph, hx(col, a), size, bold=True, anchor="center")
        self.parts = alive[-60:]

    # ------------------------------------------------ full frame

    def draw(self):
        st = self.st
        rows = bars(st.data) if st.data else []
        tracks = len(rows[:len(RING_RS)]) or 2
        f = self.fill()
        if f <= 0:
            rows = []                       # no fresh usage yet: empty rings, no numbers
        elif f < 1:
            q = round(f * 14) / 14          # a few steps: each one re-renders the rings
            rows = [(n, p * q, r) for n, p, r in rows]
        near = bool(self.mouse and self.on_plus(*self.mouse))
        key = (tuple((n, round(p), r) for n, p, r in rows), self.work, near, st.error, self.setup_phase,
               st.updated, st.retry_at > time.time(), int(time.time() // 30), self.update_label())
        if key != self._skey:               # rebuild the static layer only when something changed
            self._skey = key
            self.canvas.delete("bg")
            self.canvas.delete("static")
            mark = self.canvas.create_line(0, 0, 0, 0)
            self.card(CW)
            self.layer(mark, "bg")
            mark = self.canvas.create_line(0, 0, 0, 0)
            self.draw_rings(0, rows, tracks)
            self.draw_column(0, rows, near)
            self.layer(mark, "static")
            self.canvas.tag_lower("bg")
        self.canvas.delete("dyn")
        mark = self.canvas.create_line(0, 0, 0, 0)
        top = max((p for _, p, _ in rows), default=0)
        # Center the whole figure, hat included, in the porthole.
        drop = (-HAT_TOP.get(self.costume(), -27) - 27) / 2 * SCENE_K
        self.draw_scene(top, SCENE_K, RING_C[0], RING_C[1] + drop)
        pmark = self.canvas.create_line(0, 0, 0, 0)
        self.plus()
        for item in self.canvas.find_all():
            if item > pmark:
                self.canvas.addtag_withtag("plus", item)
        self.canvas.delete(pmark)
        self.layer(mark, "dyn")
        # Clawdy sits between the background and the rings: the rings are a round
        # porthole and anything outside it passes behind. The button is on top.
        self.canvas.tag_raise("static")
        self.canvas.tag_raise("plus")
        if self.panel_out:
            self.draw_panel_window(rows, key)

    def layer(self, mark, tag):
        """Tag everything drawn after `mark` and scale it to screen size."""
        for item in self.canvas.find_all():
            if item > mark:
                self.canvas.addtag_withtag(tag, item)
        self.canvas.delete(mark)
        if self.k != 1.0:
            self.canvas.scale(tag, 0, 0, self.k, self.k)   # moves positions; images keep their size

    def card(self, w):
        card = hx(CARD)
        if self.rounded:                    # rounded corners
            r = 16
            self.rect(r, 0, w - 2 * r, H, card)
            self.rect(0, r, w, H - 2 * r, card)
            for cx, cy in ((r, r), (w - r, r), (r, H - r), (w - r, H - r)):
                self.oval(cx, cy, r, r, card)
        else:
            self.rect(0, 0, w, H, card)
            self.canvas.create_rectangle(0, 0, w - 1, H - 1, outline=hx((0.25, 0.23, 0.21)), width=1)

    def draw_panel_window(self, rows, key):
        """The panel lives in its own window and is redrawn only when data changes."""
        if key == self._pkey:
            return
        self._pkey = key
        main, self.canvas = self.canvas, self.pcanvas
        try:
            self.canvas.delete("all")
            mark = self.canvas.create_line(0, 0, 0, 0)
            self.card(PW)
            self.draw_panel(0, rows, 1.0)
            self.layer(mark, "panel")
        finally:
            self.canvas = main

    def draw_rings(self, cx, rows, tracks=2):
        pcts = tuple(round(p) for _, p, _ in rows[:len(RING_RS)]) or (None,) * tracks
        if (pcts, self.k) != self._ring_key:
            self._ring_key = (pcts, self.k)
            self._ring_img = self.ring_image(pcts)
        # the image is already at screen resolution: place it by its center
        self.canvas.create_image(cx + RING_C[0], RING_C[1], image=self._ring_img)
        for x in (cx, cx + CW - 2):            # the image stops ~1 px short of the card edges
            self.rect(x, 16, 2, RING_C[1] + RING_RS[0] - 16, hx(CARD))

    def ring_image(self, pcts):
        """Antialiased rings with round caps, rasterized by hand (Tk can't).

        Drawn over the card color, so no alpha is needed. The inside of the
        porthole is transparent. Rebuilt only when the percentages change."""
        k = self.k
        size = int(math.ceil(2 * (RING_RS[0] + RING_W / 2 + 2) * k))
        c = size / 2.0
        half = RING_W * k / 2.0
        track = tuple(1 * 0.09 + b * 0.91 for b in CARD)
        rings = []
        hole = RING_RS[len(pcts) - 1] * k        # the innermost ring is the porthole edge
        clear = []
        for r, p in zip(RING_RS, pcts):
            rr = r * k
            ext = 270.0 * min(p, 100) / 100 if p else 0.0
            def cap(a, rr=rr):
                return rr * math.cos(math.radians(a)), -rr * math.sin(math.radians(a))
            rings.append((rr, ext, cap(225), cap(225 - 270), cap(225 - ext),
                          bar_color(p) if p else None))

        def cover(dx, dy, dist, t, rr, span, c0, c1):
            if t <= span:
                d = abs(dist - rr) - half
            else:
                d = min(math.hypot(dx - c0[0], dy - c0[1]), math.hypot(dx - c1[0], dy - c1[1])) - half
            return 0.0 if d >= 0.5 else (1.0 if d <= -0.5 else 0.5 - d)

        rows = []
        for py in range(size):
            dy = py + 0.5 - c
            row = []
            for px in range(size):
                dx = px + 0.5 - c
                dist = math.hypot(dx, dy)
                col = CARD
                hit = False
                for rr, ext, cs0, ct1, cf1, fcol in rings:
                    if abs(dist - rr) > half + 1:
                        continue
                    t = (225.0 - math.degrees(math.atan2(-dy, dx))) % 360.0
                    a = cover(dx, dy, dist, t, rr, 270.0, cs0, ct1)
                    if a:
                        hit = True
                        col = tuple(x * a + y * (1 - a) for x, y in zip(track, col))
                    if fcol:
                        a = cover(dx, dy, dist, t, rr, ext, cs0, cf1)
                        if a:
                            col = tuple(x * a + y * (1 - a) for x, y in zip(fcol, col))
                if dist < hole and not hit:
                    clear.append((px, py))        # inside the porthole: Clawdy shows through
                row.append(hx(col))
            rows.append("{" + " ".join(row) + "}")
        img = tk.PhotoImage(width=size, height=size)
        img.put(" ".join(rows))
        for px, py in clear:
            img.transparency_set(px, py, True)
        return img

    def draw_column(self, cx, rows, near):
        # one number per ring in the bottom gap, outer to inner
        shown = rows[:len(RING_RS)]
        step = 21
        num_y = RING_C[1] + 43
        xs = [cx + RING_C[0] + (i - (len(shown) - 1) / 2) * step for i in range(len(shown))]
        for x, (name, p, _) in zip(xs, shown):
            self.text(x, num_y, "%.0f" % p, hx(bar_color(p)), 8, bold=True, anchor="center")
        if not shown:
            self.text(cx + RING_C[0], num_y, "—", hx(DIM), 8, bold=True, anchor="center")

        # bottom line: the most important thing to say, else the names
        mid = cx + CW / 2
        upd = self.update_label()
        if near:
            self.text(mid, INFO_Y, tr("chat.app") if self.has_app else tr("chat.web"),
                      hx(TXT), 6, anchor="center")
        elif upd:
            self.text(mid, INFO_Y, upd[0], hx(upd[1]), 5, bold=True, anchor="center")
        elif self.work:
            self.text(mid, INFO_Y, label(self.work, short=True), hx(ORANGE), 6, bold=True, anchor="center")
        elif not rows and self.setup_phase:
            self.text(mid, INFO_Y, tr("need." + self.setup_phase), hx(ORANGE), 5, bold=True, anchor="center")
        elif not rows and self.no_usage():     # clickable: sets up Claude Code
            self.text(mid, INFO_Y, tr("need." + self.st.need), hx(ORANGE), 5, bold=True, anchor="center")
        elif not rows:
            self.text(mid, INFO_Y, self.status_msg()[:22], hx(DIM), 5, anchor="center")
        else:
            for x, (name, _, _) in zip(xs, shown):
                self.text(x, INFO_Y, short_name(name), hx(DIM), 5, anchor="center")

    def draw_panel(self, px, rows, a):
        st = self.st
        x0, x1 = px + 11, px + PW - 11
        self.text(x0, 9, tr("panel.title"), hx(DIM, a), 5, bold=True)
        if not rows:
            self.text(px + PW / 2, H / 2, self.status_msg(), hx(DIM, a), 7, anchor="center")
        shown = rows[:4]
        tight = len(shown) > 3            # with 4 limits the reset goes on the same line
        gap = 21 if tight else 27
        y = 22
        for name, p, reset in shown:
            self.text(x0, y, name, hx(TXT, a), 7)
            self.text(x1, y, "%.0f%%" % p, hx(TXT, a), 7, bold=True, anchor="e")
            if reset:
                if tight:
                    self.text(x1 - 26, y, until(reset), hx(DIM, a), 5, anchor="e")
                else:
                    self.text(x0, y + 15, tr("time.resets_in", t=until(reset)), hx(DIM, a), 5)
            self.rect(x0, y + 6, x1 - x0, 3, hx((1, 1, 1), 0.12 * a))
            self.rect(x0, y + 6, (x1 - x0) * min(p, 100) / 100, 3, hx(bar_color(p), a))
            y += gap
        if self.work:
            self.text(x0, H - 8, label(self.work), hx(ORANGE, a), 5, bold=True)
        elif st.error:
            self.text(x0, H - 8, st.error, hx(DIM, a), 5)
        elif st.updated:
            self.text(x0, H - 8, tr("time.updated", t=datetime.fromtimestamp(st.updated).strftime("%H:%M")),
                      hx(DIM, a), 5)

    def status_msg(self):
        st = self.st
        if st.error and st.retry_at > time.time():
            return tr("status.waiting", t=until(
                datetime.fromtimestamp(st.retry_at, timezone.utc).isoformat()))
        return st.error or tr("status.loading")

    def draw_scene(self, top, k, ax, ay):
        """Clawdy and its props, drawn at full scale and then moved into place."""
        mark = self.canvas.create_line(0, 0, 0, 0)
        self.fscale = k
        try:
            self.draw_clawd(SCENE_W / 2, 112, top)
        finally:
            self.fscale = 1.0
        for item in self.canvas.find_all():
            if item > mark:
                self.canvas.addtag_withtag("scene", item)
        self.canvas.delete(mark)
        if k != 1.0:
            self.canvas.scale("scene", SCENE_W / 2, 85, k, k)
        self.canvas.move("scene", ax - SCENE_W / 2, ay - 85)
        self.canvas.dtag("scene", "scene")

    def gauge(self, cx, cy, r, width, p, a=1.0, track=0.13):
        """A ring open at the bottom, filling clockwise."""
        box = (cx - r, cy - r, cx + r, cy + r)
        self.canvas.create_arc(*box, start=225, extent=-270, style="arc",
                               outline=hx((1, 1, 1), track * a), width=width)
        if p is None or p <= 0:
            return
        col = hx(bar_color(p), a)
        ext = -270 * min(p, 100) / 100
        self.canvas.create_arc(*box, start=225, extent=ext, style="arc", outline=col, width=width)
        for ang in (225, 225 + ext):                     # round caps
            x, y = cx + r * math.cos(math.radians(ang)), cy - r * math.sin(math.radians(ang))
            self.oval(x, y, width / 2, width / 2, col)

    def plus(self):
        """New chat button: pulses when idle, turns on hover and ripples on click."""
        x, y, r = self.plus_at()
        now = time.time()
        dt = min(now - self._plus_last, 0.1)
        self._plus_last = now
        near = bool(self.mouse and self.on_plus(*self.mouse))
        self.plus_hover += ((1.0 if near else 0.0) - self.plus_hover) * min(1.0, dt * 12)
        hv = ease(clamp(self.plus_hover))
        since = now - self.plus_click

        if hv < 0.05 and since > 1.0:               # idle: a soft halo every 3.5 s
            ph = (now % 3.5) / 1.4
            if ph < 1.0:
                self.halo(x, y, r + 1 + ph * 4, 1.0, ORANGE, 0.45 * (1 - ph))
        if since < 0.55:                            # click: an expanding ripple
            q = since / 0.55
            self.halo(x, y, r + 2 + ease(q) * 9, (2.5 - q) / 2, (0.95, 0.65, 0.5), 0.8 * (1 - q))

        press = math.sin(math.pi * min(since / 0.2, 1.0)) if since < 0.2 else 0.0
        rad = r * (1 + 0.12 * hv - 0.14 * press)
        spin = 90 * hv + (180 * ease(min(since / 0.45, 1.0)) if since < 0.45 else 0.0)
        key = ("btn", round(rad * self.k * 4), round(hv * 12), round(spin % 90 / 3) % 30)
        img = self.smooth_image(key, lambda: self.button_pixels(rad, hv, spin))
        self.canvas.create_image(x, y, image=img)

    def halo(self, x, y, rr, half, col, a):
        key = ("halo", round(rr * self.k * 2), round(half * 4), round(a * 20), col)
        img = self.smooth_image(key, lambda: self.halo_pixels(rr, half, col, a))
        self.canvas.create_image(x, y, image=img)

    def smooth_image(self, key, make):
        """Antialiased images for the + button, cached per screen scale."""
        cache = self._smooth
        if cache.get("k") != self.k or len(cache) > 800:
            cache.clear()
            cache["k"] = self.k
        if key not in cache:
            cache[key] = self.raster(*make())
        return cache[key]

    def raster(self, size, pixel):
        """A size×size PhotoImage; pixel(dx, dy) returns (rgb, coverage) around the center."""
        img = tk.PhotoImage(width=size, height=size)
        c = size / 2.0
        rows, clear = [], []
        for py in range(size):
            row = []
            for px in range(size):
                col, a = pixel(px + 0.5 - c, py + 0.5 - c)
                if a < 0.04:
                    clear.append((px, py))
                    a = 0.0
                row.append(hx(tuple(f * a + b * (1 - a) for f, b in zip(col, CARD))))
            rows.append("{" + " ".join(row) + "}")
        img.put(" ".join(rows))
        for px, py in clear:
            img.transparency_set(px, py, True)
        return img

    def button_pixels(self, rad, hv, spin):
        k = self.k
        R = rad * k
        arm, th = R * 0.43, 1.5 * k
        fill = tuple(lerp(a, b, hv) for a, b in zip(ORANGE, (0.95, 0.60, 0.47)))
        ca, sa = math.cos(math.radians(spin)), math.sin(math.radians(spin))

        def pixel(dx, dy):
            disc = clamp(R - math.hypot(dx, dy) + 0.5)
            if not disc:
                return fill, 0.0
            u, v = abs(dx * ca + dy * sa), abs(-dx * sa + dy * ca)
            cross = max(clamp(0.5 - max(u - arm, v - th)), clamp(0.5 - max(v - arm, u - th)))
            return tuple(lerp(f, 1.0, cross) for f in fill), disc
        return int(math.ceil(2 * R + 2)) | 1, pixel

    def halo_pixels(self, rr, half, col, a):
        k = self.k
        R, hw = rr * k, max(half * k, 0.6)

        def pixel(dx, dy):
            return col, a * clamp(hw + 0.5 - abs(math.hypot(dx, dy) - R))
        return int(math.ceil(2 * (R + hw) + 2)) | 1, pixel


# ---------------------------------------------------------------- menu

def round_rect(canvas, x1, y1, x2, y2, r, **kw):
    """Rounded rectangle (smoothed polygon)."""
    r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


class PopupMenu:
    """Right-click menu in Clawdy's style: dark and rounded, with switches and
    pills instead of checkboxes and submenus."""

    MW, ROW, PAD = 236, 26, 10
    COSTUMES = ("auto", "none", "witch", "pumpkin", "ghost", "vampire", "santa")

    def __init__(self, w, x_root, y_root):
        self.w, self.k = w, w.k
        self.hover, self.left_at, self.closed = None, None, False
        self.items = [
            ("title", "Clawdy", "v" + VERSION),
            ("action", tr("menu.chat_app" if w.has_app else "menu.chat_web"), w.new_chat),
            ("action", tr("menu.refresh"), w.refresh),
            ("action", tr("menu.updates"), lambda: w.check_updates(True)),
            ("sep",),
            ("toggle", tr("menu.hooks"), w.v_hooks, w.toggle_hooks),
            ("toggle", tr("menu.autostart"), w.v_start, w.toggle_start),
            ("toggle", tr("menu.pin"), w.v_pin, w.toggle_pin),
            ("toggle", tr("menu.walks"), w.v_walks, w.toggle_walks),
            ("sep",),
            ("pills", tr("menu.size"), [(v, tr(l)) for v, l in SIZES], lambda: w.scale, w.set_scale, 3),
            ("pills", tr("menu.costume"), [(c, tr("costume." + c)) for c in self.COSTUMES], lambda: w.costume_pref, w.set_costume, 3),
            ("sep",),
            ("action", tr("menu.quit"), w.root.destroy, "danger"),
        ]
        if w.tray and w.tray.active:
            self.items.insert(-1, ("action", tr("menu.hide"), w.hide))
        self.layout()
        k = self.k
        self.win = tk.Toplevel(w.root)
        pw, ph = round(self.MW * k), round(self.h * k)
        self.canvas = w.make_window(self.win, pw, ph)
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        x = max(4, min(x_root, sw - pw - 4))
        y = max(4, min(y_root, sh - ph - 4))
        self.win.geometry("+%d+%d" % (x, y))
        self.win.update_idletasks()
        w.round_corners(self.win, pw, ph, radius=12)
        c = self.canvas
        c.bind("<Motion>", self.on_motion)
        c.bind("<Leave>", self.on_leave)
        c.bind("<Button-1>", self.on_click)
        for seq in ("<Button-3>", "<Button-2>"):
            c.bind(seq, lambda e: self.close())
        self.win.bind("<Escape>", lambda e: self.close())
        self.win.bind("<FocusOut>", lambda e: self.win.after(150, self.check_focus))
        self.draw()
        try:
            self.win.focus_force()
        except tk.TclError:
            pass
        self.win.after(250, self.watch)

    # -------- layout --------
    def layout(self):
        """Where everything goes: [(kind, item, x1, y1, x2, y2, extra)]."""
        P, R, W = self.PAD, self.ROW, self.MW
        y, self.hits, self.drawn = P, [], []
        for it in self.items:
            kind = it[0]
            if kind == "title":
                self.drawn.append(("title", it, P, y, W - P, y + 22))
                y += 26
            elif kind == "sep":
                self.drawn.append(("sep", it, P, y + 4, W - P, y + 4))
                y += 9
            elif kind in ("action", "toggle"):
                box = (P - 4, y, W - P + 4, y + R)
                self.drawn.append((kind, it, *box))
                self.hits.append((box, it, None))
                y += R
            elif kind == "pills":
                _, label, options, get, set_, per_row = it
                self.drawn.append(("label", it, P, y, W - P, y + 18))
                y += 18
                pw = (W - 2 * P - (per_row - 1) * 5) / per_row
                for i, (value, text) in enumerate(options):
                    col, row = i % per_row, i // per_row
                    x1 = P + col * (pw + 5)
                    y1 = y + row * 24
                    box = (x1, y1, x1 + pw, y1 + 20)
                    self.drawn.append(("pill", (it, value, text), *box))
                    self.hits.append((box, it, value))
                y += ((len(options) + per_row - 1) // per_row) * 24 + 4
        self.h = y + P - 4

    # -------- drawing --------
    def draw(self):
        c, k, w = self.canvas, self.k, self.w
        c.delete("all")
        S = lambda v: v * k
        fam = w.fam
        font = lambda size, bold=False: (fam, max(6, round(size * w.scale)), "bold" if bold else "normal")
        round_rect(c, 0, 0, S(self.MW) - 1, S(self.h) - 1, S(12), fill=hx(CARD),
                   outline=hx((0.30, 0.27, 0.25)), width=1)
        for d in self.drawn:
            kind, it, x1, y1, x2, y2 = d
            hov = self.hover is not None and self.hover[0] == (x1, y1, x2, y2)
            if kind == "title":
                c.create_text(S(x1), S(y1 + 10), text=it[1], fill=hx(ORANGE), anchor="w", font=font(10, True))
                c.create_text(S(x2), S(y1 + 10), text=it[2], fill=hx(DIM), anchor="e", font=font(7))
            elif kind == "sep":
                c.create_line(S(x1), S(y1), S(x2), S(y2), fill=hx((1, 1, 1), 0.10), width=1)
            elif kind == "label":
                c.create_text(S(x1), S(y1 + 9), text=it[1], fill=hx(DIM), anchor="w", font=font(7, True))
            elif kind in ("action", "toggle"):
                if hov:
                    round_rect(c, S(x1), S(y1 + 1), S(x2), S(y2 - 1), S(7), fill=hx((1, 1, 1), 0.08), width=0)
                danger = kind == "action" and len(it) > 3 and it[3] == "danger"
                col = (0.95, 0.45, 0.40) if danger else TXT
                c.create_text(S(x1 + 8), S((y1 + y2) / 2), text=it[1], fill=hx(col), anchor="w", font=font(9))
                if kind == "toggle":                       # switch
                    on = bool(it[2].get())
                    tx2, ty = S(x2 - 8), S((y1 + y2) / 2)
                    tw, th = S(26), S(14)
                    round_rect(c, tx2 - tw, ty - th / 2, tx2, ty + th / 2, th / 2,
                               fill=hx(ORANGE if on else (0.32, 0.30, 0.28)), width=0)
                    kx = tx2 - th / 2 if on else tx2 - tw + th / 2
                    c.create_oval(kx - S(5), ty - S(5), kx + S(5), ty + S(5), fill=hx((1, 1, 1)), width=0)
            elif kind == "pill":
                item, value, text = it
                sel = item[3]() == value
                fill = ORANGE if sel else ((0.30, 0.28, 0.26) if hov else (0.20, 0.19, 0.17))
                round_rect(c, S(x1), S(y1), S(x2), S(y2), S(10), fill=hx(fill), width=0)
                c.create_text(S((x1 + x2) / 2), S((y1 + y2) / 2), text=text,
                              fill=hx((1, 1, 1) if sel else TXT), font=font(7, sel))

    # -------- interaction --------
    def find(self, ev):
        x, y = ev.x / self.k, ev.y / self.k
        for box, it, value in self.hits:
            if box[0] <= x <= box[2] and box[1] <= y <= box[3]:
                return box, it, value
        return None

    def on_motion(self, ev):
        self.left_at = None
        hit = self.find(ev)
        if (hit and hit[0]) != (self.hover and self.hover[0]):
            self.hover = hit
            self.draw()

    def on_leave(self, ev):
        self.left_at = time.time()
        if self.hover:
            self.hover = None
            self.draw()

    def on_click(self, ev):
        hit = self.find(ev)
        if not hit:
            return
        _, it, value = hit
        kind = it[0]
        if kind == "action":
            self.close()
            it[2]()
        elif kind == "toggle":
            it[2].set(not it[2].get())
            it[3]()
            self.draw()
            self.win.lift()
        elif kind == "pills":
            it[4](value)
            if it[4] == self.w.set_scale:   # the widget was resized: so is the menu
                self.close()
            else:
                self.draw()

    def watch(self):
        """Close by itself once the mouse has been gone for a while."""
        if self.closed:
            return
        if self.left_at and time.time() - self.left_at > 1.2:
            self.close()
            return
        self.win.after(200, self.watch)

    def check_focus(self):
        if self.closed:
            return
        try:
            focus = self.win.focus_get()
        except (tk.TclError, KeyError):
            focus = None
        if focus is None and self.left_at:
            self.close()

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.w.popup_menu is self:
            self.w.popup_menu = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass


# ---------------------------------------------------------------- welcome

class Welcome:
    """First run: explain what it does and ask before touching anything."""

    def __init__(self, root, on_done):
        from tkinter import ttk
        self.root, self.on_done = root, on_done
        win = self.win = tk.Toplevel(root)
        win.title(tr("welcome.title"))
        win.resizable(False, False)
        win.protocol("WM_DELETE_WINDOW", self.skip)
        style = ttk.Style(win)
        if not cs.WIN and not cs.MAC and "clam" in style.theme_names():
            style.theme_use("clam")

        k = max(1.0, min(3.0, root.winfo_fpixels("1i") / 96.0))
        banner = tk.Canvas(win, width=round(420 * k), height=round(120 * k),
                           bg=hx(CARD), highlightthickness=0)
        banner.pack(fill="x")
        px = 7 * k
        x0, y0 = 210 * k - len(SPRITE[0]) * px / 2, 60 * k - len(SPRITE) * px / 2
        for r, row in enumerate(SPRITE):
            for c, ch in enumerate(row):
                if ch != ".":
                    col = {"E": DARK, "L": ORANGE_D}.get(ch, ORANGE)
                    banner.create_rectangle(x0 + c * px, y0 + r * px, x0 + (c + 1) * px,
                                            y0 + (r + 1) * px, fill=hx(col), width=0)

        body = ttk.Frame(win, padding=(24, 16, 24, 20))
        body.pack(fill="both")
        ttk.Label(body, text=tr("welcome.hi"), font=("TkDefaultFont", 15, "bold")).pack(anchor="w")
        ttk.Label(body, wraplength=round(370 * k), justify="left",
                  text=tr("welcome.intro")
                  ).pack(anchor="w", pady=(6, 12))
        if not cs.logged_in():
            ttk.Label(body, wraplength=round(370 * k), justify="left", foreground="#b5482a",
                      text=tr("welcome.no_login")).pack(anchor="w", pady=(0, 12))

        self.v_hooks = tk.BooleanVar(value=True)
        self.v_start = tk.BooleanVar(value=True)
        ttk.Checkbutton(body, text=tr("welcome.hooks"),
                        variable=self.v_hooks).pack(anchor="w")
        ttk.Checkbutton(body, text=tr("welcome.autostart"),
                        variable=self.v_start).pack(anchor="w", pady=(4, 0))
        ttk.Label(body, foreground="#777777", wraplength=round(370 * k), justify="left",
                  text=tr("welcome.hint")
                  ).pack(anchor="w", pady=(10, 14))
        btn = ttk.Button(body, text=tr("welcome.start"), command=self.done)
        btn.pack(anchor="e")
        btn.focus_set()
        win.bind("<Return>", lambda e: self.done())

        win.update_idletasks()
        x = (win.winfo_screenwidth() - win.winfo_reqwidth()) // 2
        y = (win.winfo_screenheight() - win.winfo_reqheight()) // 3
        win.geometry("+%d+%d" % (x, y))
        win.lift()
        win.focus_force()

    def done(self):
        err = cs.setup(hooks=self.v_hooks.get(), autostart=self.v_start.get())
        self.win.destroy()
        self.on_done(err)

    def skip(self):
        """Closing the welcome changes nothing; it shows again next time."""
        self.win.destroy()
        self.on_done(None)


# ---------------------------------------------------------------- startup

def dpi_aware():
    if not cs.WIN:
        return
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def hide_from_dock():
    """A widget doesn't belong in the Dock. Tk registers a regular app at startup
    (it ignores LSUIElement), so switch the activation policy afterwards."""
    try:
        import ctypes
        import ctypes.util
        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        get = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(
            ("objc_msgSend", objc))
        set_policy = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long)(
            ("objc_msgSend", objc))
        app = get(objc.objc_getClass(b"NSApplication"), objc.sel_registerName(b"sharedApplication"))
        set_policy(app, objc.sel_registerName(b"setActivationPolicy:"), 1)   # 1 = accessory
    except Exception:
        pass


def run(demo=False, selftest=0):
    global tk
    try:
        import tkinter
    except ImportError:
        if sys.stdout:
            print(tr("run.no_tk"))
        return 1
    tk = tkinter

    lock = cs.single_instance()
    if lock is None and not (demo or selftest):
        try:
            import socket
            with socket.create_connection(("127.0.0.1", cs.LOCK_PORT), timeout=1) as c:
                c.sendall(b"show")             # already running: make it wave
        except OSError:
            pass
        return 0

    dpi_aware()
    root = tk.Tk()
    root.withdraw()
    if cs.MAC:
        # Tk on macOS assumes 72 points per inch; 96 matches Windows and Linux.
        root.tk.call("tk", "scaling", 96 / 72)
        hide_from_dock()
    try:
        root.iconphoto(True, tk.PhotoImage(file=cs.resource("assets", "icon.png")))
    except Exception:
        pass

    app = {"widget": None, "welcome": None}

    def start(err=None):
        app["welcome"] = None
        w = app["widget"] = Widget(root, demo=demo)
        if err:
            w.st.error = err[:60]
        root.deiconify()
        if selftest:
            root.after(selftest * 1000, root.destroy)

    def poll_lock():
        """Listen to other copies or the uninstaller, also during the welcome."""
        msg = b""
        try:
            conn, _ = lock.accept()
        except (BlockingIOError, OSError):
            conn = None
        if conn:
            try:
                conn.settimeout(0.5)
                msg = conn.recv(16)
            except OSError:
                pass
            finally:
                conn.close()
        if msg.startswith(b"quit"):
            root.destroy()
            return
        if msg.startswith(b"walk") and app["widget"]:
            app["widget"].maybe_walk(force=True)
        if msg.startswith(b"show"):
            if app["widget"]:
                app["widget"].greet()
            elif app["welcome"]:
                app["welcome"].win.lift()
                app["welcome"].win.focus_force()
        root.after(200, poll_lock)

    if lock:
        poll_lock()
    if cs.load_config().get("setup_done") or demo or selftest:
        start()
    else:
        app["welcome"] = Welcome(root, on_done=start)
    root.mainloop()
    if app["widget"] and app["widget"].tray:
        app["widget"].tray.stop()
    return 0
