#!/usr/bin/env python3
"""PlainBytes Short: What an API key is. 720x1280, 30fps. Frames piped to ffmpeg."""
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


# ======================= API KEY VIDEO =======================
DUR = 32.0
ST = [0, 4.55, 6.03, 9.35, 13.57, 18.03, 23.84, 25.57, 27.71]
ENDS = [4.23, 5.77, 9.12, 13.36, 17.86, 23.58, 25.41, 27.46, 30.41]
TXT = ["Behind many apps, a secret code is doing the talking, so what is an API key?",
       "Think of a hotel key card.",
       "It doesn't say who you are, it just opens the doors you paid for.",
       "An API key is a long secret code that a program shows a service, every time it makes a request.",
       "The service checks the code, then decides what that program may do, and how much.",
       "The catch: anyone who finds the key can use it, and the owner gets the bill.",
       "So never paste keys into public code.",
       "Next up: how Wi-Fi works.",
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

TITLES = [(0.1, 4.4, "What is an API key?"), (4.55, 9.3, "Like a hotel key card"),
          (9.35, 13.5, "A secret code"), (13.57, 17.95, "The service checks it"),
          (18.03, 23.7, "The catch: leaks"), (23.84, 25.5, "Keep it private"),
          (25.57, 27.6, "Next: how Wi-Fi works"), (27.71, 32.0, "Follow for more")]

def warp(tn): return float(tn)
GREEN = (120, 220, 150)

def tag(d, cx, cy, s, size=30, fill=OR, p=1.0):
    if p <= 0: return
    w_ = tw(s, size) + 40
    rr(d, (cx - w_ / 2 * p, cy - 26 * p, cx + w_ / 2 * p, cy + 26 * p), 14 * p, fill=fill)
    if p > 0.6:
        tx(d, cx, cy + 1, s, size * p, DARK, kind='p')

def phone_(d, cx, cy, w=90, h=160):
    rr(d, (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), 16, fill=PANEL, outline=WHITE, w=4)
    rr(d, (cx - w / 2 + 8, cy - h / 2 + 14, cx + w / 2 - 8, cy + h / 2 - 14), 8, fill=(30, 60, 90))

def key_icon(d, cx, cy, s, col=OR, ang=0.0):
    a = math.radians(ang); c, sn = math.cos(a), math.sin(a)
    def P(x, y): return (cx + (x * c - y * sn) * s, cy + (x * sn + y * c) * s)
    bx, by = P(-0.6, 0)
    ell(d, bx, by, 0.34 * s, fill=col)
    ell(d, bx, by, 0.14 * s, fill=DARK)
    ln(d, [P(-0.3, 0), P(0.75, 0)], col, 0.18 * s, cap=False)
    for x in (0.45, 0.7):
        ln(d, [P(x, 0), P(x, 0.28)], col, 0.15 * s, cap=False)

def checkmark(d, cx, cy, s, col=GREEN):
    ln(d, [(cx - s, cy), (cx - s * 0.3, cy + s * 0.7), (cx + s, cy - s * 0.7)], col, 7)

def crossmark(d, cx, cy, s, col=RED):
    ln(d, [(cx - s, cy - s), (cx + s, cy + s)], col, 7)
    ln(d, [(cx - s, cy + s), (cx + s, cy - s)], col, 7)

def server(d, cx, cy, w=170, h=210, t=0.0):
    rr(d, (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), 20, fill=PANEL, outline=WHITE, w=4)
    for i in range(3):
        y = cy - h / 2 + 34 + i * 58
        rr(d, (cx - w / 2 + 18, y - 20, cx + w / 2 - 18, y + 20), 8, fill=(30, 24, 20))
        ell(d, cx + w / 2 - 38, y, 7, fill=GREEN if (int(t * 3) + i) % 3 else OR)

def padlock(d, cx, cy, s, col=OR):
    d.arc([(cx - 0.55 * s) * S, (cy - 1.15 * s) * S, (cx + 0.55 * s) * S, (cy + 0.15 * s) * S], 180, 360, fill=SOFT, width=round(0.2 * s * S))
    ln(d, [(cx - 0.55 * s, cy - 0.5 * s), (cx - 0.55 * s, cy)], SOFT, 0.2 * s, cap=False)
    ln(d, [(cx + 0.55 * s, cy - 0.5 * s), (cx + 0.55 * s, cy)], SOFT, 0.2 * s, cap=False)
    rr(d, (cx - 0.9 * s, cy - 0.1 * s, cx + 0.9 * s, cy + 0.95 * s), 0.18 * s, fill=col)
    ell(d, cx, cy + 0.35 * s, 0.15 * s, fill=DARK)
    poly(d, [(cx - 0.07 * s, cy + 0.4 * s), (cx + 0.07 * s, cy + 0.4 * s), (cx + 0.1 * s, cy + 0.75 * s), (cx - 0.1 * s, cy + 0.75 * s)], DARK)

def scene1(img, d, t, tl):
    key_icon(d, 360, 340 + math.sin(t * 2) * 6, 150 * eob(tl / 0.5), OR, ang=-20 + math.sin(t * 1.5) * 6)
    robot(d, 360, 560, 0.8, t, 'confused')
    if 0.8 < tl < 4.0:
        tx(d, 510, 500, "?", 64 * eob((tl - 0.8) / 0.3), RED, stroke=4)
    if tl > 1.6:
        tag(d, 360, 795, "sk-7F3a-9xQ2", 30, fill=WHITE, p=eob((tl - 1.6) / 0.4))


def scene2(img, d, t, tl):
    # door with reader on the right
    rr(d, (440, 330, 600, 680), 14, fill=PANEL, outline=WHITE, w=4)
    opened = tl > 2.6
    if opened:
        poly(d, [(440, 330), (520, 360), (520, 650), (440, 680)], (30, 24, 20))
    tx(d, 520, 380, "204", 34, SOFT, kind='p') if not opened else None
    ell(d, 575, 520, 9, fill=GREEN if opened else RED)
    rr(d, (400, 470, 428, 560), 8, fill=GREEN if opened else RED)
    # card slides to reader
    p = eio((tl - 0.8) / 1.5)
    cx_ = lerp(190, 392, p) if tl > 0.8 else 190
    cy_ = lerp(480, 515, p)
    k = eob(tl / 0.5)
    rr(d, (cx_ - 100 * k, cy_ - 60 * k, cx_ + 100 * k, cy_ + 60 * k), 14 * k, fill=OR)
    rr(d, (cx_ - 100 * k, cy_ - 36 * k, cx_ + 100 * k, cy_ - 8 * k), 0, fill=DARK)
    if k > 0.9:
        tx(d, cx_ - 40, cy_ + 28, "HOTEL", 20, DARK, kind='p')
    if tl > 3.4:
        tag(d, 360, 760, "only the doors you paid for", 28, fill=GREEN, p=eob((tl - 3.4) / 0.4))


def scene3(img, d, t, tl):
    phone_(d, 150, 520, 110, 200)
    tx(d, 150, 520, "APP", 28, WHITE, kind='p')
    server(d, 570, 520, 170, 210, t)
    tag(d, 360, 330, "API KEY", 34, p=eob(tl / 0.4))
    f = (tl * 0.55) % 1.0
    x = lerp(240, 480, f)
    if tl > 0.6:
        key_icon(d, x, 520, 60, OR)
        for dx in (-1, 0, 1):
            pass
    if tl > 1.6:
        tag(d, 360, 650, "sk-7F3a-9xQ2", 28, fill=WHITE, p=eob((tl - 1.6) / 0.4))
    if tl > 2.8:
        tag(d, 360, 760, "sent with every request", 28, p=eob((tl - 2.8) / 0.4))


def scene4(img, d, t, tl):
    server(d, 360, 360, 150, 190, t)
    rows = [("Maps", True, 560), ("Weather", True, 630), ("Billing", False, 700)]
    for i, (nm, ok, y) in enumerate(rows):
        p = eob((tl - 0.5 - i * 0.7) / 0.4)
        if p <= 0: continue
        rr(d, (130, y - 28, 590, y + 28), 14, fill=PANEL, outline=GREEN if ok else RED, w=3)
        tx(d, 160, y, nm, 30, WHITE, anchor='lm')
        if p > 0.6:
            (checkmark if ok else crossmark)(d, 540, y, 14 if ok else 12)
    if tl > 3.0:
        tag(d, 360, 780, "limit: 1,000 per day", 28, fill=WHITE, p=eob((tl - 3.0) / 0.4))


def scene5(img, d, t, tl):
    rr(d, (90, 270, 630, 430), 18, fill=PANEL, outline=WHITE, w=4)
    for j, c in enumerate((TAN, TAN)):
        rr(d, (120, 296 + j * 0, 120, 296), 0, fill=None)
    tx(d, 120, 320, "const key =", 28, SOFT, anchor='lm', kind='p')
    tx(d, 120, 380, '"sk-7F3a-9xQ2"', 32, RED, anchor='lm', kind='p')
    tag(d, 540, 250, "PUBLIC", 26, fill=RED, p=eob((tl - 0.4) / 0.3))
    # stranger
    if tl > 1.4:
        k = eob((tl - 1.4) / 0.4)
        ell(d, 150, 560, 34 * k, fill=(90, 80, 100))
        rr(d, (105, 600, 195, 690), 30 * k, fill=(90, 80, 100))
        ln(d, [(150, 450), (150, 520)], RED, 4)
        key_icon(d, 150, 470, 40, OR)
    if tl > 2.2:
        server(d, 360, 640, 110, 140, t)
        pulses(d, (205, 640), (300, 640), tl, col=OR, n=3, size=8)
    if tl > 3.4:
        p = eob((tl - 3.4) / 0.4)
        rr(d, (500, 580, 640, 710), 14 * p, fill=WHITE)
        tx(d, 570, 612, "BILL", 28 * p, DARK, kind='p')
        tx(d, 570, 665, "$4,200", 34 * p, RED, kind='p')
        pulses(d, (425, 640), (495, 640), tl, col=RED, n=2, size=8)
    if tl > 4.6:
        tag(d, 360, 790, "the owner pays", 28, fill=RED, p=eob((tl - 4.6) / 0.4))


def scene6(img, d, t, tl):
    padlock(d, 360, 400, 110 * eob(tl / 0.5))
    if tl > 0.5:
        tag(d, 360, 710, "keep keys private", 32, fill=GREEN, p=eob((tl - 0.5) / 0.4))


def scene7(img, d, t, tl):
    cx, cy, sc = 360, 420, 1.25
    arms = (125, 125) if tl < 1.5 else (14, 14)
    robot(d, cx, cy, sc, t, 'happy', arms=arms)
    if tl < 2.14:
        tag(d, 360, 790, "next: Wi-Fi", 36, p=eob((tl - 0.3) / 0.4))
    else:
        p = eob((tl - 2.14) / 0.4)
        chip_logo(d, 238, 760, 62 * p)
        tx(d, 290, 760, "PlainBytes", 44 * p, WHITE, anchor='lm', kind='p')


def pulses(d, a, b, t, col=OR, n=3, size=9, speed=0.7):
    for k in range(n):
        f = (t * speed + k / n) % 1.0
        ell(d, lerp(a[0], b[0], f), lerp(a[1], b[1], f), size, fill=col)


STARTS = [ST[1], ST[3], ST[4], ST[5], ST[6], ST[7]]
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

