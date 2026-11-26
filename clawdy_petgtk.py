"""Pet mode on Linux: a GTK window with real per-pixel transparency.

Tk can't make a transparent window on X11, and clipping a window to a shape
flashes under a compositor whenever the shape changes. So in pet mode the Tk
window keeps being the model (Clawdy draws on its canvas as always, hidden),
and this window mirrors it: every frame the canvas items are copied as drawing
commands and painted with cairo on an RGBA window at the same position. Mouse
events travel the other way, back to the widget's own handlers.

GTK runs on its own thread (pystray's, when the tray icon is up; else one of
ours). The two sides only ever talk through queues.
"""
import os
import queue
import threading
import types

os.environ.setdefault("GDK_BACKEND", "x11")      # windows can be placed; the compositor still blends alpha


def available():
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk, Gtk  # noqa: F401
        import cairo  # noqa: F401
        return Gdk.Screen.get_default().get_rgba_visual() is not None
    except Exception:
        return False


class PetWindow:
    def __init__(self, widget, own_loop):
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        from gi.repository import GLib, Gtk
        self.GLib, self.Gtk = GLib, Gtk
        self.w = widget
        self.frames = queue.Queue(maxsize=2)      # Tk -> GTK: (x, y, w, h, ops)
        self.events = queue.Queue()               # GTK -> Tk: (kind, x, y, x_root, y_root, button)
        self.frame = None
        self.win = self.area = None
        self.closed = False
        self.pressed = False
        self.last_pos = None
        GLib.idle_add(self._build)
        if own_loop:                              # no tray icon spinning GTK for us
            threading.Thread(target=Gtk.main, daemon=True).start()

    # ---------------------------------------------------------------- GTK thread

    def _build(self):
        from gi.repository import Gdk, Gtk
        # A POPUP window is override-redirect: placed exactly where asked (even half below the
        # screen edge), never managed or clamped by the window manager, and drawn on top.
        win = Gtk.Window(type=Gtk.WindowType.POPUP)
        win.set_title("Clawdy")
        win.set_app_paintable(True)
        visual = win.get_screen().get_rgba_visual()
        if visual:
            win.set_visual(visual)
        area = Gtk.DrawingArea()
        area.add_events(Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.BUTTON_PRESS_MASK
                        | Gdk.EventMask.BUTTON_RELEASE_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK
                        | Gdk.EventMask.ENTER_NOTIFY_MASK)
        area.connect("draw", self._draw)
        area.connect("motion-notify-event", self._motion)
        area.connect("enter-notify-event", self._motion)
        area.connect("leave-notify-event", self._leave)
        area.connect("button-press-event", self._press)
        area.connect("button-release-event", self._release)
        win.add(area)
        win.set_default_size(10, 10)
        win.move(-10000, -10000)
        win.show_all()
        self.win, self.area = win, area
        self.GLib.timeout_add(16, self._pump)
        return False

    def _pump(self):
        if self.closed:
            if self.win:
                self.win.destroy()
                self.win = None
            return False
        frame = None
        try:
            while True:                            # only the newest frame matters
                frame = self.frames.get_nowait()
        except queue.Empty:
            pass
        if frame and self.win:
            x, y, w, h, _ = frame
            if not self.frame or (w, h) != self.frame[2:4]:
                self.win.resize(w, h)
            if not self.frame or (x, y) != self.frame[:2]:
                self.win.move(x, y)
            self.frame = frame
            self.area.queue_draw()
        return True

    def _draw(self, area, cr):
        import cairo
        import math
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        if not self.frame:
            return
        for op in self.frame[4]:
            kind, pts, fill = op[0], op[1], op[2]
            if fill:
                cr.set_source_rgb(*fill)
            if kind == "rectangle":                     # pixel-aligned and crisp: no seams between blocks
                x0, y0, x1, y1 = (round(v) for v in pts)
                if x1 > x0 and y1 > y0:
                    cr.set_antialias(cairo.ANTIALIAS_NONE)
                    cr.rectangle(x0, y0, x1 - x0, y1 - y0)
                    cr.fill()
                    cr.set_antialias(cairo.ANTIALIAS_DEFAULT)
            elif kind == "oval":
                x0, y0, x1, y1 = pts
                rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
                if rx > 0 and ry > 0:
                    cr.save()
                    cr.translate(x0 + rx, y0 + ry)
                    cr.scale(rx, ry)
                    cr.arc(0, 0, 1, 0, 2 * math.pi)
                    cr.restore()
                    cr.fill()
            elif kind == "polygon":
                axis = len(pts) == 8 and (pts[1] == pts[3] and pts[5] == pts[7] and pts[0] == pts[6] and pts[2] == pts[4])
                if axis:                                  # an unrotated block: treat it as a rectangle
                    cr.set_antialias(cairo.ANTIALIAS_NONE)
                    x0, y0, x1, y1 = round(pts[0]), round(pts[1]), round(pts[2]), round(pts[5])
                    cr.rectangle(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
                    cr.fill()
                    cr.set_antialias(cairo.ANTIALIAS_DEFAULT)
                else:                                     # rotated blocks: crisp too, or the joins show
                    cr.set_antialias(cairo.ANTIALIAS_NONE)
                    cr.move_to(pts[0], pts[1])
                    for i in range(2, len(pts), 2):
                        cr.line_to(pts[i], pts[i + 1])
                    cr.close_path()
                    cr.fill()
                    cr.set_antialias(cairo.ANTIALIAS_DEFAULT)
            elif kind == "arc":                      # Tk angles: degrees counter-clockwise from 3 o'clock
                x0, y0, x1, y1 = pts
                start, extent, width = op[3], op[4], op[5]
                rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
                if rx > 0 and ry > 0:
                    cr.save()
                    cr.translate(x0 + rx, y0 + ry)
                    cr.scale(rx, ry)
                    a0, a1 = -math.radians(start), -math.radians(start + extent)
                    if extent >= 0:
                        cr.arc_negative(0, 0, 1, a0, a1)
                    else:
                        cr.arc(0, 0, 1, a0, a1)
                    cr.restore()
                    cr.set_line_width(width or 1)
                    cr.stroke()
            elif kind == "line":
                cr.set_line_width(op[3] or 1)
                cr.move_to(pts[0], pts[1])
                for i in range(2, len(pts), 2):
                    cr.line_to(pts[i], pts[i + 1])
                cr.stroke()
            elif kind == "text":
                text, family, size, bold, anchor = op[3], op[4], op[5], op[6], op[7]
                cr.select_font_face(family, cairo.FONT_SLANT_NORMAL,
                                    cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
                cr.set_font_size(size * 96 / 72)
                xb, yb, tw, th, _, _ = cr.text_extents(text)
                asc, desc = cr.font_extents()[:2]
                x, y = pts
                if "e" in anchor:
                    x -= tw + xb
                elif "w" not in anchor:
                    x -= tw / 2 + xb
                if "n" in anchor:
                    y += asc
                elif "s" in anchor:
                    y -= desc
                else:
                    y += (asc - desc) / 2
                cr.move_to(x, y)
                cr.show_text(text)

    def _motion(self, area, ev):
        self.events.put(("drag" if self.pressed else "motion", ev.x, ev.y, ev.x_root, ev.y_root, 0))
        return True

    def _leave(self, area, ev):
        self.events.put(("leave", ev.x, ev.y, ev.x_root, ev.y_root, 0))
        return True

    def _press(self, area, ev):
        if ev.type.value_name != "GDK_BUTTON_PRESS":
            return True
        if ev.button == 1:
            self.pressed = True
        self.events.put(("press", ev.x, ev.y, ev.x_root, ev.y_root, ev.button))
        return True

    def _release(self, area, ev):
        if ev.button == 1:
            self.pressed = False
        self.events.put(("release", ev.x, ev.y, ev.x_root, ev.y_root, ev.button))
        return True

    # ---------------------------------------------------------------- Tk thread

    def push(self, x, y, w, h, ops):
        try:
            self.frames.put_nowait((x, y, w, h, ops))
        except queue.Full:
            try:
                self.frames.get_nowait()
                self.frames.put_nowait((x, y, w, h, ops))
            except queue.Empty:
                pass

    def poll(self):
        """Deliver the mouse to the widget's own handlers, on the Tk thread."""
        w = self.w
        while True:
            try:
                kind, x, y, xr, yr, button = self.events.get_nowait()
            except queue.Empty:
                return
            ev = types.SimpleNamespace(x=x, y=y, x_root=int(xr), y_root=int(yr))
            try:
                if kind == "motion":
                    w.on_motion(ev)
                elif kind == "drag":
                    w.on_motion(ev)
                    w.drag(ev)
                elif kind == "leave":
                    w.on_leave(ev)
                elif kind == "press" and button == 1:
                    w.press(ev)
                elif kind == "press" and button == 3:
                    w.popup(ev)
                elif kind == "release" and button == 1:
                    w.release(ev)
            except Exception as e:
                w.log("pet event", kind, e)

    def close(self):
        self.closed = True


_RGB = {}                                        # fill string -> (r, g, b) in 0..1
_SNAP = """
set out {}
foreach i [%(c)s find withtag %(tag)s] {
    set f [%(c)s itemcget $i -fill]
    if {$f eq ""} continue
    set t [%(c)s type $i]
    if {$t eq "text"} {
        lappend out [list $t [%(c)s coords $i] $f [%(c)s itemcget $i -text] [%(c)s itemcget $i -font] [%(c)s itemcget $i -anchor]]
    } elseif {$t eq "line"} {
        lappend out [list $t [%(c)s coords $i] $f [%(c)s itemcget $i -width]]
    } else {
        lappend out [list $t [%(c)s coords $i] $f]
    }
}
return $out
"""


def snapshot(canvas, root, tag="dyn"):
    """The canvas items with a tag, as plain drawing commands for the GTK side. One Tcl
    script gathers everything: asking item by item from Python cost a third of a core."""
    tk = root.tk
    ops = []
    for entry in tk.splitlist(tk.eval(_SNAP % {"c": canvas._w, "tag": tag})):
        parts = tk.splitlist(entry)
        kind, fill = parts[0], parts[2]
        rgb = _RGB.get(fill)
        if rgb is None:
            try:
                r, g, b = root.winfo_rgb(fill)
                rgb = (r / 65535, g / 65535, b / 65535)
            except Exception:
                rgb = False
            _RGB[fill] = rgb
        if not rgb:
            continue
        pts = [float(v) for v in tk.splitlist(parts[1])]
        if kind in ("rectangle", "oval", "polygon"):
            ops.append((kind, pts, rgb))
        elif kind == "line":
            ops.append((kind, pts, rgb, float(parts[3] or 1)))
        elif kind == "text":
            font = tk.splitlist(parts[4])
            family = font[0] if font else "sans"
            size = abs(int(font[1])) if len(font) > 1 else 10
            bold = "bold" in font[2:]
            ops.append(("text", pts, rgb, parts[3], family, size, bold, parts[5] or "center"))
    return ops
