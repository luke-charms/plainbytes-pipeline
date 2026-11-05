# PlainBytes Short: automated pipeline (read this first, every run)

Channel: **PlainBytes**, "tech explained simply" YouTube Shorts. Owner: Lukas.
Goal of a run: pick a trending tech topic, make a ~45-50s vertical explainer Short (animation + natural voice + music), and deliver the final MP4 plus an upload package in chat. **Do not upload to YouTube**; the owner uploads manually.

Files in this folder:
- `setup.sh` installs deps and downloads the offline Kokoro v1.0 voice (run once per session, ~1 min).
- `tts_v1.py` text to speech (Kokoro v1.0, offline, default). `tts.py` old v0.19 voice (fallback). `music.py` music bed. `assemble.sh` final mix + loudness.
- `template_chatgpt_video.py` the working animation template (720x1280, 30fps, PIL frames piped to ffmpeg). Copy and adapt it per topic.
- `used_topics.txt` topics already made. Never repeat one. Append the new topic at the end of a run.

## Run steps

1. **Setup.** Copy this folder to a working directory in the container, `bash setup.sh`. Create `TaskCreate` tasks for the steps below.
2. **Find the topic.** Use WebSearch (several queries, current date): most-searched and trending tech questions this week (Google Trends, YouTube trending tech, "how does X work" / "what is X" surges, big tech news explainers). Prefer a concept a beginner can learn in 45s that is both trending and evergreen (AI tools, Wi-Fi, Bluetooth, VPNs, 5G/6G, passwords, encryption, GPS, QR codes, CPU vs GPU, RAM, cloud, quantum, etc.). Skip anything already in `used_topics.txt`, breaking-news/politics, and anything you cannot explain accurately. Report the 2-3 candidates and why you picked one (with source links).
3. **Script.** 105-125 spoken words (~42-48s). Structure: hook line in first 2s ("X doesn't ... here's what's actually happening"), one everyday analogy, 4-6 short punchy sentences, one "catch"/surprise, end with a teaser for the next topic + "Follow for more." Accurate and simple; no claims you can't support. Write 7 scenes (hook, analogy, mechanism A, mechanism B/loop, scale/how it learned, the catch, outro).
4. **Voice.** `./venv_v1/bin/python tts_v1.py script.txt voiceover.wav 3 1.0` (Kokoro v1.0, speaker 3 = af_heart, the owner's chosen voice; ~25s to generate). The wrapper auto-adds words missing from the dictionary; if it prints `UNKNOWN WORDS`, add them to the `CUSTOM` dict in `tts_v1.py` (phonemes like `'ip': 'ˈ I p ˈ i'`, copy the style of similar entries in `kokoro-multi-lang-v1_0/lexicon-us-en.txt`) and rerun, because skipped words silently vanish from the audio. Never use the system `sherpa-onnx` for this. Check duration is 30-52s (about 3.4 words/second at speed 1.0, so 105-125 words is ~31-37s; a longer script is fine if still accurate); trim/extend and rerun otherwise. Find sentence starts: `ffmpeg -i voiceover.wav -af silencedetect=noise=-35dB:d=0.25 -f null -` (pauses of ~0.4-0.5s are sentence ends; ~0.3s are commas). The old v0.19 voice (`tts.py`, speaker 5, `OLD=1 bash setup.sh`) is fallback only.
5. **Animation.** Copy `template_chatgpt_video.py` to `make_<slug>.py` and adapt:
   - Keep the style: charcoal background, orange/yellow accents, flat 2D, friendly robot, Inter ExtraBold text, titles at top (y~60-120), captions at y~905 (centre), content region y 230-820 only (Shorts UI covers the bottom ~20% and sides).
   - Rewrite the scene functions and `TITLES`. Reuse helpers (`robot`, `bubble`, `phone`, `glow`, `chip_logo`, `ln`, `rr`, `tx`, ...). The first scene hook title is the first sentence (no caption for it).
   - **Sync:** use the time-warp technique: scenes animate on an "old" timeline; `NEW_A`/`OLD_A` anchor lists map voiceover sentence starts (new, real time) to scene boundaries (old). Put captions in real voiceover time (`CAPS`), 1-3 short chunks per sentence. `DUR` = voiceover length + ~1.5s end hold; last scene holds the PlainBytes logo end card.
   - Render previews first (`python3 -I make_x.py preview dir t1 t2 ...`), build a contact sheet and LOOK at it. Fix overlaps with captions/title/safe zones before the full render. One full render only.
6. **Mix.** `python3 music.py bed.wav DUR`; `bash assemble.sh silent.mp4 voiceover.wav bed.wav DUR final.mp4`. Verify with ffprobe (720x1280, h264+aac, duration = DUR) and loudness (~-14 to -16 LUFS integrated, true peak below -1 dBFS).
7. **Deliver.** Write a ready-to-paste text file `PlainBytes_<slug>_upload.txt` next to the MP4 and `SendUserFile` both (MP4 display render, text file display attach). If the owner's Mac folder is connected, also commit both to `~/Desktop/plainbytes/`. File layout (plain text, copy blocks separated by `=====` lines with a label, nothing else inside a block so it pastes cleanly):
   - `TITLE (pick one)`: 3 options, <60 chars, curiosity hook, honest. Mark the recommended one.
   - `DESCRIPTION`: hook line, 2-sentence explanation, subscribe line, "Visuals and narration in this video are AI-generated.", 3 hashtags.
   - `TAGS`: one comma-separated line.
   - `PINNED COMMENT`: asks for topic requests.
   - `SETTINGS`: Not made for kids; **altered/synthetic content disclosure ON**; category Science & Technology; Shorts; visibility Public after a quick watch-through.
   In the chat reply give only: topic + why it was chosen (sources), the three titles, a note that the voice is offline Kokoro, and "upload manually in Studio: Create > Upload videos". Keep it short.
8. **Bookkeeping.** Append `<topic> (published <date>)` to `used_topics.txt` (write it back to the owner's folder if it is connected). Mark the tasks complete.

## Lessons learned (do not relearn)
- The default voice is Kokoro v1.0 in its own venv (`venv_v1`, newest sherpa-onnx). It silently SKIPS words not in its lexicon (e.g. websites, explained, IP): `tts_v1.py` fixes most, read its output for UNKNOWN WORDS.
- The edge-tts (Microsoft) voice sounds good but is unreachable from the cloud container (DNS fails) and flaky on the Mac. Do not retry it.
- (old voice only) sherpa-onnx must be exactly 1.10.46 for Kokoro v0.19 (newer returns empty audio: "No lexicon available").
- Voice id 6 (am_michael) ran much slower than id 5; stick with 5 unless asked.
- The owner's Mac TTS (edge-tts) is unreliable, and the device shell is a Linux VM with no access to the TTS service. Use the offline Kokoro voice in the cloud container.
- Do not leave captions/labels near y>830: they collide with the caption block. Brand row on the end card goes at y~760.
- Pipe raw frames to ffmpeg (no PNG per frame); render to `*_tmp.mp4` then rename on success.
- API uploads are NOT an option: videos.insert from an unaudited Google Cloud project is locked private and cannot be made public (not even in Studio). Manual upload only.
- Browser tools cannot pick files in the native file dialog; do not try to automate the Studio upload.
- Be honest about quality: the animation is code-drawn, not generative video; the voice is synthetic and must be disclosed on upload.
