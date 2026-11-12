#!/usr/bin/env python3
"""PlainBytes Short: How satellite internet works. 720x1280, 30fps. Frames piped to ffmpeg."""
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



# ======================= SATELLITE INTERNET VIDEO =======================
DUR = 36.0
ST = [0, 4.13, 7.75, 13.49, 18.06, 24.65, 29.41, 31.58]
ENDS = [3.71, 7.33, 13.07, 17.64, 24.23, 28.99, 31.16, 34.39]
TXT = ["Your internet can come from space, so how does it get all the way down here?",
       "Picture a satellite as a giant cell tower floating above you.",
       "Your dish sends a signal up to the satellite, which beams it down to a ground station wired to the internet.",
       "Old satellites sat extremely high, so every message took a very long trip.",
       "Newer ones orbit much lower and move fast, so thousands of them work together and hand you off like a relay race.",
       "The catch: a dish needs a clear view of the sky, so trees and roofs can block it.",
       "Next up: how 5G works.",
       "Follow PlainBytes for more tech, explained simply."]
SENT = [(ST[i], ENDS[i], TXT[i]) for i in range(len(TXT))]

def make_caps():
    caps = []
    for a, b, s in SENT[1:]:
        words = s.split(' ')
        chunks, cur = [], ''
        for w_ in words:
            if cur and len(cur) + 1 + len(w_) > 34:
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

TITLES = [(0.1, 4.0, "Internet from space?"), (4.13, 7.7, "A cell tower in the sky"),
          (7.75, 13.4, "Dish > satellite > ground"), (13.49, 18.0, "Old: very high, slow trip"),
          (18.06, 24.6, "New: low orbit, thousands"), (24.65, 29.3, "The catch: clear sky"),
          (29.41, 31.5, "Next: how 5G works"), (31.58, 36.0, "Follow for more")]

def warp(tn): return float(tn)
GREEN = (120, 220, 150)
EARTH = (52, 84, 122); EARTH2 = (92, 140, 190)

def tag(d, cx, cy, s, size=30, fill=OR, p=1.0):
    if p <= 0: return
    w_ = tw(s, size) + 40
    rr(d, (cx - w_ / 2 * p, cy - 26 * p, cx + w_ / 2 * p, cy + 26 * p), 14 * p, fill=fill)
    if p > 0.6:
        tx(d, cx, cy + 1, s, size * p, DARK, kind='p')

def arrow(d, x0, y0, x1, y1, col=OR, w=8):
    ln(d, [(x0, y0), (x1, y1)], col, w)
    a = math.atan2(y1 - y0, x1 - x0)
    poly(d, [(x1 + math.cos(a) * 16, y1 + math.sin(a) * 16),
             (x1 + math.cos(a + 2.5) * 20, y1 + math.sin(a + 2.5) * 20),
             (x1 + math.cos(a - 2.5) * 20, y1 + math.sin(a - 2.5) * 20)], col)

def satellite(d, cx, cy, s, tilt=0):
    for sx in (-1, 1):
        x0 = cx + sx * 0.28 * s
        rr(d, (min(x0, x0 + sx * 0.75 * s), cy - 0.22 * s, max(x0, x0 + sx * 0.75 * s), cy + 0.22 * s), 0.05 * s, fill=BLUE, outline=WHITE, w=max(1, 0.03 * s))
        for k in (1, 2):
            xx = x0 + sx * 0.25 * k * s
            ln(d, [(xx, cy - 0.22 * s), (xx, cy + 0.22 * s)], WHITE, max(1, 0.025 * s), cap=False)
    rr(d, (cx - 0.28 * s, cy - 0.28 * s, cx + 0.28 * s, cy + 0.28 * s), 0.07 * s, fill=OR, outline=OR2, w=max(1, 0.04 * s))
    ell(d, cx, cy, 0.1 * s, fill=DARK)
    ln(d, [(cx, cy - 0.28 * s), (cx, cy - 0.5 * s)], SOFT, max(1, 0.04 * s))
    ell(d, cx, cy - 0.52 * s, 0.05 * s, fill=RED)

def dish(d, cx, cy, s):
    d.pieslice([(cx - s) * S, (cy - s * 0.5) * S, (cx + s) * S, (cy + s * 0.5) * S], 0, 180, fill=WHITE)
    ln(d, [(cx, cy + s * 0.45), (cx, cy + s * 0.95)], SOFT, s * 0.14)
    rr(d, (cx - s * 0.5, cy + s * 0.9, cx + s * 0.5, cy + s * 1.0), 4, fill=SOFT)
    ln(d, [(cx, cy), (cx, cy - s * 0.5)], SOFT, s * 0.07)
    ell(d, cx, cy - s * 0.52, s * 0.1, fill=RED)

def house(d, cx, cy, s):
    rr(d, (cx - s * 0.5, cy - s * 0.1, cx + s * 0.5, cy + s * 0.5), 6, fill=PANEL, outline=TAN, w=3)
    poly(d, [(cx - s * 0.6, cy - s * 0.08), (cx, cy - s * 0.6), (cx + s * 0.6, cy - s * 0.08)], OR2)
    rr(d, (cx - s * 0.1, cy + s * 0.15, cx + s * 0.1, cy + s * 0.5), 3, fill=DARK)

def tower(d, cx, cy, s):
    ln(d, [(cx - s * 0.3, cy + s), (cx, cy - s * 0.1), (cx + s * 0.3, cy + s)], TAN, s * 0.08)
    ln(d, [(cx - s * 0.2, cy + s * 0.55), (cx + s * 0.2, cy + s * 0.55)], TAN, s * 0.05)
    ln(d, [(cx - s * 0.12, cy + s * 0.25), (cx + s * 0.12, cy + s * 0.25)], TAN, s * 0.05)
    ell(d, cx, cy - s * 0.15, s * 0.07, fill=RED)

def ground_station(d, cx, cy, s):
    rr(d, (cx - s * 0.45, cy, cx + s * 0.45, cy + s * 0.5), 6, fill=PANEL, outline=TAN, w=3)
    dish(d, cx, cy - s * 0.15, s * 0.32)
    ln(d, [(cx + s * 0.45, cy + s * 0.35), (cx + s * 0.6, cy + s * 0.35)], GREEN, 5)

def earth(d, cy, r=700, col=EARTH):
    ell(d, 360, cy + r, r, fill=col, outline=EARTH2, w=4)

def pulses(d, a, b, t, col=OR, n=3, size=9, speed=0.7):
    for k in range(n):
        f = (t * speed + k / n) % 1.0
        ell(d, lerp(a[0], b[0], f), lerp(a[1], b[1], f), size, fill=col)

def dashed(d, a, b, col, w=4, n=14):
    for k in range(n):
        f0, f1 = k / n, (k + 0.55) / n
        ln(d, [(lerp(a[0], b[0], f0), lerp(a[1], b[1], f0)), (lerp(a[0], b[0], f1), lerp(a[1], b[1], f1))], col, w, cap=False)


def scene1(img, d, t, tl):
    for i, (x, y) in enumerate(((120, 300), (600, 360), (250, 250))):
        tx(d, x, y, ".", 40, SOFT)
    satellite(d, 360, 330 + math.sin(t * 2) * 6, 110 * eob(tl / 0.5))
    robot(d, 360, 590, 0.8, t, 'confused')
    if 0.8 < tl < 3.6:
        tx(d, 500, 480, "?", 64 * eob((tl - 0.8) / 0.3), RED, stroke=4)
    earth(d, 790)


def scene2(img, d, t, tl):
    satellite(d, 360, 300 + math.sin(t * 2) * 6, 120 * eob(tl / 0.5))
    tower(d, 360, 480, 220)
    if tl > 0.8:
        p = eob((tl - 0.8) / 0.4)
        tag(d, 360, 770, "a tower in the sky", 32, p=p)
    if tl > 1.6:
        for k in (1, 2, 3):
            r = 40 * k + (t * 40) % 40
            d.arc([(360 - r) * S, (350 - r * 0.6) * S, (360 + r) * S, (350 + r * 0.6) * S], 60, 120, fill=OR, width=round(5 * S))


def scene3(img, d, t, tl):
    sat = (360, 330)
    hs = (140, 650); gs = (590, 650)
    satellite(d, sat[0], sat[1], 100)
    house(d, hs[0], hs[1] + 20, 110)
    dish(d, hs[0] + 5, hs[1] - 80, 42)
    ground_station(d, gs[0], gs[1] - 30, 120)
    if tl > 0.6:
        p = clamp((tl - 0.6) / 1.5)
        e = (lerp(hs[0], sat[0], p), lerp(hs[1] - 90, sat[1] + 50, p)) if True else None
        ln(d, [(hs[0] + 5, hs[1] - 100), e], OR, 5)
        pulses(d, (hs[0] + 5, hs[1] - 100), (sat[0] - 30, sat[1] + 50), tl, n=3)
        tag(d, 150, 450, "dish sends up", 26, p=eob((tl - 0.8) / 0.4))
    if tl > 2.8:
        p = clamp((tl - 2.8) / 1.5)
        ln(d, [(sat[0] + 30, sat[1] + 50), (lerp(sat[0], gs[0], p), lerp(sat[1] + 50, gs[1] - 120, p))], GREEN, 5)
        pulses(d, (sat[0] + 30, sat[1] + 50), (gs[0], gs[1] - 120), tl, GREEN, n=3)
        tag(d, 580, 450, "beams down", 26, fill=GREEN, p=eob((tl - 3.0) / 0.4))
    if tl > 4.4:
        tag(d, 590, 790, "to the internet", 26, fill=WHITE, p=eob((tl - 4.4) / 0.4))


def scene4(img, d, t, tl):
    earth(d, 760, 900)
    sy = 270
    satellite(d, 360, sy + math.sin(t * 2) * 5, 90)
    house(d, 360, 690, 70)
    dish(d, 360, 640, 26)
    p = clamp((tl - 0.4) / 2.2)
    dashed(d, (360, 610), (360, lerp(610, sy + 55, p)), OR, 4, 18)
    if tl > 0.9:
        tag(d, 205, 450, "very high up", 28, p=eob((tl - 0.9) / 0.4))
    if tl > 2.0:
        tag(d, 500, 520, "long trip = slow", 28, fill=RED, p=eob((tl - 2.0) / 0.4))
        tx(d, 360, 770, "", 10)


def scene5(img, d, t, tl):
    earth(d, 700, 1000)
    house(d, 360, 640, 70)
    dish(d, 360, 590, 26)
    n = 7
    pos = []
    for i in range(n):
        ang = -70 + i * (140 / (n - 1)) + (t * 14) % (140 / (n - 1)) - 0
        a = math.radians(ang - 90 + 90)
        x = 360 + 330 * math.sin(math.radians(ang)); y = 560 - 300 * math.cos(math.radians(ang)) + 80
        pos.append((x, y))
        if -70 < ang < 70:
            satellite(d, x, y, 46 * eob((tl - 0.2 - i * 0.12) / 0.3))
    if tl > 1.5:
        near = min(pos, key=lambda p_: abs(p_[0] - 360))
        ln(d, [(360, 565), near], OR, 4)
        tag(d, 360, 270, "thousands, hand-off", 28, p=eob((tl - 1.5) / 0.4))
    if tl > 3.4:
        tag(d, 200, 770, "low orbit = fast", 28, fill=GREEN, p=eob((tl - 3.4) / 0.4))


def scene6(img, d, t, tl):
    satellite(d, 360, 300, 90)
    house(d, 360, 680, 90)
    dish(d, 360, 590, 34)
    dashed(d, (360, 560), (360, 370), OR, 4, 12)
    p = eob((tl - 0.8) / 0.5)
    if p > 0:
        ln(d, [(300, 470 + 60), (420, 470 + 60)], (60, 140, 70), 30 * p)
        ell(d, 300, 450, 55 * p, fill=(60, 140, 70)); ell(d, 360, 430, 65 * p, fill=(70, 160, 80)); ell(d, 425, 455, 52 * p, fill=(60, 140, 70))
        rr(d, (350, 490 - 0, 370, 540), 4, fill=(110, 70, 40)) if p > 0.9 else None
    if tl > 1.8:
        pp = eob((tl - 1.8) / 0.3)
        ln(d, [(330, 340), (390, 400)], RED, 12 * pp); ln(d, [(390, 340), (330, 400)], RED, 12 * pp)
        tag(d, 360, 770, "blocked signal", 30, fill=RED, p=eob((tl - 2.2) / 0.4))
    if tl > 3.4:
        tag(d, 360, 260, "needs clear sky", 30, p=eob((tl - 3.4) / 0.4))


def scene7(img, d, t, tl):
    cx, cy, sc = 360, 420, 1.25
    arms = (125, 125) if tl < 1.5 else (14, 14)
    robot(d, cx, cy, sc, t, 'happy', arms=arms)
    if tl < 2.17:
        tag(d, 360, 790, "next: 5G", 36, p=eob((tl - 0.3) / 0.4))
    else:
        p = eob((tl - 2.17) / 0.4)
        chip_logo(d, 238, 760, 62 * p)
        tx(d, 290, 760, "PlainBytes", 44 * p, WHITE, anchor='lm', kind='p')


STARTS = [4.13, 7.75, 13.49, 18.06, 24.65, 29.41]
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

