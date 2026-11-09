#!/usr/bin/env python3
"""PlainBytes Short: How Bluetooth trackers find lost things. 720x1280, 30fps. Frames piped to ffmpeg."""
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



# ======================= TRACKER VIDEO =======================
DUR = 40.3
SENT = [(0.10, 2.97, "A Bluetooth tracker has no GPS and no internet,"),
        (3.14, 4.81, "so how does it find your lost keys?"),
        (4.97, 6.64, "It borrows the phones of strangers."),
        (6.79, 9.2, "Imagine shouting I am here in a crowded street."),
        (9.36, 12.04, "You can't call anyone, but people walking past hear you."),
        (12.2, 16.38, "A tracker does the same, sending a tiny Bluetooth signal every few seconds."),
        (16.54, 21.75, "Any phone in the network that passes by hears it, notes where it is, and quietly sends that spot online."),
        (21.92, 26.8, "The report is encrypted, so only you can read it, and the phone that passed by cannot read it either."),
        (27.0, 29.69, "Millions of phones turn into one giant search party."),
        (29.86, 33.99, "The catch: in an empty forest with no phones nearby, nobody hears the shout."),
        (34.14, 35.82, "Next up: how QR codes work."),
        (36.0, 38.74, "Follow PlainBytes for more tech, explained simply.")]

def make_caps():
    caps = []
    for a, b, s in SENT:
        words = s.split(' ')
        chunks, cur = [], ''
        for w_ in words:
            if cur and len(cur) + 1 + len(w_) > 27:
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
CAPS = [c for c in CAPS if c[0] > 0.0 or True]

TITLES = [(0.1, 4.9, "How does a tracker find your keys?"), (5.0, 12.1, "It borrows strangers' phones"),
          (12.2, 16.45, "A tiny Bluetooth shout"), (16.55, 21.85, "A passing phone hears it"),
          (21.95, 27.9, "Encrypted: only you can read it"), (28.0, 29.8, "Millions of phones"),
          (29.9, 34.0, "The catch: empty places"), (34.1, 35.9, "Next: how QR codes work"),
          (36.0, 40.3, "Follow for more")]

NEW_A = [0, DUR]; OLD_A = [0, DUR]
def warp(tn): return float(tn)

GREEN = (120, 220, 150)

def tag(d, cx, cy, s, size=30, fill=OR, p=1.0):
    if p <= 0: return
    w_ = tw(s, size) + 40
    rr(d, (cx - w_ / 2 * p, cy - 26 * p, cx + w_ / 2 * p, cy + 26 * p), 14 * p, fill=fill)
    if p > 0.6:
        tx(d, cx, cy + 1, s, size * p, DARK, kind='p')

def tracker(d, cx, cy, r, t=0.0, pulse=False):
    if pulse:
        for k in range(3):
            ph = ((t * 0.8) + k / 3) % 1.0
            rad = r * (1.2 + ph * 3.2)
            c = tuple(int(v * (1 - ph) + 34 * ph) for v in BLUE)
            ell(d, cx, cy, rad, outline=c, w=4)
    ell(d, cx, cy, r, fill=SOFT)
    ell(d, cx, cy, r * 0.62, fill=OR)
    ell(d, cx, cy - r * 1.05, r * 0.2, outline=SOFT, w=4)

def phone_s(d, cx, cy, sc, glow_on=False):
    rr(d, (cx - 34 * sc, cy - 60 * sc, cx + 34 * sc, cy + 60 * sc), 10 * sc, fill=PANEL, outline=SOFT, w=3)
    rr(d, (cx - 28 * sc, cy - 48 * sc, cx + 28 * sc, cy + 46 * sc), 6 * sc, fill=(80, 140, 110) if glow_on else DARK)

def person(d, cx, cy, sc, t, ph=0.0, col=TAN):
    bob = math.sin(t * 6 + ph) * 3 * sc
    ell(d, cx, cy - 40 * sc + bob, 16 * sc, fill=SOFT)
    rr(d, (cx - 18 * sc, cy - 22 * sc + bob, cx + 18 * sc, cy + 34 * sc + bob), 10 * sc, fill=col)
    sw = math.sin(t * 6 + ph) * 8 * sc
    ln(d, [(cx - 8 * sc, cy + 34 * sc), (cx - 8 * sc + sw, cy + 62 * sc)], col, 8 * sc)
    ln(d, [(cx + 8 * sc, cy + 34 * sc), (cx + 8 * sc - sw, cy + 62 * sc)], col, 8 * sc)

def lock(d, cx, cy, s, col=OR):
    ln(d, [(cx - 0.35 * s, cy - 0.1 * s), (cx - 0.35 * s, cy - 0.5 * s), (cx, cy - 0.85 * s), (cx + 0.35 * s, cy - 0.5 * s), (cx + 0.35 * s, cy - 0.1 * s)], col, 0.14 * s, cap=False)
    rr(d, (cx - 0.55 * s, cy - 0.1 * s, cx + 0.55 * s, cy + 0.7 * s), 0.12 * s, fill=col)
    ell(d, cx, cy + 0.3 * s, 0.1 * s, fill=DARK)

def pin(d, cx, cy, s, col=RED):
    ell(d, cx, cy - s, s * 0.6, fill=col)
    poly(d, [(cx - s * 0.5, cy - s * 0.75), (cx + s * 0.5, cy - s * 0.75), (cx, cy)], col)
    ell(d, cx, cy - s, s * 0.22, fill=WHITE)

def cloud_s(d, cx, cy, s, col=WHITE):
    ell(d, cx - 0.5 * s, cy + 0.1 * s, 0.5 * s, 0.4 * s, fill=col)
    ell(d, cx + 0.5 * s, cy + 0.1 * s, 0.5 * s, 0.4 * s, fill=col)
    ell(d, cx, cy - 0.15 * s, 0.6 * s, 0.5 * s, fill=col)
    rr(d, (cx - 0.5 * s, cy + 0.1 * s, cx + 0.5 * s, cy + 0.5 * s), 0.1 * s, fill=col)

def tree(d, cx, cy, sc):
    rr(d, (cx - 6 * sc, cy, cx + 6 * sc, cy + 36 * sc), 2, fill=(110, 72, 40))
    poly(d, [(cx - 30 * sc, cy + 4 * sc), (cx + 30 * sc, cy + 4 * sc), (cx, cy - 56 * sc)], (70, 140, 90))
    poly(d, [(cx - 24 * sc, cy - 28 * sc), (cx + 24 * sc, cy - 28 * sc), (cx, cy - 78 * sc)], (90, 165, 105))

def cross(d, cx, cy, s, col=RED):
    ln(d, [(cx - s, cy - s), (cx + s, cy + s)], col, 9)
    ln(d, [(cx - s, cy + s), (cx + s, cy - s)], col, 9)


# ---------- scenes ----------
def scene1(img, d, t, tl):
    robot(d, 360, 380, 0.95, t, 'confused')
    p = eob((tl - 0.3) / 0.5)
    tracker(d, 360, 640, 52 * p)
    if tl > 1.2:
        q = eob((tl - 1.2) / 0.35)
        tag(d, 200, 760, "no GPS", 28, fill=RED, p=q)
    if tl > 2.0:
        q = eob((tl - 2.0) / 0.35)
        tag(d, 520, 760, "no internet", 28, fill=RED, p=q)
    if tl > 3.2:
        tx(d, 360, 530, "?", 70, RED, stroke=4)


def scene2(img, d, t, tl):
    # strangers walking by, tracker on a bench shouting
    tracker(d, 150, 640, 34, t, pulse=tl > 2.6)
    if tl > 2.6:
        bubble(d, (60, 330, 340, 410), (150, 590), fill=WHITE)
        tx(d, 200, 370, "I am here!", 34, DARK)
    for i in range(4):
        x = ((t * 55 + i * 190) % 900) - 100
        person(d, x, 700 - (i % 2) * 20, 1.4, t, ph=i)
    phone_s(d, 560, 460, 0.9, glow_on=tl > 5.0)
    if tl > 5.0:
        tx(d, 560, 560, "hears it", 26, GREEN, stroke=3)


def scene3(img, d, t, tl):
    tracker(d, 360, 560, 60, t, pulse=True)
    tag(d, 360, 330, "ping", 34, p=eob(tl / 0.3))
    tx(d, 360, 790, "every few seconds", 32, SOFT, stroke=3)


def scene4(img, d, t, tl):
    tracker(d, 130, 650, 34, t, pulse=True)
    phone_s(d, 360, 560, 1.4, glow_on=tl > 0.8)
    p = eob((tl - 1.4) / 0.4)
    if p > 0:
        pin(d, 360, 440, 40 * p)
    if tl > 2.4:
        u = clamp((tl - 2.4) / 1.4)
        py = lerp(430, 290, eio(u))
        cloud_s(d, 360, 280, 60, SOFT)
        pin(d, 360, py + 20, 22)
    if tl > 3.8:
        tx(d, 360, 760, "location sent online", 30, SOFT, stroke=3)


def scene5(img, d, t, tl):
    phone_s(d, 200, 520, 1.1)
    lock(d, 200, 520, 50, OR)
    tx(d, 200, 650, "stranger's phone", 24, SOFT, stroke=3)
    cross(d, 200, 440 - 0, 14, RED) if tl > 3.5 else None
    phone_s(d, 520, 520, 1.1, glow_on=tl > 1.5)
    if tl > 1.5:
        lock(d, 520, 440, 40, GREEN)
    tx(d, 520, 650, "your phone", 24, GREEN, stroke=3)
    ln(d, [(260, 520), (460, 520)], OR, 6)
    pin(d, 310 + 120 * eio(clamp(tl / 2.0)), 510, 20, RED)
    tag(d, 360, 780, "only you can read it", 26, fill=GREEN, p=eob((tl - 0.8) / 0.4))


def scene6(img, d, t, tl):
    import random
    rnd = random.Random(4)
    n = int(40 * clamp(tl / 1.4)) + 3
    for i in range(n):
        x = rnd.uniform(60, 660); y = rnd.uniform(300, 790)
        ell(d, x, y, 9 + 4 * math.sin(t * 5 + i), fill=BLUE)
    tracker(d, 360, 560, 30, t, pulse=True)


def scene7(img, d, t, tl):
    for x, y, s in ((120, 640, 1.2), (250, 680, 1.4), (470, 660, 1.3), (600, 640, 1.2), (360, 620, 1.1)):
        tree(d, x, y, s)
    tracker(d, 360, 730, 26, t, pulse=True)
    tx(d, 360, 480, "...", 70, SOFT)
    if tl > 2.0:
        cross(d, 360, 400, 30, RED)
        tag(d, 360, 330, "no phones, no reports", 28, fill=RED, p=eob((tl - 2.0) / 0.4))


def scene8(img, d, t, tl):
    cx, cy, sc = 360, 400, 1.25
    arms = (125, 125) if tl < 1.5 else (14, 14)
    robot(d, cx, cy, sc, t, 'happy', arms=arms)
    if tl < 1.8:
        p = eob((tl - 0.1) / 0.4)
        rr(d, (300, 660, 420, 780), 10 * p, fill=WHITE)
        for i in range(3):
            for j in range(3):
                if (i + j) % 2 == 0:
                    rr(d, (312 + i * 36, 672 + j * 36, 340 + i * 36, 700 + j * 36), 2, fill=DARK)
    else:
        p = eob((tl - 1.8) / 0.4)
        chip_logo(d, 238, 760, 62 * p)
        tx(d, 290, 760, "PlainBytes", 44 * p, WHITE, anchor='lm', kind='p')


STARTS = [4.97, 12.2, 16.54, 21.92, 28.0, 29.86, 34.14]
BOUNDS = [0] + STARTS + [DUR + 1]
SCENES = [scene1, scene2, scene3, scene4, scene5, scene6, scene7, scene8]


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

