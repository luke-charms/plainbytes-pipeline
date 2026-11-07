#!/usr/bin/env python3
"""PlainBytes Short: What the cloud really is. 720x1280, 30fps. Frames piped to ffmpeg."""
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


# ======================= CLOUD VIDEO =======================
DUR = 40.1
SENT = [(1.64, 3.59, "It's a giant warehouse full of computers."),
        (3.99, 9.86, "Save a photo to the cloud, and it's stored on another company's hard drives, inside a building called a data center."),
        (10.13, 12.97, "Think of renting a storage unit instead of buying a bigger house."),
        (13.37, 20.42, "Your phone sends the photo over the internet, and the data center keeps copies on several machines, so one broken drive loses nothing."),
        (20.67, 24.05, "Later, from any device, you log in and your photo is fetched right back."),
        (24.45, 28.49, "Companies rent the same computers by the hour, so they never have to buy their own."),
        (28.74, 33.53, "The catch: it's still another company's computer, and data centers use huge amounts of electricity."),
        (33.69, 35.67, "Next up: how Bluetooth works."),
        (35.93, 37.25, "Follow PlainBytes for more tech, explained simply.")]

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

TITLES = [(0.1, 3.9, "The cloud isn't in the sky"), (4.0, 10.0, "Stored in a data center"),
          (10.15, 13.3, "Like renting a storage unit"), (13.4, 20.6, "Copies on several machines"),
          (20.7, 28.6, "Fetch it back. Rent by the hour."), (28.75, 33.6, "The catch: it eats power"),
          (33.7, 35.8, "Next: how Bluetooth works"), (35.9, 40.1, "Follow for more")]

NEW_A = [0, DUR]; OLD_A = [0, DUR]
def warp(tn): return float(tn)

IP_ME = "203.0.113.7"
IP_SITE = "93.184.216.34"
GREEN = (120, 220, 150)

def tag(d, cx, cy, s, size=30, fill=OR, p=1.0):
    if p <= 0: return
    w_ = tw(s, size) + 40
    rr(d, (cx - w_ / 2 * p, cy - 26 * p, cx + w_ / 2 * p, cy + 26 * p), 14 * p, fill=fill)
    if p > 0.6:
        tx(d, cx, cy + 1, s, size * p, DARK, kind='p')

def phone_s(d, cx, cy, sc=1.0, lit=False):
    rr(d, (cx - 62 * sc, cy - 110 * sc, cx + 62 * sc, cy + 110 * sc), 18 * sc, fill=(60, 46, 36), outline=OR, w=3.5 * sc)
    rr(d, (cx - 53 * sc, cy - 98 * sc, cx + 53 * sc, cy + 92 * sc), 12 * sc, fill=(30, 24, 20) if not lit else (60, 44, 24))
    for i in range(3):
        rr(d, (cx - 38 * sc, cy - 70 * sc + i * 40 * sc, cx + 38 * sc, cy - 46 * sc + i * 40 * sc), 6 * sc, fill=PANEL)
    ell(d, cx, cy + 102 * sc, 3 * sc, fill=TAN)

def browser(d, cx, cy, sc=1.0, loaded=1.0, label="plainbytes.com"):
    x0, y0, x1, y1 = cx - 120 * sc, cy - 90 * sc, cx + 120 * sc, cy + 90 * sc
    rr(d, (x0, y0, x1, y1), 16 * sc, fill=(60, 46, 36), outline=OR, w=3.5 * sc)
    rr(d, (x0 + 6 * sc, y0 + 6 * sc, x1 - 6 * sc, y0 + 34 * sc), 10 * sc, fill=PANEL)
    for i, c in enumerate((RED, OR, GREEN)):
        ell(d, x0 + (20 + i * 16) * sc, y0 + 20 * sc, 4.5 * sc, fill=c)
    rr(d, (x0 + 70 * sc, y0 + 11 * sc, x1 - 14 * sc, y0 + 29 * sc), 8 * sc, fill=(30, 24, 20))
    rr(d, (x0 + 10 * sc, y0 + 44 * sc, x1 - 10 * sc, y1 - 10 * sc), 8 * sc, fill=(30, 24, 20))
    for i in range(4):
        wdt = (x1 - x0 - 40 * sc) * (0.9 if i != 3 else 0.55) * clamp(loaded * 4 - i)
        if wdt > 1:
            rr(d, (x0 + 20 * sc, y0 + (58 + i * 24) * sc, x0 + 20 * sc + wdt, y0 + (70 + i * 24) * sc), 4 * sc, fill=OR if i == 0 else TAN)

def server(d, cx, cy, sc=1.0, t=0.0):
    for i in range(3):
        y = cy - 90 * sc + i * 62 * sc
        rr(d, (cx - 75 * sc, y, cx + 75 * sc, y + 52 * sc), 10 * sc, fill=(60, 46, 36), outline=OR, w=3 * sc)
        for k in range(3):
            on = (int(t * 3) + i + k) % 3 == 0
            ell(d, cx - 52 * sc + k * 17 * sc, y + 26 * sc, 5 * sc, fill=GREEN if on else (90, 70, 50))
        ln(d, [(cx + 10 * sc, y + 26 * sc), (cx + 58 * sc, y + 26 * sc)], PANEL, 5 * sc)

def house(d, cx, cy, sc=1.0):
    poly(d, [(cx - 120 * sc, cy - 10 * sc), (cx, cy - 100 * sc), (cx + 120 * sc, cy - 10 * sc)], RED)
    rr(d, (cx - 100 * sc, cy - 10 * sc, cx + 100 * sc, cy + 100 * sc), 6 * sc, fill=SOFT)
    rr(d, (cx - 22 * sc, cy + 28 * sc, cx + 22 * sc, cy + 100 * sc), 6 * sc, fill=OR2)
    for sx in (-1, 1):
        rr(d, (cx + sx * 62 * sc - 18 * sc, cy + 10 * sc, cx + sx * 62 * sc + 18 * sc, cy + 46 * sc), 4 * sc, fill=BLUE)

def router(d, cx, cy, sc=1.0, on=False):
    if on:
        ell(d, cx, cy, 44 * sc, fill=(96, 62, 24))
    ell(d, cx, cy, 34 * sc, fill=OR if on else (96, 70, 46), outline=DARK, w=3)
    ln(d, [(cx - 18 * sc, cy + 6 * sc), (cx + 18 * sc, cy + 6 * sc)], DARK, 5 * sc)
    ln(d, [(cx, cy + 6 * sc), (cx, cy - 22 * sc)], DARK, 5 * sc)
    for r_ in (10, 18):
        ln(d, [(cx - r_ * sc * 0.7, cy - 22 * sc - r_ * sc * 0.4), (cx, cy - 22 * sc - r_ * sc), (cx + r_ * sc * 0.7, cy - 22 * sc - r_ * sc * 0.4)], DARK, 3 * sc, cap=False) if False else None

def packet(d, cx, cy, sc=1.0, lab=True):
    rr(d, (cx - 40 * sc, cy - 28 * sc, cx + 40 * sc, cy + 28 * sc), 6 * sc, fill=SOFT, outline=DARK, w=2.5)
    ln(d, [(cx - 40 * sc, cy - 28 * sc), (cx, cy + 4 * sc), (cx + 40 * sc, cy - 28 * sc)], TAN, 3 * sc, cap=False)

def pos_on(path, p):
    """path: list of points; p 0..1"""
    segs = [math.dist(path[i], path[i + 1]) for i in range(len(path) - 1)]
    tot = sum(segs); dist = clamp(p) * tot
    for i, sg in enumerate(segs):
        if dist <= sg or i == len(segs) - 1:
            q = dist / sg if sg else 0
            return (lerp(path[i][0], path[i + 1][0], q), lerp(path[i][1], path[i + 1][1], q))
        dist -= sg


# ---------- cloud props ----------
def cloud(d, cx, cy, sc=1.0, fill=WHITE):
    ell(d, cx - 40 * sc, cy + 8 * sc, 34 * sc, fill=fill)
    ell(d, cx - 2 * sc, cy - 12 * sc, 46 * sc, fill=fill)
    ell(d, cx + 46 * sc, cy + 6 * sc, 36 * sc, fill=fill)
    rr(d, (cx - 74 * sc, cy + 6 * sc, cx + 80 * sc, cy + 42 * sc), 18 * sc, fill=fill)

def photo(d, cx, cy, sc=1.0):
    rr(d, (cx - 36 * sc, cy - 28 * sc, cx + 36 * sc, cy + 28 * sc), 7 * sc, fill=WHITE)
    rr(d, (cx - 30 * sc, cy - 22 * sc, cx + 30 * sc, cy + 22 * sc), 4 * sc, fill=BLUE)
    ell(d, cx + 14 * sc, cy - 8 * sc, 6 * sc, fill=OR)
    poly(d, [(cx - 30 * sc, cy + 22 * sc), (cx - 10 * sc, cy - 6 * sc), (cx + 6 * sc, cy + 14 * sc), (cx + 14 * sc, cy + 6 * sc), (cx + 30 * sc, cy + 22 * sc)], GREEN)

def datacenter(d, cx, cy, sc=1.0, t=0.0, bad=-1):
    rr(d, (cx - 150 * sc, cy - 100 * sc, cx + 150 * sc, cy + 100 * sc), 16 * sc, fill=(40, 30, 23), outline=OR, w=4 * sc)
    for i in range(3):
        x0 = cx - 124 * sc + i * 86 * sc
        rr(d, (x0, cy - 76 * sc, x0 + 72 * sc, cy + 76 * sc), 8 * sc, fill=PANEL)
        for k in range(5):
            on = (int(t * 3) + i + k) % 3 == 0
            c = RED if i == bad else (GREEN if on else (90, 70, 50))
            ell(d, x0 + 16 * sc, cy - 54 * sc + k * 26 * sc, 5 * sc, fill=c)
            ln(d, [(x0 + 30 * sc, cy - 54 * sc + k * 26 * sc), (x0 + 60 * sc, cy - 54 * sc + k * 26 * sc)], (30, 24, 20), 5 * sc)

def machine(d, cx, cy, sc=1.0, t=0.0, bad=False, has=False):
    rr(d, (cx - 46 * sc, cy - 70 * sc, cx + 46 * sc, cy + 70 * sc), 12 * sc, fill=(60, 46, 36), outline=RED if bad else OR, w=3.5 * sc)
    for k in range(4):
        on = (int(t * 3) + k) % 3 == 0
        ell(d, cx - 26 * sc, cy - 46 * sc + k * 30 * sc, 5 * sc, fill=RED if bad else (GREEN if on else (90, 70, 50)))
        ln(d, [(cx - 10 * sc, cy - 46 * sc + k * 30 * sc), (cx + 30 * sc, cy - 46 * sc + k * 30 * sc)], PANEL, 6 * sc)
    if has and not bad:
        photo(d, cx, cy - 104 * sc, 0.7 * sc)
    if bad:
        ln(d, [(cx - 34 * sc, cy - 34 * sc), (cx + 34 * sc, cy + 34 * sc)], RED, 9 * sc)
        ln(d, [(cx + 34 * sc, cy - 34 * sc), (cx - 34 * sc, cy + 34 * sc)], RED, 9 * sc)

def laptop(d, cx, cy, sc=1.0, show=False):
    rr(d, (cx - 90 * sc, cy - 60 * sc, cx + 90 * sc, cy + 50 * sc), 12 * sc, fill=(60, 46, 36), outline=OR, w=3.5 * sc)
    rr(d, (cx - 80 * sc, cy - 50 * sc, cx + 80 * sc, cy + 40 * sc), 6 * sc, fill=(30, 24, 20))
    rr(d, (cx - 110 * sc, cy + 52 * sc, cx + 110 * sc, cy + 66 * sc), 7 * sc, fill=OR2)
    if show:
        photo(d, cx, cy - 4 * sc, 1.3 * sc)

def bt_symbol(d, cx, cy, s, fill=BLUE):
    pts = [(-0.55, -0.5), (0.55, 0.5), (0.0, 1.0), (0.0, -1.0), (0.55, -0.5), (-0.55, 0.5)]
    ln(d, [(cx + x * s, cy + y * s) for x, y in pts], fill, max(3, s * 0.16), cap=False)


# ---------- scenes (tl = seconds since scene start) ----------
def scene1(img, d, t, tl):
    cs = 1.2
    cyy = 300
    if tl >= 1.7:
        q = eio((tl - 1.7) / 0.6)
        cs = lerp(1.2, 0.6, q)
    cloud(d, 360, cyy, cs)
    if 0.8 < tl < 2.4:
        p = eob((tl - 0.8) / 0.3)
        ln(d, [(360 - 70 * p, cyy - 50 * p), (360 + 70 * p, cyy + 50 * p)], RED, 12)
        ln(d, [(360 + 70 * p, cyy - 50 * p), (360 - 70 * p, cyy + 50 * p)], RED, 12)
    if tl > 1.7:
        p = eob((tl - 1.7) / 0.6)
        datacenter(d, 360, 600, 1.0 * p, t)
        tag(d, 360, 745, "a data center", 30, p=eob((tl - 2.4) / 0.4))
        ln(d, [(360, 350), (360, 440)], OR, 6)
        poly(d, [(344, 432), (376, 432), (360, 456)], OR)


def scene2(img, d, t, tl):
    phone_s(d, 100, 520, 0.95)
    photo(d, 100, 505, 0.9)
    datacenter(d, 520, 520, 0.8, t)
    tag(d, 520, 640, "their hard drives", 24, fill=SOFT, p=eob((tl - 0.6) / 0.4))
    q = (tl * 0.45) % 1.0
    if tl < 5.2:
        x, y = pos_on([(190, 520), (380, 520)], eio(q))
        photo(d, x, y, 0.6)
    ln(d, [(190, 560), (380, 560)], (96, 70, 46), 4, cap=False)
    if tl > 2.2:
        tx(d, 360, 770, "copied over the internet", 32, SOFT, stroke=3)


def scene3(img, d, t, tl):
    p = eob(tl / 0.5)
    house(d, 170, 470, 0.9 * p)
    tx(d, 170, 640, "buy a bigger house", 24, SOFT, stroke=3)
    if tl > 1.2:
        q = eob((tl - 1.2) / 0.4)
        rr(d, (430, 400, 640, 560), 10 * q, fill=(60, 46, 36), outline=OR, w=4)
        for k in range(6):
            ln(d, [(444, 420 + k * 24), (626, 420 + k * 24)], OR2, 4, cap=False)
        tx(d, 535, 640, "rent a storage unit", 24, WHITE, stroke=3)
        tag(d, 535, 360, "the cloud", 28, p=q)
    tx(d, 360, 470, "or", 36, TAN)


MX = [330, 460, 590]
def scene4(img, d, t, tl):
    phone_s(d, 90, 520, 0.8)
    photo(d, 90, 505, 0.75)
    for i, mx in enumerate(MX):
        st = 0.8 + i * 0.9
        arrived = tl > st + 1.1
        bad = (i == 1 and tl > 5.4)
        machine(d, mx, 560, 0.8, t, bad=bad, has=arrived)
        if st < tl < st + 1.1:
            x, y = pos_on([(150, 520), (mx, 470)], eio((tl - st) / 1.1))
            photo(d, x, y, 0.5)
    tag(d, 460, 340, "copies", 26, fill=SOFT, p=eob((tl - 3.6) / 0.4))
    if tl > 5.4:
        tx(d, 460, 700, "one drive fails", 30, RED, stroke=3)
    if tl > 6.2:
        tx(d, 360, 770, "photo still safe", 36, GREEN, stroke=4)


def scene5(img, d, t, tl):
    if tl < 3.7:
        datacenter(d, 540, 460, 0.7, t)
        laptop(d, 150, 470, 0.9, show=tl > 2.0)
        tag(d, 150, 340, "log in", 26, p=eob(tl / 0.4))
        if 0.6 < tl < 2.0:
            x, y = pos_on([(440, 470), (240, 470)], eio((tl - 0.6) / 1.4))
            photo(d, x, y, 0.55)
        ln(d, [(240, 510), (440, 510)], (96, 70, 46), 4, cap=False)
        if tl > 2.0:
            tx(d, 360, 700, "any device, same photo", 32, SOFT, stroke=3)
    else:
        u = tl - 3.7
        datacenter(d, 540, 460, 0.7, t)
        for i, nm in enumerate(("App", "Store", "Game")):
            p = eob((u - 0.2 - i * 0.4) / 0.4)
            y = 360 + i * 100
            rr(d, (60, y - 34 * p, 230, y + 34 * p), 14 * p, fill=SOFT)
            if p > 0.8:
                tx(d, 145, y, nm, 30, DARK, kind='p')
            ln(d, [(230, y), (390, 460)], OR, 4, cap=False)
        cx, cy = 360, 700
        ell(d, cx - 100, cy, 38, fill=PANEL, outline=OR, w=5)
        ang = -math.pi / 2 + u * 2.4
        ln(d, [(cx - 100, cy), (cx - 100 + 24 * math.cos(ang), cy + 24 * math.sin(ang))], WHITE, 5)
        tx(d, cx + 40, cy, "rent by the hour", 32, WHITE, stroke=3, anchor='lm')


def scene6(img, d, t, tl):
    datacenter(d, 360, 470, 0.9, t)
    if tl < 2.3:
        tx(d, 360, 650, "another company's computer", 32, SOFT, stroke=3)
    else:
        p = eob((tl - 2.3) / 0.4)
        bolt(d, 200, 700, 52 * p, OR)
        bolt(d, 520, 700, 52 * p, OR)
        # power meter
        rr(d, (260, 676, 460, 724), 14, fill=PANEL, outline=OR, w=4)
        w_ = 180 * clamp((tl - 2.4) / 1.8)
        rr(d, (270, 686, 270 + w_, 714), 8, fill=RED if w_ > 120 else OR)


def scene7(img, d, t, tl):
    cx, cy, sc = 360, 400, 1.25
    arms = (125, 125) if tl < 1.5 else (14, 14)
    robot(d, cx, cy, sc, t, 'happy', arms=arms)
    if tl < 2.2:
        p = eob((tl - 0.3) / 0.4)
        ell(d, 360, 740, 58 * p, fill=PANEL, outline=BLUE, w=5)
        bt_symbol(d, 360, 740, 36 * p)
    else:
        p = eob((tl - 2.2) / 0.4)
        chip_logo(d, 238, 760, 62 * p)
        tx(d, 290, 760, "PlainBytes", 44 * p, WHITE, anchor='lm', kind='p')


STARTS = [3.99, 10.13, 13.37, 20.67, 28.74, 33.69]
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

