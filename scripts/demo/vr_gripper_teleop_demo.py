#!/usr/bin/env python3
"""
VR teleop: Quest right controller → Robotiq gripper only (no arm).

For full arm + gripper teleop (DROID VRPolicy + NUC), use:
  cd /home/pci/Desktop/DROID
  python scripts/demo/vr_teleop_demo.py

Prerequisites:
  NUC: gripper server + zerorpc (see scripts/setup/openpi_start_gripper_nuc.sh)

  Terminal — this demo (Quest USB connected):
    export PATH="$HOME/platform-tools:$PATH"
    adb shell am broadcast -a com.oculus.vrpowermanager.prox_close   # keep headset awake
    conda activate robot
    cd /home/pci/Desktop/DROID
    python scripts/demo/vr_gripper_teleop_demo.py

If controller data is empty, run: python scripts/setup/test_oculus_reader.py

Controls (right controller, same as DROID VRPolicy):
  - Side grip (RG): enable gripper teleop
  - Index trigger: gripper position (0 = open, 1 = closed)
  - A / B: UI indicators only
"""

import argparse
import importlib.util
import subprocess
import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation

ROOT = Path(__file__).resolve().parents[2]
CONTROL_HZ = 15


def _load_gripper_demo():
    path = ROOT / "scripts" / "demo" / "robotiq_gripper_demo.py"
    spec = importlib.util.spec_from_file_location("robotiq_gripper_demo", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _preflight_quest():
    adb = "adb"
    try:
        out = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=5).stdout
    except FileNotFoundError:
        print("WARN: adb not found — add platform-tools to PATH")
        return
    if "\tdevice" not in out:
        print("WARN: no authorized Quest on adb — check USB and accept debugging prompt")
        return
    print("Quest adb: device connected")
    subprocess.run(
        [adb, "shell", "am", "broadcast", "-a", "com.oculus.vrpowermanager.prox_close"],
        capture_output=True,
        timeout=5,
    )


def trigger_value(buttons):
    val = buttons.get("rightTrig", 0.0)
    if isinstance(val, (tuple, list)):
        return float(val[0]) if val else 0.0
    return float(val)


def draw_ui_panel(ax, trig, rg, pressed_a, pressed_b, gripper_pos, gripper_width, max_width, ctrl_on):
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    if pressed_a:
        ax.set_facecolor("#d5f5e3")
    elif pressed_b:
        ax.set_facecolor("#fadbd8")
    else:
        ax.set_facecolor("#f8f9fa")

    ax.text(0.5, 0.92, "Gripper (index trigger)", ha="center", fontsize=11, weight="bold")
    bar_color = "#3498db" if rg else "#95a5a6"
    ax.add_patch(plt.Rectangle((0.1, 0.72), 0.8 * trig, 0.08, color=bar_color))
    ax.add_patch(plt.Rectangle((0.1, 0.72), 0.8, 0.08, fill=False, edgecolor="#2c3e50", lw=1.5))
    ax.text(0.5, 0.65, f"{trig * 100:.0f}%", ha="center", fontsize=10)

    ax.text(0.5, 0.48, "Side grip (RG) — enable", ha="center", fontsize=11, weight="bold")
    ax.add_patch(plt.Circle((0.5, 0.35), 0.07, color="#2ecc71" if rg else "#bdc3c7"))
    ax.text(0.5, 0.35, "ON" if rg else "off", ha="center", va="center", fontsize=9, color="white" if rg else "#555")

    ax.text(0.28, 0.12, "A", ha="center", fontsize=14, weight="bold", color="#27ae60" if pressed_a else "#aaa")
    ax.text(0.72, 0.12, "B", ha="center", fontsize=14, weight="bold", color="#c0392b" if pressed_b else "#aaa")

    if not ctrl_on:
        status = "controller signal lost — check Quest USB / headset awake"
    elif not rg:
        status = "hold RG to move gripper"
    else:
        status = "TELEOP"
    ax.text(
        0.5,
        0.02,
        f"{status}\npos={gripper_pos:.3f}  width={gripper_width:.4f} m  max={max_width:.4f} m",
        ha="center",
        fontsize=8,
        family="monospace",
    )


def main():
    parser = argparse.ArgumentParser(description="Quest right controller → Robotiq gripper teleop")
    parser.add_argument("--nuc-ip", default=None, help="NUC IP (default: parameters.nuc_ip)")
    parser.add_argument("--local-gripper", action="store_true", help="Use workstation USB gripper instead")
    parser.add_argument("--ip", default="localhost", help="Local gripper gRPC host (--local-gripper only)")
    parser.add_argument("--port", type=int, default=50052, help="Local gripper gRPC port (--local-gripper only)")
    parser.add_argument("--speed", type=float, default=0.05, help="Gripper goto speed")
    parser.add_argument("--force", type=float, default=0.1, help="Gripper goto force")
    parser.add_argument("--show-cameras", action="store_true", help="Show ZED camera preview(s)")
    parser.add_argument("--all-cameras", action="store_true", help="All 3 ZEDs (requires --show-cameras)")
    parser.add_argument("--no-quest-preflight", action="store_true", help="Skip adb/prox_close preflight")
    args = parser.parse_args()

    for name in ("oculus_reader", "matplotlib", "numpy"):
        try:
            __import__(name)
        except ImportError:
            print(f"ERROR: missing {name}. Activate the DROID env first:")
            print("  conda activate robot")
            print("  cd /home/pci/Desktop/DROID")
            print("  python scripts/demo/vr_gripper_teleop_demo.py")
            sys.exit(1)

    sys.path.insert(0, str(ROOT))
    from droid.controllers.oculus_controller import VRPolicy

    if not args.no_quest_preflight:
        _preflight_quest()

    gd = _load_gripper_demo()
    from droid.misc.parameters import nuc_ip

    if args.local_gripper:
        gd.GripperInterface = gd.load_gripper_interface()
        gripper, max_width = gd.connect_gripper(args.ip, args.port)
    else:
        target_nuc = args.nuc_ip or nuc_ip
        if not target_nuc:
            print("ERROR: nuc_ip not set")
            sys.exit(1)
        gripper, max_width = gd.connect_gripper_via_nuc(target_nuc)

    camera_preview = None
    if args.show_cameras:
        from droid.misc.parameters import hand_camera_id

        if args.all_cameras:
            camera_preview = gd._AllCamerasPreview()
        else:
            if not hand_camera_id:
                print("ERROR: hand_camera_id empty in droid/misc/parameters.py")
                sys.exit(1)
            camera_preview = gd.HandCameraPreview(hand_camera_id)

    print("Starting VRPolicy — keep right controller visible to the headset.")
    controller = VRPolicy(right_controller=True)

    last_gripper_cmd_time = 0.0
    last_status_print = 0.0
    warned_no_controller = False

    fig = plt.figure(figsize=(8, 5))
    fig.canvas.manager.set_window_title("DROID VR gripper teleop")
    ax_ui = fig.add_subplot(111)

    def read_gripper_state():
        try:
            state = gripper.get_state()
            pos = gd.droid_width_to_position(state.width, max_width)
            return pos, state.width
        except Exception:
            return 0.0, gd.droid_position_to_width(0.0, max_width)

    def update(_frame):
        nonlocal last_gripper_cmd_time, last_status_print, warned_no_controller

        ax_ui.cla()

        if camera_preview is not None:
            try:
                import cv2

                cv2.imshow("DROID VR gripper cameras", camera_preview.read())
                cv2.waitKey(1)
            except Exception as exc:
                ax_ui.text(0.5, 0.55, f"Camera error: {exc}", ha="center", fontsize=9, color="red")

        controller_info = controller.get_info()
        buttons = controller._state.get("buttons", {})
        trig = trigger_value(buttons)
        rg = controller_info.get("movement_enabled", False)
        ctrl_on = controller_info.get("controller_on", False)
        pressed_a = controller_info.get("success", False)
        pressed_b = controller_info.get("failure", False)

        gripper_pos, gripper_width = read_gripper_state()

        if not controller._state.get("poses"):
            draw_ui_panel(ax_ui, 0.0, False, pressed_a, pressed_b, gripper_pos, gripper_width, max_width, False)
            ax_ui.text(0.5, 0.55, "Waiting for right controller…", ha="center", fontsize=12)
            if not warned_no_controller:
                print(
                    "No controller data yet. Put on Quest (or prox_close), "
                    "open teleop app, press a controller button."
                )
                print("Diagnose: python scripts/setup/test_oculus_reader.py")
                warned_no_controller = True
            return

        warned_no_controller = False
        obs = {
            "robot_state": {
                "cartesian_position": [0.0] * 6,
                "gripper_position": gripper_pos,
            }
        }
        _, info_dict = controller.forward(obs, include_info=True)

        if rg and "target_gripper_position" in info_dict:
            now = time.time()
            if now - last_gripper_cmd_time >= 1.0 / CONTROL_HZ:
                target = float(np.clip(info_dict["target_gripper_position"], 0.0, 1.0))
                width = gd.droid_position_to_width(target, max_width)
                gripper.goto(width=width, speed=args.speed, force=args.force, blocking=False)
                last_gripper_cmd_time = now
                gripper_pos, gripper_width = read_gripper_state()

        draw_ui_panel(ax_ui, trig, rg, pressed_a, pressed_b, gripper_pos, gripper_width, max_width, ctrl_on)

        now = time.time()
        if rg and now - last_status_print > 2.0:
            print(f"TELEOP  trigger={trig:.2f}  grip_pos={gripper_pos:.2f}  width={gripper_width:.4f} m")
            last_status_print = now

    ani = FuncAnimation(fig, update, interval=int(1000 / CONTROL_HZ), blit=False)
    try:
        plt.show()
    finally:
        controller.oculus_reader.stop()
        if camera_preview is not None:
            camera_preview.close()
            try:
                import cv2

                cv2.destroyAllWindows()
            except Exception:
                pass
        del ani


if __name__ == "__main__":
    main()
