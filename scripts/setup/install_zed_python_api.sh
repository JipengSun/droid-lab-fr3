#!/usr/bin/env bash
# Install Stereolabs ZED SDK Python bindings into the DROID `robot` conda env.
# Requires: ZED SDK already installed under /usr/local/zed (see host-installation guide).

set -euo pipefail

CONDA_ENV="${CONDA_ENV:-robot}"
PYTHON="${PYTHON:-/home/pci/anaconda3/envs/${CONDA_ENV}/bin/python}"
ZED_ROOT="/usr/local/zed"
ZED_LIB="${ZED_ROOT}/lib"
GET_PYTHON_API="${ZED_ROOT}/get_python_api.py"

if [[ ! -x "$PYTHON" ]]; then
  echo "Python not found at $PYTHON. Set CONDA_ENV or PYTHON."
  exit 1
fi

sdk_detected=false
_ldconfig_cache="$(/sbin/ldconfig -p 2>/dev/null || ldconfig -p 2>/dev/null || true)"
if grep -Fq 'libsl_zed.so' <<< "$_ldconfig_cache"; then
  sdk_detected=true
  echo "ZED SDK libraries found (libsl_zed.so)."
elif [[ -r "$GET_PYTHON_API" ]] || [[ -f "$GET_PYTHON_API" ]]; then
  sdk_detected=true
  echo "ZED SDK found at $ZED_ROOT."
fi

if [[ "$sdk_detected" != true ]]; then
  echo "ZED SDK not detected on this machine."
  echo "Install the SDK first:"
  echo "  bash scripts/setup/install_zed_sdk.sh"
  echo "Or: https://www.stereolabs.com/docs/installation/linux"
  exit 1
fi

if [[ ! -r "$GET_PYTHON_API" ]]; then
  echo "Note: $ZED_ROOT is root-only (normal). Using sudo for get_python_api.py."
fi

echo "Installing ZED Python API for: $("$PYTHON" --version)"
echo "(sudo password required)"
sudo "$PYTHON" "$GET_PYTHON_API"

echo "Configuring conda env (LD_LIBRARY_PATH hook + group check)..."
bash "$(dirname "$0")/configure_zed_env.sh"

echo ""
echo "Verifying import (via zed group)..."
export LD_LIBRARY_PATH="${ZED_LIB}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
if sg zed -c "export LD_LIBRARY_PATH='${ZED_LIB}':\${LD_LIBRARY_PATH:-}; '$PYTHON' -c \"import pyzed.sl as sl; print('pyzed OK, SDK version:', sl.Camera().get_sdk_version())\""; then
  :
else
  echo ""
  echo "Import failed in this shell. You are in group 'zed' but the session may be stale."
  echo "Fix: log out and back in, OR run:  newgrp zed"
  echo "Then:  conda deactivate && conda activate robot"
  exit 1
fi

echo ""
echo "Next: python scripts/setup/list_zed_cameras.py"
