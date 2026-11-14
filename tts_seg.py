#!/usr/bin/env python3
"""Kokoro v1.0 (multi-lang) offline TTS via sherpa-onnx >=2.0. Usage: ./venv_v1/bin/python tts_v1.py script.txt out.wav [sid=3] [speed=1.0]
Missing English words are auto-added to an extra lexicon (suffix rules) so none are skipped."""
import re, sys, os, time, sherpa_onnx, soundfile as sf
D = os.environ.get('KOKORO_V1_DIR', 'kokoro-multi-lang-v1_0') + '/'
CUSTOM = {'phone\'s': 'f ˈ O n z', 'company\'s': 'k ˈ ʌ m p ᵊ n i z', 'qr': 'k j ˈ u ˈ ɑ ɹ', 'server\'s': 's ˈ ɜ ɹ v ə ɹ z', 'vpn': 'v ˈ i p ˈ i ˈ ɛ n', 'https': 'ˈ A ʧ t ˈ i t ˈ i p ˈ i ˈ ɛ s', 'ip': 'ˈ I p ˈ i', 'gps': 'ʤ ˈ i p ˈ i ˈ ɛ s', 'cpu': 's ˈ i p ˈ i j ˈ u', 'gpu': 'ʤ ˈ i p ˈ i j ˈ u', 'that\'s': 'ð ˈ æ t s', 'computer\'s': 'k ə m p j ˈ u ɾ ə ɹ z', 'wi': 'w ˈ I', 'fi': 'f ˈ I', 'plainbytes': 'p l ˈ A n b ˈ I t s'}  # extend when a run reports unknown words
lex = {}
for line in open(D + 'lexicon-us-en.txt', encoding='utf8'):
    p = line.rstrip('\n').split(' ', 1)
    if len(p) == 2: lex[p[0].lower()] = p[1]
VOICELESS = ('p', 't', 'k', 'f', 'θ', 's', 'ʃ')
def last(ph): return ph.split(' ')[-1]
def suffix(stem_ph, kind):
    l = last(stem_ph)
    if kind == 's':
        if l in ('s', 'z', 'ʃ', 'ʒ', 'ʧ', 'ʤ'): return stem_ph + ' ɪ z'
        return stem_ph + (' s' if l in VOICELESS else ' z')
    if kind == 'd':
        if l in ('t', 'd'): return stem_ph + ' ɪ d'
        return stem_ph + (' t' if l in VOICELESS else ' d')
def guess(w):
    if w in CUSTOM: return CUSTOM[w]
    for suf, kind, cut in (('ies', 's', 3), ('es', 's', 2), ('s', 's', 1), ('ed', 'd', 2), ('d', 'd', 1)):
        if w.endswith(suf):
            for stem in ((w[:-cut] + 'y') if suf == 'ies' else None, w[:-cut], w[:-cut] + 'e'):
                if stem and stem in lex: return suffix(lex[stem], kind)
    return None
text = open(sys.argv[1], encoding='utf8').read().strip()
extra, unknown = {}, []
for w in set(re.findall(r"[A-Za-z']+", text.lower())):
    if w not in lex:
        g = guess(w)
        if g: extra[w] = g
        else: unknown.append(w)
if unknown: print('UNKNOWN WORDS (add to CUSTOM, else they are skipped):', unknown)
extra.setdefault('zzqx', 'z'); open('extra_lexicon.txt', 'w', encoding='utf8').write(''.join(f'{w} {p}\n' for w, p in extra.items()))
print('auto-added:', extra)
sid = int(sys.argv[3]) if len(sys.argv) > 3 else 3
speed = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
cfg = sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(vits=sherpa_onnx.OfflineTtsVitsModelConfig(),
    kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(model=D + 'model.onnx', voices=D + 'voices.bin', tokens=D + 'tokens.txt',
    data_dir=D + 'espeak-ng-data', dict_dir=D + 'dict', lexicon=D + 'lexicon-us-en.txt,extra_lexicon.txt', lang='en-us'), num_threads=4),
    max_num_sentences=1)
tts = sherpa_onnx.OfflineTts(cfg)
import numpy as np, json
lines=[l.strip() for l in text.split('\n') if l.strip()]
parts=[];starts=[];ends=[];cur=0.0;sr=None
for l in lines:
    a=tts.generate(l,sid=sid,speed=speed); sr=a.sample_rate
    x=np.array(a.samples); gap=np.zeros(int(0.28*sr))
    starts.append(cur); cur+=len(x)/sr; ends.append(cur); cur+=0.28
    parts+= [x,gap]
sf.write(sys.argv[2],np.concatenate(parts[:-1]),sr)
json.dump({'starts':starts,'ends':ends,'lines':lines},open(sys.argv[2]+'.json','w'))
print(starts,ends,cur)
