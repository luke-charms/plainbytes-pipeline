#!/usr/bin/env bash
# Hand the finished video to Zapier: force-push a single-commit orphan branch "outbox" containing latest.mp4
# to the PUBLIC repo luke-charms/plainbytes-outbox (Zapier fetches it by raw URL: .../<commit-sha>/latest.mp4).
# The Zap triggers on a new commit on branch "outbox"; the commit message is the video title.
# Also includes description.txt (the YouTube description, plain text) for the Zap to read.
# Usage: bash publish_outbox.sh final.mp4 "Video title (<60 chars)" description.txt
set -euo pipefail
MP4="$(readlink -f "$1")"; TITLE="$2"; DESC="$(readlink -f "$3")"
REMOTE="${OUTBOX_REMOTE:-https://github.com/luke-charms/plainbytes-outbox}"
W="$(mktemp -d)"; cd "$W"
git init -q -b outbox
cp "$MP4" latest.mp4
cp "$DESC" description.txt
printf 'Daily video hand-off for Zapier. Contents are replaced on every run.\n' > README.txt
git add -A
git -c user.name="luke-charms" -c user.email="lukas.al.hjortenfeldt@gmail.com" commit -q -m "$TITLE"
git remote add origin "$REMOTE"
git push -q --force origin outbox
echo "pushed outbox: $TITLE ($(du -h latest.mp4 | cut -f1))"
