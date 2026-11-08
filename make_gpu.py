#!/usr/bin/env python3
"""PlainBytes Short: What a GPU really is. 720x1280, 30fps. Frames piped to ffmpeg."""
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


# ======================= GPU VIDEO =======================
DUR = 41.8
SENT = [(2.53, 5.0, "It runs on a different chip: the GPU."),
        (5.1, 8.3, "A CPU is like one genius chef, cooking one dish at a time, very fast."),
        (8.49, 13.68, "A GPU is a kitchen with thousands of cooks, each doing one simple step at once."),
        (13.87, 19.57, "Drawing a game screen and training an AI both turn into millions of tiny math problems that don't depend on each other."),
        (19.78, 24.5, "So instead of solving them one by one, a GPU solves thousands together."),
        (24.70, 30.36, "That's why companies are buying them by the hundreds of thousands, and why data centers full of them use so much power."),
        (30.55, 35.65, "The catch: a GPU is bad at everything else, so your CPU still runs the show."),
        (35.90, 37.4, "Next up: how drones deliver packages."),
        (37.63, 40.3, "Follow PlainBytes for more tech, explained simply.")]

def make_caps():
    caps = []
    for a, b, s in SENT:
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

TITLES = [(0.1, 2.5, "AI doesn't run on your CPU"), (2.6, 5.05, "It runs on a GPU"),
          (5.1, 8.45, "CPU: one genius chef"), (8.5, 13.8, "GPU: thousands of cooks"),
          (13.9, 19.7, "Millions of tiny math problems"), (19.8, 24.6, "Solved together, not one by one"),
          (24.7, 30.5, "Everyone wants GPUs"), (30.6, 35.8, "The catch: only good at one thing"),
          (35.9, 37.5, "Next: how drones deliver"), (37.6, 41.8, "Follow for more")]

NEW_A = [0, DUR]; OLD_A = [0, DUR]
def warp(tn): return float(tn)

GREEN = (120, 220, 150)

def tag(d, cx, cy, s, size=30, fill=OR, p=1.0):
    if p <= 0: return
    w_ = tw(s, size) + 40
    rr(d, (cx - w_ / 2 * p, cy - 26 * p, cx + w_ / 2 * p, cy + 26 * p), 14 * p, fill=fill)
    if p > 0.6:
        tx(d, cx, cy + 1, s, size * p, DARK, kind='p')

def gpu_chip(d, cx, cy, s, label, col=OR, glow_on=False):
    for i in (-1, 0, 1):
        for k in (-1, 1):
            ln(d, [(cx + i * 0.5 * s, cy + k * 0.62 * s), (cx + i * 0.5 * s, cy + k * 0.46 * s)], col, 0.08 * s)
            ln(d, [(cx + k * 0.62 * s, cy + i * 0.5 * s), (cx + k * 0.46 * s, cy + i * 0.5 * s)], col, 0.08 * s)
    rr(d, (cx - 0.46 * s, cy - 0.46 * s, cx + 0.46 * s, cy + 0.46 * s), 0.12 * s,
       fill=(96, 62, 24) if glow_on else DARK, outline=col, w=0.07 * s)
    tx(d, cx, cy + 0.02 * s, label, 0.36 * s, col, kind='p')

def chef(d, cx, cy, sc, t, busy=True, bounce=0.0):
    y = cy + (math.sin(t * 7 + bounce) * 3 * sc if busy else 0)
    rr(d, (cx - 26 * sc, y + 4 * sc, cx + 26 * sc, y + 58 * sc), 10 * sc, fill=WHITE)
    ell(d, cx, y - 16 * sc, 22 * sc, fill=SOFT)
    ell(d, cx - 8 * sc, y - 18 * sc, 3 * sc, fill=DARK); ell(d, cx + 8 * sc, y - 18 * sc, 3 * sc, fill=DARK)
    rr(d, (cx - 22 * sc, y - 46 * sc, cx + 22 * sc, y - 30 * sc), 4 * sc, fill=WHITE)
    ell(d, cx, y - 54 * sc, 20 * sc, fill=WHITE)

def plate(d, cx, cy, sc, full=True):
    ell(d, cx, cy, 24 * sc, 8 * sc, fill=SOFT)
    if full:
        ell(d, cx, cy - 8 * sc, 14 * sc, 9 * sc, fill=RED)
        ell(d, cx + 5 * sc, cy - 12 * sc, 5 * sc, 4 * sc, fill=GREEN)

def mini_chip(d, cx, cy, s, fill=OR):
    rr(d, (cx - s, cy - s, cx + s, cy + s), s * 0.25, fill=fill)
    rr(d, (cx - s * 0.5, cy - s * 0.5, cx + s * 0.5, cy + s * 0.5), s * 0.12, fill=DARK)

def crown(d, cx, cy, s):
    poly(d, [(cx - s, cy), (cx - s, cy - s * 0.9), (cx - s * 0.5, cy - s * 0.4), (cx, cy - s), (cx + s * 0.5, cy - s * 0.4),
             (cx + s, cy - s * 0.9), (cx + s, cy)], (255, 210, 60))

def drone(d, cx, cy, sc, t):
    rr(d, (cx - 40 * sc, cy - 14 * sc, cx + 40 * sc, cy + 14 * sc), 10 * sc, fill=OR)
    for sx in (-1, 1):
        ln(d, [(cx + sx * 40 * sc, cy - 6 * sc), (cx + sx * 66 * sc, cy - 22 * sc)], OR2, 6 * sc)
        w_ = 26 * sc * (0.5 + 0.5 * abs(math.sin(t * 25)))
        ln(d, [(cx + sx * 66 * sc - w_, cy - 26 * sc), (cx + sx * 66 * sc + w_, cy - 26 * sc)], WHITE, 5 * sc)
    ln(d, [(cx, cy + 14 * sc), (cx, cy + 36 * sc)], TAN, 3 * sc, cap=False)
    rr(d, (cx - 20 * sc, cy + 36 * sc, cx + 20 * sc, cy + 68 * sc), 4 * sc, fill=SOFT, outline=TAN, w=2)


# ---------- scenes ----------
def scene1(img, d, t, tl):
    p = eob(tl / 0.5)
    robot(d, 360, 400, 1.0, t, 'confused' if tl < 2.6 else 'normal')
    if 0.9 < tl < 2.6:
        q = eob((tl - 0.9) / 0.3)
        tx(d, 360, 270, "?", 70 * q, RED, stroke=4)
    if tl > 2.4:
        q = eob((tl - 2.4) / 0.4)
        gpu_chip(d, 360, 700, 120 * q, "GPU", glow_on=True)


def scene2(img, d, t, tl):
    chef(d, 360, 440, 1.7, t)
    n_done = int(tl / 0.85)
    ell(d, 360, 640, 1)  # no-op anchor
    plate(d, 360, 640, 1.5, full=(tl % 0.85) > 0.3)
    tag(d, 360, 270, "CPU", 30, p=eob(tl / 0.4))
    for i in range(min(n_done, 3)):
        plate(d, 130 + i * 110, 740, 0.9)
    tx(d, 560, 740, "...", 36, SOFT)
    tx(d, 360, 800, "1 dish at a time", 30, SOFT, stroke=3)


def scene3(img, d, t, tl):
    cols, rows = 5, 4
    for r in range(rows):
        for c in range(cols):
            i = r * cols + c
            p = eob((tl - 0.1 - i * 0.07) / 0.35)
            if p <= 0: continue
            cx, cy = 360 + (c - 2) * 105, 390 + r * 110
            chef(d, cx, cy, 0.62 * p, t, bounce=i)
            plate(d, cx, cy + 56, 0.5 * p)
    tag(d, 360, 270, "GPU", 30, p=eob(tl / 0.4))
    if tl > 2.8:
        tx(d, 360, 800, "all cooking at once", 32, SOFT, stroke=3)


def scene4(img, d, t, tl):
    rr(d, (60, 330, 230, 440), 12, fill=PANEL, outline=OR, w=4)
    poly(d, [(120, 360), (120, 410), (165, 385)], GREEN)
    tx(d, 145, 470, "game", 26, SOFT, stroke=3)
    rr(d, (490, 330, 660, 440), 12, fill=PANEL, outline=BLUE, w=4)
    tx(d, 575, 385, "AI", 54, BLUE, kind='p')
    tx(d, 575, 470, "training", 26, SOFT, stroke=3)
    labels = ["2+3", "7x4", "9-1", "6x8", "5+5", "3x3", "8+2", "4x9", "1+7", "6-2", "5x5", "9+9"]
    for i, lab in enumerate(labels):
        c, r = i % 4, i // 4
        p = eob((tl - 0.6 - i * 0.12) / 0.3)
        if p <= 0: continue
        cx, cy = 360 + (c - 1.5) * 98, 560 + r * 70
        rr(d, (cx - 40 * p, cy - 26 * p, cx + 40 * p, cy + 26 * p), 10 * p, fill=SOFT if tl < 3.4 else (60, 90, 66))
        if p > 0.7: tx(d, cx, cy + 1, lab, 26, DARK if tl < 3.4 else WHITE, kind='p')
    ln(d, [(250, 385), (330, 480)], TAN, 4, cap=False)
    ln(d, [(470, 385), (390, 480)], TAN, 4, cap=False)
    if tl > 3.4:
        tx(d, 360, 790, "none waits for another", 32, GREEN, stroke=4)
    else:
        tx(d, 360, 790, "millions of tiny problems", 32, SOFT, stroke=3)


def scene5(img, d, t, tl):
    tx(d, 90, 340, "CPU", 30, OR, kind='p', anchor='lm')
    for k in range(8):
        on = int(tl * 1.6) % 8 == k
        done = k < int(tl * 1.6)
        rr(d, (90 + k * 68, 380, 140 + k * 68, 430), 8, fill=OR if on else (GREEN if done else PANEL))
    rr(d, (90, 450, 630, 474), 10, fill=PANEL)
    rr(d, (90, 450, 90 + 540 * clamp(tl * 0.1), 474), 10, fill=OR2)
    tx(d, 360, 505, "one by one", 26, SOFT, stroke=3)
    tx(d, 90, 585, "GPU", 30, OR, kind='p', anchor='lm')
    fin = tl > 1.6
    for k in range(8):
        for row in range(2):
            rr(d, (90 + k * 68, 620 + row * 56, 140 + k * 68, 664 + row * 56),
               8, fill=GREEN if fin else (OR if int(t * 8 + k + row) % 2 else OR2))
    rr(d, (90, 740, 630, 764), 10, fill=PANEL)
    rr(d, (90, 740, 90 + 540 * clamp(tl / 1.6), 764), 10, fill=GREEN)
    if fin:
        tx(d, 360, 800, "thousands, together: done!", 30, GREEN, stroke=3)


def scene6(img, d, t, tl):
    if tl < 2.8:
        cols, rows = 8, 4
        for r in range(rows):
            for c in range(cols):
                i = r * cols + c
                p = eob((tl - 0.05 * i) / 0.3)
                if p <= 0: continue
                mini_chip(d, 360 + (c - 3.5) * 72, 380 + r * 72, 24 * p)
        tx(d, 360, 740, "bought by the", 34, WHITE, stroke=4)
        tx(d, 360, 785, "hundreds of thousands", 34, OR, stroke=4)
    else:
        datacenter_s(d, 360, 450, 0.95, t)
        p = eob((tl - 2.9) / 0.4)
        bolt(d, 170, 640, 50 * p, OR)
        bolt(d, 550, 640, 50 * p, OR)
        rr(d, (250, 616, 470, 664), 14, fill=PANEL, outline=OR, w=4)
        w_ = 200 * clamp((tl - 3.0) / 1.8)
        rr(d, (260, 626, 260 + w_, 654), 8, fill=RED if w_ > 130 else OR)
        tx(d, 360, 740, "data centers use huge power", 30, SOFT, stroke=3)


def datacenter_s(d, cx, cy, sc, t):
    rr(d, (cx - 150 * sc, cy - 100 * sc, cx + 150 * sc, cy + 100 * sc), 16 * sc, fill=(40, 30, 23), outline=OR, w=4 * sc)
    for i in range(3):
        x0 = cx - 124 * sc + i * 86 * sc
        rr(d, (x0, cy - 76 * sc, x0 + 72 * sc, cy + 76 * sc), 8 * sc, fill=PANEL)
        for k in range(5):
            on = (int(t * 3) + i + k) % 3 == 0
            ell(d, x0 + 16 * sc, cy - 54 * sc + k * 26 * sc, 5 * sc, fill=GREEN if on else (90, 70, 50))
            ln(d, [(x0 + 30 * sc, cy - 54 * sc + k * 26 * sc), (x0 + 60 * sc, cy - 54 * sc + k * 26 * sc)], (30, 24, 20), 5 * sc)


def bolt(d, cx, cy, s, fill):
    pts = [(0.15, -1), (-0.55, 0.1), (-0.05, 0.1), (-0.2, 1), (0.6, -0.2), (0.05, -0.2)]
    poly(d, [(cx + x * s, cy + y * s) for x, y in pts], fill)


def scene7(img, d, t, tl):
    gpu_chip(d, 190, 480, 130, "GPU")
    p1 = eob((tl - 0.3) / 0.4)
    tag(d, 190, 340, "math", 28, fill=GREEN, p=p1)
    if tl > 1.6:
        q = eob((tl - 1.6) / 0.4)
        tag(d, 190, 640, "apps? no", 26, fill=RED, p=q)
        tag(d, 190, 700, "files? no", 26, fill=RED, p=q)
    if tl > 3.0:
        q = eob((tl - 3.0) / 0.4)
        gpu_chip(d, 530, 480, 130 * q, "CPU")
        crown(d, 530, 380, 36 * q)
        tx(d, 530, 640, "still the boss", 28, (255, 210, 60), stroke=3)


def scene8(img, d, t, tl):
    cx, cy, sc = 360, 400, 1.25
    arms = (125, 125) if tl < 1.5 else (14, 14)
    robot(d, cx, cy, sc, t, 'happy', arms=arms)
    if tl < 1.8:
        p = eob((tl - 0.1) / 0.4)
        drone(d, 360 + math.sin(t * 2) * 20, 700, 0.9 * p, t)
    else:
        p = eob((tl - 1.8) / 0.4)
        chip_logo(d, 238, 760, 62 * p)
        tx(d, 290, 760, "PlainBytes", 44 * p, WHITE, anchor='lm', kind='p')


STARTS = [5.1, 8.49, 13.87, 19.78, 24.70, 30.55, 35.90]
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

