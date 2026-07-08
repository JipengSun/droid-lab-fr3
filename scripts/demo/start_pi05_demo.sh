#!/usr/bin/env bash
# Fresh-start π₀.5-DROID policy demo (language/voice → arm + gripper via NUC).
#
# Prerequisite: Desk → Unlock brakes → Activate FCI
#
# Usage (workstation):
#   bash scripts/demo/start_pi05_demo.sh
#   bash scripts/demo/start_pi05_demo.sh --dry-run
#   bash scripts/demo/start_pi05_demo.sh --input-mode voice
#
set -euo pipefail
exec 1>&2

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OPENPI="${OPENPI_ROOT:-${HOME}/Desktop/openpi}"
cd "$ROOT"

source "${HOME}/anaconda3/etc/profile.d/conda.sh" 2>/dev/null || source ~/miniconda3/etc/profile.d/conda.sh
conda activate robot
export PATH="${HOME}/.local/bin:${PATH}"
export PYTHONUNBUFFERED=1

echo "=== [1/6] Clean slate ==="
bash scripts/setup/openpi_session_reset.sh

echo ""
echo "=== [2/6] FCI check (Desk must be active) ==="
if ! nc -zv -w 3 192.168.1.11 1337 2>&1; then
  echo "ERROR: FCI not active. Open https://192.168.1.11/desk/ → Activate FCI, then re-run."
  exit 1
fi

echo ""
echo "=== [3/6] Start NUC stack (gripper + Polymetis + zerorpc) ==="
bash scripts/setup/openpi_start_nuc_stack.sh

echo ""
echo "=== [4/6] Arm smoke test ==="
python scripts/demo/arm_smoke_test.py

echo ""
echo "=== [5/6] Start π₀.5 policy server (background) ==="
if [[ ! -f "${OPENPI}/scripts/serve_pi05_droid.sh" ]]; then
  echo "ERROR: OpenPI not found at ${OPENPI}"
  exit 1
fi

# Kill any leftover policy server on :8000
if command -v fuser >/dev/null 2>&1; then
  fuser -k 8000/tcp 2>/dev/null || true
fi
sleep 1

POLICY_LOG="/tmp/pi05_policy_server.log"
nohup bash "${OPENPI}/scripts/serve_pi05_droid.sh" >>"${POLICY_LOG}" 2>&1 &
POLICY_PID=$!
echo "Policy server PID ${POLICY_PID}, log: ${POLICY_LOG}"

echo -n "Waiting for :8000"
for _ in $(seq 1 120); do
  if nc -z localhost 8000 2>/dev/null; then
    echo " OK"
    break
  fi
  if ! kill -0 "${POLICY_PID}" 2>/dev/null; then
    echo ""
    echo "ERROR: policy server exited. Last log lines:"
    tail -20 "${POLICY_LOG}" || true
    exit 1
  fi
  echo -n "."
  sleep 2
done

if ! nc -z localhost 8000 2>/dev/null; then
  echo ""
  echo "ERROR: policy server did not start on :8000 within 240s"
  tail -20 "${POLICY_LOG}" || true
  exit 1
fi

echo ""
echo "=== [6/6] Start rollout client ==="
DEFAULT_ARGS=(--external-camera left --input-mode both --no-reset)
if [[ $# -eq 0 ]]; then
  set -- "${DEFAULT_ARGS[@]}"
fi

echo "Policy server: ws://127.0.0.1:8000 (leave running in background)"
echo "Rollout: python scripts/demo/openpi_pi05_rollout.py $*"
echo ""

exec python scripts/demo/openpi_pi05_rollout.py "$@"
