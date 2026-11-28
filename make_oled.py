#!/usr/bin/env python3
"""PlainBytes Short: How OLED screens work. 720x1280, 30fps. Reuses helpers from the ChatGPT template."""
import math, os, sys, re, subprocess, random
import numpy as np
from PIL import Image, ImageDraw
import template_chatgpt_video as T
from template_chatgpt_video import (S, W, H, FPS, OR, OR2, RED, WHITE, SOFT, DARK, PANEL, TAN, BLUE, BG, rr, ell, ln, poly, tx, tw,
                                    wrap, glow, robot, chip_logo, bolt, clamp, lerp, eo3, eio, eob, prog)
DUR = 46.5
GREEN = (120, 220, 130); RCOL = (255, 90, 90); BCOL = (90, 150, 255)

SENTS = ["Your OLED screen has no backlight at all.", "Here's what's actually happening.",
         "A normal LCD screen is like a window with a lamp behind it.", "The lamp is always on, and tiny shutters block the light.",
         "An OLED works differently.", "Every single pixel makes its own light, like a tiny light bulb.",
         "Electricity flows through a thin organic layer, and that layer glows red, green, or blue.",
         "To show black, the pixel just switches off.", "That's why the blacks look so deep, and the contrast is so sharp.",
         "Millions of pixels do this at once, each one turning on, dimming, or going dark, many times every second.",
         "The catch?", "Those organic materials slowly wear out, the blue ones fastest.",
         "So a still image left up for months can leave a faint ghost called burn-in.",
         "Next up: how noise cancelling headphones work.", "Follow for more."]
SS = [0, 2.30, 4.0, 7.58, 10.8, 12.3, 15.95, 21.2, 23.55, 27.0, 33.0, 33.85, 37.55, 41.8, 44.05]
SPEECH_END = 44.98
SCENES = [0, 4.0, 10.8, 15.95, 21.2, 33.0, 41.8, 99]  # scene starts
TITLES = [(0, 4, "Your OLED has no backlight"), (4, 10.8, "LCD = a lamp + shutters"), (10.8, 15.95, "OLED: every pixel glows"),
          (15.95, 21.2, "Electricity → organic glow"), (21.2, 27, "Black = pixel switched off"), (27, 33, "Millions of tiny lights"),
          (33, 41.8, "The catch: burn-in"), (41.8, 47, "Next: noise-cancelling headphones")]

def chunks(s):
    parts = [p.strip() for p in re.split(r'(?<=,)\s+', s) if p.strip()]
    out = []
    for p in parts:
        ws = p.split()
        if len(ws) > 7:
            h = (len(ws) + 1) // 2
            out += [' '.join(ws[:h]), ' '.join(ws[h:])]
        else:
            out.append(p)
    return out

CAPS = []
for i, s in enumerate(SENTS):
    if i == 0: continue
    a = SS[i]; b = SS[i + 1] if i + 1 < len(SS) else SPEECH_END
    b = min(b, SPEECH_END) if i + 1 >= len(SS) else b
    cs = chunks(s); tot = sum(len(c) for c in cs); t = a
    for c in cs:
        d_ = (b - a) * len(c) / tot
        CAPS.append((t, t + d_, c)); t += d_
CAPS.append((SPEECH_END, DUR, "")) if False else None

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

def bulb(img, d, cx, cy, s, on=1.0, col=(255, 220, 110)):
    if on > 0.05:
        glow(img, (cx - s * 0.7, cy - s * 0.9, cx + s * 0.7, cy + s * 0.5), col, r=s * 0.5, a=int(150 * on), rad=s * 0.5)
        d = ImageDraw.Draw(img)
    c = tuple(int(lerp(70, v, on)) for v in col)
    ell(d, cx, cy - s * 0.2, s * 0.62, s * 0.7, fill=c)
    rr(d, (cx - s * 0.3, cy + s * 0.4, cx + s * 0.3, cy + s * 0.58), 4, fill=TAN)
    rr(d, (cx - s * 0.22, cy + s * 0.6, cx + s * 0.22, cy + s * 0.74), 4, fill=(110, 80, 56))
    return d

def cross(d, cx, cy, r, p):
    q = eob(p)
    ln(d, [(cx - r * q, cy - r * q), (cx + r * q, cy + r * q)], RED, 16)
    ln(d, [(cx + r * q, cy - r * q), (cx - r * q, cy + r * q)], RED, 16)

PAL = [RCOL, GREEN, BCOL, (255, 200, 80), (200, 120, 255), (255, 140, 60)]

def scene1(img, d, t, tl):
    rr(d, (90, 310, 630, 640), 30, fill=(60, 46, 36), outline=OR, w=4)
    rr(d, (108, 328, 612, 622), 18, fill=(10, 8, 8))
    rr(d, (320, 640, 400, 700), 6, fill=(60, 46, 36)); rr(d, (250, 696, 470, 716), 10, fill=(60, 46, 36))
    for i, (x, y, r_, c) in enumerate([(230, 440, 70, RCOL), (360, 500, 90, BCOL), (480, 430, 75, (255, 200, 80)), (300, 560, 55, GREEN), (440, 560, 60, (200, 120, 255))]):
        rr_ = r_ * (1 + 0.08 * math.sin(t * 3 + i))
        glow(img, (x - rr_, y - rr_ * 0.7, x + rr_, y + rr_ * 0.7), c, r=22, a=190, rad=rr_ * 0.6)
    d = ImageDraw.Draw(img)
    rr(d, (108, 328, 612, 622), 18, outline=OR2, w=2)
    d = bulb(img, d, 360, 770, 44, 1.0)
    if tl > 1.0:
        cross(d, 360, 765, 62, (tl - 1.0) / 0.4)
    tx(d, 360, 262, "no backlight", 34, SOFT, stroke=3) if tl > 1.4 else None
    return d

def scene2(img, d, t, tl):
    bulb_p = min(1, tl / 0.5)
    d = bulb(img, d, 120, 520, 80, 1.0)
    tx(d, 120, 660, "lamp", 30, SOFT, stroke=3); tx(d, 120, 695, "always on", 30, OR, stroke=3)
    for k in range(5):
        y = 400 + k * 50
        ln(d, [(185, y + 20), (290, y + 20)], (255, 220, 110), 4, cap=False)
    # shutters
    n = 7
    for k in range(n):
        y0 = 330 + k * 62
        openness = 0.5 + 0.5 * math.sin(tl * 1.8 + k * 0.9) if tl > 2.2 else 0.9
        hh = 52 * (1 - 0.9 * openness) + 4
        rr(d, (300, y0 + (52 - hh) / 2, 420, y0 + (52 + hh) / 2), 4, fill=TAN)
        col = tuple(int(255 * openness * f) for f in (1, 0.86, 0.45))
        rr(d, (480, y0 + 4, 640, y0 + 48), 8, fill=(30 + col[0] * 0 + int(openness * 200), 30 + int(openness * 190), 30 + int(openness * 100)))
        ln(d, [(420, y0 + 26), (480, y0 + 26)], (255, 220, 110) if openness > 0.5 else (80, 60, 40), 3 if openness > 0.5 else 2, cap=False)
    tx(d, 360, 790, "shutters", 30, SOFT, stroke=3)
    return d

def scene3(img, d, t, tl):
    cols, rows_ = 6, 8
    for r_ in range(rows_):
        for c in range(cols):
            x = 130 + c * 92; y = 290 + r_ * 66
            idx = r_ * cols + c
            on = clamp((tl - 0.3 - idx * 0.03) / 0.3)
            col = PAL[(idx * 7 + int(tl * 2)) % len(PAL)] if tl > 1.5 else PAL[idx % 3]
            rad = 21
            if on > 0:
                glow(img, (x - 14, y - 14, x + 14, y + 14), col, r=14, a=int(150 * on), rad=14)
            d = ImageDraw.Draw(img)
            ell(d, x, y, rad, fill=tuple(int(lerp(60, v, on)) for v in col))
    if tl > 2.0:
        p = eob((tl - 2.0) / 0.4)
        ell(d, 130 + 2 * 92, 290 + 3 * 66, 38 * p, outline=WHITE, w=4)
        tx(d, 360, 810, "1 pixel = 1 tiny light", 34, OR, stroke=4)
    return d

def scene4(img, d, t, tl):
    cx0, cx1 = 130, 590
    rr(d, (cx0, 300, cx1, 350), 14, fill=TAN); tx(d, 360, 325, "cathode  −", 28, WHITE)
    rr(d, (cx0, 560, cx1, 610), 14, fill=TAN); tx(d, 360, 585, "anode  +", 28, WHITE)
    ph = (tl / 1.6) % 3 if tl > 0.8 else 0
    ci = int(ph) if tl > 0.8 else 0
    col = [RCOL, GREEN, BCOL][ci]
    glow(img, (cx0, 360, cx1, 550), col, r=34, a=int(120 + 70 * math.sin(tl * 6)), rad=20)
    d = ImageDraw.Draw(img)
    rr(d, (cx0, 360, cx1, 550), 16, fill=tuple(int(v * 0.55) for v in col), outline=col, w=4)
    tx(d, 360, 455, "organic layer", 36, WHITE, stroke=3)
    for i in range(9):
        x = cx0 + 40 + i * 47
        y = 300 + ((tl * 150 + i * 53) % 310)
        if tl > 0.3: ell(d, x, y, 7, fill=(180, 220, 255))
    ang = [-1, 0, 1]
    for i in range(5):
        x = 170 + i * 95
        ln(d, [(x, 628), (x + (i - 2) * 6, 628 + 28)], col, 5) if tl > 0.8 else None
    for i, c in enumerate([RCOL, GREEN, BCOL]):
        on = (tl > 0.8 and i == ci)
        ell(d, 215 + i * 145, 745, 34 if on else 24, fill=c if on else tuple(int(v * 0.4) for v in c))
    return d

def pixel_grid(img, d, tl, x0, y0, nx, ny, step, rad, mode):
    rnd = random.Random(5)
    for r_ in range(ny):
        for c in range(nx):
            x = x0 + c * step; y = y0 + r_ * step
            base = rnd.random()
            lvl = 0.5 + 0.5 * math.sin(tl * (2 + base * 3) + base * 20)
            if lvl < 0.25: lvl = 0.0
            col = PAL[(r_ * nx + c) % len(PAL)]
            c2 = tuple(int(lerp(26, v, lvl)) for v in col)
            ell(d, x, y, rad, fill=c2)

def scene5(img, d, t, tl):
    if tl < 5.8:
        p = eo3(tl / 0.5)
        # LCD panel (left) vs OLED panel (right)
        rr(d, (50, 310, 340, 600), 20, fill=(52, 52, 60), outline=SOFT, w=3)
        rr(d, (380, 310, 670, 600), 20, fill=(0, 0, 0), outline=OR, w=3)
        glow(img, (200, 300, 340, 400), (255, 255, 255), r=18, a=60, rad=12)
        d = ImageDraw.Draw(img)
        for x0 in (195, 525):
            ell(d, x0, 410, 38, fill=WHITE)
        tx(d, 195, 640, "LCD: glowing grey", 30, SOFT, stroke=3)
        tx(d, 525, 640, "OLED: true black", 30, OR, stroke=3)
        if tl > 2.2:
            q = eob((tl - 2.2) / 0.4)
            ell(d, 525, 520, 22 * q, fill=(8, 8, 8), outline=WHITE, w=3)
            tx(d, 525, 520, "OFF", 16 * q, WHITE)
            tx(d, 360, 740, "pixel off = no light", 34, OR, stroke=4)
    else:
        q = tl - 5.8
        pixel_grid(img, d, tl, 130, 290, 7, 7, 76, 26, 0)
        tx(d, 360, 810, "on · dim · off, again and again", 30, SOFT, stroke=3)
    return d

def scene6(img, d, t, tl):
    rr(d, (90, 290, 630, 560), 20, fill=(10, 8, 8), outline=OR, w=3)
    wear = clamp((tl - 1.0) / 6.0)
    ghost = tl > 6.8
    bg = [RCOL, BCOL, GREEN, (255, 200, 80)][int(tl / 1.2) % 4] if not ghost else (60, 60, 66)
    rr(d, (100, 300, 620, 550), 14, fill=tuple(int(v * 0.5) for v in bg))
    if not ghost:
        rr(d, (120, 320, 270, 372), 8, fill=DARK, outline=WHITE, w=3); tx(d, 195, 346, "LIVE", 30, WHITE)
    else:
        tx(d, 195, 346, "LIVE", 30, (88, 88, 96))
        q = eob((tl - 6.8) / 0.4)
        tx(d, 360, 450, "burn-in", 70 * q, RED, stroke=5)
    labels = [("R", RCOL, 0.25), ("G", GREEN, 0.4), ("B", BCOL, 1.0)]
    tx(d, 360, 610, "pixel life", 28, SOFT, stroke=3)
    for i, (l, c, rate) in enumerate(labels):
        y = 665 + i * 50
        tx(d, 130, y, l, 30, c, stroke=2)
        rr(d, (170, y - 16, 600, y + 16), 10, fill=(50, 40, 32))
        w_ = 430 * (1 - wear * rate)
        rr(d, (170, y - 16, 170 + max(14, w_), y + 16), 10, fill=c)
    return d

def scene7(img, d, t, tl):
    cx, cy, sc = 360, 420, 1.25
    arms = (125, 125) if tl < 1.5 else (14, 14)
    robot(d, cx, cy, sc, t, 'happy', arms=arms)
    if tl > 2.4:
        p = eob((tl - 2.4) / 0.4)
        chip_logo(d, 238, 760, 62 * p)
        tx(d, 290, 760, "PlainBytes", 44 * p, WHITE, anchor='lm', kind='p')
    return d

SC = [scene1, scene2, scene3, scene4, scene5, scene6, scene7]

def render_frame(tn, idx=0):
    img = BG.copy(); d = ImageDraw.Draw(img)
    si = max(i for i in range(7) if tn >= SCENES[i])
    r = SC[si](img, d, tn, tn - SCENES[si])
    d = r if r is not None else ImageDraw.Draw(img)
    draw_title(d, tn); draw_caption(d, tn)
    for st_ in SCENES[1:7]:
        if 0 <= tn - st_ < 0.15:
            img = Image.blend(img, Image.new('RGB', img.size, WHITE), 0.25 * (1 - (tn - st_) / 0.15))
    return img.reduce(S)

def preview(times, out):
    os.makedirs(out, exist_ok=True)
    for t in times: render_frame(t).save(f"{out}/f_{t:05.2f}.png")

def full(outfile):
    tmp = outfile.replace('.mp4', '_tmp.mp4')
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-an',
           '-c:v', 'libx264', '-crf', '19', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', tmp]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(DUR * FPS)
    for i in range(n):
        p.stdin.write(render_frame(i / FPS, i).tobytes())
        if i % 150 == 0: print('frame', i, '/', n, flush=True)
    p.stdin.close()
    if p.wait() == 0: os.rename(tmp, outfile); print('done', outfile)
    else: print('ffmpeg failed')

if __name__ == '__main__':
    if sys.argv[1] == 'preview': preview([float(x) for x in sys.argv[3:]], sys.argv[2])
    else: full(sys.argv[2])
