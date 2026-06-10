#!/usr/bin/env bash
# Launch Polymetis gRPC gripper server + Robotiq 2F modbus client.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
POLYMETIS_DIR="$ROOT/droid/fairo/polymetis/polymetis"
LAUNCH_GRIPPER="$POLYMETIS_DIR/python/scripts/launch_gripper.py"

if [[ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]]; then
  # shellcheck source=/dev/null
  source "$HOME/anaconda3/etc/profile.d/conda.sh"
elif [[ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]]; then
  # shellcheck source=/dev/null
  source "$HOME/miniconda3/etc/profile.d/conda.sh"
else
  echo "ERROR: conda not found."
  exit 1
fi

if conda env list | grep -qE '^polymetis-local '; then
  conda activate polymetis-local
else
  echo "ERROR: conda env 'polymetis-local' not found."
  echo "Install it with:"
  echo "  bash $ROOT/scripts/setup/install_polymetis_gripper.sh"
  exit 1
fi

if [[ ! -f "$LAUNCH_GRIPPER" ]]; then
  echo "ERROR: launch_gripper.py not found at $LAUNCH_GRIPPER"
  exit 1
fi

# Kill stale gripper processes (ignore errors if none running).
pkill -9 -f launch_gripper.py 2>/dev/null || true
pkill -9 gripper 2>/dev/null || true

# Resolve Robotiq RS485 USB port.
GRIPPER_COMPORT="${GRIPPER_COMPORT:-}"
if [[ -z "$GRIPPER_COMPORT" ]]; then
  shopt -s nullglob
  ports=(/dev/ttyUSB* /dev/ttyACM*)
  shopt -u nullglob
  if ((${#ports[@]} == 0)); then
    echo "ERROR: No serial device found (/dev/ttyUSB* or /dev/ttyACM*)."
    echo ""
    echo "The Robotiq gripper needs its RS485-USB adapter plugged into this machine."
    echo "Check:"
    echo "  1. Gripper power and USB cable to the laptop (not only the NUC)"
    echo "  2. Run: lsusb   (look for FTDI / Prolific / CP210x / QinHeng)"
    echo "  3. After plugging in, run: ls /dev/ttyUSB* /dev/ttyACM*"
    echo ""
    echo "If the port is different, set it explicitly, e.g.:"
    echo "  GRIPPER_COMPORT=/dev/ttyUSB1 bash $0"
    exit 1
  elif ((${#ports[@]} == 1)); then
    GRIPPER_COMPORT="${ports[0]}"
  else
    echo "Multiple serial devices found:"
    printf '  %s\n' "${ports[@]}"
    echo "Set the gripper port explicitly, e.g.:"
    echo "  GRIPPER_COMPORT=/dev/ttyUSB0 bash $0"
    exit 1
  fi
fi

if [[ ! -e "$GRIPPER_COMPORT" ]]; then
  echo "ERROR: Gripper port $GRIPPER_COMPORT does not exist."
  exit 1
fi

echo "Using gripper serial port: $GRIPPER_COMPORT"
sudo chmod a+rw "$GRIPPER_COMPORT" || {
  echo "WARN: chmod on $GRIPPER_COMPORT failed — you may need sudo or dialout group:"
  echo "  sudo usermod -aG dialout \$USER   # then log out and back in"
}

cd "$POLYMETIS_DIR/python/scripts"
exec python "$LAUNCH_GRIPPER" gripper=robotiq_2f "gripper.comport=$GRIPPER_COMPORT"
