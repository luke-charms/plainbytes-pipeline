#!/usr/bin/env python3
"""PlainBytes Short: How deepfakes work. 720x1280, 30fps. Frames piped to ffmpeg."""
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


# ======================= DEEPFAKE VIDEO =======================
DUR = 38.3
ST = [0, 3.46, 7.06, 10.33, 13.69, 16.77, 20.89, 25.06, 27.46, 31.8, 33.95]
ENDS = [3.2, 6.8, 10.05, 13.4, 16.5, 20.6, 24.8, 27.2, 31.5, 33.7, 36.8]
TXT = ["How can a video show someone saying something they never said?",
       "It's called a deepfake, and it's made by two AIs playing a game.",
       "One AI is a forger. The other is a detective.",
       "The forger makes a fake face, and the detective says fake.",
       "So the forger tries again, millions of times.",
       "Each round, the fakes get a little better, until the detective can't tell.",
       "Voice works the same way, and a short clip can be enough to copy someone.",
       "The catch: seeing is no longer believing.",
       "If a call asks for money, hang up and call back on a number you already know.",
       "Next up: how an eSIM works.",
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

TITLES = [(0.1, 3.3, "Words never said?"), (3.46, 6.9, "Two AIs, one game"),
          (7.06, 10.2, "Forger vs detective"), (10.33, 13.6, "Fake face... caught!"),
          (13.69, 16.7, "Again and again"), (16.77, 20.8, "Fakes get better"),
          (20.89, 25.0, "Voices get copied"), (25.06, 27.4, "Seeing isn't believing"),
          (27.46, 31.7, "Hang up, call back"), (31.8, 33.9, "Next: eSIM"), (33.95, 38.3, "Follow for more")]

def warp(tn): return float(tn)
GREEN = (120, 220, 150)

def tag(d, cx, cy, s, size=30, fill=OR, p=1.0):
    if p <= 0: return
    w_ = tw(s, size) + 40
    rr(d, (cx - w_ / 2 * p, cy - 26 * p, cx + w_ / 2 * p, cy + 26 * p), 14 * p, fill=fill)
    if p > 0.6:
        tx(d, cx, cy + 1, s, size * p, DARK if fill != RED else WHITE, kind='p')

SKIN = (255, 214, 170)
def face(d, cx, cy, r, real=True, glitch=0.0, col=SKIN):
    if r < 6: return
    ell(d, cx, cy, r, r * 1.12, fill=col)
    ell(d, cx - r * 0.35, cy - r * 0.15, r * 0.11, fill=DARK)
    ell(d, cx + r * 0.35, cy - r * 0.15, r * 0.11, fill=DARK)
    ln(d, [(cx - r * 0.3, cy + r * 0.5), (cx, cy + r * 0.6), (cx + r * 0.3, cy + r * 0.5)], DARK, max(2, r * 0.07))
    if not real:
        for i in range(3):
            y = cy - r * 0.5 + i * r * 0.5 + glitch
            rr(d, (cx - r, y, cx + r, y + r * 0.1), 0, fill=(255, 90, 54))

def frame_(d, cx, cy, w, h, p=1.0):
    if p <= 0.05: return
    rr(d, (cx - w / 2 * p, cy - h / 2 * p, cx + w / 2 * p, cy + h / 2 * p), 20 * p, fill=PANEL, outline=WHITE, w=4)

def bubble_(d, cx, cy, s, w=300, h=70, fill=WHITE, col=DARK, size=24, p=1.0):
    if p <= 0.05: return
    rr(d, (cx - w / 2 * p, cy - h / 2 * p, cx + w / 2 * p, cy + h / 2 * p), 18 * p, fill=fill)
    if p > 0.6: tx(d, cx, cy, s, size * p, col, kind='p')

def lens(d, cx, cy, s=1.0, col=BLUE):
    if s <= 0.05: return
    ell(d, cx, cy, 42 * s, outline=col, w=9 * s)
    ln(d, [(cx + 30 * s, cy + 30 * s), (cx + 68 * s, cy + 68 * s)], col, 12 * s)

def brush(d, cx, cy, s=1.0):
    ln(d, [(cx - 20 * s, cy + 40 * s), (cx + 30 * s, cy - 40 * s)], TAN, 10 * s)
    ell(d, cx + 34 * s, cy - 46 * s, 12 * s, fill=RED)

def person(d, cx, cy, kind, p=1.0):
    if p <= 0.05: return
    ell(d, cx, cy, 62 * p, fill=RED if kind == 'forger' else BLUE)
    rr(d, (cx - 42 * p, cy - 16 * p, cx + 42 * p, cy + 6 * p), 6 * p, fill=DARK)
    ell(d, cx - 18 * p, cy - 5 * p, 6 * p, fill=WHITE); ell(d, cx + 18 * p, cy - 5 * p, 6 * p, fill=WHITE)
    ln(d, [(cx - 18 * p, cy + 30 * p), (cx + 18 * p, cy + 30 * p)], DARK, 5 * p)
    if kind == 'forger': brush(d, cx + 82 * p, cy + 60 * p, p)
    else: lens(d, cx - 82 * p, cy + 56 * p, 0.8 * p)

def wave(d, cx, cy, w, col, amp=36, ph=0.0, n=15, p=1.0):
    for i in range(n):
        x = cx - w / 2 + w * i / (n - 1)
        h = amp * (0.35 + 0.65 * abs(math.sin(i * 0.9 + ph))) * p
        ln(d, [(x, cy - h), (x, cy + h)], col, 8)

def scene1(img, d, t, tl):
    pp = eob(tl / 0.5)
    frame_(d, 360, 440, 420, 340, pp)
    if pp > 0.9:
        face(d, 360, 430, 92, True)
        ell(d, 360, 505, 12, 8, fill=DARK) if tl % 0.6 < 0.3 else None
    bubble_(d, 360, 650, "Send me money!", 330, 70, WHITE, DARK, 26, eob((tl - 0.8) / 0.4))
    robot(d, 600, 700, 0.45, t, 'confused')

def scene2(img, d, t, tl):
    pa = eob((tl - 0.2) / 0.4); pb = eob((tl - 0.9) / 0.4)
    rr(d, (90, 360, 330, 520), 28, fill=PANEL, outline=RED, w=4) if pa > 0.9 else None
    rr(d, (390, 360, 630, 520), 28, fill=PANEL, outline=BLUE, w=4) if pb > 0.9 else None
    if pa > 0.9: tx(d, 210, 440, "AI #1", 52, WHITE, kind='p')
    if pb > 0.9: tx(d, 510, 440, "AI #2", 52, WHITE, kind='p')
    if tl > 1.4: tx(d, 360, 440, "vs", 36, OR, kind='p')
    tag(d, 360, 640, "deepfake = a game", 34, p=eob((tl - 1.8) / 0.4))

def scene3(img, d, t, tl):
    person(d, 190, 460, 'forger', eob((tl - 0.2) / 0.5))
    person(d, 530, 460, 'detective', eob((tl - 1.6) / 0.5))
    tag(d, 190, 650, "forger", 30, fill=RED, p=eob((tl - 0.6) / 0.4))
    tag(d, 530, 650, "detective", 30, fill=BLUE, p=eob((tl - 2.0) / 0.4))

def scene4(img, d, t, tl):
    person(d, 150, 420, 'forger', 0.8)
    person(d, 580, 420, 'detective', 0.8)
    f = eio(clamp((tl - 0.6) / 1.2))
    x = lerp(220, 500, f)
    frame_(d, x, 560, 150, 180)
    face(d, x, 555, 40, False, glitch=math.sin(tl * 12) * 3)
    if tl > 1.9:
        tag(d, 530, 720, "FAKE!", 44, fill=RED, p=eob((tl - 1.9) / 0.4))

def scene5(img, d, t, tl):
    cx, cy = 360, 450
    for k in range(2):
        a0 = tl * 160 + k * 180
        d.arc([(cx - 130) * S, (cy - 130) * S, (cx + 130) * S, (cy + 130) * S], a0, a0 + 140, fill=OR, width=round(14 * S))
        a = math.radians(a0 + 140)
        ex, ey = cx + 130 * math.cos(a), cy + 130 * math.sin(a)
        ell(d, ex, ey, 14, fill=OR)
    n = int(1000000 * eio(clamp(tl / 2.6)) ** 3)
    tx(d, cx, cy, f"{n:,}", 46, WHITE, kind='p')
    tag(d, 360, 690, "try again, again, again", 28, p=eob((tl - 0.6) / 0.4))

def scene6(img, d, t, tl):
    for i in range(3):
        cx = 150 + i * 210
        p = eob((tl - 0.3 - 1.0 * i) / 0.4)
        frame_(d, cx, 440, 170, 210, p)
        if p > 0.9:
            face(d, cx, 440, 46, i == 2, glitch=(2 - i) * 2 * math.sin(tl * 10))
    if tl > 3.0:
        tag(d, 360, 640, "which is real?", 32, fill=BLUE, p=eob((tl - 3.0) / 0.4))
    if tl > 3.6:
        tag(d, 360, 730, "detective can't tell", 26, fill=WHITE, p=eob((tl - 3.6) / 0.4))

def scene7(img, d, t, tl):
    wave(d, 360, 380, 480, OR, 40, tl * 6, 17)
    ar = eob((tl - 0.8) / 0.4)
    if ar > 0.1: poly(d, [(330, 480), (390, 480), (360, 530)], WHITE)
    wave(d, 360, 640, 480, RED, 40, tl * 6 + 0.6, 17, p=eob((tl - 1.2) / 0.5))
    tag(d, 160, 300, "real voice", 24, p=eob((tl - 0.3) / 0.4))
    tag(d, 160, 740, "copied voice", 24, fill=RED, p=eob((tl - 1.8) / 0.4))
    if tl > 2.8: tag(d, 520, 740, "short clip is enough", 22, fill=WHITE, p=eob((tl - 2.8) / 0.4))

def scene8(img, d, t, tl):
    p = eob(tl / 0.5)
    ell(d, 360, 450, 130 * p, 70 * p, fill=WHITE)
    ell(d, 360, 450, 42 * p, fill=OR2); ell(d, 360, 450, 18 * p, fill=DARK)
    if tl > 0.9:
        q = eob((tl - 0.9) / 0.3)
        ln(d, [(360 - 150 * q, 450 - 150 * q), (360 + 150 * q, 450 + 150 * q)], RED, 16)
        ln(d, [(360 + 150 * q, 450 - 150 * q), (360 - 150 * q, 450 + 150 * q)], RED, 16)
    tag(d, 360, 690, "seeing ≠ believing", 34, p=eob((tl - 1.2) / 0.4))

def scene9(img, d, t, tl):
    phone_ = lambda cx, cy: (rr(d, (cx - 80, cy - 140, cx + 80, cy + 140), 24, fill=PANEL, outline=WHITE, w=4))
    phone_(200, 450)
    bubble_(d, 200, 420, "Send money", 130, 54, RED, WHITE, 18, eob((tl - 0.3) / 0.4))
    if tl > 1.4:
        p = eob((tl - 1.4) / 0.4)
        ell(d, 200, 530, 30 * p, fill=RED)
        ln(d, [(188, 530), (212, 530)], WHITE, 6)
    if tl > 2.6:
        f = eio(clamp((tl - 2.6) / 0.8))
        ln(d, [(300, 450), (300 + 90 * f, 450)], WHITE, 6)
        if f > 0.9: poly(d, [(390, 430), (420, 450), (390, 470)], WHITE)
        rr(d, (430, 330, 590, 570), 24, fill=PANEL, outline=GREEN, w=4)
        tx(d, 510, 420, "Mom", 30, WHITE, kind='p')
        ell(d, 510, 490, 26, fill=GREEN)
    tag(d, 360, 700, "call back: known number", 26, fill=GREEN, p=eob((tl - 3.2) / 0.4))

def scene10(img, d, t, tl):
    p = eob(tl / 0.5)
    rr(d, (270, 330, 450, 550), 20 * p, fill=OR) if p > 0.2 else None
    poly(d, [(410, 330), (450, 370), (450, 330)], DARK) if p > 0.9 else None
    rr(d, (300, 400, 420, 510), 10, fill=(255, 220, 130)) if p > 0.9 else None
    tag(d, 360, 650, "next: how an eSIM works", 30, p=eob((tl - 0.3) / 0.4))

def scene11(img, d, t, tl):
    cx, cy, sc = 360, 420, 1.25
    arms = (125, 125) if tl < 1.0 else (14, 14)
    robot(d, cx, cy, sc, t, 'happy', arms=arms)
    p = eob((tl - 0.6) / 0.4)
    chip_logo(d, 238, 760, 62 * p)
    tx(d, 290, 760, "PlainBytes", 44 * p, WHITE, anchor='lm', kind='p')

BOUNDS = ST[:] + [DUR + 1]
SCENES = [scene1, scene2, scene3, scene4, scene5, scene6, scene7, scene8, scene9, scene10, scene11]
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
    for st_ in BOUNDS[1:10]:
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

