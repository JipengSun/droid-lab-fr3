#!/usr/bin/env bash
# Install Stereolabs ZED SDK system package (one-time, requires sudo).
set -euo pipefail

INSTALLER="${ZED_INSTALLER:-/home/pci/Desktop/Franka_Robot/downloads/ZED_SDK_Ubuntu22_cuda11.8_v4.2.5.zstd.run}"

_ldconfig_cache="$(/sbin/ldconfig -p 2>/dev/null || ldconfig -p 2>/dev/null || true)"
if grep -Fq 'libsl_zed.so' <<< "$_ldconfig_cache"; then
  echo "ZED SDK already installed (libsl_zed.so present)."
  echo "Run: bash scripts/setup/install_zed_python_api.sh"
  exit 0
fi

if [[ ! -f "$INSTALLER" ]]; then
  echo "Installer not found: $INSTALLER"
  echo "Download from https://www.stereolabs.com/developers/release/"
  exit 1
fi

echo "Installing ZED SDK from:"
echo "  $INSTALLER"
echo ""
echo "When prompted:"
echo "  - Install CUDA dependencies: Yes (if you have an NVIDIA GPU)"
echo "  - Accept defaults for other options"
echo ""
chmod +x "$INSTALLER"
sudo "$INSTALLER"

echo ""
echo "SDK install finished. Reboot if the installer asked you to."
echo "Then run: bash scripts/setup/install_zed_python_api.sh"
