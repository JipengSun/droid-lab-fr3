#!/usr/bin/env python3
"""
DROID-style VR teleop: Quest right controller → Franka arm + Robotiq gripper (both via NUC).

Matches scripts/tests/collect_trajectory.py + droid/controllers/oculus_controller.VRPolicy:
  - RG (side grip): enable teleop (arm + gripper)
  - Controller pose delta → cartesian_velocity on the arm
  - Index trigger → gripper position (0 open, 1 closed)
  - RJ: reset VR orientation frame
  - A / B: success / failure flags (UI only here)

Prerequisites:
  NUC: Polymetis + zerorpc :4242 + gripper server :50052 (see nuc-admin.md)
  Desk: Unlock brakes → Activate FCI

  VR teleop (workstation):
    export PATH="$HOME/platform-tools:$PATH"
    adb devices    # must show Quest as "device" before starting
    conda activate robot
    cd /home/pci/Desktop/DROID
    python scripts/demo/vr_teleop_demo.py

If arm preflight fails (empty buffer / timeout), see recovery below or run gripper-only:
    python scripts/demo/vr_gripper_teleop_demo.py

NUC recovery (from workstation, after Desk → Activate FCI):
    ssh nuc '...'   # see .cursor/skills/control-arm-via-nuc/nuc-admin.md

Optional cameras:
    python scripts/demo/vr_teleop_demo.py --show-cameras
      # hand RGB+depth + both third-person RGB
    python scripts/demo/vr_teleop_demo.py --show-cameras --all-cameras
      # all 3 ZEDs with RGB+depth per camera (heavier USB load)

Dry-run (no robot commands):
    python scripts/demo/vr_teleop_demo.py --dry-run

On launch the arm moves to DROID home joints and the gripper opens (skip with --no-reset-arm).
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
ZERORPC_TIMEOUT_S = 30
LAUNCH_ROBOT_TIMEOUT_S = 45

# DROID default home joints (see droid/robot_env.py reset_joints)
RESET_JOINTS = np.array([0, -1 / 5 * np.pi, 0, -4 / 5 * np.pi, 0, 3 / 5 * np.pi, 0.0])


def _require_robot_env(dry_run: bool):
    """All modes need the DROID `robot` conda env — not `(base)`."""
    required = ["oculus_reader", "matplotlib", "numpy"]
    if not dry_run:
        required.append("zerorpc")
    missing = []
    for name in required:
        try:
            __import__(name)
        except ImportError:
            missing.append(name)
    if missing:
        print("ERROR: missing packages:", ", ".join(missing))
        print("Activate the DROID env first:")
        print("  conda activate robot")
        print("  cd /home/pci/Desktop/DROID")
        print("  python scripts/demo/vr_teleop_demo.py")
        sys.exit(1)


def _preflight_quest():
    """Fail fast before homing the arm if Quest is not visible to adb."""
    adb = "adb"
    try:
        out = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=5).stdout
    except FileNotFoundError:
        print("ERROR: adb not found. Add platform-tools to PATH:")
        print("  export PATH=\"$HOME/platform-tools:$PATH\"")
        print("  bash scripts/setup/quest3_adb_setup.sh")
        sys.exit(1)

    if "\tdevice" not in out:
        print("ERROR: no Quest visible to adb (USB debugging not ready).")
        print("  adb devices output:")
        for line in out.strip().splitlines():
            print(f"    {line}")
        print("\nFix:")
        print("  1. Plug Quest into workstation with USB-C data cable")
        print("  2. export PATH=\"$HOME/platform-tools:$PATH\"")
        print("  3. Put on headset → Allow USB debugging → Always allow")
        print("  4. adb devices   # must show: <serial>    device")
        print("  5. Optional: adb shell am broadcast -a com.oculus.vrpowermanager.prox_close")
        print("  6. Diagnose: python scripts/setup/test_oculus_reader.py")
        print("\nFirst-time setup: bash scripts/setup/quest3_adb_setup.sh")
        sys.exit(1)

    serial = next(line.split()[0] for line in out.splitlines() if "\tdevice" in line)
    print(f"Quest adb OK ({serial})")
    subprocess.run(
        [adb, "shell", "am broadcast", "-a", "com.oculus.vrpowermanager.prox_close"],
        capture_output=True,
        timeout=5,
    )


def _load_gripper_demo():
    path = ROOT / "scripts" / "demo" / "robotiq_gripper_demo.py"
    spec = importlib.util.spec_from_file_location("robotiq_gripper_demo", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _preflight_nuc(nuc_ip: str):
    """Fail fast with actionable message if NUC ports are down."""
    import socket

    def _port_open(host, port, timeout=2.0):
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False

    if not _port_open(nuc_ip, 4242):
        print(f"ERROR: NUC zerorpc not reachable at {nuc_ip}:4242")
        print("Start the NUC stack:")
        print("  bash scripts/setup/openpi_start_nuc_stack.sh")
        print("Or step by step: openpi_start_gripper_nuc.sh → polymetis → zerorpc")
        sys.exit(1)

    if not _port_open(nuc_ip, 50052):
        print(f"WARN: NUC gripper port {nuc_ip}:50052 not open.")
        print("  bash scripts/setup/openpi_start_gripper_nuc.sh")
        print("launch_robot may proceed without gripper if server is still starting...")


def _print_arm_recovery():
    print(
        "\n=== ARM UNAVAILABLE — VR teleop cannot move the Franka ===\n"
        "Common causes:\n"
        "  • Polymetis state buffer empty (FCI off or franka_panda_client dead)\n"
        "  • NUC zerorpc hung after a reflex / communication_constraints_violation\n"
        "  • launch_robot timed out — NUC gripper gRPC hung or stack not started\n"
        "    Fix: bash scripts/setup/openpi_start_nuc_stack.sh (see nuc-admin.md)\n"
        "\nFix (workstation Desk browser):\n"
        "  1. https://192.168.1.11/desk/ → Unlock brakes → Execution → Activate FCI\n"
        "\nFix (NUC — see .cursor/skills/control-arm-via-nuc/nuc-admin.md):\n"
        "  2. Relaunch Polymetis + zerorpc on the NUC\n"
        "  3. Verify: python scripts/demo/arm_smoke_test.py\n"
        "\nGripper-only fallback:\n"
        "  python scripts/demo/vr_gripper_teleop_demo.py\n"
    )


def connect_arm(nuc_ip: str, dry_run: bool):
    import zerorpc

    from droid.misc.server_interface import ServerInterface

    if dry_run:
        print("DRY-RUN: skipping NUC connection")
        return None

    print(f"Connecting to NUC at {nuc_ip}:4242 (zerorpc timeout {ZERORPC_TIMEOUT_S}s)...")
    _preflight_nuc(nuc_ip)
    try:
        robot = ServerInterface(ip_address=nuc_ip, launch=False, timeout=ZERORPC_TIMEOUT_S)
    except Exception as exc:
        print(f"ERROR: could not connect zerorpc: {exc}")
        _print_arm_recovery()
        raise SystemExit(1) from exc

    # launch_robot can block on NUC while connecting gripper gRPC — use longer timeout.
    robot.server.timeout = LAUNCH_ROBOT_TIMEOUT_S
    try:
        robot.launch_robot()
        print("launch_robot OK")
    except zerorpc.exceptions.RemoteError as err:
        print(f"launch_robot failed: {err}")
        _print_arm_recovery()
        raise SystemExit(1) from err
    except zerorpc.exceptions.TimeoutExpired as err:
        print(f"ERROR: launch_robot timed out after {LAUNCH_ROBOT_TIMEOUT_S}s: {err}")
        print("Most likely: gripper server on NUC not ready. Run:")
        print("  bash scripts/setup/openpi_start_nuc_stack.sh")
        print("  scp droid/franka/robot.py nuc:/home/pci/Desktop/Franka/droid/droid/franka/robot.py")
        print("  bash scripts/setup/openpi_start_zerorpc.sh")
        _print_arm_recovery()
        raise SystemExit(1) from err
    except Exception as exc:
        print(f"launch_robot skipped ({exc.__class__.__name__})")

    robot.server.timeout = ZERORPC_TIMEOUT_S

    try:
        state, _ = robot.get_robot_state()
        pos = state["cartesian_position"]
        print(f"Arm connected. EE xyz=({pos[0]:+.3f}, {pos[1]:+.3f}, {pos[2]:+.3f})")
    except zerorpc.exceptions.TimeoutExpired as err:
        print(f"ERROR: get_robot_state timed out: {err}")
        _print_arm_recovery()
        raise SystemExit(1) from err
    except zerorpc.exceptions.RemoteError as err:
        _print_arm_recovery()
        print(f"RemoteError: {err}")
        raise SystemExit(1) from err

    return robot


def reset_arm_home(robot):
    """Move arm to DROID default ready pose before teleop (blocking)."""
    import zerorpc

    print("Resetting arm to DROID home pose (blocking)...")
    try:
        robot.update_joints(RESET_JOINTS, velocity=False, blocking=True)
        state, _ = robot.get_robot_state()
        pos = state["cartesian_position"]
        print(
            f"Arm home OK. EE xyz=({pos[0]:+.3f}, {pos[1]:+.3f}, {pos[2]:+.3f})  "
            f"joints={np.round(state['joint_positions'], 3)}"
        )
    except zerorpc.exceptions.TimeoutExpired as err:
        print(f"ERROR: arm reset timed out: {err}")
        _print_arm_recovery()
        raise SystemExit(1) from err
    except zerorpc.exceptions.RemoteError as err:
        print(f"ERROR: arm reset failed: {err}")
        _print_arm_recovery()
        raise SystemExit(1) from err


def open_nuc_gripper(robot):
    """Open Robotiq gripper on NUC before teleop."""
    print("Opening gripper on NUC...")
    robot.update_gripper(0.0, velocity=False, blocking=True)
    state, _ = robot.get_robot_state()
    print(f"Gripper open OK. position={state['gripper_position']:.3f}")


def read_gripper_position(robot, max_width):
    try:
        state, _ = robot.get_robot_state()
        return float(state["gripper_position"])
    except Exception:
        return 0.0


def merge_robot_state(arm_state, gripper_pos):
    state = dict(arm_state)
    state["gripper_position"] = gripper_pos
    return state


def draw_ui_panel(
    ax,
    controller_info,
    info_dict,
    gripper_pos,
    gripper_width,
    max_width,
    trig,
    arm_status,
    ee_pos,
):
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    pressed_a = controller_info.get("success", False)
    pressed_b = controller_info.get("failure", False)
    rg = controller_info.get("movement_enabled", False)
    ctrl_on = controller_info.get("controller_on", False)

    if pressed_a:
        ax.set_facecolor("#d5f5e3")
    elif pressed_b:
        ax.set_facecolor("#fadbd8")
    else:
        ax.set_facecolor("#f8f9fa")

    ax.text(0.5, 0.96, "DROID VR teleop (arm + gripper)", ha="center", fontsize=11, weight="bold")

    ax.text(0.5, 0.84, "Side grip (RG) — enable teleop", ha="center", fontsize=10, weight="bold")
    ax.add_patch(plt.Circle((0.5, 0.76), 0.06, color="#2ecc71" if rg else "#bdc3c7"))
    ax.text(0.5, 0.76, "ON" if rg else "off", ha="center", va="center", fontsize=8, color="white" if rg else "#555")

    ax.text(0.5, 0.62, "Gripper (index trigger)", ha="center", fontsize=10, weight="bold")
    bar_color = "#3498db" if rg else "#95a5a6"
    ax.add_patch(plt.Rectangle((0.1, 0.52), 0.8 * trig, 0.06, color=bar_color))
    ax.add_patch(plt.Rectangle((0.1, 0.52), 0.8, 0.06, fill=False, edgecolor="#2c3e50", lw=1.5))
    ax.text(0.5, 0.46, f"{trig * 100:.0f}%", ha="center", fontsize=9)

    ax.text(0.28, 0.08, "A", ha="center", fontsize=13, weight="bold", color="#27ae60" if pressed_a else "#aaa")
    ax.text(0.72, 0.08, "B", ha="center", fontsize=13, weight="bold", color="#c0392b" if pressed_b else "#aaa")

    status = "TELEOP" if rg else "hold RG to move arm + gripper"
    if not ctrl_on:
        status = "controller signal lost — check Quest USB"
    if arm_status != "ok":
        status = arm_status

    lines = [status]
    if ee_pos is not None:
        lines.append(f"ee xyz=({ee_pos[0]:+.3f}, {ee_pos[1]:+.3f}, {ee_pos[2]:+.3f})")
    if info_dict.get("target_cartesian_position") is not None:
        t = info_dict["target_cartesian_position"]
        lines.append(f"target xyz=({t[0]:+.3f}, {t[1]:+.3f}, {t[2]:+.3f})")
    lines.append(f"grip pos={gripper_pos:.3f}  width={gripper_width:.4f} m")

    ax.text(0.5, 0.30, "\n".join(lines), ha="center", va="top", fontsize=8, family="monospace")


def trigger_value(buttons):
    val = buttons.get("rightTrig", 0.0)
    if isinstance(val, (tuple, list)):
        return float(val[0]) if val else 0.0
    return float(val)


def main():
    parser = argparse.ArgumentParser(description="Quest VR teleop — Franka arm + Robotiq gripper (NUC)")
    parser.add_argument("--nuc-ip", default=None, help="NUC IP (default: droid/misc/parameters.py nuc_ip)")
    parser.add_argument("--max-gripper-width", type=float, default=0.085, help="Robotiq max width (m) for UI")
    parser.add_argument("--show-cameras", action="store_true", help="Hand RGB+depth + both third-person RGB")
    parser.add_argument("--all-cameras", action="store_true", help="All 3 ZEDs RGB+depth each (heavy USB)")
    parser.add_argument("--dry-run", action="store_true", help="Log VR actions without sending robot commands")
    parser.add_argument(
        "--no-reset-arm",
        action="store_true",
        help="Skip moving arm to DROID home pose and opening gripper at startup",
    )
    parser.add_argument(
        "--no-quest-preflight",
        action="store_true",
        help="Skip adb Quest check (not recommended)",
    )
    args = parser.parse_args()
    _require_robot_env(args.dry_run)

    sys.path.insert(0, str(ROOT))
    from droid.controllers.oculus_controller import VRPolicy
    from droid.misc.parameters import nuc_ip

    nuc = args.nuc_ip or nuc_ip
    if not nuc and not args.dry_run:
        print("ERROR: nuc_ip not set in parameters.py and --nuc-ip not given")
        sys.exit(1)

    gd = _load_gripper_demo()

    if not args.no_quest_preflight:
        _preflight_quest()

    robot = connect_arm(nuc, args.dry_run)
    max_width = args.max_gripper_width

    if not args.dry_run and not args.no_reset_arm and robot is not None:
        reset_arm_home(robot)
        open_nuc_gripper(robot)

    camera_preview = None
    if args.show_cameras:
        from droid.misc.parameters import hand_camera_id, varied_camera_1_id, varied_camera_2_id

        if args.all_cameras:
            camera_preview = gd._AllCamerasPreview()
        else:
            for name, serial in (
                ("hand_camera_id", hand_camera_id),
                ("varied_camera_1_id", varied_camera_1_id),
                ("varied_camera_2_id", varied_camera_2_id),
            ):
                if not serial:
                    print(f"ERROR: {name} empty in droid/misc/parameters.py")
                    print("Run: python scripts/setup/list_zed_cameras.py")
                    sys.exit(1)
            camera_preview = gd.TeleopCamerasPreview(
                hand_camera_id, varied_camera_1_id, varied_camera_2_id
            )

    print("Starting VRPolicy (OculusReader thread) — keep right controller visible.")
    controller = VRPolicy(right_controller=True)

    last_status_print = 0.0
    arm_status = "ok"
    consecutive_arm_errors = 0

    fig = plt.figure(figsize=(9, 5))
    fig.canvas.manager.set_window_title("DROID VR teleop — arm + gripper")
    ax_ui = fig.add_subplot(111)

    def update(_frame):
        nonlocal last_status_print, arm_status, consecutive_arm_errors

        ax_ui.cla()
        if camera_preview is not None:
            try:
                import cv2

                frame = camera_preview.read()
                cv2.imshow("DROID VR teleop cameras", frame)
                cv2.waitKey(1)
            except Exception:
                pass

        controller_info = controller.get_info()
        buttons = controller._state.get("buttons", {})
        trig = trigger_value(buttons)

        gripper_pos = read_gripper_position(robot, max_width) if robot else 0.0
        gripper_width = gd.droid_position_to_width(gripper_pos, max_width)

        info_dict = {}
        ee_pos = None
        movement_enabled = controller_info.get("movement_enabled", False)

        if not args.dry_run and robot is not None and arm_status == "ok":
            import zerorpc

            try:
                arm_state, _ = robot.get_robot_state()
                ee_pos = arm_state["cartesian_position"][:3]
                obs = {"robot_state": merge_robot_state(arm_state, gripper_pos)}

                if not controller._state.get("poses"):
                    info_dict = {}
                else:
                    action, info_dict = controller.forward(obs, include_info=True)

                    if movement_enabled:
                        grip_target = float(
                            np.clip(info_dict.get("target_gripper_position", gripper_pos), 0.0, 1.0)
                        )
                        full_action = np.concatenate([action[:6], [grip_target]])
                        robot.update_command(
                            full_action,
                            action_space="cartesian_velocity",
                            gripper_action_space="position",
                            blocking=False,
                        )

                consecutive_arm_errors = 0

            except zerorpc.exceptions.TimeoutExpired as err:
                consecutive_arm_errors += 1
                arm_status = f"NUC timeout ({consecutive_arm_errors}) — see terminal"
                if consecutive_arm_errors == 1:
                    print(f"WARN: NUC arm timeout: {err}")
                    _print_arm_recovery()
            except zerorpc.exceptions.RemoteError as err:
                consecutive_arm_errors += 1
                arm_status = "NUC error — see terminal"
                if consecutive_arm_errors == 1:
                    print(f"WARN: NUC arm error: {err}")
                    if "empty buffer" in str(err):
                        _print_arm_recovery()
        elif args.dry_run and controller._state.get("poses"):
            obs = {
                "robot_state": {
                    "cartesian_position": [0.0] * 6,
                    "gripper_position": gripper_pos,
                }
            }
            _, info_dict = controller.forward(obs, include_info=True)

        draw_ui_panel(
            ax_ui, controller_info, info_dict, gripper_pos, gripper_width, max_width, trig, arm_status, ee_pos
        )

        now = time.time()
        if now - last_status_print > 2.0 and movement_enabled and arm_status == "ok":
            ee = info_dict.get("target_cartesian_position")
            if ee is not None:
                print(f"TELEOP  target_xyz=({ee[0]:+.3f}, {ee[1]:+.3f}, {ee[2]:+.3f})  grip={gripper_pos:.2f}")
            last_status_print = now

    interval_ms = int(1000 / CONTROL_HZ)
    ani = FuncAnimation(fig, update, interval=interval_ms, blit=False)
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
