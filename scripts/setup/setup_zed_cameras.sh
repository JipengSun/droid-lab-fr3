#!/usr/bin/env bash
# ZED hand-camera setup for DROID laptop (robot conda env).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

echo "=== Step 1: ZED SDK Python API (pyzed) ==="
_ldconfig_cache="$(/sbin/ldconfig -p 2>/dev/null || ldconfig -p 2>/dev/null || true)"
if grep -Fq 'libsl_zed.so' <<< "$_ldconfig_cache"; then
  echo "ZED SDK system libraries: OK"
else
  echo "ZED SDK not installed. Run first:"
  echo "  bash scripts/setup/install_zed_sdk.sh"
  exit 1
fi

if [[ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]]; then
  # shellcheck source=/dev/null
  source "$HOME/anaconda3/etc/profile.d/conda.sh"
else
  echo "ERROR: anaconda not found."
  exit 1
fi

PYTHON="${PYTHON:-$HOME/anaconda3/envs/robot/bin/python}"
if "$PYTHON" -c "import pyzed.sl as sl" 2>/dev/null; then
  echo "pyzed already installed for robot env."
else
  echo "Installing pyzed (will prompt for sudo password)..."
  bash "$ROOT/scripts/setup/install_zed_python_api.sh"
fi
if ! grep -Fq 'libsl_zed.so' <<< "$(/sbin/ldconfig -p 2>/dev/null || true)"; then
  echo "WARN: libsl_zed.so not in ldconfig. If import fails, run:"
  echo "  export LD_LIBRARY_PATH=/usr/local/zed/lib:\$LD_LIBRARY_PATH"
fi
if ! lsusb | grep -qi stereolabs; then
  echo "WARN: No Stereolabs USB device seen. Plug in ZED cameras."
fi

echo ""
echo "=== Step 3: List camera serial numbers ==="
conda activate robot
python "$ROOT/scripts/setup/list_zed_cameras.py"

echo ""
echo "=== Step 4: Test capture ==="
python "$ROOT/scripts/setup/test_zed_cameras.py"

echo ""
echo "=== Next steps ==="
echo "1. Edit droid/misc/parameters.py and set hand_camera_id to your ZED-M serial."
echo "2. Optional third-person IDs: varied_camera_1_id, varied_camera_2_id (ZED 2i)."
echo "3. Run gripper + camera demo:"
echo "     bash droid/franka/launch_gripper.sh          # terminal 1"
echo "     conda activate robot"
echo "     python scripts/demo/robotiq_gripper_demo.py --show-cameras"
