#!/usr/bin/env python3
"""PlainBytes Short: What a RAM works. 720x1280, 30fps. Frames piped to ffmpeg."""
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



# ======================= RAM VIDEO =======================
DUR = 41.6
ST = [0, 4.18, 5.62, 9.36, 12.73, 18.56, 22.71, 29.54, 32.74, 35.14, 37.36]
TXT = ["Your computer has a memory that wipes itself every time you shut it down.",
       "It's called RAM.",
       "Think of RAM as your desk, and your storage as a filing cabinet.",
       "The cabinet holds everything, but it's slow to reach into.",
       "So the computer pulls what you're using onto the desk, where the processor can grab it almost instantly.",
       "A bigger desk means more things open at once, without constant shuffling.",
       "Inside, RAM holds tiny electric charges that leak away, so it has to refresh them over and over, every second.",
       "The catch: cut the power, and the desk wipes clean.",
       "That's why unsaved work vanishes.",
       "Next up: how QR codes work.",
       "Follow PlainBytes for more tech, explained simply."]
ENDS = [3.75, 5.2, 8.95, 12.3, 18.2, 22.55, 29.2, 32.4, 34.8, 36.95, 40.15]
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

TITLES = [(0.1, 4.15, "Your computer's memory wipes itself"), (4.2, 5.6, "It's called RAM"),
          (5.65, 9.3, "RAM = desk, storage = cabinet"), (9.4, 12.7, "The cabinet is slow to reach"),
          (12.8, 18.5, "Pull it onto the desk"), (18.6, 22.6, "Bigger desk, more open at once"),
          (22.75, 29.5, "Tiny charges that leak"), (29.6, 32.7, "Cut the power..."),
          (32.8, 35.1, "Unsaved work vanishes"), (35.2, 37.3, "Next: how QR codes work"),
          (37.4, 41.6, "Follow for more")]

def warp(tn): return float(tn)
GREEN = (120, 220, 150)
DOC = [(255, 200, 120), (120, 200, 255), (150, 230, 170), (255, 130, 110), (230, 170, 255)]

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

def bolt(d, cx, cy, s, fill):
    pts = [(0.15, -1), (-0.55, 0.1), (-0.05, 0.1), (-0.2, 1), (0.6, -0.2), (0.05, -0.2)]
    poly(d, [(cx + x * s, cy + y * s) for x, y in pts], fill)

def doc(d, cx, cy, sc, col=(255, 200, 120)):
    rr(d, (cx - 16 * sc, cy - 21 * sc, cx + 16 * sc, cy + 21 * sc), 4 * sc, fill=col)
    for k in range(3):
        ln(d, [(cx - 9 * sc, cy - 9 * sc + k * 9 * sc), (cx + 9 * sc, cy - 9 * sc + k * 9 * sc)], DARK, 2.2 * sc, cap=False)

def desk(d, cx, cy, w):
    rr(d, (cx - w / 2, cy, cx + w / 2, cy + 22), 8, fill=(190, 130, 70))
    for sx in (-1, 1):
        rr(d, (cx + sx * (w / 2 - 22) - 8, cy + 22, cx + sx * (w / 2 - 22) + 8, cy + 110), 4, fill=(150, 100, 56))

def cabinet(d, cx, cy, sc, open_p=0.0):
    rr(d, (cx - 70 * sc, cy - 100 * sc, cx + 70 * sc, cy + 100 * sc), 12 * sc, fill=(120, 130, 150), outline=(80, 90, 110), w=3)
    for k in range(3):
        y0 = cy - 92 * sc + k * 64 * sc
        ox = 26 * sc * open_p if k == 1 else 0
        rr(d, (cx - 60 * sc, y0 + ox * 0.0, cx + 60 * sc, y0 + 56 * sc + ox), 8 * sc, fill=(150, 160, 180) if k != 1 else (170, 180, 200))
        rr(d, (cx - 18 * sc, y0 + 22 * sc + ox / 2, cx + 18 * sc, y0 + 32 * sc + ox / 2), 4 * sc, fill=DARK)

def monitor(d, cx, cy, w, h, on=True):
    rr(d, (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), 14, fill=PANEL, outline=OR, w=4)
    rr(d, (cx - w / 2 + 12, cy - h / 2 + 12, cx + w / 2 - 12, cy + h / 2 - 12), 8, fill=(70, 100, 130) if on else (12, 10, 8))
    rr(d, (cx - 30, cy + h / 2, cx + 30, cy + h / 2 + 20), 4, fill=OR2)

def qr(d, cx, cy, s):
    n = 9; cell = s / n
    pat = [0b101101011, 0b010110100, 0b110010111, 0b001101001, 0b101011010, 0b011100110, 0b110101011, 0b100011101, 0b010110011]
    x0, y0 = cx - s / 2, cy - s / 2
    rr(d, (x0 - 10, y0 - 10, x0 + s + 10, y0 + s + 10), 10, fill=WHITE)
    for r in range(n):
        for c in range(n):
            corner = (r < 3 and c < 3) or (r < 3 and c > 5) or (r > 5 and c < 3)
            if corner:
                edge = r in (0, 2, 6, 8) or c in (0, 2, 6, 8)
                on = edge or (r in (1, 7) and c in (1, 7)) or (r == 1 and c == 7) or (r == 7 and c == 1) or (r == 1 and c == 1)
                on = True if (r % 8 in (0, 2) or c % 8 in (0, 2) or (r % 6 == 1 and c % 6 == 1)) else on
            else:
                on = (pat[r] >> c) & 1
            if on:
                rr(d, (x0 + c * cell, y0 + r * cell, x0 + (c + 1) * cell, y0 + (r + 1) * cell), 1, fill=DARK)


# ---------- scenes ----------
def scene1(img, d, t, tl):
    robot(d, 360, 400, 0.95, t, 'confused' if tl < 2.6 else 'oops')
    if 0.8 < tl < 2.4:
        tx(d, 360, 250, "?", 64 * eob((tl - 0.8) / 0.3), RED, stroke=4)
    monitor(d, 360, 690, 280, 150, on=tl < 2.5)
    if tl < 2.5:
        for k in range(3):
            rr(d, (265, 650 + k * 28, 265 + 170 - k * 40, 664 + k * 28), 6, fill=(190, 225, 255))
    else:
        tx(d, 360, 690, "wiped!", 34, RED, stroke=3)


def scene2(img, d, t, tl):
    if tl < 1.44:
        p = eob(tl / 0.4)
        gpu_chip(d, 360, 520, 170 * p, "RAM", glow_on=True)
        return
    q = tl - 1.44
    desk(d, 190, 560, 280)
    for i in range(3):
        doc(d, 120 + i * 70, 536, 0.9 * eob((q - 0.5 - i * 0.2) / 0.3), DOC[i])
    cabinet(d, 540, 560, 1.15)
    tag(d, 190, 400, "RAM", 32, p=eob((q - 0.1) / 0.4))
    tag(d, 540, 400, "Storage", 32, fill=(150, 170, 200), p=eob((q - 1.6) / 0.4))
    tx(d, 190, 730, "desk", 28, SOFT, stroke=3)
    tx(d, 540, 730, "filing cabinet", 28, SOFT, stroke=3)


def scene3(img, d, t, tl):
    cabinet(d, 360, 540, 1.7, open_p=eio(tl / 2.2))
    tag(d, 360, 300, "holds everything", 30, fill=(150, 170, 200), p=eob(tl / 0.4))
    if tl > 1.0:
        cx, cy = 580, 360
        ell(d, cx, cy, 44, fill=WHITE, outline=OR2, w=5)
        a = tl * 1.2
        ln(d, [(cx, cy), (cx + math.sin(a) * 30, cy - math.cos(a) * 30)], DARK, 5)
        ln(d, [(cx, cy), (cx + math.sin(a / 12) * 20, cy - math.cos(a / 12) * 20)], DARK, 5)
        tx(d, 580, 430, "slow", 28, RED, stroke=3)


def scene4(img, d, t, tl):
    cabinet(d, 110, 620, 0.9)
    desk(d, 420, 600, 360)
    gpu_chip(d, 560, 400, 110, "CPU")
    for i in range(3):
        st = 0.5 + i * 1.0
        p = eio((tl - st) / 0.9)
        if p <= 0:
            continue
        x = lerp(120, 330 + i * 80, p); y = lerp(620, 576, p) - math.sin(p * math.pi) * 90
        doc(d, x, y, 0.95, DOC[i])
        if tl > 3.8:
            pass
    if tl > 3.9:
        q = eio((tl - 3.9) / 0.35)
        x = lerp(410, 530, q); y = lerp(576, 440, q)
        doc(d, x, y, 0.8, DOC[1])
        tag(d, 360, 280, "almost instant!", 30, fill=GREEN, p=eob((tl - 4.2) / 0.3))


def scene5(img, d, t, tl):
    tx(d, 360, 270, "small desk", 28, SOFT, stroke=3)
    desk(d, 360, 380, 220)
    for i in range(3):
        doc(d, 300 + i * 60, 356, 0.9 * eob((tl - 0.3 - i * 0.2) / 0.3), DOC[i])
    tx(d, 360, 560, "big desk", 28, SOFT, stroke=3)
    desk(d, 360, 640, 560)
    for i in range(8):
        doc(d, 130 + i * 65, 616, 0.9 * eob((tl - 1.3 - i * 0.2) / 0.3), DOC[i % 5])


def scene6(img, d, t, tl):
    cols, rows = 4, 3
    for r in range(rows):
        for c in range(cols):
            i = r * cols + c
            cx, cy = 360 + (c - 1.5) * 128, 360 + r * 130
            ph = (i * 0.37) % 1.0
            if tl < 3.4:
                lvl = clamp(1 - (tl * 0.28 + ph * 0.1))
            else:
                lvl = 1 - 0.7 * ((tl * 0.55 + ph) % 1.0)
            rr(d, (cx - 42, cy - 46, cx + 42, cy + 46), 10, fill=PANEL, outline=OR2, w=3)
            col = GREEN if lvl > 0.55 else (OR if lvl > 0.3 else RED)
            h = 74 * lvl
            rr(d, (cx - 32, cy + 38 - h, cx + 32, cy + 38), 6, fill=col)
    if tl < 3.4:
        tx(d, 360, 790, "charges slowly leak away", 30, RED, stroke=3)
    else:
        tag(d, 360, 790, "refreshed again and again", 28, fill=GREEN, p=eob((tl - 3.4) / 0.4))


def scene7(img, d, t, tl):
    desk(d, 360, 560, 520)
    off = tl > 1.6
    for i in range(6):
        gone = clamp((tl - 1.9 - i * 0.15) / 0.4) if off else 0
        if gone < 1:
            doc(d, 160 + i * 80, 536, 0.95 * (1 - gone), DOC[i % 5])
    if not off:
        bolt(d, 360, 380, 60, OR)
    else:
        bolt(d, 360, 380, 60, (110, 90, 70))
        ln(d, [(300, 320), (420, 440)], RED, 12); ln(d, [(420, 320), (300, 440)], RED, 12)
    if tl > 3.4:
        tag(d, 360, 730, "unsaved work: gone", 30, fill=RED, p=eob((tl - 3.4) / 0.4))


def scene8(img, d, t, tl):
    cx, cy, sc = 360, 400, 1.25
    arms = (125, 125) if tl < 1.5 else (14, 14)
    robot(d, cx, cy, sc, t, 'happy', arms=arms)
    if tl < 1.8:
        qr(d, 360 + math.sin(t * 2) * 10, 745, 130 * eob((tl - 0.1) / 0.4))
    else:
        p = eob((tl - 1.8) / 0.4)
        chip_logo(d, 238, 760, 62 * p)
        tx(d, 290, 760, "PlainBytes", 44 * p, WHITE, anchor='lm', kind='p')


STARTS = [4.18, 5.62, 9.36, 12.73, 18.56, 22.71, 29.54, 35.14]
STARTS = [4.18, 9.36, 12.73, 18.56, 22.71, 29.54, 35.14]
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

