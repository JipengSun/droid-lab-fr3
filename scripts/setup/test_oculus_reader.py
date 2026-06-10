#!/usr/bin/env python3
"""Diagnose Oculus Quest reader — shows why output may be empty."""

import re
import subprocess
import sys
import time

TAG = "wE9ryARX"
APK = "com.rail.oculus.teleop"
ADB = __import__("os").environ.get("ADB", "adb")


def run(cmd, timeout=15):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.stdout + r.stderr


def main():
    print("=== Oculus Reader diagnostic ===\n")

    devices = run([ADB, "devices"]).strip()
    print("adb devices:\n", devices, sep="")
    if "\tdevice" not in devices:
        print("\nERROR: No authorized device. Fix adb first.")
        sys.exit(1)

    model = run([ADB, "shell", "getprop", "ro.product.model"]).strip()
    print(f"\nHeadset model: {model}")
    if "Quest 3" in model:
        print(
            "\nNOTE: Quest 3 often needs a newer teleop APK than the default DROID bundle.\n"
            "See: https://github.com/rail-berkeley/oculus_reader/issues/5\n"
            "Quest 3 APK (manual download):\n"
            "  https://drive.google.com/file/d/17iIzHUHXtzlwmAXW5QfGqwRpsePxq_MA/view\n"
            "Replace droid/oculus_reader/oculus_reader/APK/teleop-debug.apk then reinstall.\n"
        )

    installed = APK in run([ADB, "shell", "pm", "list", "packages"])
    print(f"APK installed ({APK}): {installed}")

    print("\nLaunching teleop app...")
    run([ADB, "shell", "am", "start", "-n", f"{APK}/.MainActivity"])

    print(
        "\n*** PUT ON THE HEADSET NOW ***\n"
        "1. Accept any permission prompts\n"
        "2. You should see the DROID teleop VR scene (not just a black screen)\n"
        "3. Pick up controllers — keep them in view of the headset cameras\n"
        "4. Press buttons and move controllers\n"
        "\nCapturing logcat for 15 seconds...\n"
    )

    proc = subprocess.Popen(
        [ADB, "logcat", "-v", "brief", "-s", f"{TAG}:I", "OculusTeleop:I", "OculusTeleop:V"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    time.sleep(15)
    proc.terminate()
    out, _ = proc.communicate(timeout=5)
    lines = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        lines.append(line)
        if TAG in line:
            print("DATA:", line[:200], flush=True)
        elif "AppPaused" in line or "AppResumed" in line:
            print("APP:", line, flush=True)

    tag_lines = [l for l in lines if TAG in l]
    print(f"\n--- Summary ---")
    print(f"wE9ryARX log lines captured: {len(tag_lines)}")

    if not tag_lines:
        print(
            "\nNo controller data received. Common causes:\n"
            "  • Headset was off / app not in VR foreground (shows AppPaused in logcat)\n"
            "  • Quest 3 + old APK — install Quest 3 APK from GitHub issue #5\n"
            "  • Controllers asleep — press a button, hold in front of headset\n"
            "  • Hand tracking only — use Touch controllers, not bare hands\n"
        )
        sys.exit(1)

    # Parse latest sample like reader.py
    last = tag_lines[-1]
    m = re.search(rf"{TAG}:\s*(.*)", last)
    payload = m.group(1) if m else ""
    print(f"Latest payload (truncated): {payload[:120]}...")
    if payload.strip() in ("", "&"):
        print("WARNING: App running but no controller transforms in payload.")
    else:
        print("SUCCESS: Controller data is flowing. reader.py should work with headset on.")


if __name__ == "__main__":
    main()
