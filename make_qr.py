#!/usr/bin/env python3
"""PlainBytes Short: How QR codes work. 720x1280, 30fps. Frames piped to ffmpeg."""
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



# ======================= QR VIDEO =======================
DUR = 35.0
ST = [0, 3.40, 6.47, 10.50, 15.56, 19.84, 25.01, 29.18, 30.87]
ENDS = [3.08, 6.04, 10.08, 15.30, 19.50, 24.57, 28.86, 30.41, 33.4]
TXT = ["A QR code is just a picture, so how does your phone read it?",
       "Think of it as a tiny map made of black and white squares.",
       "Each square is a one or a zero, and together they spell out a web address.",
       "Three big squares in the corners tell your camera which way is up, so you can scan from any angle.",
       "Your phone reads the squares in order, turns them into text, and opens the link.",
       "The clever part: QR codes carry extra backup data, so even a scratched code still works.",
       "The catch: a QR code can hide any link, so check the address before you tap.",
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

TITLES = [(0.1, 3.3, "A QR code is just a picture"), (3.4, 6.4, "A tiny map of squares"),
          (6.5, 10.4, "Square = 1 or 0"), (10.5, 15.5, "Corners show which way is up"),
          (15.6, 19.8, "Squares > text > link"), (19.9, 24.9, "Built-in backup data"),
          (25.0, 29.1, "A QR can hide any link"), (29.2, 30.8, "Next: how Wi-Fi works"),
          (30.9, 35.0, "Follow for more")]

def warp(tn): return float(tn)
GREEN = (120, 220, 150)

def tag(d, cx, cy, s, size=30, fill=OR, p=1.0):
    if p <= 0: return
    w_ = tw(s, size) + 40
    rr(d, (cx - w_ / 2 * p, cy - 26 * p, cx + w_ / 2 * p, cy + 26 * p), 14 * p, fill=fill)
    if p > 0.6:
        tx(d, cx, cy + 1, s, size * p, DARK, kind='p')

PAT = [
 "00110101011", "01001010100", "11010011001", "00101100110", "10011010101", "01100101010",
 "10101001101", "01010110010", "11001011001", "00110100110", "10101011010"]
N = 11
def finder(r, c):
    return (r < 3 and c < 3) or (r < 3 and c > 7) or (r > 7 and c < 3)

def qrdraw(d, cx, cy, s, bg=True, fade=1.0):
    if s < 30: return
    cell = s / N; x0, y0 = cx - s / 2, cy - s / 2
    if bg: rr(d, (x0 - 12, y0 - 12, x0 + s + 12, y0 + s + 12), 12, fill=WHITE)
    for r in range(N):
        for c in range(N):
            if finder(r, c):
                rr_ = r if r < 3 else r - 8; cc = c if c < 3 else (c - 8 if c > 7 else c)
                on = not (rr_ == 1 and cc == 1) and not False
                on = (rr_ in (0, 2) or cc in (0, 2)) or (rr_ == 1 and cc == 1)
                # ring with solid centre
                on = (rr_ in (0, 2) or cc in (0, 2) or (rr_ == 1 and cc == 1))
            else:
                on = PAT[r][c] == '1'
            if on:
                rr(d, (x0 + c * cell + 0.5, y0 + r * cell + 0.5, x0 + (c + 1) * cell - 0.5, y0 + (r + 1) * cell - 0.5), 2, fill=DARK)

def qr_rot(img, cx, cy, s, ang, finder_glow=False, pulse=0.0):
    L = int(s + 60)
    lay = Image.new('RGBA', (L * S, L * S), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    qrdraw(ld, L / 2, L / 2, s)
    if finder_glow:
        cell = s / N; x0 = L / 2 - s / 2; y0 = L / 2 - s / 2
        for (r, c) in ((0, 0), (0, 8), (8, 0)):
            rr(ld, (x0 + c * cell - 6, y0 + r * cell - 6, x0 + (c + 3) * cell + 6, y0 + (r + 3) * cell + 6), 8,
               outline=(255, 176, 32), w=5 + 3 * pulse)
    lay = lay.rotate(ang, resample=Image.BICUBIC)
    img.paste(lay, (int((cx - L / 2) * S), int((cy - L / 2) * S)), lay)

def arrow(d, x0, y0, x1, y1, col=OR, w=8):
    ln(d, [(x0, y0), (x1, y1)], col, w)
    a = math.atan2(y1 - y0, x1 - x0)
    poly(d, [(x1 + math.cos(a) * 16, y1 + math.sin(a) * 16),
             (x1 + math.cos(a + 2.5) * 20, y1 + math.sin(a + 2.5) * 20),
             (x1 + math.cos(a - 2.5) * 20, y1 + math.sin(a - 2.5) * 20)], col)

def wifi(d, cx, cy, s, col=OR):
    for k in (1, 2, 3):
        r = s * k / 3
        d.arc([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], 225, 315, fill=col, width=round(9 * S))
    ell(d, cx, cy, 9, fill=col)

def chip_logo2(d, cx, cy, s):
    chip_logo(d, cx, cy, s)


def scene1(img, d, t, tl):
    robot(d, 360, 380, 0.9, t, 'confused')
    if 0.6 < tl < 3.0:
        tx(d, 360, 250, "?", 64 * eob((tl - 0.6) / 0.3), RED, stroke=4)
    qr_rot(img, 360, 690, 200 * eob(tl / 0.5), 0)
    return ImageDraw.Draw(img)


def scene2(img, d, t, tl):
    s = 300
    qr_rot(img, 360, 500, s * eob(tl / 0.5), 0)
    d = ImageDraw.Draw(img)
    cell = s / N; x0 = 360 - s / 2; y0 = 500 - s / 2
    g = clamp((tl - 0.9) / 1.2)
    for i in range(N + 1):
        ln(d, [(x0, y0 + i * cell), (x0 + s * g, y0 + i * cell)], (255, 176, 32), 2, cap=False)
        ln(d, [(x0 + i * cell, y0), (x0 + i * cell, y0 + s * g)], (255, 176, 32), 2, cap=False)
    tag(d, 360, 760, "black + white squares", 30, p=eob((tl - 1.6) / 0.4))
    return d


def scene3(img, d, t, tl):
    bits = [1, 0, 1, 1, 0, 1, 0, 0]
    cw = 70; x0 = 360 - cw * 4
    for i, b in enumerate(bits):
        p = eob((tl - 0.3 - i * 0.25) / 0.3)
        if p <= 0: continue
        c = x0 + i * cw + cw / 2
        rr(d, (c - 30 * p, 330 - 30 * p, c + 30 * p, 330 + 30 * p), 8, fill=DARK if b else WHITE, outline=OR, w=3)
        tx(d, c, 400, str(b), 38 * p, OR if b else SOFT, stroke=3)
    if tl > 2.4:
        p = eob((tl - 2.4) / 0.4)
        arrow(d, 360, 450, 360, 540)
        tag(d, 360, 610, "https://plainbytes", 30, fill=WHITE, p=p)
        tag(d, 360, 690, "a web address", 28, fill=GREEN, p=eob((tl - 3.0) / 0.4))


def scene4(img, d, t, tl):
    ang = math.sin(tl * 1.6) * 28 if tl > 0.8 else 0
    pulse = (math.sin(tl * 6) + 1) / 2
    qr_rot(img, 360, 520, 290, ang, finder_glow=tl > 0.5, pulse=pulse)
    d = ImageDraw.Draw(img)
    tag(d, 360, 280, "3 corner markers", 30, p=eob((tl - 0.6) / 0.4))
    if tl > 2.8:
        tag(d, 360, 790, "scan from any angle", 30, fill=GREEN, p=eob((tl - 2.8) / 0.4))
    return d


def scene5(img, d, t, tl):
    qrdraw(d, 130, 500, 150)
    tag(d, 130, 620, "squares", 26, fill=SOFT, p=eob((tl - 0.2) / 0.3))
    if tl > 0.8:
        arrow(d, 205, 500, 270, 500)
    if tl > 1.2:
        for i, b in enumerate("10110"):
            p = eob((tl - 1.2 - i * 0.12) / 0.25)
            tx(d, 330 + i * 0 , 440 + i * 36, b, 34 * p, OR, stroke=3) if False else None
        tx(d, 355, 500, "1011", 44 * eob((tl - 1.2) / 0.3), OR, stroke=3)
        tag(d, 355, 620, "text", 26, fill=SOFT, p=eob((tl - 1.4) / 0.3))
    if tl > 2.2:
        arrow(d, 425, 500, 490, 500)
    if tl > 2.6:
        p = eob((tl - 2.6) / 0.4)
        ell(d, 600, 500, 56 * p, fill=(70, 120, 170), outline=WHITE, w=4)
        ln(d, [(544 * 1 + 56 - 56 * p, 500), (600 + 56 * p, 500)], WHITE, 3, cap=False)
        ell(d, 600, 500, 24 * p, 56 * p, outline=WHITE, w=3)
        tag(d, 600, 620, "link opens", 26, fill=GREEN, p=eob((tl - 2.9) / 0.3))


def scene6(img, d, t, tl):
    qrdraw(d, 360, 480, 290)
    p = eio((tl - 0.9) / 0.8)
    if p > 0:
        pts = [(250, 380), (330, 440), (270, 480), (400, 540), (330, 560), (470, 600)]
        n = max(2, int(len(pts) * p) + 1)
        ln(d, pts[:n], RED, 12)
    if tl > 2.2:
        tag(d, 360, 760, "still works!", 32, fill=GREEN, p=eob((tl - 2.2) / 0.4))
    if tl > 1.6:
        tag(d, 360, 270, "extra backup data", 30, p=eob((tl - 1.6) / 0.4))


def scene7(img, d, t, tl):
    qr_rot(img, 360, 430, 210, 0)
    d = ImageDraw.Draw(img)
    robot(d, 560, 330, 0.5, t, 'smug', arms=(14, 14))
    if tl > 1.0:
        p = eob((tl - 1.0) / 0.4)
        rr(d, (130, 600, 590, 670), 30, fill=PANEL, outline=OR, w=3)
        tx(d, 360, 636, "link: ???", 34 * p, SOFT)
    if tl > 2.6:
        tag(d, 360, 760, "check before you tap", 30, fill=GREEN, p=eob((tl - 2.6) / 0.4))


def scene8(img, d, t, tl):
    cx, cy, sc = 360, 400, 1.25
    arms = (125, 125) if tl < 1.5 else (14, 14)
    robot(d, cx, cy, sc, t, 'happy', arms=arms)
    if tl < 1.65:
        wifi(d, 360, 790, 90 * eob((tl - 0.1) / 0.4))
    else:
        p = eob((tl - 1.65) / 0.4)
        chip_logo(d, 238, 760, 62 * p)
        tx(d, 290, 760, "PlainBytes", 44 * p, WHITE, anchor='lm', kind='p')


STARTS = [3.40, 6.47, 10.50, 15.56, 19.84, 25.01, 29.18]
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

