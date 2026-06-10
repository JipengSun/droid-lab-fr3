#!/usr/bin/env bash
# Minimal Polymetis install for Robotiq gripper control on the DROID laptop.
# Full robot control still needs the NUC build from the host-installation guide.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
POLYMETIS_DIR="$ROOT/droid/fairo/polymetis/polymetis"

if [[ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]]; then
  # shellcheck source=/dev/null
  source "$HOME/anaconda3/etc/profile.d/conda.sh"
elif [[ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]]; then
  # shellcheck source=/dev/null
  source "$HOME/miniconda3/etc/profile.d/conda.sh"
else
  echo "ERROR: conda not found. Install anaconda or miniconda first."
  exit 1
fi

if ! conda env list | grep -qE '^polymetis-local '; then
  echo "Creating conda env polymetis-local (python 3.8)..."
  conda create -n polymetis-local python=3.8 -y
fi

conda activate polymetis-local

echo "Installing Python dependencies for gripper server..."
pip install "pip<24.1"
# Pin grpc + protobuf together; protoc output must match the runtime version.
pip install \
  "grpcio==1.46.0" \
  "grpcio-tools==1.46.0" \
  "protobuf==3.20.3" \
  "omegaconf==2.0.6" \
  "hydra-core==1.0.6" \
  "pymodbus==2.5.3" \
  pyserial \
  numpy

echo "Generating protobuf stubs (normally produced by cmake build)..."
mkdir -p "$POLYMETIS_DIR/build"
python -m grpc_tools.protoc \
  -I"$POLYMETIS_DIR/protos" \
  --python_out="$POLYMETIS_DIR/build" \
  --grpc_python_out="$POLYMETIS_DIR/build" \
  "$POLYMETIS_DIR/protos/polymetis.proto"
ln -sf ../../build/polymetis_pb2.py "$POLYMETIS_DIR/python/polymetis_pb2/polymetis_pb2.py"
ln -sf ../../build/polymetis_pb2_grpc.py "$POLYMETIS_DIR/python/polymetis_pb2_grpc/polymetis_pb2_grpc.py"

echo "Installing polymetis (editable, gripper server is Python-only)..."
pip install -e "$POLYMETIS_DIR"

echo ""
echo "Verifying install..."
python -c "from polymetis import GripperInterface; print('polymetis OK')"
command -v launch_gripper.py
echo ""
echo "Done. Start the gripper server with:"
echo "  bash $ROOT/droid/franka/launch_gripper.sh"
