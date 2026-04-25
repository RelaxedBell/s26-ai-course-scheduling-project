#!/usr/bin/env bash
# Allocates a Rivanna GPU node, starts `ollama serve` on it, and opens a
# local SSH tunnel so localhost:11434 reaches that node. The project's
# OllamaClient (auto backend, src/llm/llm_client.py:244) probes
# localhost:11434 first, so no code changes are needed — just run this
# script before launching the app.
#
# Usage:  scripts/rivanna_warmup.sh
# Stop:   Ctrl-C  (cancels the SLURM job and closes the tunnel)
#
# Prereqs:
#   - `ssh rivanna` works from this machine (set up ~/.ssh/config with
#     ProxyJump through portal.cs.virginia.edu).
#   - You have a Rivanna SLURM allocation (set RIVANNA_ACCOUNT below).
#   - First run will install ollama into ~/bin on Rivanna automatically.
#
# Required env:
#   RIVANNA_ACCOUNT     SLURM allocation name (e.g. cs-4710-sp26)
#
# Optional env (defaults shown):
#   RIVANNA_HOST=rivanna           ssh alias for the login node
#   RIVANNA_PARTITION=gpu
#   RIVANNA_GRES=gpu:1
#   RIVANNA_TIME=04:00:00          wall time — set to cover demo + buffer
#   OLLAMA_MODEL=qwen2.5:7b
#   LOCAL_PORT=11434

set -euo pipefail

: "${RIVANNA_ACCOUNT:?Set RIVANNA_ACCOUNT to your SLURM allocation name}"
SSH_HOST="${RIVANNA_HOST:-rivanna}"
PARTITION="${RIVANNA_PARTITION:-gpu}"
GRES="${RIVANNA_GRES:-gpu:1}"
TIME="${RIVANNA_TIME:-04:00:00}"
MODEL="${OLLAMA_MODEL:-qwen2.5:7b}"
LOCAL_PORT="${LOCAL_PORT:-11434}"
REMOTE_PORT=11434

# Bail early if the local port is already taken — would mask the tunnel
# silently and the app would talk to the wrong server.
if (command -v lsof >/dev/null && lsof -i ":${LOCAL_PORT}" -sTCP:LISTEN >/dev/null 2>&1) \
   || (command -v ss >/dev/null && ss -ltn "sport = :${LOCAL_PORT}" | grep -q LISTEN); then
  echo "ERROR: localhost:${LOCAL_PORT} is already in use."
  echo "  Stop whatever is bound (probably a previous warmup or local ollama)"
  echo "  or set LOCAL_PORT=<other> and OLLAMA_BASE_URL accordingly."
  exit 1
fi

JOB_NAME="ai-llm-$(date +%s)-$$"
REMOTE_SLURM="/tmp/${JOB_NAME}.slurm"
REMOTE_LOG="/tmp/${JOB_NAME}.out"

echo "[1/5] Checking ollama on ${SSH_HOST}..."
if ! ssh "${SSH_HOST}" 'test -x "$HOME/bin/ollama"'; then
  echo "  -> not found; installing into ~/bin (one-time)..."
  ssh "${SSH_HOST}" bash <<'INSTALL'
set -e
mkdir -p "$HOME/bin"
cd "$HOME"
# Pinned to a GitHub release because ollama.com/download/ no longer serves
# the .tgz layout this script expects ($HOME/bin/ollama + $HOME/lib/...).
curl -fsSL https://github.com/ollama/ollama/releases/download/v0.5.7/ollama-linux-amd64.tgz -o /tmp/ollama.tgz
tar -xzf /tmp/ollama.tgz
rm /tmp/ollama.tgz
test -x "$HOME/bin/ollama"
INSTALL
fi
echo "  -> ok"

echo "[2/5] Submitting SLURM job (${JOB_NAME})..."
JOB_ID=$(ssh "${SSH_HOST}" bash <<EOF
set -e
cat > "${REMOTE_SLURM}" <<'SLURM'
#!/bin/bash
#SBATCH --job-name=${JOB_NAME}
#SBATCH --partition=${PARTITION}
#SBATCH --gres=${GRES}
#SBATCH --account=${RIVANNA_ACCOUNT}
#SBATCH --time=${TIME}
#SBATCH --output=${REMOTE_LOG}
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G

export PATH="\$HOME/bin:\$PATH"
export OLLAMA_HOST=0.0.0.0:${REMOTE_PORT}
export OLLAMA_MODELS="\$HOME/.ollama/models"

ollama serve >> ${REMOTE_LOG}.serve 2>&1 &
OLLAMA_PID=\$!
sleep 8

# Pull model if missing (first run on this account), then load into VRAM.
ollama pull ${MODEL} >> ${REMOTE_LOG}.pull 2>&1 || true
ollama run ${MODEL} "ready" </dev/null >> ${REMOTE_LOG}.warm 2>&1 || true

wait \$OLLAMA_PID
SLURM
sbatch --parsable "${REMOTE_SLURM}"
EOF
)
echo "  -> job id: ${JOB_ID}"

echo "[3/5] Waiting for SLURM to assign a node..."
NODE=""
LAST_STATE=""
while [ -z "${NODE}" ]; do
  STATE=$(ssh "${SSH_HOST}" "squeue -j ${JOB_ID} -h -o '%T'" 2>/dev/null | tr -d ' \n' || true)
  case "${STATE}" in
    "")
      echo "  -> job no longer in queue; check ${REMOTE_LOG} on ${SSH_HOST}"
      exit 1
      ;;
    RUNNING)
      NODE=$(ssh "${SSH_HOST}" "squeue -j ${JOB_ID} -h -o '%N'" | tr -d ' \n')
      ;;
    FAILED|CANCELLED|TIMEOUT|OUT_OF_MEMORY|NODE_FAIL)
      echo "  -> SLURM state: ${STATE}"
      exit 1
      ;;
    *)
      [ "${STATE}" != "${LAST_STATE}" ] && echo "  -> ${STATE}..."
      LAST_STATE="${STATE}"
      sleep 5
      ;;
  esac
done
echo "  -> node: ${NODE}"

cleanup() {
  echo ""
  echo "[!] Releasing allocation (scancel ${JOB_ID})..."
  if [ -n "${TUNNEL_PID:-}" ]; then
    kill "${TUNNEL_PID}" 2>/dev/null || true
  fi
  ssh "${SSH_HOST}" "scancel ${JOB_ID}" 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

echo "[4/5] Opening tunnel localhost:${LOCAL_PORT} -> ${NODE}:${REMOTE_PORT}..."
ssh -N -L "${LOCAL_PORT}:${NODE}:${REMOTE_PORT}" "${SSH_HOST}" &
TUNNEL_PID=$!
sleep 2

echo "[5/5] Waiting for ollama to respond (model load can take 30-60s)..."
READY=0
for i in $(seq 1 60); do
  if curl -fsS --max-time 3 "http://localhost:${LOCAL_PORT}/api/tags" >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 3
done

if [ "${READY}" -ne 1 ]; then
  echo "  -> timed out. Check the SLURM log: ssh ${SSH_HOST} 'tail ${REMOTE_LOG}*'"
  cleanup
fi

cat <<READY

  ============================================================
   READY. Ollama on Rivanna is reachable at localhost:${LOCAL_PORT}.
   Model: ${MODEL}   Node: ${NODE}   Job: ${JOB_ID}
   Wall time: ${TIME}

   Smoke test:
     curl http://localhost:${LOCAL_PORT}/api/tags

   Run the app as normal — create_llm_client(backend="auto")
   will detect this tunnel and use it automatically:
     uvicorn src.api.app:app --reload

   Press Ctrl-C here to release the GPU allocation.
  ============================================================

READY

wait "${TUNNEL_PID}"
