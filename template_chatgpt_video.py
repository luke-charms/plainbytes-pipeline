#!/usr/bin/env python3
"""PlainBytes Short: How ChatGPT actually works. 720x1280, 30fps, 50s. Frames piped to ffmpeg."""
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
TITLES = [(0, 4, "ChatGPT doesn't understand you"), (7, 11, "Autocomplete… on steroids"),
          (15, 19, "Most likely next word?"), (19, 27, "Pick a word → repeat"),
          (27, 35, "Trained on billions of pages"), (40, 44, "Sounds right ≠ is true"),
          (44, 50, "Next: What's an AI agent?")]
CAPS = [(2.59, 4.13, "Here's what it's actually doing."),
        (4.13, 6.9, "It's basically autocomplete on steroids…"),
        (6.92, 10.16, "Same idea, just trained on a huge amount of text."),
        (10.16, 13.74, "Type 'the cat sat on the', and it doesn't picture a cat."),
        (13.74, 17.34, "It just calculates which word is most likely to come next."),
        (17.34, 20.39, "It picks one, adds it, then does it again."),
        (20.39, 21.43, "Word by word."),
        (21.43, 22.99, "That's the entire answer."),
        (22.99, 26.0, "It learned those odds by reading billions of pages"),
        (26.0, 29.15, "and spotting patterns in how language fits together."),
        (29.15, 33.65, "That's why it sounds so smart, but can also make things up with total confidence."),
        (33.65, 36.38, "It predicts what sounds right, not what's true."),
        (36.38, 39.65, "So: super useful, not a mind."),
        (39.65, 43.5, "Next up: what's an AI agent? Follow for more.")]

# time warp: new (voiceover) time -> old (animation) time
NEW_A = [0, 4.13, 6.9, 10.16, 13.74, 17.34, 22.99, 29.15, 33.65, 36.38, 43.5]
OLD_A = [0, 4, 7, 11, 15, 19, 27, 35, 40, 44, 50]
def warp(tn): return float(np.interp(tn, NEW_A, OLD_A))


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


# ---------- scenes ----------
def scene1(img, d, t, tl):
    mood = 'confused' if tl > 1.2 else 'normal'
    robot(d, 360, 520, 1.5, t, mood)
    bubble(d, (430, 300, 650, 372), (470, 420))
    for i in range(3):
        r_ = 8 + 4 * max(0, math.sin(t * 7 - i * 0.9))
        ell(d, 475 + i * 40, 336, r_, fill=TAN)
    if tl > 1.3:
        p = eob((tl - 1.3) / 0.5)
        tx(d, 235, 330 + math.sin(t * 6) * 3, '?', 190 * p, RED, stroke=5)


def phone(d, cx, cy, sc, tap=0.0, typed=False, glow_=False):
    rr(d, (cx - 170 * sc, cy - 290 * sc, cx + 170 * sc, cy + 290 * sc), 40 * sc, fill=(60, 46, 36), outline=OR, w=4 * sc)
    rr(d, (cx - 158 * sc, cy - 278 * sc, cx + 158 * sc, cy + 278 * sc), 30 * sc, fill=(30, 24, 20))
    rr(d, (cx - 140 * sc, cy - 250 * sc, cx + 140 * sc, cy - 180 * sc), 14 * sc, fill=PANEL)
    s = "I'm on my" + (" way" if typed else "")
    tx(d, cx - 124 * sc, cy - 215 * sc, s, 30 * sc, WHITE, anchor='lm')
    if int(tap * 3) % 2 == 0 and not typed:
        cxp = cx - 124 * sc + tw(s, 30 * sc) + 6 * sc
        rr(d, (cxp, cy - 234 * sc, cxp + 3 * sc, cy - 198 * sc), 1, fill=OR)
    chips = [("way", -140, -52), ("own", -44, 44), ("phone", 52, 140)]
    for i, (w_, a, b) in enumerate(chips):
        on = (i == 0 and tap > 0)
        rr(d, (cx + a * sc, cy - 150 * sc, cx + b * sc, cy - 104 * sc), 12 * sc, fill=OR if on else PANEL)
        tx(d, cx + (a + b) / 2 * sc, cy - 127 * sc, w_, 26 * sc, DARK if on else WHITE)
    rows = [(10, -60), (9, -8), (7, 44)]
    for n, yy in rows:
        total = n * 26 + (n - 1) * 5
        for k in range(n):
            x0 = cx - total / 2 * sc + k * 31 * sc
            rr(d, (x0, cy + yy * sc, x0 + 26 * sc, cy + (yy + 40) * sc), 6 * sc, fill=(62, 48, 38))
    rr(d, (cx - 100 * sc, cy + 96 * sc, cx + 100 * sc, cy + 136 * sc), 8 * sc, fill=(62, 48, 38))


def scene2(img, d, t, tl):
    if tl < 3:
        tap = 1 if tl > 1.7 else 0
        phone(d, 360, 530, 1.0, tap=(tl if not tap else 1), typed=tl > 2.1)
        if 1.7 < tl < 2.1:
            r_ = 10 + 60 * (tl - 1.7) / 0.4
            ell(d, 360 - 96 * 1.0, 530 - 127, r_, outline=OR, w=3)
    else:
        q = tl - 3
        p = eio(q / 0.9)
        sc = lerp(1.0, 0.34, p)
        phone(d, lerp(360, 150, p), lerp(530, 330, p), sc, typed=True)
        g = eob((q - 0.2) / 0.6)
        if g > 0:
            pulse = 1 + 0.04 * math.sin(t * 8)
            bw, bh = 640 * g * pulse, 170 * g * pulse
            box = (360 - bw / 2, 600 - bh / 2, 360 + bw / 2, 600 + bh / 2)
            glow(img, box, OR, r=26, a=170)
            d = ImageDraw.Draw(img)
            rr(d, box, 40 * g, fill=PANEL, outline=OR, w=5)
            for i, (w_, cxx) in enumerate((("the", 140), ("a", 360), ("and", 580))):
                rr(d, (360 + (cxx - 360 - 82) * g, 600 - 46 * g, 360 + (cxx - 360 + 82) * g, 600 + 46 * g), 22 * g, fill=OR if i == 1 else (70, 54, 42))
                tx(d, 360 + (cxx - 360) * g, 600, w_, 46 * g, DARK if i == 1 else WHITE)
            bolt(d, 60, 600, 55 * g * pulse, OR); bolt(d, 660, 600, 55 * g * pulse, OR)
            if q > 1.2:
                tx(d, 360, 740, "× billions of examples", 34, SOFT, stroke=3)
    return d


def scene3(img, d, t, tl):
    rr(d, (50, 290, 670, 410), 30, fill=PANEL, outline=OR, w=3)
    full = "The cat sat on the…"
    if tl < 4:
        n = int(len(full) * eio(tl / 2.4)) if tl < 2.4 else len(full)
        s = full[:n]
    else:
        s = full
    tx(d, 90, 350, s, 46, WHITE, anchor='lm')
    if tl < 4:
        for cxx, cyy, r_ in ((338, 445, 8), (350, 480, 12), (362, 520, 16)):
            ell(d, cxx, cyy, r_ * eo3((tl - 2.2) * 1.2 + 0.2) if tl > 2 else 0.01, fill=SOFT)
        if tl > 1.8:
            p = eob((tl - 1.8) / 0.5)
            ell(d, 360, 660, 170 * p, 120 * p, fill=SOFT)
            cat(d, 360, 665, 78 * p)
            if tl > 2.6:
                q = eob((tl - 2.6) / 0.35)
                ln(d, [(360 - 80 * q, 665 - 80 * q), (360 + 80 * q, 665 + 80 * q)], RED, 18)
                ln(d, [(360 + 80 * q, 665 - 80 * q), (360 - 80 * q, 665 + 80 * q)], RED, 18)
    else:
        q = tl - 4
        items = [("mat", 62), ("sofa", 21), ("floor", 12), ("moon", 1)]
        for i, (w_, pct) in enumerate(items):
            y = 505 + i * 74
            p = eo3((q - 0.15 - i * 0.22) / 0.6)
            tx(d, 60, y, w_, 38, OR if i == 0 else WHITE, anchor='lm')
            rr(d, (215, y - 24, 215 + 380, y + 24), 12, fill=(60, 46, 36))
            bw = max(6, pct * 5.8) * p
            rr(d, (215, y - 24, 215 + bw, y + 24), 12, fill=OR if i == 0 else TAN)
            if p > 0.5:
                tx(d, 215 + bw + 12, y, f"{int(pct * p)}%", 30, WHITE, anchor='lm')
        tx(d, 360, 790, "(example odds)", 26, SOFT)


def scene4(img, d, t, tl):
    base = ["The", "cat", "sat", "on", "the"]
    adds = [("mat", 0.6), ("and", 1.9), ("fell", 3.0), ("asleep", 3.9), ("in", 4.7), ("the", 5.4), ("sun.", 6.0)]
    tokens = [(w_, -9) for w_ in base] + [(w_, a) for w_, a in adds if tl >= a]
    rr(d, (40, 255, 680, 650), 32, fill=PANEL, outline=OR, w=3)
    size = 54
    sp = tw(' ', size)
    lines, cur, curw = [], [], 0
    for tok in tokens:
        w_ = tw(tok[0], size)
        if cur and curw + sp + w_ > 560:
            lines.append((cur, curw)); cur, curw = [], 0
        curw += (sp if cur else 0) + w_
        cur.append(tok)
    lines.append((cur, curw))
    for li, (toks, lw) in enumerate(lines):
        x = 360 - lw / 2
        y = 345 + li * 84
        for w_, a in toks:
            age = tl - a
            new = a >= 0 and age < 0.6
            sc_ = 1 + 0.25 * (1 - eo3(age / 0.3)) if new else 1
            tx(d, x, y - (10 * (1 - eo3(age / 0.25)) if new else 0), w_, size * sc_, OR if new else WHITE, anchor='lm')
            x += tw(w_, size) + sp
    ang = tl * 240
    cx, cy, r_ = 360, 790, 52
    ln_pts = []
    for k in range(0, 271, 10):
        a = math.radians(ang + k)
        ln_pts.append((cx + r_ * math.cos(a), cy + r_ * math.sin(a)))
    ln(d, ln_pts, OR, 11)
    a = math.radians(ang + 270)
    tipx, tipy = cx + r_ * math.cos(a), cy + r_ * math.sin(a)
    tang = a + math.pi / 2
    poly(d, [(tipx + 22 * math.cos(tang), tipy + 22 * math.sin(tang)),
             (tipx + 20 * math.cos(a), tipy + 20 * math.sin(a)),
             (tipx - 20 * math.cos(a), tipy - 20 * math.sin(a))], OR)


BOOK_COLS = [(255, 176, 32), (255, 90, 54), (243, 217, 184), (200, 120, 60), (120, 170, 200), (150, 200, 140)]
ROWS = [(805, 5), (766, 5), (727, 4), (688, 4), (649, 3), (610, 2)]
BOOKS = []
_i = 0
for yy, n in ROWS:
    for k in range(n):
        bw = 118 + (_i * 37) % 26
        x = 360 + (k - (n - 1) / 2) * 128 + ((_i * 53) % 21 - 10)
        BOOKS.append((x, yy, bw, BOOK_COLS[_i % len(BOOK_COLS)], 0.3 + _i * 0.3))
        _i += 1
NET = [(90, 330), (170, 270), (80, 450), (180, 400), (610, 300), (540, 360), (640, 440), (560, 480), (120, 560), (600, 580)]
EDGES = [(0, 1), (0, 2), (1, 3), (2, 3), (4, 5), (4, 6), (5, 7), (6, 7), (2, 8), (7, 9), (3, 8), (6, 9)]


def scene5(img, d, t, tl):
    pulse = int(tl * 3.2) % len(NET)
    for a, b in EDGES:
        lit = (a == pulse or b == pulse or a == (pulse - 1) % len(NET) or b == (pulse - 1) % len(NET))
        ln(d, [NET[a], NET[b]], OR if lit else (78, 56, 38), 3 if lit else 2, cap=False)
    for i, (x, y) in enumerate(NET):
        lit = ((pulse - i) % len(NET)) < 2
        ell(d, x, y, 9 if lit else 6, fill=OR if lit else (96, 70, 46))
    robot(d, 360, 430, 1.3, t, 'read', look=math.sin(tl * 2.2), arms=(20, 20))
    for i in range(12):
        ph = tl * 0.9 + i * 0.37
        px = 360 + math.sin(ph * 2.0 + i) * (240 + (i % 3) * 20)
        py = 300 + ((ph * 140) % 420)
        if tl > 0.6 + i * 0.1:
            rotpoly(d, px, py, 34, 44, math.sin(ph * 3) * 40, SOFT)
    for x, yy, bw, col, spawn in BOOKS:
        if tl < spawn: continue
        fall = prog(tl, spawn, 0.45)
        y = lerp(-60, yy, fall * fall)
        if fall >= 1:
            y = yy - 8 * math.sin(clamp((tl - spawn - 0.45) / 0.25) * math.pi)
        rr(d, (x - bw / 2, y - 18, x + bw / 2, y + 18), 5, fill=col, outline=DARK, w=2)
        ln(d, [(x - bw / 2 + 14, y - 14), (x - bw / 2 + 14, y + 14)], DARK, 3, cap=False)
        ln(d, [(x + bw / 2 - 18, y), (x + bw / 2 - 40, y)], DARK, 3, cap=False)


MOON_HOLES = [(-34, -30, 16), (30, -10, 12), (-10, 28, 18), (40, 40, 10), (-52, 14, 9)]
STAMP = None

def get_stamp():
    global STAMP
    if STAMP is None:
        im = Image.new('RGBA', (600 * S, 180 * S), (0, 0, 0, 0))
        sd = ImageDraw.Draw(im)
        sd.rounded_rectangle([10 * S, 10 * S, 590 * S, 170 * S], radius=26 * S, outline=RED + (255,), width=12 * S, fill=(26, 12, 10, 235))
        sd.text((300 * S, 92 * S), "FACT CHECK?", font=F(78), fill=RED + (255,), anchor='mm')
        STAMP = im.rotate(10, expand=True, resample=Image.BICUBIC)
    return STAMP


def scene6(img, d, t, tl):
    mood = 'oops' if tl > 5.6 else 'smug'
    robot(d, 205, 520, 1.25, t, mood, arms=(14, 14))
    typed = "The moon is made of cheese."
    n = int(len(typed) * clamp((tl - 0.4) / 2.6))
    bubble(d, (40, 255, 680, 372), (230, 420))
    tx(d, 70, 313, typed[:n], 40, DARK, anchor='lm')
    if tl > 3.2:
        p = eob((tl - 3.2) / 0.5)
        ell(d, 520, 560, 112 * p, fill=(255, 214, 102), outline=(210, 160, 50), w=5)
        for hx, hy, hr in MOON_HOLES:
            ell(d, 520 + hx * 1.15 * p, 560 + hy * 1.15 * p, hr * 1.15 * p, fill=(232, 176, 60))
    return d


def scene7(img, d, t, tl):
    cx, cy, sc = 360, 400, 1.25
    arms = (125, 125) if tl < 2.0 else (14, 14)
    mood = 'flat' if tl < 2.0 else 'happy'
    y = robot(d, cx, cy, sc, t, mood, arms=arms)
    if tl >= 2.0:
        p = eob((tl - 2.0) / 0.45)
        hx, hy = hand_pos(cx, y, sc, 1, 14)
        bw = 100 * sc * 0.8 * p
        rr(d, (hx - bw / 2, hy + 6, hx + bw / 2, hy + 6 + 66 * p), 10 * p, fill=(176, 104, 40), outline=DARK, w=3)
        ln(d, [(hx - 18 * p, hy + 6), (hx - 18 * p, hy - 10 * p), (hx + 18 * p, hy - 10 * p), (hx + 18 * p, hy + 6)], DARK, 6 * p, cap=False)
        rr(d, (hx - 7 * p, hy + 30 * p, hx + 7 * p, hy + 44 * p), 3, fill=OR)
        q = eob((tl - 2.3) / 0.45)
        rr(d, (cx - 46 * sc * q, y + 156 * sc - 14 * q, cx + 46 * sc * q, y + 156 * sc + 14 * q), 12 * q, fill=RED)
        if q > 0.6:
            tx(d, cx, y + 156 * sc, "AGENT", 18 * q, WHITE)
    if tl > 3.4:
        p = eob((tl - 3.4) / 0.4)
        chip_logo(d, 238, 760, 62 * p)
        tx(d, 290, 760, "PlainBytes", 44 * p, WHITE, anchor='lm', kind='p')


STARTS = [4, 11, 19, 27, 35, 44]


def render_frame(tn, idx=0):
    t = warp(tn)
    img = BG.copy()
    d = ImageDraw.Draw(img)
    if t < 4: scene1(img, d, t, t)
    elif t < 11:
        r = scene2(img, d, t, t - 4)
        d = r if r is not None else d
    elif t < 19: scene3(img, d, t, t - 11)
    elif t < 27: scene4(img, d, t, t - 19)
    elif t < 35: scene5(img, d, t, t - 27)
    elif t < 44:
        scene6(img, d, t, t - 35)
        if t >= 40.0:
            s = lerp(2.4, 1.0, eo3((t - 40.0) / 0.18))
            st = get_stamp()
            sw, sh = int(st.width * s * 0.62), int(st.height * s * 0.62)
            sm = st.resize((sw, sh), Image.LANCZOS)
            img.paste(sm, (int(370 * S - sw / 2), int(630 * S - sh / 2)), sm)
            d = ImageDraw.Draw(img)
    else: scene7(img, d, t, t - 44)
    draw_title(d, t)
    draw_caption(d, tn)
    for st_ in STARTS:
        if 0 <= t - st_ < 0.15:
            a = 0.25 * (1 - (t - st_) / 0.15)
            img = Image.blend(img, Image.new('RGB', img.size, WHITE), a)
    if 40.15 <= t < 40.5:
        amp = 9 * S * (1 - (t - 40.15) / 0.35)
        rnd = np.random.RandomState(idx)
        img = ImageChops.offset(img, int(rnd.uniform(-amp, amp)), int(rnd.uniform(-amp, amp)))
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
