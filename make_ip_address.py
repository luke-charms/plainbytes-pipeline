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


# ======================= IP ADDRESS VIDEO (new scenes) =======================
DUR = 34.1
SENT = [(0.30, 4.10, "Right now, your phone has an address, and so does every website you visit."),
        (4.58, 8.48, "It's called an IP address, and it works just like the street address of your house."),
        (8.91, 13.90, "When you open a site, your device sends a small packet labeled with your address and the destination."),
        (14.35, 19.47, "Routers along the way read that label and pass the packet forward, hop by hop, until it arrives."),
        (19.90, 24.49, "Then the website replies to your address, and the page appears in about a tenth of a second."),
        (24.95, 29.43, "The catch: websites only see one shared address for your whole home, and it can change."),
        (29.88, 32.80, "Follow PlainBytes for more tech, explained simply.")]

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

TITLES = [(0.3, 4.4, "Everything online has an address"), (4.6, 8.7, "IP address = street address"),
          (8.9, 14.2, "Packets carry two addresses"), (14.4, 19.7, "Routers pass it along"),
          (19.9, 24.8, "Reply in ~0.1 seconds"), (25.0, 29.7, "One shared address. It changes."),
          (29.9, 34.1, "Follow for more")]

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


# ---------- scenes (tl = seconds since scene start) ----------
def scene1(img, d, t, tl):
    pp = eob(tl / 0.6)
    phone_s(d, 160, 480, 1.35 * pp)
    browser(d, 540, 480, 1.0 * pp)
    tag(d, 160, 300, IP_ME, 28, p=eob((tl - 0.8) / 0.4))
    tag(d, 540, 335, IP_SITE, 28, p=eob((tl - 1.3) / 0.4))
    # dashed link
    if tl > 1.9:
        n = int(10 * eo3((tl - 1.9) / 0.8))
        for i in range(n):
            x = 255 + i * 22
            ln(d, [(x, 480), (x + 11, 480)], SOFT, 4, cap=False)
    robot(d, 360, 720, 0.55, t, 'normal', arms=(20, 20))


def scene2(img, d, t, tl):
    p = eob(tl / 0.6)
    house(d, 190, 470, 1.15 * p)
    tag(d, 190, 320, "12 Oak Street", 28, fill=SOFT, p=eob((tl - 0.4) / 0.4))
    if tl > 1.4:
        q = eob((tl - 1.4) / 0.4)
        tx(d, 360, 470, "=", 90 * q, WHITE, stroke=4)
        phone_s(d, 540, 470, 1.15 * q)
        tag(d, 540, 320, IP_ME, 28, p=eob((tl - 1.9) / 0.4))
    if tl > 2.6:
        tx(d, 360, 680, "Where to send things", 36, SOFT, stroke=4)
        tx(d, 360, 730, "so they find you", 36, SOFT, stroke=4)


PH = (110, 520); SV = (610, 520)
def scene3(img, d, t, tl):
    phone_s(d, PH[0], PH[1], 1.05)
    server(d, SV[0], SV[1], 1.05, t)
    tag(d, PH[0], 355, IP_ME, 24)
    tag(d, SV[0], 355, IP_SITE, 24)
    if tl < 2.4:
        p = eob(tl / 0.5)
        cx, cy = 360, 520
        rr(d, (cx - 150 * p, cy - 95 * p, cx + 150 * p, cy + 95 * p), 18 * p, fill=SOFT, outline=DARK, w=3)
        if p > 0.8:
            tx(d, cx - 130, cy - 55, "FROM", 22, TAN, anchor='lm')
            tx(d, cx + 130, cy - 55, IP_ME, 28, DARK, anchor='rm', kind='p')
            tx(d, cx - 130, cy + 5, "TO", 22, TAN, anchor='lm')
            tx(d, cx + 130, cy + 5, IP_SITE, 28, DARK, anchor='rm', kind='p')
            ln(d, [(cx - 130, cy + 38), (cx + 130, cy + 38)], TAN, 3, cap=False)
            tx(d, cx, cy + 66, "data", 24, TAN)
    else:
        q = eio((tl - 2.4) / 2.6)
        x, y = pos_on([(PH[0] + 80, 520), (SV[0] - 100, 520)], q)
        packet(d, x, y - math.sin(q * math.pi) * 20, 1.2)


NODES = [(95, 700), (250, 560), (400, 700), (540, 560)]
def scene4(img, d, t, tl):
    phone_s(d, 70, 430, 0.7)
    server(d, 650, 430, 0.7, t)
    path = [(70, 520)] + NODES + [(650, 520)]
    q = eio(tl / 4.8)
    for i in range(len(path) - 1):
        ln(d, [path[i], path[i + 1]], (96, 70, 46), 4, cap=False)
    pk = pos_on(path, q)
    hops = 0
    for i, n_ in enumerate(NODES):
        reached = q * (len(path) - 1) >= i + 1 - 0.1
        near = math.dist(pk, n_) < 60
        router(d, n_[0], n_[1], 1.0, on=near)
        if reached: hops = i + 1
    packet(d, pk[0], pk[1] - 8, 0.9)
    tx(d, 360, 330, "hop %d" % hops if hops else "start", 54, OR, stroke=4)
    tx(d, 360, 800, "each router: read label, pass it on", 28, SOFT, stroke=3)


def scene5(img, d, t, tl):
    phone_s(d, 150, 560, 0.95)
    server(d, 580, 360, 0.8, t)
    # reply packet going back
    q = eio(tl / 1.6)
    if q < 1:
        x, y = pos_on([(540, 400), (190, 500)], q)
        packet(d, x, y, 0.9)
    loaded = clamp((tl - 1.4) / 1.2)
    browser(d, 150 + 0 * loaded, 400 if False else 340, 0.0) if False else None
    if tl > 1.4:
        p = eob((tl - 1.4) / 0.4)
        browser(d, 200, 300, 0.9 * p, loaded=loaded)
    # stopwatch
    cx, cy = 520, 640
    ell(d, cx, cy, 92, fill=PANEL, outline=OR, w=6)
    ln(d, [(cx, cy - 92), (cx, cy - 112)], OR, 8)
    ln(d, [(cx - 14, cy - 114), (cx + 14, cy - 114)], OR, 8)
    ang = -math.pi / 2 + 2 * math.pi * clamp(tl / 4.0) * 0.1 * 10 * 0.1 * 10 if False else -math.pi / 2 + 2 * math.pi * clamp(tl / 4.5) * 0.1
    ln(d, [(cx, cy), (cx + 64 * math.cos(ang), cy + 64 * math.sin(ang))], WHITE, 7)
    ell(d, cx, cy, 8, fill=OR)
    tx(d, cx, cy + 50, "0.1 s", 30, SOFT, kind='p')
    tx(d, 190, 760, "page loaded", 36, GREEN if loaded >= 1 else SOFT, stroke=3)


def scene6(img, d, t, tl):
    # home with 3 devices -> one router -> one shared IP
    rr(d, (30, 260, 690, 600), 30, fill=(40, 30, 23), outline=TAN, w=3)
    tx(d, 70, 290, "your home", 26, SOFT, anchor='lm')
    phone_s(d, 120, 440, 0.55)
    # laptop
    rr(d, (200, 380, 320, 450), 8, fill=(60, 46, 36), outline=OR, w=3)
    rr(d, (185, 452, 335, 466), 6, fill=OR2)
    # tv
    rr(d, (370, 385, 470, 445), 8, fill=(60, 46, 36), outline=OR, w=3)
    ln(d, [(420, 447), (420, 468)], OR2, 5)
    router(d, 590, 450, 1.1, on=True)
    for (x, y) in ((120, 440), (260, 415), (420, 415)):
        ln(d, [(x + 35, y - 10), (555, 440)], (150, 112, 78), 3, cap=False)
    # outgoing line to world
    ln(d, [(590, 495), (590, 640)], OR, 5)
    ip = IP_ME if tl < 3.4 else "203.0.113.42"
    flip = 3.4 <= tl < 3.8
    tag(d, 590, 690, ip, 30, fill=RED if tl >= 3.4 else OR)
    if tl > 1.0:
        tx(d, 330, 690, "all share this one", 30, SOFT, anchor='rm', stroke=3)
    if tl >= 3.4:
        p = eob((tl - 3.4) / 0.4)
        tx(d, 360, 770, "…and it can change", 40 * p, WHITE, stroke=4)


def scene7(img, d, t, tl):
    cx, cy, sc = 360, 400, 1.25
    arms = (125, 125) if tl < 1.5 else (14, 14)
    robot(d, cx, cy, sc, t, 'happy', arms=arms)
    if tl > 1.8:
        p = eob((tl - 1.8) / 0.4)
        chip_logo(d, 238, 760, 62 * p)
        tx(d, 290, 760, "PlainBytes", 44 * p, WHITE, anchor='lm', kind='p')


STARTS = [4.5, 8.8, 14.3, 19.8, 24.9, 29.8]
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

