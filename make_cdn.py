#!/usr/bin/env python3
"""PlainBytes Short: How DNS works. 720x1280, 30fps. Frames piped to ffmpeg."""
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


# ======================= CDN VIDEO =======================
DUR = 36.4
ST = [0, 4.70, 6.81, 9.47, 15.91, 19.02, 22.74, 25.51, 30.63, 32.21]
ENDS = [4.3, 6.5, 9.2, 15.55, 18.65, 22.4, 25.15, 30.3, 31.8, 34.8]
TXT = ["Why does a video load instantly, even when the website is on the other side of the planet?",
       "Because it usually isn't coming from there.",
       "Think of a CDN as a chain of corner shops.",
       "Instead of one giant warehouse far away, copies of popular files are stored on servers in cities around the world.",
       "When you open a page, you get the files from the nearest one.",
       "A shorter trip means faster loading, and less traffic for the main server.",
       "Streaming sites, shops and news pages all use one.",
       "The catch: when a big CDN has an outage, thousands of sites seem to break at the same time.",
       "Next up: how cookies work.",
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

TITLES = [(0.1, 4.3, "Why is it so fast?"), (4.7, 6.7, "It isn't coming from far away"),
          (6.81, 9.4, "A chain of corner shops"), (9.47, 15.8, "Copies stored worldwide"),
          (15.91, 18.9, "Served from the nearest"), (19.02, 22.7, "Shorter trip, faster page"),
          (22.74, 25.4, "Everyone uses one"), (25.51, 30.5, "The catch: outages"),
          (30.63, 32.1, "Next: cookies"), (32.21, 36.4, "Follow for more")]

def warp(tn): return float(tn)
GREEN = (120, 220, 150)

def tag(d, cx, cy, s, size=30, fill=OR, p=1.0):
    if p <= 0: return
    w_ = tw(s, size) + 40
    rr(d, (cx - w_ / 2 * p, cy - 26 * p, cx + w_ / 2 * p, cy + 26 * p), 14 * p, fill=fill)
    if p > 0.6:
        tx(d, cx, cy + 1, s, size * p, DARK, kind='p')

def phone_(d, cx, cy, w=90, h=160):
    if w < 30 or h < 40: return
    rr(d, (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), 16, fill=PANEL, outline=WHITE, w=4)
    rr(d, (cx - w / 2 + 8, cy - h / 2 + 14, cx + w / 2 - 8, cy + h / 2 - 14), 8, fill=(30, 60, 90))

def server(d, cx, cy, s=1.0, lit=GREEN):
    for k in range(3):
        y = cy + (k - 1) * 52 * s
        rr(d, (cx - 80 * s, y - 22 * s, cx + 80 * s, y + 22 * s), 10 * s, fill=PANEL, outline=OR, w=3)
        ell(d, cx - 56 * s, y, 6 * s, fill=lit if k != 1 else OR)
        ln(d, [(cx - 30 * s, y), (cx + 56 * s, y)], TAN, 5 * s)

def mini(d, cx, cy, s=1.0, col=OR, lit=GREEN):
    if s <= 0.05: return
    for k in range(2):
        y = cy + (k - 0.5) * 34 * s
        rr(d, (cx - 44 * s, y - 15 * s, cx + 44 * s, y + 15 * s), 8 * s, fill=PANEL, outline=col, w=3)
        ell(d, cx - 28 * s, y, 4.5 * s, fill=lit)
        ln(d, [(cx - 12 * s, y), (cx + 28 * s, y)], TAN, 4 * s)

def shop(d, cx, cy, s=1.0):
    rr(d, (cx - 50 * s, cy - 20 * s, cx + 50 * s, cy + 60 * s), 8 * s, fill=SOFT)
    rr(d, (cx - 14 * s, cy + 10 * s, cx + 14 * s, cy + 60 * s), 4 * s, fill=TAN)
    poly(d, [(cx - 62 * s, cy - 18 * s), (cx + 62 * s, cy - 18 * s), (cx + 50 * s, cy - 56 * s), (cx - 50 * s, cy - 56 * s)], OR)
    for i in range(4):
        x = cx - 62 * s + i * 31 * s
        if i % 2 == 0:
            poly(d, [(x, cy - 18 * s), (x + 31 * s, cy - 18 * s), (x + 27 * s, cy - 56 * s), (x + 4 * s, cy - 56 * s)], RED)

def pulses(d, a, b, t, col=OR, n=3, size=9, speed=0.7):
    for k in range(n):
        f = (t * speed + k / n) % 1.0
        ell(d, lerp(a[0], b[0], f), lerp(a[1], b[1], f), size, fill=col)

def scene1(img, d, t, tl):
    phone_(d, 120, 470, 110 * eob(tl / 0.5), 200 * eob(tl / 0.5))
    server(d, 590, 340, 0.7 * eob((tl - 0.2) / 0.5))
    if tl > 0.8:
        tag(d, 590, 440, "far away", 26, fill=WHITE, p=eob((tl - 0.8) / 0.4))
    if tl > 1.4:
        pulses(d, (190, 470), (520, 380), tl, OR, n=4, size=8, speed=0.35)
    if tl > 3.6:
        tag(d, 120, 620, "loads fast!", 28, fill=GREEN, p=eob((tl - 3.6) / 0.4))
    robot(d, 360, 700, 0.5, t, 'confused')
    if tl > 4.5:
        tx(d, 500, 610, "?", 64 * eob((tl - 4.5) / 0.3), RED, stroke=4)

def scene2(img, d, t, tl):
    for i, x in enumerate((130, 290, 450, 610)):
        p = eob((tl - 0.15 * i) / 0.4)
        if p > 0.05: shop(d, x, 480, 0.8 * p)
    if tl > 1.0:
        tag(d, 360, 650, "close to you", 30, p=eob((tl - 1.0) / 0.4))

def scene3(img, d, t, tl):
    # one far warehouse fades out, copies appear around a map panel
    rr(d, (60, 300, 660, 640), 24, fill=PANEL, outline=TAN, w=3)
    pos = [(160, 380), (360, 360), (560, 390), (230, 520), (450, 530), (580, 580), (130, 590)]
    if tl < 2.0:
        server(d, 360, 470, 0.9 * eob(tl / 0.5))
        if tl > 0.6:
            tag(d, 360, 700, "one far warehouse", 28, fill=WHITE, p=eob((tl - 0.6) / 0.4))
    else:
        for i, (x, y) in enumerate(pos):
            mini(d, x, y, 0.9 * eob((tl - 2.0 - 0.28 * i) / 0.4))
        tag(d, 360, 710, "copies everywhere", 30, p=eob((tl - 2.4) / 0.4))
        if tl > 5.0:
            tag(d, 360, 780, "stored on servers", 26, fill=GREEN, p=eob((tl - 5.0) / 0.4))

def scene4(img, d, t, tl):
    pos = [(130, 330), (360, 300), (590, 330), (130, 470), (590, 470)]
    for i, (x, y) in enumerate(pos):
        mini(d, x, y, 0.95, col=OR if i != 3 else GREEN)
    phone_(d, 360, 600, 100 * eob(tl / 0.4), 180 * eob(tl / 0.4))
    if tl > 0.6:
        p = clamp((tl - 0.6) / 1.0)
        ln(d, [(300, 560), (300 + (170 - 300) * p, 560 + (480 - 560) * p)], GREEN, 8)
        ln(d, [(300, 560), (300 + (170 - 300) * 0, 560)], GREEN, 1)
    if tl > 1.6:
        tag(d, 360, 760, "nearest one", 32, fill=GREEN, p=eob((tl - 1.6) / 0.4))

def scene5(img, d, t, tl):
    tx(d, 110, 330, "far", 30, WHITE, anchor='lm', kind='p')
    tx(d, 110, 440, "near", 30, WHITE, anchor='lm', kind='p')
    rr(d, (200, 310, 640, 350), 20, fill=PANEL)
    rr(d, (200, 420, 640, 460), 20, fill=PANEL)
    pf = eio(clamp(tl / 4.5)); pn = eio(clamp(tl / 1.6))
    rr(d, (200, 310, 200 + 440 * pf, 350), 20, fill=RED)
    rr(d, (200, 420, 200 + 440 * pn, 460), 20, fill=GREEN)
    if tl > 1.8:
        tag(d, 360, 560, "faster + less traffic", 30, p=eob((tl - 1.8) / 0.4))
    for i, s in enumerate(("Streaming", "Shops", "News")):
        if tl > 3.6 + 0.4 * i:
            tag(d, 150 + i * 210, 700, s, 26, fill=WHITE, p=eob((tl - 3.6 - 0.4 * i) / 0.4))

def scene6(img, d, t, tl):
    pos = [(150, 330), (360, 330), (570, 330), (150, 460), (360, 460), (570, 460)]
    for i, (x, y) in enumerate(pos):
        mini(d, x, y, 0.95)
        s = clamp((tl - 1.2 - 0.25 * i) / 0.3)
        if s > 0:
            ln(d, [(x - 22, y - 22), (x + 22, y + 22)], RED, 9 * s)
            ln(d, [(x + 22, y - 22), (x - 22, y + 22)], RED, 9 * s)
    if tl > 0.4:
        tag(d, 360, 252, "one big CDN goes down", 26, fill=RED, p=eob((tl - 0.4) / 0.4))
    robot(d, 360, 640, 0.45, t, 'oops')
    if tl > 3.4:
        tag(d, 360, 800, "thousands of sites at once", 26, fill=WHITE, p=eob((tl - 3.4) / 0.4))

def scene7(img, d, t, tl):
    cx, cy, sc = 360, 420, 1.25
    arms = (125, 125) if tl < 1.5 else (14, 14)
    robot(d, cx, cy, sc, t, 'happy', arms=arms)
    if tl < 1.6:
        tag(d, 360, 790, "next: cookies", 36, p=eob((tl - 0.1) / 0.4))
    else:
        p = eob((tl - 1.6) / 0.4)
        chip_logo(d, 238, 760, 62 * p)
        tx(d, 290, 760, "PlainBytes", 44 * p, WHITE, anchor='lm', kind='p')

BOUNDS = [0, ST[2], ST[3], ST[4], ST[5], ST[7], ST[8], DUR + 1]
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
    for st_ in BOUNDS[1:7]:
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

