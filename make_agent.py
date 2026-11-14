#!/usr/bin/env python3
"""PlainBytes Short: What an AI agent is. 720x1280, 30fps. Frames piped to ffmpeg."""
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


DUR = 41.0
ST = [0, 2.46, 4.34, 10.25, 11.56, 15.57, 19.57, 22.04, 27.06, 31.02, 34.20, 36.65]
ENDS = [2.18, 4.06, 9.97, 11.28, 15.29, 19.29, 21.76, 26.78, 30.74, 33.92, 36.37, 39.47]
TXT = ["An AI agent isn't just a chatbot.",
       "It actually does things for you.",
       "Think of a chatbot as a friend who gives advice, and an agent as an assistant who goes and does the errands.",
       "You give it a goal.",
       "It makes a plan, then picks a tool, like a browser or a calendar.",
       "It tries a step, looks at the result, and decides what to do next.",
       "That loop repeats until the job is done.",
       "Under the hood, it's a language model that can call tools, read what comes back, and keep going.",
       "The catch: it can make mistakes while acting, like buying the wrong thing.",
       "That's why companies are adding limits and kill switches.",
       "Next up: what is a quantum computer?",
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

TITLES = [(0.1, 4.3, "Not just a chatbot"), (4.34, 10.2, "Advice vs errands"),
          (10.25, 15.5, "Goal, plan, tools"), (15.57, 22.0, "Try, look, decide"),
          (22.04, 27.0, "A model plus tools"), (27.06, 34.1, "The catch: mistakes"),
          (34.2, 36.6, "Next: quantum"), (36.65, 41.0, "Follow for more")]

def warp(tn): return float(tn)
GREEN = (120, 220, 150)

def tag(d, cx, cy, s, size=30, fill=OR, p=1.0):
    if p <= 0: return
    w_ = tw(s, size) + 40
    rr(d, (cx - w_ / 2 * p, cy - 26 * p, cx + w_ / 2 * p, cy + 26 * p), 14 * p, fill=fill)
    if p > 0.6:
        tx(d, cx, cy + 1, s, size * p, DARK, kind='p')

def check(d, cx, cy, s, col=GREEN):
    ln(d, [(cx - 0.5 * s, cy), (cx - 0.15 * s, cy + 0.4 * s), (cx + 0.55 * s, cy - 0.45 * s)], col, max(3, 0.22 * s))

def browser(d, cx, cy, w=150, h=110):
    rr(d, (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), 12, fill=WHITE)
    rr(d, (cx - w / 2, cy - h / 2, cx + w / 2, cy - h / 2 + 26), 12, fill=BLUE)
    for i, c in enumerate((RED, OR, GREEN)):
        ell(d, cx - w / 2 + 16 + i * 16, cy - h / 2 + 13, 5, fill=c)
    for k in range(3):
        ln(d, [(cx - w / 2 + 16, cy - 8 + k * 20), (cx + w / 2 - 16 - k * 25, cy - 8 + k * 20)], TAN, 6)

def calendar(d, cx, cy, w=120, h=120):
    rr(d, (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), 12, fill=WHITE)
    rr(d, (cx - w / 2, cy - h / 2, cx + w / 2, cy - h / 2 + 30), 12, fill=RED)
    for r_ in range(3):
        for c_ in range(4):
            ell(d, cx - 40 + c_ * 27, cy - 8 + r_ * 24, 6, fill=TAN if (r_, c_) != (1, 2) else OR)

def mail(d, cx, cy, w=130, h=90):
    rr(d, (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), 10, fill=WHITE)
    ln(d, [(cx - w / 2 + 6, cy - h / 2 + 8), (cx, cy + 8), (cx + w / 2 - 6, cy - h / 2 + 8)], TAN, 6)

def node(d, cx, cy, s, p, fill=OR):
    if p <= 0: return
    r = 62 * eob(p)
    ell(d, cx, cy, r, fill=fill, outline=WHITE, w=4)
    if p > 0.6: tx(d, cx, cy + 1, s, 28, DARK, kind='p')

def scene1(img, d, t, tl):
    robot(d, 360, 560, 0.85, t, 'normal' if tl < 2.4 else 'happy', arms=(14, 14) if tl < 2.4 else (125, 125))
    if tl < 2.4:
        p = eob((tl - 0.5) / 0.4)
        if p > 0:
            bubble(d, (170, 290, 550, 390), (330, 450))
            tx(d, 360, 340, "Here are some tips...", 28 * p, DARK, kind='p')
    else:
        for i, s_ in enumerate(("flight booked", "email sent", "meeting set")):
            q = eob((tl - 2.7 - i * 0.35) / 0.3)
            if q > 0:
                tag(d, 360, 270 + i * 62, s_, 28, fill=GREEN, p=q)

def scene2(img, d, t, tl):
    tag(d, 360, 270, "chatbot", 30, p=eob((tl - 0.3) / 0.3))
    if tl > 0.6:
        p = eob((tl - 0.6) / 0.4)
        bubble(d, (130, 320, 590, 430), (360, 490), fill=WHITE)
        tx(d, 360, 375, "Try an early flight!", 30 * p, DARK, kind='p')
    robot(d, 360, 640, 0.55, t, 'normal')
    if tl > 3.0:
        # agent lane
        rr(d, (60, 520, 660, 780), 24, fill=PANEL)
        tag(d, 360, 560, "agent", 30, fill=GREEN, p=eob((tl - 3.0) / 0.3))
        for i, s_ in enumerate(("groceries", "parcel", "tickets")):
            q = tl - 3.5 - i * 0.7
            tx(d, 240, 630 + i * 50, s_, 28, WHITE, anchor='lm')
            if q > 0: check(d, 520, 630 + i * 50, 16 * eob(q / 0.3))

def scene3(img, d, t, tl):
    tag(d, 360, 280, "GOAL: book a trip", 32, p=eob((tl - 0.2) / 0.4))
    if tl > 1.5:
        rr(d, (110, 350, 610, 570), 24, fill=PANEL)
        tx(d, 360, 385, "PLAN", 28, OR, kind='p')
        for i, s_ in enumerate(("find flights", "pick dates", "pay")):
            q = eob((tl - 1.9 - i * 0.5) / 0.3)
            if q > 0:
                tx(d, 180, 440 + i * 46, str(i + 1) + ".  " + s_, 28 * q, WHITE, anchor='lm')
    if tl > 3.2:
        p = eob((tl - 3.2) / 0.4)
        browser(d, 220, 700, 170 * p, 120 * p)
    if tl > 3.9:
        p = eob((tl - 3.9) / 0.4)
        calendar(d, 500, 700, 120 * p, 120 * p)

def scene4(img, d, t, tl):
    cx, cy, R = 360, 520, 170
    pos = [(cx, cy - R), (cx + R * 0.87, cy + R * 0.5), (cx - R * 0.87, cy + R * 0.5)]
    for a_, b_ in ((0, 1), (1, 2), (2, 0)):
        if tl > 1.0 + a_ * 1.1:
            ln(d, [pos[a_], pos[b_]], SOFT, 5)
    for i, s_ in enumerate(("TRY", "LOOK", "DECIDE")):
        node(d, pos[i][0], pos[i][1], s_, (tl - 0.3 - i * 1.1) / 0.4, fill=(OR, BLUE, GREEN)[i])
    if tl > 3.4:
        f = ((tl - 3.4) * 0.5) % 1.0
        seg = int(f * 3); u = f * 3 - seg
        a_, b_ = pos[seg], pos[(seg + 1) % 3]
        ell(d, lerp(a_[0], b_[0], u), lerp(a_[1], b_[1], u), 12, fill=RED)
    if tl > 4.0:
        tag(d, 360, 770, "repeat until done", 30, p=eob((tl - 4.0) / 0.4))
    if tl > 5.8:
        check(d, 360, 520, 40 * eob((tl - 5.8) / 0.3))

def scene5(img, d, t, tl):
    rr(d, (230, 380, 490, 520), 28, fill=OR, outline=WHITE, w=4)
    tx(d, 360, 430, "LANGUAGE", 28, DARK, kind='p'); tx(d, 360, 468, "MODEL", 28, DARK, kind='p')
    tools = [((130, 270), "browser"), ((590, 270), "calendar"), ((360, 650), "email")]
    for i, (pt, s_) in enumerate(tools):
        q = eob((tl - 0.6 - i * 0.6) / 0.4)
        if q > 0:
            if i == 0: browser(d, pt[0], pt[1], 150 * q, 100 * q)
            elif i == 1: calendar(d, pt[0], pt[1], 110 * q, 110 * q)
            else: mail(d, pt[0], pt[1], 130 * q, 90 * q)
            tx(d, pt[0], pt[1] + (78 if i < 2 else 66), s_, 22, SOFT)
    if tl > 2.4:
        for pt, _ in tools:
            a_ = (360 + (pt[0] - 360) * 0.45, 450 + (pt[1] - 450) * 0.45)
            b_ = (360 + (pt[0] - 360) * 0.8, 450 + (pt[1] - 450) * 0.8)
            pulses(d, a_, b_, tl, col=GREEN, n=2, size=8)
    if tl > 3.6:
        tag(d, 360, 790, "reads results, keeps going", 26, p=eob((tl - 3.6) / 0.4))

def pulses(d, a, b, t, col=OR, n=3, size=9, speed=0.7):
    for k in range(n):
        f = (t * speed + k / n) % 1.0
        ell(d, lerp(a[0], b[0], f), lerp(a[1], b[1], f), size, fill=col)

def scene6(img, d, t, tl):
    if tl < 3.9:
        robot(d, 360, 480, 0.85, t, 'oops')
        if tl > 1.2:
            tag(d, 360, 750, "bought the wrong thing", 28, fill=RED, p=eob((tl - 1.2) / 0.4))
            tx(d, 560, 380, "!", 72 * eob((tl - 1.2) / 0.3), RED, stroke=4)
    else:
        q = eob((tl - 3.9) / 0.4)
        rr(d, (200, 300, 520, 360), 16, fill=PANEL, outline=OR, w=4)
        tx(d, 360, 330, "LIMITS: ask before buying", 24, WHITE, kind='p') if q > 0.6 else None
        ell(d, 360, 520, 100 * q, fill=RED, outline=WHITE, w=8)
        if q > 0.6: tx(d, 360, 522, "STOP", 44, WHITE, kind='p')
        tag(d, 360, 720, "kill switch", 30, p=eob((tl - 4.6) / 0.4))

def scene7(img, d, t, tl):
    cx, cy, sc = 360, 420, 1.25
    arms = (125, 125) if tl < 1.5 else (14, 14)
    robot(d, cx, cy, sc, t, 'happy', arms=arms)
    if tl < 2.45:
        tag(d, 360, 790, "next: quantum computers", 32, p=eob((tl - 0.3) / 0.4))
    else:
        p = eob((tl - 2.45) / 0.4)
        chip_logo(d, 238, 760, 62 * p)
        tx(d, 290, 760, "PlainBytes", 44 * p, WHITE, anchor='lm', kind='p')

STARTS = [ST[i] for i in (2, 3, 4, 5, 7, 8, 10)][:6]
BOUNDS = [0, 4.34, 10.25, 15.57, 22.04, 27.06, 34.20, DUR + 1]
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
