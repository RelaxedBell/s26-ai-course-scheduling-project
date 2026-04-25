#!/usr/bin/env bash
# Starts a tmux session with both long-lived dev processes:
#   - Left pane:  Rivanna LLM warmup (allocates GPU + opens SSH tunnel)
#   - Right pane: uvicorn dev server (waits for tunnel, then starts)
#
# Usage:    scripts/dev_start.sh
# Reattach: tmux attach -t ai-dev
# Stop all: tmux kill-session -t ai-dev   (also releases the SLURM allocation)
#
# Requires RIVANNA_ACCOUNT to be exported (or set in your shell rc).

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION="${TMUX_SESSION:-ai-dev}"
VENV_ACTIVATE="${PROJECT_DIR}/.venv/bin/activate"
APP_URL="http://localhost:8000"

if ! command -v tmux >/dev/null; then
  echo "tmux is required (sudo pacman -S tmux)" >&2
  exit 1
fi

if [ ! -f "${VENV_ACTIVATE}" ]; then
  echo "No venv at ${VENV_ACTIVATE}. Create one with: uv venv .venv" >&2
  exit 1
fi

if [ -z "${RIVANNA_ACCOUNT:-}" ]; then
  echo "RIVANNA_ACCOUNT not set. Export it first (your SLURM allocation name)." >&2
  exit 1
fi

if tmux has-session -t "${SESSION}" 2>/dev/null; then
  echo "Session '${SESSION}' already running — attaching."
  exec tmux attach -t "${SESSION}"
fi

# Left pane: Rivanna warmup. Trailing `bash` keeps the pane alive after exit
# so error output stays visible instead of vanishing.
tmux new-session -d -s "${SESSION}" -c "${PROJECT_DIR}" -n dev \
  "RIVANNA_ACCOUNT='${RIVANNA_ACCOUNT}' scripts/rivanna_warmup.sh; \
   echo; echo '[warmup exited — Ctrl-D to close pane]'; bash"

# Right pane: poll the tunnel, then start uvicorn. If the warmup never comes
# up the loop just keeps polling; kill the session to stop it.
tmux split-window -h -t "${SESSION}:dev" -c "${PROJECT_DIR}" \
  "source '${VENV_ACTIVATE}'; \
   echo 'Waiting for Rivanna LLM tunnel on localhost:11434...'; \
   until curl -fsS --max-time 2 http://localhost:11434/api/tags >/dev/null 2>&1; do \
     sleep 3; \
   done; \
   echo 'Tunnel up. Starting uvicorn.'; \
   exec uvicorn src.api.app:app --reload"

tmux select-pane -L -t "${SESSION}:dev"

# Open the app in a browser once uvicorn is likely up. Backgrounded so it
# doesn't block the attach below.
( sleep 12
  if command -v xdg-open >/dev/null; then
    xdg-open "${APP_URL}" >/dev/null 2>&1 || true
  fi
) &

cat <<MSG
Started tmux session '${SESSION}':
  left  pane: rivanna_warmup.sh (Ctrl-C in pane releases the GPU)
  right pane: uvicorn (auto-starts when tunnel is ready)

Detach: Ctrl-B then D     Stop everything: tmux kill-session -t ${SESSION}
Browser will open ${APP_URL} in ~12s.
MSG

exec tmux attach -t "${SESSION}"
