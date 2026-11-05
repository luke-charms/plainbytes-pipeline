#!/usr/bin/env bash
# One-time setup per session: installs Python deps and downloads the offline Kokoro voice models.
# Usage: bash setup.sh   (run from inside the pipeline folder)
#  - ./venv_v1 + ./kokoro-multi-lang-v1_0 : Kokoro v1.0 voice (DEFAULT, voice af_heart, via tts_v1.py, sherpa-onnx 2.x)
#  - system sherpa-onnx 1.10.46 + ./kokoro-en-v0_19 : old voice (fallback only, via tts.py); pass OLD=1 to install it
set -e
pip install -q --break-system-packages soundfile numpy pillow 2>&1 | grep -v WARNING || true
if [ ! -x venv_v1/bin/python ]; then
  python3 -m venv venv_v1
  ./venv_v1/bin/pip install -q sherpa-onnx soundfile numpy 2>&1 | grep -v WARNING || true
fi
if [ ! -d kokoro-multi-lang-v1_0 ]; then
  curl -sSL -m 300 -o kokoro_v1.tar.bz2 https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/kokoro-multi-lang-v1_0.tar.bz2
  tar xjf kokoro_v1.tar.bz2 && rm kokoro_v1.tar.bz2
fi
if [ "${OLD:-0}" = "1" ] && [ ! -d kokoro-en-v0_19 ]; then
  pip install -q --break-system-packages "sherpa-onnx==1.10.46" 2>&1 | grep -v WARNING || true
  curl -sSL -m 300 -o kokoro.tar.bz2 https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/kokoro-en-v0_19.tar.bz2
  tar xjf kokoro.tar.bz2 && rm kokoro.tar.bz2
fi
./venv_v1/bin/python -c "import sherpa_onnx; print('sherpa-onnx (v1 venv)', sherpa_onnx.__version__)"
which ffmpeg ffprobe
fc-list | grep -qi "Inter-ExtraBold" && echo "font ok" || echo "WARNING: Inter-ExtraBold.otf missing"
