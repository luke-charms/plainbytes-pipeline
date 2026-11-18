#!/usr/bin/env python3
"""PlainBytes Short: What is MCP. Adapts template_chatgpt_video helpers."""
import sys, os, math, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageChops
import template_chatgpt_video as T
from template_chatgpt_video import *

DUR = 39.7
TITLES = [(0, 4.28, "Your AI can't use your apps"), (4.28, 11.5, "MCP = USB-C for AI"),
          (11.5, 19.68, "One plug, any tool"), (19.68, 26.92, "Menu → pick → result"),
          (26.92, 31.67, "Build once, plug in anywhere"), (31.67, 35.46, "Only plug in tools you trust"),
          (35.46, 40, "Next: Encryption keys")]
CAPS = [(2.2, 4.28, "MCP is the plug that lets it."), (4.28, 6.06, "Think of USB-C."),
        (6.06, 10.26, "One shape of plug, and any device works with any charger."),
        (10.26, 11.5, "MCP does that for AI."),
        (11.5, 14.0, "It's a shared standard, so an AI app can connect to tools"),
        (14.0, 16.1, "like your calendar, files, or a database."),
        (16.1, 19.68, "A tool shares a menu of what it can do."),
        (19.68, 24.15, "The AI reads the menu, picks an action, and asks for it."),
        (24.15, 26.92, "The tool does the job and sends back the result."),
        (26.92, 29.3, "Before this, every connection was custom built."),
        (29.3, 31.67, "Now one tool can work with many AI apps."),
        (31.67, 33.44, "The catch: a connected tool can act for you,"),
        (33.44, 35.46, "so only plug in ones you trust."),
        (35.46, 37.3, "Next up: what is an encryption key?"),
        (37.3, 39.7, "Follow PlainBytes for more.")]
NEW_A = [0, 4.28, 11.5, 19.68, 26.92, 31.67, 35.46, 39.7]
OLD_A = [0, 4, 10, 17, 24, 30, 36, 42]
def warp(tn): return float(np.interp(tn, NEW_A, OLD_A))
T.TITLES = TITLES; T.CAPS = CAPS

def icon(d, kind, cx, cy, s=1.0, col=OR):
    rr(d, (cx-52*s, cy-52*s, cx+52*s, cy+52*s), 16*s, fill=PANEL, outline=col, w=3*s)
    if kind == 'cal':
        rr(d, (cx-30*s, cy-28*s, cx+30*s, cy+30*s), 6*s, fill=SOFT)
        rr(d, (cx-30*s, cy-28*s, cx+30*s, cy-12*s), 6*s, fill=RED)
        for i in range(3):
            for j in range(2): ell(d, cx-16*s+i*16*s, cy+4*s+j*14*s, 3.5*s, fill=DARK)
    elif kind == 'file':
        poly(d, [(cx-26*s, cy-32*s), (cx+8*s, cy-32*s), (cx+26*s, cy-14*s), (cx+26*s, cy+32*s), (cx-26*s, cy+32*s)], SOFT)
        for k in range(3): ln(d, [(cx-14*s, cy-4*s+k*12*s), (cx+14*s, cy-4*s+k*12*s)], DARK, 3*s, cap=False)
    elif kind == 'db':
        for k in range(3):
            yy = cy-20*s+k*20*s
            ell(d, cx, yy, 28*s, 9*s, fill=SOFT if k == 0 else (200, 175, 140), outline=DARK, w=2*s)
        rr(d, (cx-28*s, cy-20*s, cx+28*s, cy+20*s), 0, fill=(225, 198, 160))
        for k in range(3): ell(d, cx, cy-20*s+k*20*s, 28*s, 9*s, outline=DARK, w=2*s)
    elif kind == 'phone':
        rr(d, (cx-20*s, cy-34*s, cx+20*s, cy+34*s), 8*s, fill=SOFT); ell(d, cx, cy+26*s, 3*s, fill=DARK)
    elif kind == 'laptop':
        rr(d, (cx-34*s, cy-26*s, cx+34*s, cy+14*s), 5*s, fill=SOFT); rr(d, (cx-42*s, cy+16*s, cx+42*s, cy+26*s), 4*s, fill=(200, 175, 140))
    elif kind == 'head':
        d.arc([(cx-28*s)*S, (cy-34*s)*S, (cx+28*s)*S, (cy+22*s)*S], 180, 360, fill=SOFT, width=int(6*s*S))
        rr(d, (cx-34*s, cy-4*s, cx-20*s, cy+22*s), 5*s, fill=OR); rr(d, (cx+20*s, cy-4*s, cx+34*s, cy+22*s), 5*s, fill=OR)

def lock(d, cx, cy, s):
    d.arc([(cx-12*s)*S, (cy-26*s)*S, (cx+12*s)*S, (cy-2*s)*S], 180, 360, fill=RED, width=int(5*s*S))
    rr(d, (cx-16*s, cy-8*s, cx+16*s, cy+16*s), 5*s, fill=RED)

def plug(d, cx, cy, s, col=OR):
    rr(d, (cx-60*s, cy-44*s, cx+60*s, cy+44*s), 22*s, fill=DARK, outline=col, w=5*s)
    rr(d, (cx-34*s, cy-12*s, cx+34*s, cy+12*s), 12*s, fill=col)

def sc1(img, d, t, tl):
    robot(d, 360, 560, 1.45, t, 'confused' if tl > 1 else 'normal')
    pos = [('cal', 120, 330), ('file', 600, 330), ('db', 120, 800), ('file', 600, 800)]
    pos = [('cal', 110, 330), ('file', 610, 330), ('db', 610, 780)]
    for i, (k, x, y) in enumerate(pos):
        p = eob((tl - 0.2 - i * 0.2) / 0.5)
        if p > 0:
            icon(d, k, x, y, 0.95 * p); lock(d, x + 40, y + 44, 0.9 * p)
    if tl > 1.4:
        p = eob((tl - 1.4) / 0.5); tx(d, 520, 520 + math.sin(t*6)*3, '?', 130*p, RED, stroke=5)

def sc2(img, d, t, tl):
    p = eo3(tl / 0.8)
    plug(d, 360, 330, 1.6 * p)
    tx(d, 360, 330, "USB-C", 40 * p, WHITE, stroke=3)
    devs = [('phone', 120, 640), ('laptop', 360, 700), ('head', 600, 640)]
    for i, (k, x, y) in enumerate(devs):
        q = prog(tl, 1.0 + i * 0.5, 0.6)
        if q > 0:
            ln(d, [(360 + (x - 360) * 0.25, 410), (x, y - 62)], OR if q >= 1 else TAN, 6)
            icon(d, k, x, y, 1.0 * eob(q))
    if tl > 3.4:
        c = eob((tl - 3.4) / 0.5)
        rr(d, (360 - 230 * c, 790 - 30 * c, 360 + 230 * c, 790 + 30 * c), 16, fill=OR)
        tx(d, 360, 790, "Same plug for all", 32 * c, DARK)
    if tl > 5.0:
        q = eob((tl - 5.0) / 0.5)
        tx(d, 360, 225, "→ MCP for AI", 40 * q, OR, stroke=4)

def sc3(img, d, t, tl):
    robot(d, 130, 520, 0.95, t, 'happy' if tl > 2 else 'normal')
    rr(d, (50, 395, 210, 425), 10, fill=OR) if False else None
    tx(d, 130, 760, "AI app", 32, WHITE, stroke=4)
    cx, cy = 360, 520
    ph = eob(tl / 0.6)
    plug(d, cx, cy, 0.9 * ph); tx(d, cx, cy, "MCP", 34 * ph, WHITE, stroke=3)
    tools = [('cal', 600, 330, "Calendar"), ('file', 600, 520, "Files"), ('db', 600, 710, "Database")]
    for i, (k, x, y, name) in enumerate(tools):
        q = prog(tl, 1.0 + i * 0.8, 0.5)
        if q > 0:
            ln(d, [(cx + 60, cy), (x - 56, y)], OR, 5, cap=False)
            icon(d, k, x, y, 0.85 * eob(q))
            tx(d, x, y + 70, name, 24 * q, SOFT, stroke=3)
    ln(d, [(215, cy), (cx - 62, cy)], OR, 5, cap=False)
    for i in range(3):
        u = (tl * 0.9 + i / 3) % 1
        ln_ = lerp(215, cx - 62, u); ell(d, ln_, cy, 7, fill=WHITE)

def sc4(img, d, t, tl):
    robot(d, 150, 500, 0.9, t, 'read', look=1, arms=(20, 20))
    rr(d, (300, 270, 680, 600), 26, fill=PANEL, outline=OR, w=4)
    tx(d, 490, 305, "TOOL MENU", 28, OR)
    items = ["add_event", "find_file", "run_query"]
    sel = 1 if tl > 2.2 else -1
    for i, s in enumerate(items):
        y = 375 + i * 66
        on = (i == sel)
        rr(d, (322, y - 26, 658, y + 26), 12, fill=OR if on else (66, 50, 38))
        tx(d, 490, y, s, 28, DARK if on else WHITE)
    if tl > 0.6 and tl < 2.2:
        yy = 375 + (int(tl * 3) % 3) * 66
        ln(d, [(255, 440), (310, yy)], SOFT, 4)
    if tl > 2.2:
        p = prog(tl, 2.2, 0.8)
        ln(d, [(255, 440), (lerp(255, 310, p), lerp(440, 441, p))], OR, 6)
        q = eob((tl - 3.4) / 0.5)
        if q > 0:
            rr(d, (190, 650, 670, 740), 26, fill=SOFT)
            tx(d, 430, 695, "✔ Result: report.pdf", 36 * q, DARK)

def sc5(img, d, t, tl):
    # before: tangled; after: tidy via MCP
    ais = [180, 360, 540]; tools_ = [180, 360, 540]
    ay, ty = 330, 700
    if tl < 3:
        tx(d, 360, 255, "Before: custom links", 32, SOFT, stroke=3)
        for i, a in enumerate(ais):
            for j, b in enumerate(tools_):
                p = prog(tl, 0.1 + (i * 3 + j) * 0.1, 0.4)
                if p > 0: ln(d, [(a, ay + 40), (lerp(a, b, p), lerp(ay + 40, ty - 40, p))], RED, 3, cap=False)
    else:
        tx(d, 360, 255, "Now: one plug", 32, OR, stroke=3)
        q = eob((tl - 3) / 0.5)
        plug(d, 360, 515, 0.8 * q); tx(d, 360, 515, "MCP", 30 * q, WHITE, stroke=3)
        for a in ais: ln(d, [(a, ay + 40), (360 + (a - 360) * 0.3, 475)], OR, 4, cap=False)
        for b in tools_: ln(d, [(360 + (b - 360) * 0.3, 555), (b, ty - 40)], OR, 4, cap=False)
    for a in ais: rr(d, (a - 50, ay - 40, a + 50, ay + 40), 14, fill=OR); tx(d, a, ay, "AI", 30, DARK)
    for b, k in zip(tools_, ('cal', 'file', 'db')): icon(d, k, b, ty, 0.8)

def sc6(img, d, t, tl):
    robot(d, 190, 520, 1.1, t, 'oops' if tl > 1.5 else 'normal')
    icon(d, 'file', 540, 430, 1.2)
    if tl > 0.8:
        p = eob((tl - 0.8) / 0.5)
        poly(d, [(540, 300 - 10*p), (610*0+600, 360), (480, 360)], RED) if False else None
        poly(d, [(540, 255), (600, 345), (480, 345)], (255, 214, 102))
        tx(d, 540, 318, "!", 46 * p, DARK)
    if tl > 2.4:
        q = eob((tl - 2.4) / 0.5)
        rr(d, (60, 700, 660, 790), 26, fill=(70, 20, 14), outline=RED, w=5)
        tx(d, 360, 745, "It can act for you", 40 * q, WHITE)

def sc7(img, d, t, tl):
    robot(d, 360, 400, 1.25, t, 'happy', arms=(14, 14))
    if tl > 1.2:
        p = eob((tl - 1.2) / 0.4)
        chip_logo(d, 238, 760, 62 * p); tx(d, 290, 760, "PlainBytes", 44 * p, WHITE, anchor='lm', kind='p')

SC = [sc1, sc2, sc3, sc4, sc5, sc6, sc7]
def render_frame(tn, idx=0):
    t = warp(tn)
    i = max(0, min(6, int(np.searchsorted(OLD_A, t, side='right') - 1)))
    img = BG.copy(); d = ImageDraw.Draw(img)
    r = SC[i](img, d, t, t - OLD_A[i])
    d = r if r is not None else ImageDraw.Draw(img)
    T.draw_title(d, tn); T.draw_caption(d, tn)
    for st_ in OLD_A[1:7]:
        if 0 <= t - st_ < 0.15:
            img = Image.blend(img, Image.new('RGB', img.size, WHITE), 0.25 * (1 - (t - st_) / 0.15))
    return img.reduce(S)

def preview(times, out):
    os.makedirs(out, exist_ok=True)
    for t in times: render_frame(t).save(f"{out}/f_{t:05.2f}.png")

def full(outfile):
    tmp = outfile.replace('.mp4', '_tmp.mp4')
    p = subprocess.Popen(['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-an','-c:v','libx264','-crf','19','-preset','veryfast','-pix_fmt','yuv420p','-movflags','+faststart',tmp], stdin=subprocess.PIPE)
    n = int(DUR * FPS)
    for i in range(n):
        p.stdin.write(render_frame(i / FPS, i).tobytes())
        if i % 200 == 0: print('frame', i, n, flush=True)
    p.stdin.close()
    if p.wait() == 0: os.rename(tmp, outfile); print('done')
    else: print('ffmpeg failed')

if __name__ == '__main__':
    if sys.argv[1] == 'preview': preview([float(x) for x in sys.argv[3:]], sys.argv[2])
    else: full(sys.argv[2])
