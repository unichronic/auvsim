"""Tiny pictorial wiring-diagram engine: parts drawn as boards/chips with their
printed pin labels, joined by coloured wires. Emits compact SVG (text stays text).

Conventions on every sheet:
  - a dot on a wire = joined; wires that cross without a dot are NOT joined
  - pins are labelled exactly as printed on the part
"""
from xml.sax.saxutils import escape


def _n(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")

COL = dict(
    v33='#d32f2f', v5='#ef6c00', gnd='#263238', sda='#1e88e5', scl='#8e24aa',
    ow='#2e7d32', ana='#00897b', data='#546e7a', clk='#c2185b', spi='#6d4c41',
    trig='#f9a825', probe='#0288d1', note='#546e7a',
)
PITCH = 22


class Sheet:
    def __init__(self, w, h, title, subtitle=''):
        self.w, self.h = w, h
        self.el = []
        self.defs = []
        self.text(24, 34, title, size=21, weight='700', fill='#1a1a18')
        if subtitle:
            self.text(24, 58, subtitle, size=13, fill='#546e7a')

    # ---- primitives -------------------------------------------------------
    def rect(self, x, y, w, h, fill='none', stroke='#333', sw=1.2, r=0, extra=''):
        self.el.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r}" '
                       f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>')

    def circle(self, x, y, r, fill='none', stroke='#333', sw=1.2):
        self.el.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

    def line(self, x1, y1, x2, y2, stroke='#333', sw=1.2, dash=''):
        d = f' stroke-dasharray="{dash}"' if dash else ''
        self.el.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def text(self, x, y, s, size=12, fill='#222', anchor='start', weight='400', rotate=0, family='sans', italic=False):
        cls = ['m'] if family == 'mono' else []
        if weight in ('700', 'bold'): cls.append('b')
        elif weight == '600': cls.append('sb')
        if italic: cls.append('i')
        c = f' class="{" ".join(cls)}"' if cls else ''
        a = '' if anchor == 'start' else f' text-anchor="{anchor}"'
        rot = f' transform="rotate({rotate} {_n(x)} {_n(y)})"' if rotate else ''
        self.el.append(f'<text x="{_n(x)}" y="{_n(y)}" font-size="{size}" fill="{fill}"{a}{c}{rot}>{escape(s)}</text>')

    def path(self, d, stroke, sw=2.6, dash='', fill='none', cap='round'):
        ds = f' stroke-dasharray="{dash}"' if dash else ''
        self.el.append(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" class="w"{ds}/>')

    # ---- wires ------------------------------------------------------------
    def wire(self, pts, color, sw=2.6, dash='', dots=(), label=None, label_at=None, r=6):
        """Orthogonal wire through pts with rounded corners."""
        d = f'M{pts[0][0]:.1f},{pts[0][1]:.1f}'
        for i in range(1, len(pts) - 1):
            (x0, y0), (x1, y1), (x2, y2) = pts[i - 1], pts[i], pts[i + 1]
            rr = min(r, abs(x1 - x0) / 2 + abs(y1 - y0) / 2, abs(x2 - x1) / 2 + abs(y2 - y1) / 2)
            ax = x1 - (rr if x1 > x0 else -rr if x1 < x0 else 0)
            ay = y1 - (rr if y1 > y0 else -rr if y1 < y0 else 0)
            bx = x1 + (rr if x2 > x1 else -rr if x2 < x1 else 0)
            by = y1 + (rr if y2 > y1 else -rr if y2 < y1 else 0)
            d += f' L{ax:.1f},{ay:.1f} Q{x1:.1f},{y1:.1f} {bx:.1f},{by:.1f}'
        d += f' L{pts[-1][0]:.1f},{pts[-1][1]:.1f}'
        # light outline so crossings read clearly
        self.path(d, '#ffffff', sw=sw + 2.4, dash=dash)
        self.path(d, color, sw=sw, dash=dash)
        for i in dots:
            self.circle(pts[i][0], pts[i][1], 4.2, fill=color, stroke='#fff', sw=1.2)
        if label:
            (lx, ly) = label_at or pts[len(pts) // 2]
            self.tag(lx, ly, label, color)

    def tag(self, x, y, s, color, size=10.5):
        w = 6.4 * len(s) + 10
        self.rect(x - w / 2, y - 9, w, 17, fill='#ffffff', stroke=color, sw=1.1, r=8)
        self.text(x, y + 4, s, size=size, fill=color, anchor='middle', weight='600')

    # ---- output -----------------------------------------------------------
    def svg(self):
        import re
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
                f'viewBox="0 0 {self.w} {self.h}">')
        style = ("<style>text{font-family:'DejaVu Sans',Arial,sans-serif}"
                 ".m{font-family:'DejaVu Sans Mono',Menlo,monospace}.b{font-weight:700}.sb{font-weight:600}"
                 ".i{font-style:italic}.w{stroke-linecap:round;stroke-linejoin:round}</style>")
        bg = f'<rect width="{self.w}" height="{self.h}" fill="#fbfbf9"/>'
        defs = ('<defs><g id="pa"><circle r="5.6" fill="#e0c060" stroke="#6b5b1e"/><circle r="2.1" fill="#333"/></g>'
                '<g id="pd"><circle r="5.6" fill="#d8d3c0" stroke="#6b5b1e"/><circle r="2.1" fill="#333"/></g></defs>')
        body = '\n'.join(self.el)
        rnd = lambda m: str(round(float(m.group(0))))
        body = re.sub(r'(\s(?:x|y|cx|cy|x1|y1|x2|y2|width|height)=")(-?\d+\.\d+)', lambda m: m.group(1) + str(round(float(m.group(2)))), body)
        body = re.sub(r'd="[^"]*"', lambda m: re.sub(r'-?\d+\.\d+', rnd, m.group(0)), body)
        body = re.sub(r'rotate\([^)]*\)', lambda m: re.sub(r'-?\d+\.\d+', rnd, m.group(0)), body)
        body = re.sub(r'(\d)\.0(?![\d])', r'\1', body)          # 12.0 -> 12
        body = body.replace(' rx="0"', '')
        return head + '\n' + style + defs + '\n' + bg + '\n' + body + '\n</svg>\n'


# ---- generic parts -----------------------------------------------------------
def pin_pad(s, x, y, used, square=False, color='#c9a227'):
    if square:
        s.rect(x - 5.5, y - 5.5, 11, 11, fill='#e0c060' if used else '#d8d3c0', stroke='#6b5b1e', sw=1)
    else:   # one shared definition per state, reused with <use> (keeps files small)
        s.el.append(f'<use href="#{"pa" if used else "pd"}" x="{_n(x)}" y="{_n(y)}"/>')


def header_column(s, x, y0, labels, used, side, pitch=PITCH, label_color='#fff', label_off=12):
    """Vertical pin header. side='left' puts labels to the right of the pins
    (pins on the board's left edge). Returns {label#idx: (x,y)} and {label: (x,y)} for unique labels."""
    pins = {}
    for i, lab in enumerate(labels):
        y = y0 + i * pitch
        u = f'{lab}#{i}' in used or (lab in used and lab not in ('GND', '5V', '3.3V'))
        pin_pad(s, x, y, u, square=(i == 0))
        tx = x + label_off if side == 'left' else x - label_off
        s.text(tx, y + 4, lab, size=10.5, fill=label_color if u else '#a5d6a7',
               anchor='start' if side == 'left' else 'end', weight='700' if u else '400', family='mono')
        pins[f'{lab}#{i}'] = (x, y)
        pins.setdefault(lab, (x, y))
    return pins


SHRIKE_LEFT = ['5V', '3.3V', 'IO5', 'IO6', 'IO7', 'IO8', 'IO9', 'GND', 'IO10', 'IO11',
               'IO14', 'IO15', 'GND', 'F17', 'F18', 'F0', 'F1', 'F2', 'F7']
SHRIKE_RIGHT = ['5V', '3.3V', 'IO29', 'IO28', 'IO27', 'IO26', 'GND', 'IO25', 'IO24', 'IO23',
                'IO22', 'IO21', 'GND', 'IO20', 'IO19', 'IO18', 'IO17', 'IO16', 'GND']


def shrike(s, x, y, used=(), note='Shrike Lite (top view, USB-C at top)'):
    """Vicharak Shrike Lite, both headers in physical order (Vicharak shrike_pinouts.svg).
    Returns (left_pins, right_pins)."""
    w, h = 190, 36 + 19 * PITCH + 24
    s.rect(x, y, w, h, fill='#1b7a3a', stroke='#0d4d22', sw=2, r=10)
    # USB-C
    s.rect(x + w / 2 - 26, y - 12, 52, 26, fill='#cfd8dc', stroke='#78909c', sw=1.5, r=6)
    s.text(x + w / 2, y + 30, 'USB-C', size=10, fill='#e8f5e9', anchor='middle')
    # chips for flavour
    s.rect(x + 70, y + 170, 52, 52, fill='#212121', stroke='#000', r=3)
    s.text(x + 96, y + 200, 'RP2040', size=9, fill='#bdbdbd', anchor='middle')
    s.rect(x + 76, y + 300, 40, 40, fill='#212121', stroke='#000', r=3)
    s.text(x + 96, y + 324, 'FPGA', size=9, fill='#bdbdbd', anchor='middle')
    # 'L:IO5' / 'R:GND#12' pick a side; unprefixed keys apply to both headers
    both = {k for k in used if not k.startswith(('L:', 'R:'))}
    used_l = both | {k[2:] for k in used if k.startswith('L:')}
    used_r = both | {k[2:] for k in used if k.startswith('R:')}
    left = header_column(s, x + 16, y + 44, SHRIKE_LEFT, used_l, 'left')
    right = header_column(s, x + w - 16, y + 44, SHRIKE_RIGHT, used_r, 'right')
    s.text(x + w / 2, y + h + 20, note, size=11, fill='#1a1a18', anchor='middle', weight='600')
    return left, right


def module(s, x, y, title, pins, used=None, color='#283593', w=150, pitch=PITCH, side='left',
           subtitle='', text_color='#fff'):
    """Breakout module with a single header column on its left (or right) edge."""
    used = set(pins) if used is None else set(used)
    h = 30 + len(pins) * pitch + (16 if subtitle else 6)
    s.rect(x, y, w, h, fill=color, stroke='#0b0b2b', sw=1.6, r=6)
    s.text(x + w / 2 + (12 if side == 'left' else -12), y + 20, title, size=12.5, fill=text_color,
           anchor='middle', weight='700')
    if subtitle:
        s.text(x + w / 2 + (12 if side == 'left' else -12), y + h - 8, subtitle, size=9.5,
               fill=text_color, anchor='middle')
    px = x + 14 if side == 'left' else x + w - 14
    out = {}
    for i, lab in enumerate(pins):
        py = y + 36 + i * pitch
        u = lab in used
        pin_pad(s, px, py, u)
        s.text(px + (12 if side == 'left' else -12), py + 4, lab, size=10.5,
               fill=text_color if u else '#9fa8da', anchor='start' if side == 'left' else 'end',
               weight='700' if u else '400', family='mono')
        out[lab] = (px, py)
    return out


def dip(s, x, y, n, title, names, pitch=PITCH, w=140, sub=''):
    """DIP-n chip, top view, notch up. Pin 1 top-left, counts down the left and up the right.
    Pin names are printed INSIDE the body so incoming wires never cover them.
    Returns {pin_number: (tip_x, tip_y)}."""
    half = n // 2
    h = half * pitch + 18
    s.rect(x, y, w, h, fill='#263238', stroke='#000', sw=1.5, r=4)
    s.path(f'M{x + w/2 - 11:.1f},{y:.1f} A11,11 0 0 0 {x + w/2 + 11:.1f},{y:.1f}', '#90a4ae', sw=1.5)
    s.circle(x + 8, y + 7, 2.6, fill='#90a4ae', stroke='none', sw=0)
    s.text(x + w / 2, y - 10, title, size=13, fill='#1a1a18', anchor='middle', weight='700')
    if sub:
        s.text(x + w / 2, y + h + 16, sub, size=9.5, fill='#546e7a', anchor='middle', italic=True)
    pins = {}
    for i in range(half):
        py = y + 18 + i * pitch
        s.rect(x - 14, py - 3.5, 14, 7, fill='#cfd8dc', stroke='#78909c', sw=0.8)
        s.text(x + 6, py + 4, f'{i + 1:>2} {names[i]}', size=10, fill='#eceff1', family='mono', weight='600')
        pins[i + 1] = (x - 14, py)
        pn = n - i
        s.rect(x + w, py - 3.5, 14, 7, fill='#cfd8dc', stroke='#78909c', sw=0.8)
        s.text(x + w - 6, py + 4, f'{names[pn - 1]} {pn:>2}', size=10, fill='#eceff1', anchor='end',
               family='mono', weight='600')
        pins[pn] = (x + w + 14, py)
    return pins


def resistor(s, x1, y1, x2, y2, value, label_side=1):
    """Pictorial resistor between two points (horizontal or vertical). Leads are part of it."""
    horiz = abs(y2 - y1) < 1e-6
    L = abs(x2 - x1) if horiz else abs(y2 - y1)
    body = min(34, L - 10)
    s.line(x1, y1, x2, y2, stroke='#9e9e9e', sw=1.8)
    if horiz:
        cx = (x1 + x2) / 2
        s.rect(cx - body / 2, y1 - 6.5, body, 13, fill='#90caf9', stroke='#1565c0', sw=1.1, r=5)
        s.text(cx, y1 - 11 if label_side > 0 else y1 + 21, value, size=10, fill='#0d47a1', anchor='middle', weight='700')
    else:
        cy = (y1 + y2) / 2
        s.rect(x1 - 6.5, cy - body / 2, 13, body, fill='#90caf9', stroke='#1565c0', sw=1.1, r=5)
        s.text(x1 + 11 if label_side > 0 else x1 - 11, cy + 4, value, size=10, fill='#0d47a1',
               anchor='start' if label_side > 0 else 'end', weight='700')


def capacitor(s, x1, y1, x2, y2, value, label_side=1):
    horiz = abs(y2 - y1) < 1e-6
    s.line(x1, y1, x2, y2, stroke='#9e9e9e', sw=1.8)
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    s.circle(cx, cy, 8, fill='#ffb74d', stroke='#e65100', sw=1.1)
    if horiz:
        s.text(cx, cy - 12 if label_side > 0 else cy + 22, value, size=10, fill='#bf360c', anchor='middle', weight='700')
    else:
        s.text(cx + 12 if label_side > 0 else cx - 12, cy + 4, value, size=10, fill='#bf360c',
               anchor='start' if label_side > 0 else 'end', weight='700')


def rail(s, x1, x2, y, color, name):
    s.rect(x1, y - 5, x2 - x1, 10, fill=color, stroke='none', sw=0, r=5)
    s.text(x1 + 6, y - 9, name, size=11, fill=color, weight='700')
    return y


def legend(s, x, y, items, extra=()):
    s.rect(x, y, 250, 24 + 18 * (len(items) + len(extra)), fill='#ffffff', stroke='#cfd8dc', sw=1, r=6)
    s.text(x + 10, y + 17, 'Wire colours', size=11, fill='#1a1a18', weight='700')
    for i, (c, t) in enumerate(items):
        yy = y + 34 + i * 18
        s.line(x + 12, yy - 4, x + 40, yy - 4, stroke=COL[c], sw=3)
        s.text(x + 48, yy, t, size=10.5, fill='#37474f')
    for j, t in enumerate(extra):
        s.text(x + 12, y + 34 + (len(items) + j) * 18, t, size=10, fill='#546e7a', italic=True)


def notes(s, x, y, lines, size=11, width=None, title=None):
    if title:
        s.text(x, y, title, size=12, weight='700', fill='#1a1a18')
        y += 18
    for i, t in enumerate(lines):
        s.text(x, y + i * 17, t, size=size, fill='#37474f')


def save(sheet, stem, outdir):
    import os
    svg = sheet.svg()
    p = os.path.join(outdir, stem + '.svg')
    open(p, 'w').write(svg)
    try:
        import cairosvg
        cairosvg.svg2png(bytestring=svg.encode(), write_to=os.path.join(outdir, stem + '.png'), output_width=sheet.w * 1.3)
    except Exception as e:  # PNG is only for local review
        print('png skipped:', e)
    return p


def module_top(s, x, y, title, pins, used=None, color='#283593', pitch=26, w=None, subtitle='',
               text_color='#fff', dim='#9fa8da', lead_colors=None):
    """Breakout with its header along the TOP edge (pins left->right). Returns {label: (x, y)}."""
    used = set(pins) if used is None else set(used)
    w = w or max(120, 36 + (len(pins) - 1) * pitch)
    h = 118 + (14 if subtitle else 0)
    s.rect(x, y, w, h, fill=color, stroke='#0b0b2b', sw=1.6, r=6)
    out = {}
    for i, lab in enumerate(pins):
        px, py = x + 18 + i * pitch, y + 13
        u = lab in used
        if lead_colors:
            s.rect(px - 3, py, 6, 26, fill=lead_colors[i], stroke='#111', sw=0.6)
        pin_pad(s, px, py, u)
        s.text(px + 4, py + 16, lab, size=10, fill=text_color if u else dim, anchor='start',
               family='mono', weight='700' if u else '400', rotate=90)
        out[lab] = (px, py)
    s.text(x + w / 2, y + h - (22 if subtitle else 9), title, size=12, fill=text_color, anchor='middle', weight='700')
    if subtitle:
        s.text(x + w / 2, y + h - 7, subtitle, size=9.5, fill=text_color, anchor='middle')
    return out


def drop(s, p, bus_y, color, dot=True):
    """Vertical wire from a top-edge pin up to a horizontal bus, with a junction dot."""
    s.wire([p, (p[0], bus_y)], color, dots=(1,) if dot else ())


def gnd_sym(s, x, y, lead=12):
    """Ground symbol hanging below (x, y): 'connect to the GND rail'."""
    s.line(x, y, x, y + lead, stroke=COL['gnd'], sw=2)
    for i, w in enumerate((18, 12, 6)):
        s.line(x - w / 2, y + lead + i * 4, x + w / 2, y + lead + i * 4, stroke=COL['gnd'], sw=2)


def dip2(s, x, y, n, title, names, pitch=40, w=100, sub='', flip=False):
    """DIP-n top view. flip=False: notch up, pin 1 top-left.
    flip=True: rotated 180° (notch down), so pins (n/2+1..n) run down the LEFT side.
    Returns {pin_number: (tip_x, tip_y)}."""
    half = n // 2
    h = (half - 1) * pitch + 36
    s.rect(x, y, w, h, fill='#263238', stroke='#000', sw=1.5, r=4)
    ny = y + h if flip else y
    s.path(f'M{x + w/2 - 11:.1f},{ny:.1f} A11,11 0 0 {0 if flip else 0} {x + w/2 + 11:.1f},{ny:.1f}'
           if not flip else f'M{x + w/2 - 11:.1f},{ny:.1f} A11,11 0 0 1 {x + w/2 + 11:.1f},{ny:.1f}', '#90a4ae', sw=1.5)
    s.text(x + w / 2, y + h / 2 - 2, title, size=12, fill='#eceff1', anchor='middle', weight='700')
    if sub:
        s.text(x + w / 2, y + h / 2 + 14, sub, size=9, fill='#b0bec5', anchor='middle')
    if flip:
        left = list(range(half + 1, n + 1))            # 5,6,7,8 top->bottom
        right = list(range(half, 0, -1))               # 4,3,2,1 top->bottom
        s.circle(x + w - 12, y + h - 14, 3.2, fill='#90a4ae', stroke='none', sw=0)
    else:
        left = list(range(1, half + 1))
        right = list(range(n, half, -1))
        s.circle(x + 12, y + 14, 3.2, fill='#90a4ae', stroke='none', sw=0)
    pins = {}
    for i in range(half):
        py = y + 18 + i * pitch
        for side, pn in (('L', left[i]), ('R', right[i])):
            if side == 'L':
                s.rect(x - 14, py - 3.5, 14, 7, fill='#cfd8dc', stroke='#78909c', sw=0.8)
                s.text(x + 6, py + 4, str(pn), size=8.5, fill='#90a4ae', family='mono')
                s.text(x - 18, py - 7, names[pn - 1], size=10, fill='#1a1a18', anchor='end', family='mono', weight='700')
                pins[pn] = (x - 14, py)
            else:
                s.rect(x + w, py - 3.5, 14, 7, fill='#cfd8dc', stroke='#78909c', sw=0.8)
                s.text(x + w - 6, py + 4, str(pn), size=8.5, fill='#90a4ae', anchor='end', family='mono')
                s.text(x + w + 18, py - 7, names[pn - 1], size=10, fill='#1a1a18', family='mono', weight='700')
                pins[pn] = (x + w + 14, py)
    return pins


def bnc(s, x, y, label='BNC out'):
    """BNC socket seen from the front. Returns dict(center=(x,y), shell=(x, y+20))."""
    s.circle(x, y, 17, fill='#cfd8dc', stroke='#607d8b', sw=2)
    s.circle(x, y, 9, fill='#eceff1', stroke='#607d8b', sw=1.2)
    s.circle(x, y, 3, fill='#c9a227', stroke='#6b5b1e', sw=1)
    s.text(x, y - 24, label, size=11, fill='#1a1a18', anchor='middle', weight='700')
    s.text(x + 22, y + 4, 'centre', size=9, fill='#546e7a')
    s.text(x + 22, y + 22, 'shell', size=9, fill='#546e7a')
    return dict(center=(x, y), shell=(x, y + 17))


def terminal(s, x, y, text, color='#37474f', side='left'):
    """A labelled connection point (e.g. 'LADDER OUT from Stage 4')."""
    s.circle(x, y, 6, fill='#fff', stroke=color, sw=2.4)
    s.text(x - 12 if side == 'left' else x + 12, y + 4, text, size=11, fill=color,
           anchor='end' if side == 'left' else 'start', weight='700')
    return (x, y)


def scope(s, x, y, w=300, h=200):
    """Oscilloscope front panel. Returns {'CH1': (x,y), 'CH2': (x,y)} input positions."""
    s.rect(x, y, w, h, fill='#eceff1', stroke='#455a64', sw=2, r=10)
    s.rect(x + 16, y + 16, w * 0.6, h - 60, fill='#102027', stroke='#000', r=4)
    # stair-step sine hint
    import math
    pts = []
    for i in range(40):
        t = i / 39
        v = round(math.sin(t * 2 * math.pi * 2) * 8) / 8
        pts.append((x + 24 + t * (w * 0.6 - 16), y + 16 + (h - 60) / 2 - v * (h - 90) / 2))
    d = 'M' + ' L'.join(f'{a:.1f},{b:.1f}' for a, b in pts)
    s.path(d, '#ffeb3b', sw=1.6)
    s.text(x + w / 2, y + h - 14, 'Oscilloscope', size=12, fill='#263238', anchor='middle', weight='700')
    c1 = (x + w * 0.78, y + h * 0.35)
    c2 = (x + w * 0.78, y + h * 0.62)
    for c, n in ((c1, 'CH1'), (c2, 'CH2')):
        s.circle(*c, 11, fill='#cfd8dc', stroke='#607d8b', sw=2)
        s.circle(*c, 3, fill='#c9a227', stroke='#6b5b1e', sw=1)
        s.text(c[0] + 18, c[1] + 4, n, size=11, fill='#263238', weight='700')
    return {'CH1': c1, 'CH2': c2}


def laptop(s, x, y):
    s.rect(x, y, 170, 110, fill='#cfd8dc', stroke='#455a64', sw=2, r=6)
    s.rect(x + 10, y + 10, 150, 90, fill='#263238', stroke='#000', r=3)
    s.text(x + 85, y + 50, 'arduino-cli', size=11, fill='#a5d6a7', anchor='middle', family='mono')
    s.text(x + 85, y + 68, 'serial monitor', size=11, fill='#a5d6a7', anchor='middle', family='mono')
    s.path(f'M{x - 14},{y + 110} L{x + 184},{y + 110} L{x + 196},{y + 124} L{x - 26},{y + 124} Z', '#455a64', sw=1.5, fill='#b0bec5')
    s.text(x + 85, y + 144, 'Laptop', size=12, fill='#1a1a18', anchor='middle', weight='700')
    return (x + 196, y + 60)


def to92(s, x, y, title='2N2222', legs=('E', 'B', 'C')):
    """TO-92 transistor, flat face towards you, legs down. Leg names are printed ON the body
    (wires can't cover them). Returns {leg: (x, y_tip)}."""
    s.path(f'M{x - 24},{y} L{x + 24},{y} L{x + 24},{y - 28} A24,24 0 0 0 {x - 24},{y - 28} Z',
           '#212121', sw=1.2, fill='#263238')
    s.text(x, y - 58, title, size=11, fill='#1a1a18', anchor='middle', weight='700')
    out = {}
    for i, lg in enumerate(legs):
        lx = x - 14 + i * 14
        s.line(lx, y, lx, y + 26, stroke='#9e9e9e', sw=2.2)
        s.text(lx, y - 6, lg, size=11, fill='#ffffff', anchor='middle', weight='700', family='mono')
        out[lg] = (lx, y + 26)
    return out
