#!/usr/bin/env bash
# Trig Ops (delivery dashboard) one-command deploy.
# Usage:  bash deploy.sh "what changed"
# Requires: the trig-delivery Netlify site linked to github.com/trig-modern/trig-ops
#           (Netlify → Site config → Build & deploy → linked repo). Then push = live.
set -e
cd "$(dirname "$0")"
rm -f .git/index.lock                       # clear any stale lock
echo "→ staging changes…"
git add -A
git commit -m "${1:-Update Trig Ops}" || echo "(nothing new to commit)"
echo "→ syncing with origin (rebase, never force)…"
git pull --rebase --autostash origin main
echo "→ pushing…"
git push origin main
echo "✅ Pushed to github.com/trig-modern/trig-ops."
echo "   If the trig-delivery Netlify site is git-linked, it auto-publishes in ~30s."
