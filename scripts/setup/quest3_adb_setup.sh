#!/usr/bin/env bash
# Quest 3 ADB setup for DROID on Ubuntu/Linux.
# Run: bash scripts/setup/quest3_adb_setup.sh

set -euo pipefail

ADB="${ADB:-$HOME/platform-tools/adb}"
if [[ ! -x "$ADB" ]]; then
  ADB="$(command -v adb || true)"
fi

UDEV_RULES="/etc/udev/rules.d/51-oculus-quest.rules"

echo "=== Quest 3 ADB setup ==="

# 1. udev rules (fixes 'no permissions' in adb devices)
if [[ ! -f "$UDEV_RULES" ]]; then
  echo "Installing udev rules (requires sudo)..."
  sudo tee "$UDEV_RULES" > /dev/null <<'EOF'
# Meta / Oculus Quest (vendor 2833)
SUBSYSTEM=="usb", ATTR{idVendor}=="2833", MODE="0666", GROUP="plugdev"
# Generic Android adb (fallback)
SUBSYSTEM=="usb", ATTR{idVendor}=="18d1", MODE="0666", GROUP="plugdev"
EOF
  sudo udevadm control --reload-rules
  sudo udevadm trigger
  echo "udev rules installed."
else
  echo "udev rules already present at $UDEV_RULES"
fi

# 2. plugdev group
if ! groups "$USER" | grep -q plugdev; then
  echo "Adding $USER to plugdev group (requires sudo, log out/in after)..."
  sudo usermod -aG plugdev "$USER"
  echo "Added to plugdev. You may need to unplug/replug Quest or reboot."
fi

# 3. system adb (optional; user install at ~/platform-tools also works)
if ! command -v adb >/dev/null 2>&1; then
  echo "Installing android-tools-adb via apt..."
  sudo apt-get update
  sudo apt-get install -y android-tools-adb
fi

# 4. Restart adb
if [[ -x "$HOME/platform-tools/adb" ]]; then
  export PATH="$HOME/platform-tools:$PATH"
fi
adb kill-server || true
adb start-server

echo ""
echo "=== Next: authorize on the headset ==="
echo "1. Keep Quest 3 connected via USB-C"
echo "2. Put on the headset"
echo "3. Accept 'Allow USB debugging' and check 'Always allow from this computer'"
echo "4. Run: adb devices"
echo "   Expected: 2G97C5ZJ1405WY    device"
echo ""
adb devices -l
