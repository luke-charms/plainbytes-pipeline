# PlainBytes Short: automated pipeline (read this first, every run)

Channel: **PlainBytes**, "tech explained simply" YouTube Shorts. Owner: Lukas.
Goal of a run: pick a trending tech topic, make a ~45-50s vertical explainer Short (animation + natural voice + music), and deliver the final MP4 plus an upload package in chat. **Do not upload to YouTube**; the owner uploads manually.

Files in this folder:
- `setup.sh` installs deps and downloads the offline Kokoro voice (run once per session).
- `tts.py` text to speech (Kokoro, sherpa-onnx 1.10.46, offline). `music.py` music bed. `assemble.sh` final mix + loudness.
- `template_chatgpt_video.py` the working animation template (720x1280, 30fps, PIL frames piped to ffmpeg). Copy and adapt it per topic.
- `used_topics.txt` topics already made. Never repeat one. Append the new topic at the end of a run.

## Run steps

1. **Setup.** Copy this folder to a working directory in the container, `bash setup.sh`. Create `TaskCreate` tasks for the steps below.
2. **Find the topic.** Use WebSearch (several queries, current date): most-searched and trending tech questions this week (Google Trends, YouTube trending tech, "how does X work" / "what is X" surges, big tech news explainers). Prefer a concept a beginner can learn in 45s that is both trending and evergreen (AI tools, Wi-Fi, Bluetooth, VPNs, 5G/6G, passwords, encryption, GPS, QR codes, CPU vs GPU, RAM, cloud, quantum, etc.). Skip anything already in `used_topics.txt`, breaking-news/politics, and anything you cannot explain accurately. Report the 2-3 candidates and why you picked one (with source links).
3. **Script.** 105-125 spoken words (~42-48s). Structure: hook line in first 2s ("X doesn't ... here's what's actually happening"), one everyday analogy, 4-6 short punchy sentences, one "catch"/surprise, end with a teaser for the next topic + "Follow for more." Accurate and simple; no claims you can't support. Write 7 scenes (hook, analogy, mechanism A, mechanism B/loop, scale/how it learned, the catch, outro).
4. **Voice.** `python3 tts.py script.txt voiceover.wav 5 1.05` (speaker 5 = am_adam). Check duration is 38-52s; if outside, trim/extend the script and rerun. Find sentence starts: `ffmpeg -i voiceover.wav -af silencedetect=noise=-35dB:d=0.25 -f null -` (pauses of ~0.4-0.5s are sentence ends; ~0.3s are commas).
5. **Animation.** Copy `template_chatgpt_video.py` to `make_<slug>.py` and adapt:
   - Keep the style: charcoal background, orange/yellow accents, flat 2D, friendly robot, Inter ExtraBold text, titles at top (y~60-120), captions at y~905 (centre), content region y 230-820 only (Shorts UI covers the bottom ~20% and sides).
   - Rewrite the scene functions and `TITLES`. Reuse helpers (`robot`, `bubble`, `phone`, `glow`, `chip_logo`, `ln`, `rr`, `tx`, ...). The first scene hook title is the first sentence (no caption for it).
   - **Sync:** use the time-warp technique: scenes animate on an "old" timeline; `NEW_A`/`OLD_A` anchor lists map voiceover sentence starts (new, real time) to scene boundaries (old). Put captions in real voiceover time (`CAPS`), 1-3 short chunks per sentence. `DUR` = voiceover length + ~1.5s end hold; last scene holds the PlainBytes logo end card.
   - Render previews first (`python3 -I make_x.py preview dir t1 t2 ...`), build a contact sheet and LOOK at it. Fix overlaps with captions/title/safe zones before the full render. One full render only.
6. **Mix.** `python3 music.py bed.wav DUR`; `bash assemble.sh silent.mp4 voiceover.wav bed.wav DUR final.mp4`. Verify with ffprobe (720x1280, h264+aac, duration = DUR) and loudness (~-14 to -16 LUFS integrated, true peak below -1 dBFS).
7. **Deliver.** `SendUserFile` the final MP4 (display render). In the reply give: topic + why it was chosen (sources), and the upload package: 3 title options (<60 chars, curiosity hook, honest), description (hook line, 2-sentence explanation, subscribe line, "Visuals and narration in this video are AI-generated.", 3 hashtags), tags, pinned comment (asks for topic requests), settings (Not made for kids; **turn ON the altered/synthetic content disclosure**; category Science & Technology). Note the voice is the offline Kokoro voice. Keep it short.
8. **Bookkeeping.** Append `<topic> (published <date>)` to `used_topics.txt` (write it back to the owner's folder if it is connected). Mark the tasks complete.

## Lessons learned (do not relearn)
- sherpa-onnx must be exactly 1.10.46 for Kokoro v0.19 (newer returns empty audio: "No lexicon available").
- Voice id 6 (am_michael) ran much slower than id 5; stick with 5 unless asked.
- The owner's Mac TTS (edge-tts) is unreliable, and the device shell is a Linux VM with no access to the TTS service. Use the offline Kokoro voice in the cloud container.
- Do not leave captions/labels near y>830: they collide with the caption block. Brand row on the end card goes at y~760.
- Pipe raw frames to ffmpeg (no PNG per frame); render to `*_tmp.mp4` then rename on success.
- Be honest about quality: the animation is code-drawn, not generative video; the voice is synthetic and must be disclosed on upload.
