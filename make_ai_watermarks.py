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


# ======================= AI WATERMARKS VIDEO =======================
DUR = 39.7
SENT = [(0.25, 3.15, "Some AI text carries a hidden signature that you can't see."),
        (3.30, 9.30, "Think of a chef who adds the same tiny pinch of salt to every dish, too small to taste, but a lab test can find it."),
        (9.48, 13.00, "When an AI writes, it picks each next word from a list of good options."),
        (13.20, 19.55, "A secret key quietly nudges those picks toward certain words, and over a whole paragraph, the nudges form a pattern."),
        (19.76, 25.30, "A detector with the same key checks for that pattern, and a match means the text probably came from that AI."),
        (25.49, 32.80, "The catch: short texts, heavy rewriting, or translation can wash the signature out, and it only works for models that add one."),
        (33.10, 35.40, "Next up: how HTTPS keeps your data private."),
        (35.54, 38.15, "Follow PlainBytes for more tech, explained simply.")]

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

TITLES = [(0.25, 3.2, "AI text can hide a signature"), (3.3, 9.4, "Like a pinch of salt"),
          (9.5, 13.1, "AI picks the next word"), (13.2, 19.7, "A secret key nudges the picks"),
          (19.8, 25.4, "A detector checks the pattern"), (25.5, 33.0, "The catch"),
          (33.1, 39.7, "Follow for more")]

NEW_A = [0, DUR]; OLD_A = [0, DUR]
def warp(tn): return float(tn)

GREEN = (120, 220, 150)
WORDS = "the cat sat on a warm soft mat near the old wooden door and slept all day long".split()

def tag(d, cx, cy, s, size=30, fill=OR, p=1.0, col=DARK):
    if p <= 0: return
    w_ = tw(s, size) + 40
    rr(d, (cx - w_ / 2 * p, cy - 26 * p, cx + w_ / 2 * p, cy + 26 * p), 14 * p, fill=fill)
    if p > 0.6:
        tx(d, cx, cy + 1, s, size * p, col, kind='p')

def doc(d, cx, cy, w, h, lit=None, p=1.0):
    """text document card; lit = set of line indexes highlighted"""
    rr(d, (cx - w / 2 * p, cy - h / 2 * p, cx + w / 2 * p, cy + h / 2 * p), 18 * p, fill=SOFT)
    if p < 0.9: return
    n = 6
    for i in range(n):
        y = cy - h / 2 + 38 + i * (h - 70) / (n - 1)
        ww = (w - 60) * (0.95 if i % 3 != 2 else 0.6)
        col = TAN
        if lit and i in lit: col = OR2
        rr(d, (cx - w / 2 + 30, y - 6, cx - w / 2 + 30 + ww, y + 6), 6, fill=col)

def key(d, cx, cy, s=1.0, col=OR):
    ell(d, cx - 22 * s, cy, 20 * s, fill=col)
    ell(d, cx - 22 * s, cy, 8 * s, fill=DARK)
    ln(d, [(cx - 2 * s, cy), (cx + 48 * s, cy)], col, 10 * s, cap=False)
    ln(d, [(cx + 30 * s, cy), (cx + 30 * s, cy + 16 * s)], col, 9 * s, cap=False)
    ln(d, [(cx + 46 * s, cy), (cx + 46 * s, cy + 12 * s)], col, 9 * s, cap=False)

def check(d, cx, cy, s, col=GREEN):
    ln(d, [(cx - 0.5 * s, cy), (cx - 0.15 * s, cy + 0.4 * s), (cx + 0.55 * s, cy - 0.45 * s)], col, max(3, 0.22 * s))

def magnifier(d, cx, cy, r, col=WHITE):
    ell(d, cx, cy, r, outline=col, w=8)
    ln(d, [(cx + r * 0.7, cy + r * 0.7), (cx + r * 1.6, cy + r * 1.6)], col, 12)

def word_grid(d, tl, mark, x0=60, y0=330, cols=4, lit_t=None):
    """grid of word chips; mark = indexes that get coloured once lit_t(i) < tl"""
    for i, w_ in enumerate(WORDS):
        r, c = divmod(i, cols)
        cw = 148
        x = x0 + c * (cw + 12); y = y0 + r * 74
        p = eob((tl - 0.08 * i) / 0.3)
        if p <= 0: continue
        on = i in mark and lit_t is not None and tl > lit_t(i)
        rr(d, (x, y, x + cw * p, y + 56 * p), 14, fill=OR if on else PANEL)
        if p > 0.7:
            tx(d, x + cw / 2, y + 29, w_, 28, DARK if on else SOFT, kind='p')

MARK = {1, 4, 6, 9, 11, 13, 16}   # words favoured by the secret key


# ---------- scenes (tl = seconds since scene start) ----------
def scene1(img, d, t, tl):
    p = eob(tl / 0.6)
    doc(d, 360, 450, 440, 330, p=p)
    if tl > 1.2:
        q = eio((tl - 1.2) / 1.0)
        glow(img, (150, 330, 570, 570), BLUE, r=30, a=int(90 * q * (0.6 + 0.4 * math.sin(t * 5))))
        d = ImageDraw.Draw(img)
        tag(d, 360, 650, "hidden signature", 30, fill=BLUE, p=eob((tl - 1.6) / 0.4))
    robot(d, 360, 760, 0.5, t, 'normal', arms=(20, 20))
    return d


def scene2(img, d, t, tl):
    p = eob(tl / 0.6)
    # plate with dish
    ell(d, 200, 470, 130 * p, 40 * p, fill=SOFT)
    ell(d, 200, 460, 100 * p, 28 * p, fill=(190, 120, 60))
    # salt pinch
    if tl > 1.2:
        q = eo3((tl - 1.2) / 1.0)
        for k in range(6):
            sx = 165 + k * 14; sy = 380 + 70 * q - (k % 2) * 12
            ell(d, sx, sy, 3.5, fill=WHITE)
        tag(d, 200, 330, "tiny pinch of salt", 26, fill=SOFT, p=eob((tl - 1.2) / 0.4))
    # lab test tube
    if tl > 3.0:
        q = eob((tl - 3.0) / 0.5)
        tx(d, 400, 470, "→", 70 * q, WHITE, stroke=4)
        rr(d, (500, 380, 560, 560), 24 * q, fill=PANEL, outline=OR, w=4)
        rr(d, (504, 470, 556, 556), 20 * q, fill=BLUE)
        tag(d, 530, 330, "lab test", 26, fill=BLUE, p=eob((tl - 3.3) / 0.4))
        if tl > 4.2:
            check(d, 610, 450, 50 * eob((tl - 4.2) / 0.3))
    if tl > 4.6:
        tx(d, 360, 690, "Invisible to you.", 40, WHITE, stroke=4)
        tx(d, 360, 745, "Visible to a test.", 40, OR, stroke=4)


def scene3(img, d, t, tl):
    tx(d, 360, 300, "The cat sat on a warm …", 40, WHITE, stroke=4)
    opts = ["mat", "rug", "sofa", "floor"]
    for i, o in enumerate(opts):
        p = eob((tl - 0.5 - 0.2 * i) / 0.35)
        y = 380 + i * 82
        if p <= 0: continue
        pick = tl > 2.6 and i == 0
        rr(d, (210, y, 510, y + 64), 18, fill=OR if pick else PANEL)
        tx(d, 360, y + 33, o, 34, DARK if pick else SOFT, kind='p')
    tx(d, 360, 740, "a list of good options", 32, SOFT, stroke=3)


def scene4(img, d, t, tl):
    key(d, 360, 280, 1.2)
    word_grid(d, tl, MARK, lit_t=lambda i: 1.2 + 0.45 * sorted(MARK).index(i))
    if tl > 1.0:
        tag(d, 360, 770, "a pattern builds up", 30, fill=OR, p=eob((tl - 1.0) / 0.4))


def scene5(img, d, t, tl):
    word_grid(d, 99, MARK, y0=300, lit_t=lambda i: 0)
    magnifier(d, 200 + 220 * eio(min(tl, 2.5) / 2.5), 420, 70)
    key(d, 200, 720, 0.9)
    tx(d, 360, 720, "same key", 28, SOFT, anchor='lm', stroke=3)
    if tl > 2.8:
        p = eob((tl - 2.8) / 0.4)
        tag(d, 330, 790, "MATCH", 32, fill=GREEN, p=p)
        check(d, 460, 790, 30 * p, col=GREEN)


def scene6(img, d, t, tl):
    rows = [("Short text", "not enough clues"), ("Heavy rewrite or translation", "pattern fades"), ("Models with no watermark", "nothing to find")]
    for i, (a, b) in enumerate(rows):
        p = eob((tl - 0.4 - 1.8 * i) / 0.4)
        if p <= 0: continue
        y = 280 + i * 165
        if p < 0.8: continue
        rr(d, (50, y, 670, y + 140), 24, fill=PANEL, outline=RED, w=3)
        if True:
            tx(d, 360, y + 48, a, 32, WHITE, kind='p')
            tx(d, 360, y + 98, b, 28, RED)


def scene7(img, d, t, tl):
    cx, cy, sc = 360, 340, 1.1
    arms = (125, 125) if tl < 1.5 else (14, 14)
    robot(d, cx, cy, sc, t, 'happy', arms=arms)
    if tl > 0.3:
        p = eob((tl - 0.3) / 0.4)
        tx(d, 360, 640, "Next: how HTTPS works", 38 * p, OR, stroke=4)
    if tl > 2.6:
        p = eob((tl - 2.6) / 0.4)
        chip_logo(d, 238, 760, 62 * p)
        tx(d, 290, 760, "PlainBytes", 44 * p, WHITE, anchor='lm', kind='p')


STARTS = [3.3, 9.48, 13.2, 19.76, 25.49, 33.1]
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

