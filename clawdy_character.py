"""The character: a body color plus one part per slot (head, face, body) and,
optionally, a whole skin drawn by the user. Built-in costumes are presets of
parts. Parts are 32×32 PNGs in assets/parts/<slot>/, user skins live in
<config>/skins/ (see clawdy_skins.py for the pixel format)."""
import os
import random

import clawdy_system as cs

SLOTS = ("head", "face", "body")
PARTS = {"head": ["witch", "santa", "elf", "antlers", "tophat", "caphelmet", "thorhelm", "doomhood", "frank",
                  "slick", "cowboy", "chef", "pirate", "astronaut", "ninja"],
         "face": ["stitches", "fangs", "rednose", "carrot", "scowl", "glasses", "eyepatch", "blush"],
         "body": ["cape", "bolts", "sheet", "pumpkin", "scarf", "snowcoat", "gingerbread", "tree", "sweater",
                  "ironsuit", "capsuit", "thorcape", "hulkpants", "spidersuit", "doomcape", "bandana"]}
# body colors: (key, rgb 0-1). The first one is Clawdy's own.
COLORS = [("orange", (0.851, 0.467, 0.341)), ("coral", (0.93, 0.42, 0.42)), ("gold", (0.93, 0.70, 0.25)),
          ("green", (0.33, 0.72, 0.50)), ("teal", (0.25, 0.65, 0.68)), ("sky", (0.40, 0.65, 0.92)),
          ("lavender", (0.62, 0.52, 0.88)), ("pink", (0.94, 0.56, 0.74)), ("cream", (0.93, 0.88, 0.78)),
          ("slate", (0.42, 0.45, 0.52))]
PRESETS = {"none": {}, "witch": {"head": "witch"}, "pumpkin": {"body": "pumpkin"}, "ghost": {"body": "sheet"},
           "vampire": {"head": "slick", "face": "fangs", "body": "cape"},
           "frank": {"head": "frank", "face": "stitches", "body": "bolts"}, "santa": {"head": "santa"},
           "elf": {"head": "elf", "body": "sweater"}, "reindeer": {"head": "antlers", "face": "rednose"},
           "snowman": {"head": "tophat", "face": "carrot", "body": "snowcoat"},
           "gingerbread": {"body": "gingerbread"}, "tree": {"body": "tree"},
           "iron": {"body": "ironsuit"}, "captain": {"head": "caphelmet", "body": "capsuit"},
           "thunder": {"head": "thorhelm", "body": "thorcape"},
           "hulk": {"color": "green", "face": "scowl", "body": "hulkpants"},
           "spidey": {"body": "spidersuit"}, "doom": {"head": "doomhood", "body": "doomcape"},
           "cowboy": {"head": "cowboy", "body": "bandana"}, "chef": {"head": "chef"},
           "pirate": {"head": "pirate", "face": "eyepatch"}, "astronaut": {"head": "astronaut"},
           "ninja": {"head": "ninja"}}
PRESET_ORDER = ["none", "witch", "pumpkin", "ghost", "vampire", "frank", "santa", "elf", "reindeer",
                "snowman", "gingerbread", "tree", "iron", "captain", "thunder", "hulk", "spidey", "doom",
                "cowboy", "chef", "pirate", "astronaut", "ninja"]
BEHAVES = ("ghost", "pumpkin", "witch", "vampire", "frank", "santa", "reindeer", "snowman",
           "gingerbread", "tree", "elf", "iron", "captain", "thunder", "hulk", "spidey", "doom")
HEROES = ("iron", "captain", "thunder", "hulk", "spidey", "doom")
XMAS = ("santa", "reindeer", "elf", "snowman", "gingerbread", "tree")   # the Christmas wardrobe, by day


def load(cfg=None):
    cfg = cfg if cfg is not None else cs.load_config()
    ch = cfg.get("character") or {}
    out = {"color": ch.get("color") or "orange", "skin": ch.get("skin")}
    for slot in SLOTS:
        v = ch.get(slot)
        out[slot] = v if v in PARTS[slot] else None
    if out["color"] not in dict(COLORS):
        out["color"] = "orange"
    return out


def save(ch):
    cs.update_config(character={k: ch.get(k) for k in ("color", "skin") + SLOTS})


def color_rgb(ch):
    return dict(COLORS).get(ch.get("color"), COLORS[0][1])


def preset(name, color="orange"):
    ch = {"color": color, "skin": None, "head": None, "face": None, "body": None}
    ch.update(PRESETS.get(name, {}))
    return ch


def identity(ch):
    """Which built-in costume this character behaves like (tricks, walks, props)."""
    if ch.get("skin"):
        return "custom"
    for name in BEHAVES:                     # ghost and pumpkin first: whole-body looks
        p = PRESETS[name]
        if all(ch.get(slot) == part for slot, part in p.items() if slot in SLOTS):
            return name
    return "custom" if any(ch.get(s) for s in SLOTS) else "none"


def matches(ch, name):
    """True when the character is exactly this preset (any color)."""
    p = PRESETS.get(name, {})
    return not ch.get("skin") and all(ch.get(s) == p.get(s) for s in SLOTS)


def shuffle(ch):
    out = dict(ch)
    out["skin"] = None
    out["color"] = random.choice(COLORS)[0]
    for slot in SLOTS:
        out[slot] = random.choice(PARTS[slot] + [None, None])
    if not any(out[s] for s in SLOTS):
        out["head"] = random.choice(PARTS["head"])
    return out


def part_path(slot, name, back=False):
    return cs.resource("assets", "parts", slot, name + ("_back" if back else "") + ".png")


_FRAMES = {}
FRAME_RATE = 3                                   # animated parts: frames per second


def part_frames(slot, name):
    """[paths] of an animated part (name.png, name_f2.png, name_f3.png…), cached."""
    key = (slot, name)
    if key not in _FRAMES:
        frames = [part_path(slot, name)]
        n = 2
        while os.path.exists(cs.resource("assets", "parts", slot, "%s_f%d.png" % (name, n))):
            frames.append(cs.resource("assets", "parts", slot, "%s_f%d.png" % (name, n)))
            n += 1
        _FRAMES[key] = frames
    return _FRAMES[key]


def part_now(slot, name):
    """The frame of a part to draw right now (a twinkle, a glowing nose…)."""
    frames = part_frames(slot, name)
    if len(frames) == 1:
        return frames[0]
    import time
    return frames[int(time.time() * FRAME_RATE) % len(frames)]


def skins_folder():
    return os.path.join(cs.config_dir(), "skins")


def user_skins():
    """Whole skins the user dropped into the skins folder: [(name, path)]."""
    out = []
    try:
        for f in sorted(os.listdir(skins_folder())):
            if f.lower().endswith(".png") and not f.startswith("_") and not f.endswith("_back.png"):
                out.append((f[:-4], os.path.join(skins_folder(), f)))
    except OSError:
        pass
    return out


def layers(ch, layer):
    """PNG paths to draw for this character, bottom to top, behind ("back") or in front."""
    paths = []
    if layer == "back":
        if ch.get("body"):
            paths.append(part_path("body", ch["body"], back=True))
        return paths
    for slot in ("body", "head", "face"):
        if ch.get(slot):
            paths.append(part_now(slot, ch[slot]))
    if ch.get("skin"):
        paths.append(os.path.join(skins_folder(), ch["skin"] + ".png"))
        back = os.path.join(skins_folder(), ch["skin"] + "_back.png")
        if os.path.exists(back):
            paths.insert(0, back)
    return paths
