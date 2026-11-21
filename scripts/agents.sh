#!/usr/bin/env bash
# Start the hackathon agents in tmux on skull-fort so they survive SSH drops.
#   ssh ralph@skull-fort
#   cd ~/Code/capture-to-vault && ./scripts/agents.sh
#   detach: Ctrl-b d      reattach later: tmux attach -t hack      switch window: Ctrl-b <number>
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PARENT="$(dirname "$REPO")"
SESSION="${SESSION:-hack}"
cd "$REPO"

command -v tmux >/dev/null || { echo "Install tmux first (brew install tmux / sudo apt install tmux)"; exit 1; }
[ -f .env ] || cp .env.example .env
grep -q '^GEMINI_API_KEY=.\+' .env || echo ">> GEMINI_API_KEY is empty in $REPO/.env. Agents can start coding; add the key before running anything live (c2v/config.py reloads .env)."

# One git repo, one worktree per lane, so the agents never edit the same checkout.
if ! git rev-parse --git-dir >/dev/null 2>&1; then
  git init -q -b main
  git config user.name >/dev/null || git config user.name "Ralphael Alcober"
  git config user.email >/dev/null || git config user.email "23alcor@users.noreply.github.com"
  git add -A
  git commit -qm "Scaffold: shared spec, schemas, vault index, verifier, scorer, lane stubs"
fi
for lane in a b c; do
  wt="$PARENT/c2v-lane-$lane"
  [ -d "$wt" ] || git worktree add -q -b "lane-$lane" "$wt" main
  ln -sf "$REPO/.env" "$wt/.env"
done

# Shared virtualenv.
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -U pip
  .venv/bin/pip install -q -r requirements.txt
fi
ENV_SETUP="source '$REPO/.venv/bin/activate'; set -a; [ -f .env ] && . ./.env; set +a; export PYTHONPATH=."

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Session '$SESSION' already running. Attach with: tmux attach -t $SESSION"; exit 0
fi

tmux new-session -d -s "$SESSION" -n awake -c "$REPO"
# Keep the machine awake while the session lives (macOS: caffeinate, Linux: systemd-inhibit).
if command -v caffeinate >/dev/null; then
  tmux send-keys -t "$SESSION:awake" "caffeinate -dims" C-m
elif command -v systemd-inhibit >/dev/null; then
  tmux send-keys -t "$SESSION:awake" "systemd-inhibit --what=sleep:idle:handle-lid-switch --why=hackathon sleep infinity" C-m
fi

start_agent() {  # window, lane, command
  local win="$1" lane="$2" cmd="$3" dir="$PARENT/c2v-lane-$2"
  tmux new-window -t "$SESSION" -n "$win" -c "$dir"
  tmux send-keys -t "$SESSION:$win" "$ENV_SETUP" C-m
  if command -v "${cmd%% *}" >/dev/null; then
    tmux send-keys -t "$SESSION:$win" "$cmd \"\$(cat '$REPO/scripts/prompts/lane-$lane.md')\"" C-m
  else
    tmux send-keys -t "$SESSION:$win" "echo '${cmd%% *} not found on PATH. Kickoff prompt: $REPO/scripts/prompts/lane-$lane.md'" C-m
  fi
}

start_agent claude a "claude"
start_agent codex  b "codex"
start_agent cursor c "cursor-agent"

tmux new-window -t "$SESSION" -n run -c "$REPO"
tmux send-keys -t "$SESSION:run" "$ENV_SETUP; python -m pytest -q" C-m

tmux select-window -t "$SESSION:claude"
echo "Started. Attach with: tmux attach -t $SESSION"
