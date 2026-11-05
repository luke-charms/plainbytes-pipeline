#!/usr/bin/env python3
"""PlainBytes Short: What a VPN really does. 720x1280, 30fps. Frames piped to ffmpeg."""
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


# ======================= VPN VIDEO =======================
DUR = 38.9
SENT = [(0.25, 4.15, "A VPN doesn't make you invisible online, it just changes who can see you."),
        (4.35, 8.45, "Think of sending your mail through a private courier, instead of the local post office."),
        (8.6, 12.3, "Without a VPN, your internet provider sees every site you visit."),
        (12.46, 16.75, "With one, your phone locks your traffic and sends it to the VPN server first."),
        (16.9, 20.15, "Your provider only sees scrambled data going to one place."),
        (20.28, 25.0, "Then the VPN server visits the website for you, so the site sees the server's address, not yours."),
        (25.21, 30.6, "The catch: the VPN company can now see your activity, and it won't stop logins, cookies, or viruses from tracking you."),
        (30.78, 32.8, "Next up: what a passkey is."),
        (32.98, 36.0, "Follow PlainBytes for more tech, explained simply.")]

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

TITLES = [(0.25, 4.3, "A VPN isn't invisibility"), (4.35, 8.55, "A private courier"),
          (8.6, 12.4, "Your provider sees it all"), (12.46, 20.2, "The VPN tunnel"),
          (20.28, 25.1, "The site sees the VPN"), (25.21, 30.7, "The catch"),
          (30.78, 38.9, "Follow for more")]

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



def eye(d, cx, cy, s=1.0, col=WHITE, pupil=RED):
    poly(d, [(cx - 40 * s, cy), (cx - 20 * s, cy - 18 * s), (cx, cy - 24 * s), (cx + 20 * s, cy - 18 * s), (cx + 40 * s, cy),
             (cx + 20 * s, cy + 18 * s), (cx, cy + 24 * s), (cx - 20 * s, cy + 18 * s)], col)
    ell(d, cx, cy, 13 * s, fill=pupil); ell(d, cx, cy, 5 * s, fill=DARK)

def isp(d, cx, cy, sc=1.0):
    rr(d, (cx - 60 * sc, cy - 45 * sc, cx + 60 * sc, cy + 45 * sc), 12 * sc, fill=(60, 46, 36), outline=RED, w=3 * sc)
    tx(d, cx, cy + 22 * sc, "provider", 20 * sc, SOFT, kind='p')
    eye(d, cx, cy - 12 * sc, 0.7 * sc)

def globe(d, cx, cy, r):
    ell(d, cx, cy, r, fill=(40, 70, 90), outline=BLUE, w=3)
    ell(d, cx, cy, r * 0.45, r, outline=BLUE, w=2)
    ln(d, [(cx - r, cy), (cx + r, cy)], BLUE, 2, cap=False)
    ln(d, [(cx - r * 0.87, cy - r * 0.5), (cx + r * 0.87, cy - r * 0.5)], BLUE, 2, cap=False)
    ln(d, [(cx - r * 0.87, cy + r * 0.5), (cx + r * 0.87, cy + r * 0.5)], BLUE, 2, cap=False)

def scene1(img, d, t, tl):
    p = eob(tl / 0.6)
    phone_s(d, 360, 520, 1.1 * p)
    if tl > 0.6:
        q = eob((tl - 0.6) / 0.4)
        for i, (ex, ey) in enumerate(((140, 380), (580, 400), (150, 640), (570, 660))):
            eye(d, ex, ey, 1.1 * q)
            ln(d, [(ex + (60 if ex < 360 else -60), ey), (ex + (120 if ex < 360 else -120), ey + (60 if ey < 500 else -60))], (96, 70, 46), 3, cap=False)
    if tl > 2.2:
        tag(d, 360, 790, "only changes who sees you", 28, fill=SOFT, p=eob((tl - 2.2) / 0.4))


def scene2(img, d, t, tl):
    # courier van driving in
    x = lerp(-160, 360, eo3(tl / 1.4))
    ln(d, [(0, 640), (720, 640)], (96, 70, 46), 6, cap=False)
    rr(d, (x - 110, 470, x + 40, 620), 16, fill=OR, outline=DARK, w=3)
    rr(d, (x + 40, 520, x + 110, 620), 14, fill=OR2, outline=DARK, w=3)
    rr(d, (x + 60, 535, x + 98, 575), 6, fill=BLUE)
    for wx in (x - 70, x + 70):
        ell(d, wx, 628, 24, fill=DARK, outline=SOFT, w=4)
    padlock(d, x - 35, 535, 0.9)
    tx(d, x - 35, 595, "private", 22, DARK, kind='p')
    if tl > 1.8:
        tag(d, 360, 740, "private courier", 30, fill=SOFT, p=eob((tl - 1.8) / 0.4))
    if tl > 1.8:
        ell(d, 110, 420, 0.0001)
        rr(d, (50, 340, 170, 420), 10, fill=PANEL, outline=TAN, w=3)
        tx(d, 110, 380, "post office", 20, SOFT, kind='p')
        ln(d, [(60, 420), (160, 420)], RED, 4, cap=False)
        ln(d, [(75, 355), (145, 405)], RED, 5)
        ln(d, [(145, 355), (75, 405)], RED, 5)


def scene3(img, d, t, tl):
    phone_s(d, 90, 520, 0.7)
    q = eob((tl - 0.3) / 0.5)
    isp(d, 360, 520, 1.2 * q)
    globe(d, 630, 520, 56 * q)
    ln(d, [(150, 520), (290, 520)], (96, 70, 46), 4, cap=False)
    ln(d, [(430, 520), (574, 520)], (96, 70, 46), 4, cap=False)
    sites = ["shop.com", "news.com", "bank.com"]
    for i, s_ in enumerate(sites):
        st = 1.0 + 0.8 * i
        if tl > st:
            p = eob((tl - st) / 0.35)
            msg(d, 360, 640 + i * 56, s_, fill=SOFT, size=24, sc=p)
    if tl > 3.4:
        tx(d, 360, 440, "provider's log", 24, RED, stroke=3)


def scene4(img, d, t, tl):
    phone_s(d, 90, 500, 0.7)
    q = eob(tl / 0.5)
    # tunnel
    rr(d, (150, 470, 570, 530), 30, fill=(20, 14, 10), outline=OR, w=4)
    padlock(d, 120, 400, 0.6) if tl > 0.6 else None
    server(d, 640, 500, 0.5 * q, t)
    tx(d, 640, 590, "VPN server", 22, OR, kind='p')
    isp(d, 360, 690, 0.8 * eob((tl - 1.2) / 0.4) if tl > 1.2 else 0.0001)
    pk = eio((tl - 0.6) / 3.0)
    x = lerp(190, 520, pk)
    if tl > 0.6:
        msg(d, x, 500, "x9#k2", fill=OR, size=22)
    if tl > 4.4:
        p = eob((tl - 4.4) / 0.4)
        tag(d, 360, 330, "sees only scrambled data", 26, fill=SOFT, p=p)
        tx(d, 360, 770, "one destination", 26, SOFT, stroke=3) if p > 0.8 else None
    else:
        tx(d, 360, 330, "traffic locked", 26, SOFT, stroke=3) if tl > 1.0 else None


def scene5(img, d, t, tl):
    q = eob(tl / 0.5)
    server(d, 140, 500, 0.7 * q, t)
    tx(d, 140, 610, "VPN server", 22, OR, kind='p')
    globe(d, 580, 500, 62 * q)
    tx(d, 580, 590, "website", 22, BLUE, kind='p')
    ln(d, [(230, 500), (505, 500)], (96, 70, 46), 4, cap=False)
    if tl > 0.6:
        x = lerp(240, 500, eio((tl - 0.6) / 1.4))
        msg(d, x, 450, "visit!", fill=SOFT, size=22)
    if tl > 2.4:
        p = eob((tl - 2.4) / 0.4)
        rr(d, (130, 680, 590, 780), 20, fill=PANEL, outline=GREEN, w=3)
        tx(d, 360, 715, "site sees: VPN address", 26, WHITE, kind='p')
        tx(d, 360, 755, "not yours", 26, GREEN)


def scene6(img, d, t, tl):
    rows = [("The VPN company sees you", "choose one you trust", RED), ("Logins, cookies, viruses", "can still track you", RED)]
    for i, (a, b, c) in enumerate(rows):
        p = eob((tl - 0.4 - 2.4 * i) / 0.4)
        if p < 0.8: continue
        y = 290 + i * 200
        rr(d, (40, y, 680, y + 160), 24, fill=PANEL, outline=c, w=3)
        tx(d, 360, y + 55, a, 32, WHITE, kind='p')
        tx(d, 360, y + 110, b, 28, c)
    if tl > 5.0:
        eye(d, 360, 720, 1.4)


def scene7(img, d, t, tl):
    cx, cy, sc = 360, 340, 1.1
    arms = (125, 125) if tl < 1.5 else (14, 14)
    robot(d, cx, cy, sc, t, 'happy', arms=arms)
    if tl > 0.3:
        p = eob((tl - 0.3) / 0.4)
        tx(d, 360, 640, "Next: what a passkey is", 38 * p, OR, stroke=4)
    if tl > 2.6:
        p = eob((tl - 2.6) / 0.4)
        chip_logo(d, 238, 760, 62 * p)
        tx(d, 290, 760, "PlainBytes", 44 * p, WHITE, anchor='lm', kind='p')


STARTS = [4.35, 8.6, 12.46, 20.28, 25.21, 30.78]
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

