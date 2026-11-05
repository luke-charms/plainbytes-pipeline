#!/usr/bin/env python3
"""PlainBytes Short: How AI text watermarks work. 720x1280, 30fps. Frames piped to ffmpeg."""
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


# ======================= HTTPS VIDEO =======================
DUR = 35.8
SENT = [(0.25, 3.80, "Your data hops across many machines online, and none of them can read it."),
        (3.98, 8.55, "Think of mailing a letter in a locked box that only you and the website can open."),
        (8.72, 13.00, "First, the website shows an ID, called a certificate, so your browser knows it's the real one."),
        (13.15, 18.40, "Then your browser and the site use clever math to agree on a secret key, without ever sending it."),
        (18.55, 22.70, "From then on, everything is scrambled with that key, so spies only see gibberish."),
        (22.88, 29.10, "The catch: HTTPS hides what you send, not always which site you visit, and a fake site can have a padlock too."),
        (29.35, 31.50, "Next up: what a VPN really does."),
        (31.63, 34.20, "Follow PlainBytes for more tech, explained simply.")]

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

TITLES = [(0.25, 3.9, "Strangers can't read your data"), (3.98, 8.6, "A locked box"),
          (8.72, 13.05, "Step 1: show an ID"), (13.15, 18.5, "Step 2: agree on a secret key"),
          (18.55, 22.8, "Step 3: scramble everything"), (22.88, 29.3, "The catch"),
          (29.35, 35.8, "Follow for more")]

NEW_A = [0, DUR]; OLD_A = [0, DUR]
def warp(tn): return float(tn)

GREEN = (120, 220, 150)

def tag(d, cx, cy, s, size=30, fill=OR, p=1.0, col=DARK):
    if p <= 0: return
    w_ = tw(s, size) + 40
    rr(d, (cx - w_ / 2 * p, cy - 26 * p, cx + w_ / 2 * p, cy + 26 * p), 14 * p, fill=fill)
    if p > 0.6:
        tx(d, cx, cy + 1, s, size * p, col, kind='p')

def check(d, cx, cy, s, col=GREEN):
    ln(d, [(cx - 0.5 * s, cy), (cx - 0.15 * s, cy + 0.4 * s), (cx + 0.55 * s, cy - 0.45 * s)], col, max(3, 0.22 * s))

def padlock(d, cx, cy, s=1.0, col=OR, open_=False):
    r = 22 * s
    if open_:
        ln(d, [(cx - r, cy - 10 * s), (cx - r, cy - 34 * s), (cx, cy - 50 * s), (cx + r, cy - 34 * s)], SOFT, 8 * s, cap=False)
    else:
        ln(d, [(cx - r, cy - 8 * s), (cx - r, cy - 30 * s), (cx - r * 0.5, cy - 46 * s), (cx + r * 0.5, cy - 46 * s), (cx + r, cy - 30 * s), (cx + r, cy - 8 * s)], SOFT, 8 * s, cap=False)
    rr(d, (cx - 34 * s, cy - 8 * s, cx + 34 * s, cy + 42 * s), 10 * s, fill=col)
    ell(d, cx, cy + 15 * s, 6 * s, fill=DARK)
    ln(d, [(cx, cy + 17 * s), (cx, cy + 30 * s)], DARK, 5 * s, cap=False)

def key(d, cx, cy, s=1.0, col=OR):
    ell(d, cx - 22 * s, cy, 20 * s, fill=col)
    ell(d, cx - 22 * s, cy, 8 * s, fill=DARK)
    ln(d, [(cx - 2 * s, cy), (cx + 48 * s, cy)], col, 10 * s, cap=False)
    ln(d, [(cx + 30 * s, cy), (cx + 30 * s, cy + 16 * s)], col, 9 * s, cap=False)
    ln(d, [(cx + 46 * s, cy), (cx + 46 * s, cy + 12 * s)], col, 9 * s, cap=False)

def phone_s(d, cx, cy, sc=1.0):
    rr(d, (cx - 62 * sc, cy - 110 * sc, cx + 62 * sc, cy + 110 * sc), 18 * sc, fill=(60, 46, 36), outline=OR, w=3.5 * sc)
    rr(d, (cx - 53 * sc, cy - 98 * sc, cx + 53 * sc, cy + 92 * sc), 12 * sc, fill=(30, 24, 20))
    for i in range(3):
        rr(d, (cx - 38 * sc, cy - 70 * sc + i * 40 * sc, cx + 38 * sc, cy - 46 * sc + i * 40 * sc), 6 * sc, fill=PANEL)

def server(d, cx, cy, sc=1.0, t=0.0):
    for i in range(3):
        y = cy - 90 * sc + i * 62 * sc
        rr(d, (cx - 75 * sc, y, cx + 75 * sc, y + 52 * sc), 10 * sc, fill=(60, 46, 36), outline=OR, w=3 * sc)
        for k in range(3):
            on = (int(t * 3) + i + k) % 3 == 0
            ell(d, cx - 52 * sc + k * 17 * sc, y + 26 * sc, 5 * sc, fill=GREEN if on else (90, 70, 50))
        ln(d, [(cx + 10 * sc, y + 26 * sc), (cx + 58 * sc, y + 26 * sc)], PANEL, 5 * sc)

def node(d, cx, cy, on=False):
    ell(d, cx, cy, 24, fill=OR if on else (96, 70, 46), outline=DARK, w=3)

def pos_on(path, p):
    segs = [math.dist(path[i], path[i + 1]) for i in range(len(path) - 1)]
    tot = sum(segs); dist = clamp(p) * tot
    for i, sg in enumerate(segs):
        if dist <= sg or i == len(segs) - 1:
            q = dist / sg if sg else 0
            return (lerp(path[i][0], path[i + 1][0], q), lerp(path[i][1], path[i + 1][1], q))
        dist -= sg

def msg(d, cx, cy, text, fill=SOFT, col=DARK, size=24, sc=1.0):
    w_ = tw(text, size) + 36
    rr(d, (cx - w_ / 2 * sc, cy - 26 * sc, cx + w_ / 2 * sc, cy + 26 * sc), 12 * sc, fill=fill)
    if sc > 0.7: tx(d, cx, cy + 1, text, size * sc, col, kind='p')


# ---------- scenes (tl = seconds since scene start) ----------
def scene1(img, d, t, tl):
    path = [(80, 520), (210, 600), (360, 500), (510, 600), (640, 520)]
    p0 = eob(tl / 0.6)
    phone_s(d, 80, 420, 0.55 * p0)
    server(d, 640, 420, 0.5 * p0, t)
    for i in range(len(path) - 1):
        ln(d, [path[i], path[i + 1]], (96, 70, 46), 4, cap=False)
    q = eio((tl - 0.4) / 3.0)
    pk = pos_on(path, q)
    for n_ in path[1:-1]:
        node(d, n_[0], n_[1], on=math.dist(pk, n_) < 50)
    if tl > 0.4:
        msg(d, pk[0], pk[1] - 50, "x9#k2", fill=OR, size=22)
        padlock(d, pk[0], pk[1] - 98, 0.5)
    if tl > 2.0:
        tag(d, 360, 720, "strangers can't read it", 30, fill=SOFT, p=eob((tl - 2.0) / 0.4))
    robot(d, 360, 810, 0.0001, t) if False else None


def scene2(img, d, t, tl):
    p = eob(tl / 0.6)
    rr(d, (210, 360, 510, 540), 20 * p, fill=(150, 100, 56), outline=DARK, w=3)
    rr(d, (210, 360, 510, 400), 20 * p, fill=(176, 120, 66))
    padlock(d, 360, 440 + 0 * p, 1.4 * p, open_=(tl < 1.6))
    if tl > 2.2:
        q = eob((tl - 2.2) / 0.5)
        phone_s(d, 120, 640, 0.42 * q)
        key(d, 120, 740, 0.9 * q)
    if tl > 2.8:
        q = eob((tl - 2.8) / 0.5)
        server(d, 600, 640, 0.42 * q, t)
        key(d, 580, 740, 0.9 * q)
    if tl > 3.6:
        tx(d, 360, 800 if False else 600, "only 2 keys exist", 32, SOFT, stroke=3)


def scene3(img, d, t, tl):
    phone_s(d, 110, 520, 0.8)
    server(d, 590, 520, 0.8, t)
    q = eob((tl - 0.5) / 0.6)
    if q > 0:
        w_, h_ = 320 * q, 170 * q
        rr(d, (360 - w_ / 2, 330 - h_ / 2, 360 + w_ / 2, 330 + h_ / 2), 16, fill=SOFT, outline=DARK, w=3)
        if q > 0.9:
            ell(d, 240, 300, 24, fill=OR)
            tx(d, 240, 301, "ID", 22, DARK, kind='p')
            tx(d, 400, 300, "certificate", 30, DARK, kind='p')
            ln(d, [(220, 350), (500, 350)], TAN, 4, cap=False)
            ln(d, [(220, 375), (420, 375)], TAN, 4, cap=False)
    if tl > 2.2:
        p = eob((tl - 2.2) / 0.4)
        tag(d, 360, 690, "real site", 30, fill=GREEN, p=p)
        check(d, 470, 690, 30 * p)
    if tl > 1.4:
        tx(d, 130, 680, "browser checks", 26, SOFT, anchor='mm', stroke=3)


def scene4(img, d, t, tl):
    phone_s(d, 90, 500, 0.7)
    server(d, 630, 500, 0.7, t)
    # each side has a private colour, swaps mixed colours, ends with the same shared key
    ell(d, 90, 350, 18, fill=OR); tx(d, 90, 310, "secret", 20, SOFT)
    ell(d, 630, 350, 18, fill=BLUE); tx(d, 630, 310, "secret", 20, SOFT)
    if tl > 0.8:
        q = eio((tl - 0.8) / 1.8)
        ell(d, lerp(120, 330, q), 560, 14, fill=(255, 140, 120))
        ell(d, lerp(600, 390, q), 600, 14, fill=(140, 170, 255))
    if tl > 3.0:
        p = eob((tl - 3.0) / 0.5)
        key(d, 360, 700, 1.4 * p)
        tag(d, 360, 790, "same secret key", 30, fill=OR, p=eob((tl - 3.3) / 0.4))
    if tl > 1.0 and tl < 3.0:
        tx(d, 360, 450, "mixed values swap", 28, SOFT, stroke=3)
        tx(d, 360, 490, "the key never travels", 28, SOFT, stroke=3)


def scene5(img, d, t, tl):
    phone_s(d, 90, 480, 0.6)
    server(d, 630, 480, 0.6, t)
    ln(d, [(150, 540), (570, 540)], (96, 70, 46), 4, cap=False)
    q = eio(tl / 3.4)
    x = lerp(160, 560, q)
    plain = x < 260
    msg(d, x, 540 - 60, "hello" if plain else "x9#k2", fill=SOFT if plain else OR, size=24)
    # padlock gate
    padlock(d, 260, 470, 0.7, open_=False)
    tx(d, 260, 570, "scramble", 22, SOFT)
    # spy
    if tl > 1.2:
        p = eob((tl - 1.2) / 0.4)
        ell(d, 360, 700, 30 * p, fill=PANEL, outline=WHITE, w=3)
        ell(d, 360, 700, 10 * p, fill=WHITE)
        if p > 0.9:
            tx(d, 360, 760, "spy sees: x9#k2", 28, RED, stroke=3)


def scene6(img, d, t, tl):
    rows = [("Hides: what you send", "Not always: which site", GREEN), ("Fake sites can have padlocks too", "check the address", RED)]
    for i, (a, b, c) in enumerate(rows):
        p = eob((tl - 0.4 - 2.4 * i) / 0.4)
        if p < 0.8: continue
        y = 290 + i * 200
        rr(d, (40, y, 680, y + 160), 24, fill=PANEL, outline=c, w=3)
        tx(d, 360, y + 55, a, 30, WHITE, kind='p')
        tx(d, 360, y + 110, b, 28, c)
    if tl > 5.0:
        padlock(d, 360, 720, 0.9)


def scene7(img, d, t, tl):
    cx, cy, sc = 360, 340, 1.1
    arms = (125, 125) if tl < 1.5 else (14, 14)
    robot(d, cx, cy, sc, t, 'happy', arms=arms)
    if tl > 0.3:
        p = eob((tl - 0.3) / 0.4)
        tx(d, 360, 640, "Next: what a VPN does", 38 * p, OR, stroke=4)
    if tl > 2.6:
        p = eob((tl - 2.6) / 0.4)
        chip_logo(d, 238, 760, 62 * p)
        tx(d, 290, 760, "PlainBytes", 44 * p, WHITE, anchor='lm', kind='p')


STARTS = [3.98, 8.72, 13.15, 18.55, 22.88, 29.35]
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

