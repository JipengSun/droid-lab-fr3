#!/usr/bin/env bash
# Conda hooks + checks so pyzed can load libsl_zed.so (requires `zed` group membership).
set -euo pipefail

CONDA_ENV="${CONDA_ENV:-robot}"
CONDA_PREFIX="${CONDA_PREFIX:-/home/pci/anaconda3/envs/${CONDA_ENV}}"
ACTIVATE_DIR="${CONDA_PREFIX}/etc/conda/activate.d"
DEACTIVATE_DIR="${CONDA_PREFIX}/etc/conda/deactivate.d"

mkdir -p "$ACTIVATE_DIR" "$DEACTIVATE_DIR"

cat > "${ACTIVATE_DIR}/zed.sh" <<'EOF'
# Stereolabs ZED SDK (installed under /usr/local/zed, group `zed`)
export _DROID_OLD_LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"
export LD_LIBRARY_PATH="/usr/local/zed/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
EOF

cat > "${DEACTIVATE_DIR}/zed.sh" <<'EOF'
if [[ -n "${_DROID_OLD_LD_LIBRARY_PATH+x}" ]]; then
  export LD_LIBRARY_PATH="${_DROID_OLD_LD_LIBRARY_PATH}"
  unset _DROID_OLD_LD_LIBRARY_PATH
fi
EOF

echo "Installed conda hooks in ${CONDA_ENV}: LD_LIBRARY_PATH includes /usr/local/zed/lib"

if ! id -nG "$USER" | grep -qw zed; then
  echo ""
  echo "WARNING: user $USER is not in group 'zed'."
  echo "Add yourself (then log out and back in):"
  echo "  sudo usermod -aG zed \$USER"
  exit 1
fi

if ! sg zed -c "test -r /usr/local/zed/lib/libsl_zed.so" 2>/dev/null; then
  echo ""
  echo "WARNING: cannot read /usr/local/zed yet."
  echo "Log out and back in (or run: newgrp zed) so the zed group applies to your session."
  exit 1
fi

PYTHON="${CONDA_PREFIX}/bin/python"
echo "Verifying pyzed import..."
sg zed -c "export LD_LIBRARY_PATH=/usr/local/zed/lib:\${LD_LIBRARY_PATH:-}; \"$PYTHON\" -c \"import pyzed.sl as sl; print('pyzed OK, SDK', sl.Camera().get_sdk_version())\""

echo ""
echo "If import fails in your current terminal, run:  newgrp zed"
echo "Or log out and back in once, then:  conda activate robot"
