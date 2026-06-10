#!/usr/bin/env python3
"""Arm-only smoke test: read state and optionally nudge joint 7.

Polymetis must already be running on the NUC. Always use launch=False so the
workstation does not relaunch the arm stack or NUC gripper.

Usage:
    conda activate robot
    cd /home/pci/Desktop/DROID
    python scripts/demo/arm_smoke_test.py              # read-only
    python scripts/demo/arm_smoke_test.py --move       # small joint-7 nudge + return
"""
import argparse
import sys
import time

# IDE terminals (e.g. Cursor) may swallow stdout from Python — mirror shell openpi_*.sh fix.
sys.stdout = sys.stderr

import numpy as np
import zerorpc

from droid.misc.parameters import nuc_ip
from droid.misc.server_interface import ServerInterface

_EMPTY_BUFFER = "Cannot retrieve robot state from empty buffer"


def _print_recovery_hint(err_text):
    if _EMPTY_BUFFER not in err_text:
        return
    print(
        "\n--- Polymetis state buffer is empty (NUC fix required) ---\n"
        "gRPC :50051 is up but franka_panda_client is not streaming joint state.\n"
        "\n"
        "On workstation (Desk browser only):\n"
        "  1. https://192.168.1.11/desk/ → Unlock brakes → Execution → Activate FCI\n"
        "  2. Watchman: disable SLP-C / SLS-C rules that block FCI\n"
        "\n"
        "On NUC (physical access or NUC agent):\n"
        "  1. Sync patched droid/franka/robot.py (gripper optional) to NUC repo\n"
        "  2. Relaunch Polymetis:\n"
        "     pkill -9 franka_panda_cl; pkill -9 run_server\n"
        "     launch_robot.py robot_client=franka_hardware use_real_time=false\n"
        "  3. Restart zerorpc: python scripts/server/run_server.py\n"
        "  4. Check /tmp/polymetis_connect.log ends with 'Connected.'\n"
        "\n"
        "See docs/workstation-agent-handoff.md and docs/nuc-agent-instructions.md\n"
    )


def main():
    parser = argparse.ArgumentParser(description="DROID arm smoke test via NUC zerorpc")
    parser.add_argument(
        "--move",
        action="store_true",
        help="Nudge joint 7 by +0.05 rad, wait 2s, return to start",
    )
    parser.add_argument("--ip", default=nuc_ip, help="NUC IP (default: parameters.nuc_ip)")
    args = parser.parse_args()

    robot = ServerInterface(ip_address=args.ip, launch=False)
    try:
        robot.launch_robot()
        print("launch_robot OK")
    except zerorpc.exceptions.RemoteError as err:
        print(f"launch_robot skipped (RemoteError: gripper likely absent on NUC)")
    except Exception as err:
        print(f"launch_robot skipped ({err.__class__.__name__})")

    try:
        start = np.array(robot.get_joint_positions())
        ee = np.array(robot.get_ee_pose())
    except zerorpc.exceptions.RemoteError as err:
        _print_recovery_hint(str(err))
        sys.exit(1)
    print("joints (rad):", np.round(start, 4))
    print("ee_pose [x,y,z,rx,ry,rz]:", np.round(ee, 4))

    if not args.move:
        print("\nRead-only OK. Re-run with --move for a small joint-7 test.")
        return

    target = start.copy()
    target[6] += 0.05
    print("\nMoving joint 7 by +0.05 rad...")
    robot.update_joints(target, velocity=False, blocking=True)
    time.sleep(2)
    print("at target:", np.round(robot.get_joint_positions(), 4))

    print("Returning to start...")
    robot.update_joints(start, velocity=False, blocking=True)
    time.sleep(1)
    final = np.array(robot.get_joint_positions())
    print("final joints:", np.round(final, 4))
    print("max delta from start:", np.max(np.abs(final - start)))


if __name__ == "__main__":
    main()
