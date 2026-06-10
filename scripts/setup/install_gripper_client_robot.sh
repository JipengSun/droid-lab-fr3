#!/usr/bin/env bash
# Install minimal gripper gRPC client deps into the DROID `robot` env so
# robotiq_gripper_demo.py --show-cameras can talk to the gripper server
# while using droid camera code (cv2 + pyzed).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
POLYMETIS_PYTHON="$ROOT/droid/fairo/polymetis/polymetis/python"

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

if ! conda env list | grep -qE '^robot '; then
  echo "ERROR: conda env 'robot' not found."
  exit 1
fi

conda activate robot

echo "Installing gRPC client for gripper (robot env)..."
pip install "grpcio==1.46.0" "protobuf==3.20.3"

echo "Verifying gripper client import..."
python - <<PY
import sys
sys.path.insert(0, "$POLYMETIS_PYTHON")
from polymetis.gripper_interface import GripperInterface
print("GripperInterface OK in robot env")
PY

echo ""
echo "Done. Run camera + gripper demo with:"
echo "  conda activate robot"
echo "  python $ROOT/scripts/demo/robotiq_gripper_demo.py --show-cameras"
echo ""
echo "Keep the gripper server running in polymetis-local (other terminal):"
echo "  conda activate polymetis-local"
echo "  bash $ROOT/droid/franka/launch_gripper.sh"
