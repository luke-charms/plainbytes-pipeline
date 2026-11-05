#!/usr/bin/env bash
# Once-per-day guard so a repeated prompt/turn never makes a second video.
#   bash run_lock.sh check   -> exit 3 if a run already started/finished today (Copenhagen date)
#   bash run_lock.sh start   -> write the lock (status started) and push it to main
#   bash run_lock.sh done    -> mark today's lock done and push it
# A "started" lock older than 90 minutes counts as stale (crashed run) and does not block.
set -uo pipefail
cd "$(dirname "$0")"
F=run_lock.txt
TODAY="$(TZ=Europe/Copenhagen date +%F)"; NOW="$(date +%s)"
git pull -q --rebase origin main 2>/dev/null || true
cmd="${1:-check}"
push_lock() {
  git add "$F"
  git -c user.name="luke-charms" -c user.email="luke-charms@users.noreply.github.com" commit -q -m "run lock: $TODAY $1" || true
  git push -q origin main 2>/dev/null || { git pull -q --rebase origin main 2>/dev/null; git push -q origin main 2>/dev/null || echo "warning: could not push lock"; }
}
case "$cmd" in
  check)
    if [ -f "$F" ]; then
      read -r D S E < "$F"
      if [ "$D" = "$TODAY" ]; then
        if [ "$S" = "done" ] || [ $((NOW-E)) -lt 5400 ]; then echo "ALREADY RAN TODAY ($D $S)"; exit 3; fi
      fi
    fi
    echo "no lock for today: proceed";;
  start) echo "$TODAY started $NOW" > "$F"; push_lock started; echo "lock written";;
  done)  echo "$TODAY done $NOW" > "$F"; push_lock done; echo "lock marked done";;
  *) echo "usage: run_lock.sh check|start|done"; exit 2;;
esac
