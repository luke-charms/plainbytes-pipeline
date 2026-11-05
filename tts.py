#!/usr/bin/env python3
"""Offline text-to-speech with Kokoro (sherpa-onnx 1.10.46).
Usage: python3 tts.py script.txt out.wav [speaker_id=5] [speed=1.05]
Male voices: 5=am_adam, 6=am_michael, 9=bm_george, 10=bm_lewis. (6 ran noticeably slower/longer in testing.)
Female: 0=af, 1=af_bella, 2=af_nicole, 3=af_sarah, 4=af_sky, 7=bf_emma, 8=bf_isabella.
NOTE: newer sherpa-onnx (>=1.12 / 2.x) needs a lexicon for this model and returns empty audio. Keep 1.10.46.
"""
import sys, time, soundfile as sf, sherpa_onnx

m = 'kokoro-en-v0_19'
cfg = sherpa_onnx.OfflineTtsConfig(
    model=sherpa_onnx.OfflineTtsModelConfig(
        kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(
            model=f'{m}/model.onnx', voices=f'{m}/voices.bin',
            tokens=f'{m}/tokens.txt', data_dir=f'{m}/espeak-ng-data'),
        num_threads=2, provider='cpu'),
    max_num_sentences=1)
tts = sherpa_onnx.OfflineTts(cfg)
text = open(sys.argv[1]).read().replace('\n', ' ')
sid = int(sys.argv[3]) if len(sys.argv) > 3 else 5
speed = float(sys.argv[4]) if len(sys.argv) > 4 else 1.05
t = time.time()
a = tts.generate(text, sid=sid, speed=speed)
if len(a.samples) == 0:
    sys.exit('TTS returned no audio (check sherpa-onnx version == 1.10.46)')
sf.write(sys.argv[2], a.samples, a.sample_rate)
print('duration_s', round(len(a.samples) / a.sample_rate, 2), 'gen_s', round(time.time() - t, 1))
