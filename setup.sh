#!/usr/bin/env bash
# One-time setup per session: installs Python deps and downloads the offline Kokoro voice model.
# Usage: bash setup.sh   (run from inside the pipeline folder; creates ./kokoro-en-v0_19)
set -e
pip install -q --break-system-packages "sherpa-onnx==1.10.46" soundfile numpy pillow 2>&1 | grep -v WARNING || true
if [ ! -d kokoro-en-v0_19 ]; then
  curl -sSL -m 300 -o kokoro.tar.bz2 https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/kokoro-en-v0_19.tar.bz2
  tar xjf kokoro.tar.bz2 && rm kokoro.tar.bz2
fi
python3 -c "import sherpa_onnx; print('sherpa-onnx', sherpa_onnx.__version__)"
which ffmpeg ffprobe
fc-list | grep -qi "Inter-ExtraBold" && echo "font ok" || echo "WARNING: Inter-ExtraBold.otf missing"
