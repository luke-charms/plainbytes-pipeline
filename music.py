#!/usr/bin/env python3
"""Synthesize a light upbeat music bed. Usage: python3 music.py out.wav DURATION_SECONDS"""
import sys, wave
import numpy as np

out_path, T = sys.argv[1], float(sys.argv[2]) + 1.0   # a second of slack; the mix trims it
sr = 44100
n = int(sr * T)
out = np.zeros(n)
bpm = 112
beat = 60 / bpm
midi = lambda m: 440 * 2 ** ((m - 69) / 12)


def add(freq, start, dur, amp, decay=9, harm=(1, .35, .15)):
    i0 = int(start * sr)
    if i0 >= n:
        return
    m = int(sr * dur)
    tt = np.arange(m) / sr
    w = sum(h * np.sin(2 * np.pi * freq * (k + 1) * tt) for k, h in enumerate(harm))
    seg = amp * np.exp(-tt * decay) * w
    e = min(m, n - i0)
    out[i0:i0 + e] += seg[:e]


chords = [(57, [69, 72, 76]), (53, [65, 69, 72]), (48, [64, 67, 72]), (55, [62, 67, 71])]  # Am F C G
b, k = 0.0, 0
while b * beat < T:
    root, tones = chords[k % 4]
    t0 = b * beat
    for q in range(4):
        add(midi(root - 12), t0 + q * beat, beat * 0.9, 0.22, decay=5, harm=(1, .25))
    for e in range(8):
        add(midi(tones[e % 3]), t0 + e * beat / 2, 0.3, 0.10, decay=10)
    b += 4
    k += 1
bb = 0
while bb * beat < T:
    t0 = bb * beat
    i0 = int(t0 * sr)
    m = int(sr * 0.18)
    tt = np.arange(m) / sr
    kick = 0.28 * np.sin(2 * np.pi * (55 + 90 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 16)
    e = min(m, n - i0)
    out[i0:i0 + e] += kick[:e]
    j0 = int((t0 + beat / 2) * sr)
    mh = int(sr * 0.04)
    hat = 0.05 * np.random.RandomState(int(bb)).randn(mh) * np.exp(-np.arange(mh) / sr * 80)
    e2 = min(mh, n - j0)
    if e2 > 0:
        out[j0:j0 + e2] += hat[:e2]
    bb += 1
out /= np.max(np.abs(out))
out *= 0.30
w = wave.open(out_path, 'wb')
w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
w.writeframes((out * 32767).astype(np.int16).tobytes())
w.close()
print('music ok', out_path)
