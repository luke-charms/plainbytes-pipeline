#!/usr/bin/env python3
"""PlainBytes Short: How tap to pay works. 720x1280, 30fps. Frames piped to ffmpeg."""
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


# ======================= TAP TO PAY VIDEO =======================
DUR = 37.4
ST = [0, 2.4, 4.4, 6.48, 9.88, 13.23, 18.44, 21.38, 25.59, 30.21, 32.8]
ENDS = [2.12, 4.12, 6.2, 9.6, 12.95, 18.16, 21.1, 25.31, 29.93, 32.52, 35.62]
TXT = ["Tap to pay doesn't send your card number.",
       "Here's what's actually happening.",
       "Think of it like a one-time ticket.",
       "When you tap, the terminal sends out a tiny radio field.",
       "That field powers your card's chip, or wakes up your phone's.",
       "Then your device answers with a stand-in number and a secret code made just for this purchase.",
       "The bank checks the code and approves it in seconds.",
       "If a thief copied that code, it would be useless, because it never works twice.",
       "The catch: it only works within a few centimeters, so you have to hold it close.",
       "Next up: how end-to-end encryption works.",
       "Follow PlainBytes for more tech, explained simply."]
SENT = [(ST[i], ENDS[i], TXT[i]) for i in range(len(TXT))]

def make_caps():
    caps = []
    for a, b, s in SENT[1:]:
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

TITLES = [(0.1, 4.3, "Tap to pay: no card number sent"), (4.4, 6.4, "A one-time ticket"),
          (6.48, 13.1, "A tiny radio field"), (13.23, 21.3, "One-time secret code"),
          (21.38, 25.5, "A copied code is useless"), (25.59, 30.1, "The catch: stay close"),
          (30.21, 32.7, "Next: encryption"), (32.8, 37.4, "Follow for more")]

def warp(tn): return float(tn)
GREEN = (120, 220, 150)

def tag(d, cx, cy, s, size=30, fill=OR, p=1.0):
    if p <= 0: return
    w_ = tw(s, size) + 40
    rr(d, (cx - w_ / 2 * p, cy - 26 * p, cx + w_ / 2 * p, cy + 26 * p), 14 * p, fill=fill)
    if p > 0.6:
        tx(d, cx, cy + 1, s, size * p, DARK, kind='p')

def phone_(d, cx, cy, w=90, h=160, screen=(30, 60, 90)):
    if w < 30 or h < 40: return
    rr(d, (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), 16, fill=PANEL, outline=WHITE, w=4)
    rr(d, (cx - w / 2 + 8, cy - h / 2 + 14, cx + w / 2 - 8, cy + h / 2 - 14), 8, fill=screen)

def terminal(d, cx, cy, s=1.0):
    rr(d, (cx - 70 * s, cy - 100 * s, cx + 70 * s, cy + 100 * s), 16 * s, fill=PANEL, outline=OR, w=4)
    rr(d, (cx - 52 * s, cy - 80 * s, cx + 52 * s, cy - 30 * s), 8 * s, fill=(30, 60, 90))
    tx(d, cx, cy - 55 * s, "$24.50", 24 * s, WHITE, kind='p')
    for i in range(3):
        for j in range(3):
            rr(d, (cx - 44 * s + j * 32 * s, cy - 10 * s + i * 26 * s, cx - 24 * s + j * 32 * s, cy + 6 * s + i * 26 * s), 4 * s, fill=TAN)

def card(d, cx, cy, s=1.0, col=BLUE, chip=True):
    rr(d, (cx - 80 * s, cy - 50 * s, cx + 80 * s, cy + 50 * s), 12 * s, fill=col)
    if chip:
        rr(d, (cx - 60 * s, cy - 22 * s, cx - 30 * s, cy + 6 * s), 5 * s, fill=OR)
    ln(d, [(cx - 60 * s, cy + 28 * s), (cx + 30 * s, cy + 28 * s)], (230, 240, 255), 5 * s)

def waves(d, cx, cy, t, col=OR, n=3, maxr=200, a0=-60, a1=60, speed=0.6):
    for k in range(n):
        f = (t * speed + k / n) % 1.0
        r = 30 + maxr * f
        d.arc([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], a0, a1, fill=col, width=round(6 * S * (1 - f * 0.6)))

def pulses(d, a, b, t, col=OR, n=3, size=9, speed=0.7):
    for k in range(n):
        f = (t * speed + k / n) % 1.0
        ell(d, lerp(a[0], b[0], f), lerp(a[1], b[1], f), size, fill=col)

def ticket(d, cx, cy, s=1.0, col=OR, label="1x"):
    rr(d, (cx - 90 * s, cy - 46 * s, cx + 90 * s, cy + 46 * s), 10 * s, fill=col)
    ell(d, cx - 90 * s, cy, 14 * s, fill=(30, 22, 16)); ell(d, cx + 90 * s, cy, 14 * s, fill=(30, 22, 16))
    tx(d, cx, cy + 1, label, 30 * s, DARK, kind='p')

def scene1(img, d, t, tl):
    pe = eob(tl / 0.5)
    terminal(d, 520, 520, 0.9 * pe)
    phone_(d, 190, 520, 100 * pe, 180 * pe)
    if tl > 0.8:
        waves(d, 250, 520, tl, OR, n=2, maxr=100, a0=-40, a1=40)
    tag(d, 190, 690, "4921 8830 5562", 24, fill=RED, p=eob((tl - 1.2) / 0.4))
    if tl > 1.8:
        p = eob((tl - 1.8) / 0.3)
        tx(d, 190, 690, "", 10)
        ln(d, [(80, 690), (80 + 220 * p, 690)], WHITE, 5)
    if tl > 3.0:
        tx(d, 360, 330, "?", 64 * eob((tl - 3.0) / 0.3), OR, stroke=4)

def scene2(img, d, t, tl):
    ticket(d, 360, 450, 1.3 * eob(tl / 0.45), label="ONE USE")
    if tl > 1.0:
        p = eob((tl - 1.0) / 0.4)
        tag(d, 360, 640, "works once", 30, fill=WHITE, p=p)

def scene3(img, d, t, tl):
    terminal(d, 160, 480, 0.85)
    card(d, 540, 480, 0.8, chip=True) if tl < 5.2 else phone_(d, 540, 480, 90, 160)
    waves(d, 220, 480, tl, OR, n=3, maxr=230, a0=-35, a1=35, speed=0.45)
    if tl > 0.8:
        tag(d, 360, 330, "radio field", 28, p=eob((tl - 0.8) / 0.4))
    if tl > 1.6 and tl < 5.2:
        glow(img, (500, 440, 580, 520), OR, r=22, a=int(170 * eo3((tl - 1.6) / 0.5)), rad=14)
        tag(d, 540, 640, "chip wakes up", 28, fill=GREEN, p=eob((tl - 1.8) / 0.4))
    if tl >= 5.2:
        tag(d, 540, 640, "phone wakes up", 28, fill=GREEN, p=eob((tl - 5.3) / 0.4))

def scene4(img, d, t, tl):
    phone_(d, 160, 520, 100, 180)
    rr(d, (520, 460, 640, 580), 20, fill=PANEL, outline=OR, w=4)
    tx(d, 580, 520, "BANK", 28, OR, kind='p')
    tag(d, 330, 330, "stand-in number", 26, fill=WHITE, p=eob((tl - 0.6) / 0.4))
    tag(d, 330, 400, "secret code", 26, p=eob((tl - 1.8) / 0.4))
    if tl > 0.8:
        pulses(d, (215, 520), (515, 520), tl, col=WHITE, n=3, size=9, speed=0.5)
    if tl > 4.6:
        p = eob((tl - 4.6) / 0.4)
        ell(d, 580, 650, 44 * p, fill=GREEN)
        ln(d, [(560, 650), (576, 668), (604, 632)], DARK, 9 * p) if p > 0.6 else None
        tag(d, 360, 760, "approved in seconds", 28, fill=GREEN, p=eob((tl - 5.6) / 0.4))

def scene5(img, d, t, tl):
    ticket(d, 220, 450, 0.9, label="CODE 7Q2")
    if tl > 1.0:
        k = clamp((tl - 1.0) / 0.9)
        ticket(d, 220 + 330 * k, 450 + 0 * k, 0.9, col=SOFT, label="COPY")
    if tl > 2.1:
        p = eob((tl - 2.1) / 0.35)
        ell(d, 550, 450, 56 * p, fill=RED)
        ln(d, [(528, 428), (572, 472)], WHITE, 9 * p) if p > 0.6 else None
        ln(d, [(572, 428), (528, 472)], WHITE, 9 * p) if p > 0.6 else None
    tag(d, 360, 640, "never works twice", 30, fill=WHITE, p=eob((tl - 2.6) / 0.4))

def scene6(img, d, t, tl):
    terminal(d, 160, 470, 0.8)
    card(d, 520, 470, 0.7, chip=True)
    # distance ruler
    ln(d, [(240, 650), (450, 650)], WHITE, 6)
    ln(d, [(240, 630), (240, 670)], WHITE, 6); ln(d, [(450, 630), (450, 670)], WHITE, 6)
    tag(d, 345, 590, "a few cm", 30, fill=RED, p=eob((tl - 0.5) / 0.4))
    if tl > 1.8:
        cx = lerp(560, 330, eio((tl - 1.8) / 1.2)) if tl < 3.0 else 330
        rr(d, (cx - 56, 466 - 35, cx + 56, 466 + 35), 9, fill=BLUE)
    waves(d, 225, 470, tl, OR, n=2, maxr=110, a0=-30, a1=30, speed=0.5)
    if tl > 3.2:
        tag(d, 360, 790, "hold it close", 30, fill=WHITE, p=eob((tl - 3.2) / 0.4))

def scene7(img, d, t, tl):
    cx, cy, sc = 360, 420, 1.25
    arms = (125, 125) if tl < 1.5 else (14, 14)
    robot(d, cx, cy, sc, t, 'happy', arms=arms)
    if tl < 2.4:
        tag(d, 360, 790, "next: encryption", 36, p=eob((tl - 0.1) / 0.4))
    else:
        p = eob((tl - 2.4) / 0.4)
        chip_logo(d, 238, 760, 62 * p)
        tx(d, 290, 760, "PlainBytes", 44 * p, WHITE, anchor='lm', kind='p')


STARTS = ST[2:9]
BOUNDS = [0, ST[2], ST[3], ST[5], ST[7], ST[8], ST[9], DUR + 1]
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

