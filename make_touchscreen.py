#!/usr/bin/env python3
"""PlainBytes Short: What is an IP address. 720x1280, 30fps. Frames piped to ffmpeg."""
import math, os, sys, subprocess
from functools import lru_cache
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

W, H, S, FPS = 720, 1280, 2, 30
DUR = 43.5
OR = (255, 176, 32); OR2 = (226, 136, 20); RED = (255, 90, 54); WHITE = (255, 255, 255)
SOFT = (243, 217, 184); DARK = (22, 17, 13); PANEL = (48, 36, 28); EYE = (255, 243, 214)
TAN = (150, 112, 78); BLUE = (120, 200, 255)

INTER = '/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf'
POP = '/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf'


@lru_cache(maxsize=None)
def F(size, kind='b'):
    return ImageFont.truetype(INTER if kind == 'b' else POP, max(1, int(round(size * S))))


def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def lerp(a, b, t): return a + (b - a) * t
def eo3(t): t = clamp(t); return 1 - (1 - t) ** 3
def eio(t): t = clamp(t); return 3 * t * t - 2 * t * t * t
def eob(t, s=1.70158):
    t = clamp(t); return 1 + (s + 1) * (t - 1) ** 3 + s * (t - 1) ** 2
def prog(t, a, dur): return clamp((t - a) / dur)


# ---------- drawing helpers (coordinates in 720x1280 space) ----------
def rr(d, box, r, fill=None, outline=None, w=0):
    d.rounded_rectangle([box[0] * S, box[1] * S, box[2] * S, box[3] * S], radius=max(0, r * S),
                        fill=fill, outline=outline, width=round(w * S))

def ell(d, cx, cy, rx, ry=None, fill=None, outline=None, w=0):
    ry = rx if ry is None else ry
    d.ellipse([(cx - rx) * S, (cy - ry) * S, (cx + rx) * S, (cy + ry) * S], fill=fill, outline=outline, width=round(w * S))

def poly(d, pts, fill):
    d.polygon([(x * S, y * S) for x, y in pts], fill=fill)

def ln(d, pts, fill, w, cap=True):
    d.line([(x * S, y * S) for x, y in pts], fill=fill, width=max(1, round(w * S)), joint='curve')
    if cap:
        for x, y in (pts[0], pts[-1]):
            ell(d, x, y, w / 2, fill=fill)

def tx(d, x, y, s, size, fill=WHITE, anchor='mm', kind='b', stroke=0, sf=DARK):
    d.text((x * S, y * S), s, font=F(size, kind), fill=fill, anchor=anchor,
           stroke_width=round(stroke * S), stroke_fill=sf)

def tw(s, size, kind='b'):
    return F(size, kind).getlength(s) / S

def wrap(s, size, maxw, kind='b'):
    words, lines, cur = s.split(' '), [], ''
    for w_ in words:
        trial = (cur + ' ' + w_).strip()
        if tw(trial, size, kind) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur); cur = w_
    if cur: lines.append(cur)
    return lines

def rotpoly(d, cx, cy, w, h, ang, fill):
    a = math.radians(ang); c, s_ = math.cos(a), math.sin(a)
    pts = []
    for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
        pts.append((cx + dx * c - dy * s_, cy + dx * s_ + dy * c))
    poly(d, pts, fill)

def glow(img, box, color, r=26, a=150, rad=30):
    x0, y0, x1, y1 = [int(v * S) for v in box]
    pad = int(r * S * 2)
    ov = Image.new('RGBA', (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.rounded_rectangle([pad, pad, pad + x1 - x0, pad + y1 - y0], radius=int(rad * S), fill=color + (a,))
    ov = ov.filter(ImageFilter.GaussianBlur(r * S))
    img.paste(ov, (x0 - pad, y0 - pad), ov)


# ---------- background ----------
def make_bg():
    ys = np.linspace(0, 1, H * S)[:, None, None]
    xs = np.linspace(0, 1, W * S)[None, :, None]
    t = np.clip(0.65 * ys + 0.35 * xs, 0, 1)
    c1 = np.array((26, 20, 16), float); c2 = np.array((48, 32, 21), float)
    arr = (c1 + (c2 - c1) * t).astype(np.uint8)
    arr = np.broadcast_to(arr, (H * S, W * S, 3)).copy()
    im = Image.fromarray(arr, 'RGB')
    d = ImageDraw.Draw(im)
    col = (66, 46, 30)
    for y0, dirx in ((250, 1), (700, 1), (1000, 1)):
        for side in (0, 1):
            xs_ = (lambda x: x) if side == 0 else (lambda x: W - x)
            pts = [(xs_(0), y0), (xs_(34), y0), (xs_(54), y0 + 20), (xs_(74), y0 + 20)]
            ln(d, pts, col, 3, cap=False)
            ell(d, *pts[-1], 5, fill=col)
    return im

BG = make_bg()


# ---------- characters / props ----------
def robot(d, cx, cy, sc, t, mood='normal', arms=(14, 14), look=0.0, bob=True):
    y = cy + (math.sin(t * 4.2) * 5 * sc if bob else 0)
    for side, th in ((-1, arms[0]), (1, arms[1])):
        sx, sy = cx + side * 66 * sc, y + 105 * sc
        a = math.radians(th)
        ex, ey = sx + side * math.sin(a) * 80 * sc, sy + math.cos(a) * 80 * sc
        ln(d, [(sx, sy), (ex, ey)], OR2, 17 * sc)
        ell(d, ex, ey, 15 * sc, fill=OR)
    rr(d, (cx - 68 * sc, y + 66 * sc, cx + 68 * sc, y + 196 * sc), 28 * sc, fill=OR2)
    rr(d, (cx - 40 * sc, y + 98 * sc, cx + 40 * sc, y + 152 * sc), 14 * sc, fill=DARK)
    ell(d, cx - 16 * sc, y + 125 * sc, 7 * sc, fill=RED)
    ell(d, cx + 12 * sc, y + 125 * sc, 7 * sc, fill=OR)
    ln(d, [(cx, y - 80 * sc), (cx, y - 112 * sc)], OR2, 7 * sc)
    ell(d, cx, y - 121 * sc, 11 * sc, fill=RED)
    rr(d, (cx - 114 * sc, y - 30 * sc, cx - 90 * sc, y + 22 * sc), 9 * sc, fill=OR2)
    rr(d, (cx + 90 * sc, y - 30 * sc, cx + 114 * sc, y + 22 * sc), 9 * sc, fill=OR2)
    rr(d, (cx - 96 * sc, y - 82 * sc, cx + 96 * sc, y + 62 * sc), 36 * sc, fill=OR)
    rr(d, (cx - 76 * sc, y - 62 * sc, cx + 76 * sc, y + 42 * sc), 24 * sc, fill=DARK)
    e1, e2, ey = cx - 32 * sc, cx + 32 * sc, y - 20 * sc
    my = y + 22 * sc
    blink = (t % 3.6) < 0.12
    if mood in ('normal', 'flat', 'read') and blink:
        for ex in (e1, e2):
            ln(d, [(ex - 11 * sc, ey), (ex + 11 * sc, ey)], EYE, 5 * sc)
    elif mood in ('normal', 'flat', 'read'):
        for ex in (e1, e2):
            ell(d, ex, ey, 14 * sc, fill=EYE)
            ell(d, ex + look * 6 * sc, ey, 6 * sc, fill=DARK)
    if mood == 'normal':
        pts = [(cx - 24 * sc + i * 6 * sc, my + 8 * sc * (1 - ((i - 4) / 4) ** 2)) for i in range(9)]
        ln(d, pts, EYE, 5 * sc)
    elif mood in ('flat', 'read'):
        ln(d, [(cx - 18 * sc, my + 6 * sc), (cx + 18 * sc, my + 6 * sc)], EYE, 5 * sc)
    elif mood == 'confused':
        ell(d, e1, ey, 15 * sc, fill=EYE); ell(d, e1 + 3 * sc, ey, 6 * sc, fill=DARK)
        ell(d, e2, ey + 2 * sc, 9 * sc, fill=EYE); ell(d, e2 - 1 * sc, ey + 2 * sc, 4 * sc, fill=DARK)
        ln(d, [(e2 - 16 * sc, ey - 22 * sc), (e2 + 14 * sc, ey - 32 * sc)], EYE, 5 * sc)
        pts = [(cx - 24 * sc + i * 6 * sc, my + 6 * sc + math.sin(i * 1.3) * 4 * sc) for i in range(9)]
        ln(d, pts, EYE, 5 * sc)
    elif mood == 'smug':
        for ex in (e1, e2):
            ell(d, ex, ey, 14 * sc, fill=EYE); ell(d, ex + 3 * sc, ey + 3 * sc, 6 * sc, fill=DARK)
            rr(d, (ex - 16 * sc, ey - 16 * sc, ex + 16 * sc, ey - 2 * sc), 0, fill=DARK)
            ln(d, [(ex - 15 * sc, ey - 2 * sc), (ex + 15 * sc, ey - 2 * sc)], EYE, 4 * sc, cap=False)
        ln(d, [(cx - 24 * sc, my + 4 * sc), (cx + 6 * sc, my + 12 * sc), (cx + 26 * sc, my - 2 * sc)], EYE, 5 * sc)
    elif mood == 'happy':
        for ex in (e1, e2):
            ln(d, [(ex - 11 * sc, ey + 6 * sc), (ex, ey - 6 * sc), (ex + 11 * sc, ey + 6 * sc)], EYE, 5 * sc)
        d.pieslice([(cx - 22 * sc) * S, (my - 12 * sc) * S, (cx + 22 * sc) * S, (my + 22 * sc) * S], 0, 180, fill=EYE)
    elif mood == 'oops':
        for ex in (e1, e2):
            ell(d, ex, ey, 16 * sc, fill=EYE); ell(d, ex + 2 * sc, ey - 3 * sc, 4 * sc, fill=DARK)
        ell(d, cx, my + 5 * sc, 9 * sc, 7 * sc, fill=EYE)
        dy = (t * 26) % 26
        poly(d, [(cx + 92 * sc, y - 62 * sc + dy), (cx + 84 * sc, y - 44 * sc + dy), (cx + 100 * sc, y - 44 * sc + dy)], BLUE)
        ell(d, cx + 92 * sc, y - 42 * sc + dy, 8 * sc, fill=BLUE)
    return y


def hand_pos(cx, y, sc, side, th):
    a = math.radians(th)
    return (cx + side * 66 * sc + side * math.sin(a) * 80 * sc, y + 105 * sc + math.cos(a) * 80 * sc)


def bubble(d, box, tail, fill=WHITE):
    rr(d, box, 28, fill=fill)
    x0, y0, x1, y1 = box
    tx_, ty_ = tail
    bx = clamp(tx_, x0 + 40, x1 - 40)
    poly(d, [(bx - 22, y1 - 4), (bx + 22, y1 - 4), (tx_, ty_)], fill)


def cat(d, cx, cy, r):
    c = (255, 200, 120)
    poly(d, [(cx - r * 0.95, cy - r * 0.2), (cx - r * 0.8, cy - r * 1.3), (cx - r * 0.1, cy - r * 0.75)], c)
    poly(d, [(cx + r * 0.95, cy - r * 0.2), (cx + r * 0.8, cy - r * 1.3), (cx + r * 0.1, cy - r * 0.75)], c)
    ell(d, cx, cy, r, r * 0.88, fill=c)
    for sx in (-1, 1):
        ell(d, cx + sx * r * 0.38, cy - r * 0.1, r * 0.12, r * 0.16, fill=DARK)
        ln(d, [(cx + sx * r * 0.45, cy + r * 0.28), (cx + sx * r * 1.15, cy + r * 0.2)], DARK, 2.5, cap=False)
        ln(d, [(cx + sx * r * 0.45, cy + r * 0.36), (cx + sx * r * 1.15, cy + r * 0.46)], DARK, 2.5, cap=False)
    poly(d, [(cx - r * 0.1, cy + r * 0.12), (cx + r * 0.1, cy + r * 0.12), (cx, cy + r * 0.24)], (230, 120, 110))


def chip_logo(d, cx, cy, s):
    for i in (-1, 0, 1):
        ln(d, [(cx + i * 0.5 * s, cy - 0.62 * s), (cx + i * 0.5 * s, cy - 0.46 * s)], OR, 0.07 * s)
        ln(d, [(cx + i * 0.5 * s, cy + 0.46 * s), (cx + i * 0.5 * s, cy + 0.62 * s)], OR, 0.07 * s)
        ln(d, [(cx - 0.62 * s, cy + i * 0.5 * s), (cx - 0.46 * s, cy + i * 0.5 * s)], OR, 0.07 * s)
        ln(d, [(cx + 0.46 * s, cy + i * 0.5 * s), (cx + 0.62 * s, cy + i * 0.5 * s)], OR, 0.07 * s)
    rr(d, (cx - 0.46 * s, cy - 0.46 * s, cx + 0.46 * s, cy + 0.46 * s), 0.12 * s, fill=DARK, outline=OR, w=0.07 * s)
    tx(d, cx, cy + 0.02 * s, 'P', 0.62 * s, OR, kind='p')


def bolt(d, cx, cy, s, fill):
    pts = [(0.15, -1), (-0.55, 0.1), (-0.05, 0.1), (-0.2, 1), (0.6, -0.2), (0.05, -0.2)]
    poly(d, [(cx + x * s, cy + y * s) for x, y in pts], fill)


# ---------- titles & captions ----------

# time warp: new (voiceover) time -> old (animation) time


def draw_title(d, t):
    for a, b, s in TITLES:
        if a <= t < b:
            p = eob((t - a) / 0.35)
            size = 50 * (0.85 + 0.15 * p)
            lines = wrap(s, 50, 640)
            y0 = 118 - (len(lines) - 1) * 31
            for i, l in enumerate(lines):
                tx(d, 360, y0 + i * 62, l, size, WHITE, stroke=5)
            bw = 130 * eo3((t - a) / 0.5)
            rr(d, (360 - bw / 2, y0 + len(lines) * 62 - 20, 360 + bw / 2, y0 + len(lines) * 62 - 12), 4, fill=OR)
            return

def draw_caption(d, t):
    for a, b, s in CAPS:
        if a <= t < b:
            off = 14 * (1 - eo3((t - a) / 0.15))
            lines = wrap(s, 38, 640)
            y0 = 905 - (len(lines) - 1) * 24 + off
            for i, l in enumerate(lines):
                tx(d, 360, y0 + i * 50, l, 38, WHITE, stroke=7)
            return


# ======================= TOUCHSCREEN VIDEO =======================
DUR = 36.2
SENT = [(0.15, 2.6, None),
        (2.63, 9.10, "Think of a net of invisible tripwires under the glass, a grid of tiny electrodes, each holding a small electric charge."),
        (9.18, 14.10, "Your finger is slightly conductive, so when it gets close, it steals a little of that charge."),
        (14.14, 19.60, "The phone checks every crossing of the grid, finds where the charge dropped most, and that spot is your touch."),
        (19.69, 22.00, "It repeats this about a hundred times a second."),
        (22.14, 25.40, "Two fingers just means two dips, which is how pinch to zoom works."),
        (25.52, 28.80, "The catch: normal gloves and plastic pens do nothing, because they don't conduct."),
        (28.86, 30.10, "Next up: how Bluetooth works."),
        (30.30, 33.60, "Follow PlainBytes for more tech, explained simply.")]

def make_caps():
    caps = []
    for a, b, s in SENT:
        if not s: continue
        words = s.split(' ')
        chunks, cur = [], ''
        for w_ in words:
            if cur and len(cur) + 1 + len(w_) > 30:
                chunks.append(cur); cur = w_
            else:
                cur = (cur + ' ' + w_).strip()
        chunks.append(cur)
        tot = sum(len(c) for c in chunks); t0 = a
        for c in chunks:
            t1 = t0 + (b - a) * len(c) / tot
            caps.append((t0, t1, c)); t0 = t1
    return caps
CAPS = make_caps()

TITLES = [(0.1, 2.6, "Your screen doesn't feel pressure. It feels you."), (2.63, 9.15, "A grid of tiny charged sensors"),
          (9.18, 14.1, "Your finger steals charge"), (14.14, 22.1, "The biggest dip = your touch"),
          (22.14, 25.5, "Two dips = two fingers"), (25.52, 28.8, "Gloves and pens: no dip"),
          (28.86, 36.2, "Follow for more")]

NEW_A = [0, DUR]; OLD_A = [0, DUR]
def warp(tn): return float(tn)

GREEN = (120, 220, 150)
SKIN = (255, 205, 160)

def mix(c1, c2, t):
    t = clamp(t); return tuple(int(lerp(a, b, t)) for a, b in zip(c1, c2))

def phone_s(d, cx, cy, sc=1.0):
    rr(d, (cx - 62 * sc, cy - 110 * sc, cx + 62 * sc, cy + 110 * sc), 18 * sc, fill=(60, 46, 36), outline=OR, w=3.5 * sc)
    rr(d, (cx - 53 * sc, cy - 98 * sc, cx + 53 * sc, cy + 92 * sc), 12 * sc, fill=(30, 24, 20))
    for i in range(3):
        rr(d, (cx - 38 * sc, cy - 70 * sc + i * 40 * sc, cx + 38 * sc, cy - 46 * sc + i * 40 * sc), 6 * sc, fill=PANEL)

def finger(d, x, y, sc=1.0, ang=0, fill=SKIN):
    """fingertip whose tip is at (x,y), pointing down, tilted by ang degrees"""
    a = math.radians(ang)
    ux, uy = -math.sin(a), -math.cos(a)  # direction away from tip
    pts = [(x + ux * k * sc, y + uy * k * sc) for k in (28, 70, 120, 170)]
    ln(d, [(x + ux * 28 * sc, y + uy * 28 * sc), (x + ux * 150 * sc, y + uy * 150 * sc)], fill, 56 * sc)
    ell(d, x + ux * 28 * sc, y + uy * 28 * sc, 28 * sc, fill=fill)
    ell(d, x + ux * 52 * sc - math.cos(a) * 0, y + uy * 52 * sc, 11 * sc, 8 * sc, fill=mix(fill, (255, 255, 255), 0.35))

def grid(d, cx, cy, cols, rows, gap, charge=lambda i, j: 1.0, ghost=False):
    x0 = cx - (cols - 1) * gap / 2; y0 = cy - (rows - 1) * gap / 2
    pad = gap * 0.6
    rr(d, (x0 - pad, y0 - pad, x0 + (cols - 1) * gap + pad, y0 + (rows - 1) * gap + pad), 20, fill=(34, 26, 20), outline=TAN, w=3)
    lc = (86, 64, 44)
    for i in range(cols):
        ln(d, [(x0 + i * gap, y0), (x0 + i * gap, y0 + (rows - 1) * gap)], lc, 4, cap=False)
    for j in range(rows):
        ln(d, [(x0, y0 + j * gap), (x0 + (cols - 1) * gap, y0 + j * gap)], lc, 4, cap=False)
    for i in range(cols):
        for j in range(rows):
            c = clamp(charge(i, j))
            ell(d, x0 + i * gap, y0 + j * gap, 5 + 8 * c, fill=mix((90, 70, 50), OR, c))
    return x0, y0

def gpos(cx, cy, cols, rows, gap, i, j):
    return (cx - (cols - 1) * gap / 2 + i * gap, cy - (rows - 1) * gap / 2 + j * gap)

def tag(d, cx, cy, s, size=30, fill=OR, p=1.0):
    if p <= 0: return
    w_ = tw(s, size) + 40
    rr(d, (cx - w_ / 2 * p, cy - 26 * p, cx + w_ / 2 * p, cy + 26 * p), 14 * p, fill=fill)
    if p > 0.6:
        tx(d, cx, cy + 1, s, size * p, DARK, kind='p')

def dipfn(cx, cy, cols, rows, gap, fingers, rad=1.6, depth=1.0):
    def f(i, j):
        x, y = gpos(cx, cy, cols, rows, gap, i, j)
        c = 1.0
        for (fx, fy, k) in fingers:
            dd = math.dist((x, y), (fx, fy)) / gap
            c -= depth * k * max(0.0, 1 - dd / rad) ** 1.2
        return c
    return f

def ripple(d, x, y, t, col=OR):
    for k in range(3):
        p = ((t * 1.4 + k / 3) % 1.0)
        ell(d, x, y, 14 + 70 * p, outline=col + (0,)[:0] if False else mix(col, (30, 24, 20), p), w=4 * (1 - p) + 1)


GC, GR, GG = 6, 7, 78     # grid dims
GX, GY = 360, 470

def scene1(img, d, t, tl):
    pp = eob(tl / 0.6)
    phone_s(d, 250, 500, 1.55 * pp)
    robot(d, 585, 560, 0.6, t, 'normal', arms=(20, 20))
    tipx, tipy = 250, 470
    p = eo3((tl - 0.5) / 0.6)
    fy = lerp(tipy - 110, tipy, p)
    finger(d, tipx + 6, fy, 1.0, ang=-14)
    if tl > 1.1:
        ripple(d, tipx, tipy, tl)

def scene2(img, d, t, tl):
    n = int(GC * GR * eo3(tl / 3.0))
    def ch(i, j):
        k = j * GC + i
        return clamp((n - k) / 1.5 + 0.0) if k < n else 0.0
    grid(d, GX, GY, GC, GR, GG, ch)
    tag(d, 360, 800, "each dot holds a charge", 28, fill=SOFT, p=eob((tl - 3.0) / 0.4))

def scene3(img, d, t, tl):
    cols, rows, gap = GC, GR, GG
    p = eio(clamp(tl / 3.0))
    fx, fy = gpos(GX, GY, cols, rows, gap, 2, 3)
    fx += 0.5 * gap; 
    tipy = lerp(fy - 170, fy - 25, p)
    near = p
    fn = dipfn(GX, GY, cols, rows, gap, [(fx, fy, near)], rad=1.9)
    grid(d, GX, GY, cols, rows, gap, fn)
    # charge flowing up into the finger
    if p > 0.5:
        for k in range(5):
            q = (t * 1.2 + k / 5) % 1.0
            ang = k * 1.256
            sx, sy = fx + math.cos(ang) * gap * 1.1, fy + math.sin(ang) * gap * 1.1
            ex, ey = fx, tipy
            ell(d, lerp(sx, ex, q), lerp(sy, ey, q), 6, fill=YEL)
    finger(d, fx, tipy, 1.0)
    tag(d, 360, 800, "finger steals some charge", 28, fill=SOFT, p=eob((tl - 3.0) / 0.4))

YEL = (255, 226, 120)

def scene4(img, d, t, tl):
    cols, rows, gap = GC, GR, GG
    fx, fy = gpos(GX, GY, cols, rows, gap, 3, 3)
    fx -= 0.3 * gap
    fn = dipfn(GX, GY, cols, rows, gap, [(fx, fy, 1.0)], rad=1.9)
    grid(d, GX, GY, cols, rows, gap, fn)
    # scan sweep
    gx0 = GX - (cols - 1) * gap / 2; gy0 = GY - (rows - 1) * gap / 2
    sw = (tl * 0.9) % 1.0
    sy = gy0 + (rows - 1) * gap * sw
    ln(d, [(gx0 - 20, sy), (gx0 + (cols - 1) * gap + 20, sy)], YEL, 3, cap=False)
    finger(d, fx, fy - 8, 0.0001)
    if tl > 2.4:
        p = eob((tl - 2.4) / 0.4)
        ell(d, fx, fy, 40 * p, outline=GREEN, w=5)
        ln(d, [(fx - 55 * p, fy), (fx - 28 * p, fy)], GREEN, 5, cap=False)
        ln(d, [(fx + 28 * p, fy), (fx + 55 * p, fy)], GREEN, 5, cap=False)
        tag(d, 360, 800, "biggest dip = touch", 28, fill=GREEN, p=p)
    if tl > 5.55:
        p = eob((tl - 5.55) / 0.4)
        tag(d, 360, 800, "~100 scans per second", 28, fill=OR, p=p)

def scene5(img, d, t, tl):
    cols, rows, gap = GC, GR, GG
    a = (gpos(GX, GY, cols, rows, gap, 1, 2)); b = (gpos(GX, GY, cols, rows, gap, 4, 4))
    s = eio(clamp(tl / 2.6))
    a2 = (lerp(a[0], a[0] + 40, s), lerp(a[1], a[1] + 30, s))
    b2 = (lerp(b[0], b[0] - 40, s), lerp(b[1], b[1] - 30, s))
    fn = dipfn(GX, GY, cols, rows, gap, [(a2[0], a2[1], 1.0), (b2[0], b2[1], 1.0)], rad=1.5)
    grid(d, GX, GY, cols, rows, gap, fn)
    for (px, py) in (a2, b2):
        ell(d, px, py, 30, outline=GREEN, w=4)
    # pinch arrows
    ln(d, [(a2[0] - 20, a2[1] - 20), (a2[0] - 60, a2[1] - 50)], SOFT, 4)
    ln(d, [(b2[0] + 20, b2[1] + 20), (b2[0] + 60, b2[1] + 50)], SOFT, 4)
    tag(d, 360, 800, "2 dips = pinch to zoom", 28, fill=SOFT, p=eob((tl - 1.4) / 0.4))

def scene6(img, d, t, tl):
    cols, rows, gap = 5, 5, 70
    grid(d, 360, 590, cols, rows, gap, lambda i, j: 1.0)
    p = eio(clamp(tl / 1.6))
    # glove (mitten)
    gx, gy = 235, lerp(350, 440, p)
    rr(d, (gx - 42, gy - 120, gx + 42, gy - 10), 30, fill=(110, 130, 190))
    ell(d, gx, gy - 8, 42, 30, fill=(110, 130, 190))
    rr(d, (gx + 34, gy - 80, gx + 70, gy - 26), 16, fill=(110, 130, 190))
    rr(d, (gx - 44, gy - 150, gx + 44, gy - 116), 10, fill=(80, 96, 150))
    # pen
    px, py = 485, lerp(330, 470, p)
    rotpoly(d, px, py - 70, 22, 140, 8, (190, 190, 200))
    poly(d, [(px - 10, py - 5), (px + 12, py - 5), (px, py + 14)], (60, 60, 70))
    if tl > 1.7:
        q = eob((tl - 1.7) / 0.4)
        for (cx_, cy_) in ((gx, 590), (px, 590)):
            ln(d, [(cx_ - 26 * q, cy_ - 26 * q), (cx_ + 26 * q, cy_ + 26 * q)], RED, 9)
            ln(d, [(cx_ - 26 * q, cy_ + 26 * q), (cx_ + 26 * q, cy_ - 26 * q)], RED, 9)
        tag(d, 360, 810, "no charge stolen", 28, fill=SOFT, p=q)

def scene7(img, d, t, tl):
    cx, cy, sc = 360, 400, 1.25
    arms = (125, 125) if tl < 1.5 else (14, 14)
    robot(d, cx, cy, sc, t, 'happy', arms=arms)
    if tl > 1.8:
        p = eob((tl - 1.8) / 0.4)
        chip_logo(d, 238, 760, 62 * p)
        tx(d, 290, 760, "PlainBytes", 44 * p, WHITE, anchor='lm', kind='p')

STARTS = [2.63, 9.18, 14.14, 22.14, 25.52, 28.86]
BOUNDS = [0] + STARTS + [DUR + 1]
SCENES = [scene1, scene2, scene3, scene4, scene5, scene6, scene7]


def render_frame(tn, idx=0):
    t = warp(tn)
    img = BG.copy()
    d = ImageDraw.Draw(img)
    for i, fn in enumerate(SCENES):
        if BOUNDS[i] <= t < BOUNDS[i + 1]:
            r = fn(img, d, t, t - BOUNDS[i])
            if r is not None: d = r
            break
    draw_title(d, t)
    draw_caption(d, tn)
    for st_ in STARTS:
        if 0 <= t - st_ < 0.15:
            a = 0.25 * (1 - (t - st_) / 0.15)
            img = Image.blend(img, Image.new('RGB', img.size, WHITE), a)
    return img.reduce(S)



def preview(times, out):
    os.makedirs(out, exist_ok=True)
    for t in times:
        render_frame(t, int(t * 30)).save(f"{out}/f_{t:05.2f}.png")


def full(outfile):
    tmp = outfile.replace('.mp4', '_tmp.mp4')
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
           '-i', '-', '-an', '-c:v', 'libx264', '-crf', '19', '-preset', 'veryfast', '-pix_fmt', 'yuv420p',
           '-movflags', '+faststart', tmp]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(DUR * FPS)
    for i in range(n):
        p.stdin.write(render_frame(i / FPS, i).tobytes())
        if i % 150 == 0:
            print('frame', i, '/', n, flush=True)
    p.stdin.close()
    if p.wait() == 0:
        os.rename(tmp, outfile)
        print('done', outfile)
    else:
        print('ffmpeg failed')


if __name__ == '__main__':
    if sys.argv[1] == 'preview':
        preview([float(x) for x in sys.argv[3:]], sys.argv[2])
    else:
        full(sys.argv[2])

