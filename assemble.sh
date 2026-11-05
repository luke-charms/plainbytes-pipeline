#!/usr/bin/env bash
# Mix voice + music under a finished silent video, normalise loudness, mux.
# Usage: bash assemble.sh silent_video.mp4 voiceover.wav bed.wav TOTAL_SECONDS out.mp4
# TOTAL_SECONDS must equal the silent video's duration (voiceover length + ~1.5s end hold).
set -e
V="$1"; VO="$2"; BED="$3"; DUR="$4"; OUT="$5"
FADE_START=$(python3 -c "print(max(0,$DUR-2.5))")
TMP="${OUT%.mp4}_tmp.mp4"
ffmpeg -y -loglevel error -i "$V" -i "$BED" -i "$VO" \
 -filter_complex "[1:a]atrim=0:$DUR,asetpts=N/SR/TB,volume=0.5,afade=t=out:st=$FADE_START:d=2.5[m];[2:a]aresample=44100,apad=pad_dur=3,atrim=0:$DUR[v];[m][v]amix=inputs=2:duration=longest:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11,atrim=0:$DUR[a]" \
 -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k -ac 2 -t "$DUR" "$TMP"
mv "$TMP" "$OUT"
ffprobe -v error -show_entries format=duration,size -of default=nw=1 "$OUT"
