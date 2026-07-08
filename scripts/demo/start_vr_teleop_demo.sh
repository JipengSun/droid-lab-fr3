#!/usr/bin/env bash
# Fresh-start VR teleop demo (Quest → arm + gripper via NUC).
#
# Prerequisite: Desk → Unlock brakes → Activate FCI
#
# Usage (workstation):
#   bash scripts/demo/start_vr_teleop_demo.sh
#   bash scripts/demo/start_vr_teleop_demo.sh --no-reset-arm   # skip arm homing
#
set -euo pipefail
exec 1>&2

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

source "${HOME}/anaconda3/etc/profile.d/conda.sh" 2>/dev/null || source ~/miniconda3/etc/profile.d/conda.sh
conda activate robot
export PATH="${HOME}/platform-tools:${PATH}"
export PYTHONUNBUFFERED=1

echo "=== [1/5] Clean slate ==="
bash scripts/setup/openpi_session_reset.sh

echo ""
echo "=== [2/5] FCI check (Desk must be active) ==="
if ! nc -zv -w 3 192.168.1.11 1337 2>&1; then
  echo "ERROR: FCI not active. Open https://192.168.1.11/desk/ → Activate FCI, then re-run."
  exit 1
fi

echo ""
echo "=== [3/5] Start NUC stack (gripper + Polymetis + zerorpc) ==="
bash scripts/setup/openpi_start_nuc_stack.sh

echo ""
echo "=== [4/5] Arm smoke test ==="
python scripts/demo/arm_smoke_test.py

echo ""
echo "=== [5/5] Quest adb ==="
if ! adb devices | grep -q $'\tdevice'; then
  echo "ERROR: no authorized Quest on adb. Put on headset → Allow USB debugging."
  adb devices
  exit 1
fi
adb shell am broadcast -a com.oculus.vrpowermanager.prox_close 2>/dev/null || true

echo ""
echo "=== Starting VR teleop (hand + third-person cameras) ==="
exec python scripts/demo/vr_teleop_demo.py --show-cameras "$@"
