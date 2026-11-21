#!/usr/bin/env bash
# Merge lane branches into main, run tests, then sync main back into every lane.
#   ./scripts/merge.sh a        (just lane A)
#   ./scripts/merge.sh a c b    (recommended order)
# Ask each agent to commit its work before you run this.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PARENT="$(dirname "$REPO")"
cd "$REPO"

git checkout -q main
for lane in "$@"; do
  echo ">> merging lane-$lane"
  git merge --no-edit "lane-$lane"
done

[ -d .venv ] && source .venv/bin/activate
PYTHONPATH=. python -m pytest -q

for lane in a b c; do
  wt="$PARENT/c2v-lane-$lane"
  if [ -n "$(git -C "$wt" status --porcelain)" ]; then
    echo ">> lane-$lane has uncommitted changes; not syncing it (commit there, then re-run)"
  else
    git -C "$wt" merge -q --no-edit main && echo ">> lane-$lane synced with main"
  fi
done
