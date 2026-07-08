#!/usr/bin/env python3
"""
Demo: Robotiq 2F gripper open/close cycle (DROID-style), with optional hand camera preview.

Default (this lab): gripper USB on NUC — start gripper server on the NUC, then run
this demo from the workstation via zerorpc:

  bash scripts/setup/openpi_start_gripper_nuc.sh   # once per session (NUC)
  conda activate robot
  cd /home/pci/Desktop/DROID
  python scripts/demo/robotiq_gripper_demo.py

With hand cameras:

  python scripts/demo/robotiq_gripper_demo.py --show-cameras

Legacy local gripper (workstation USB + polymetis-local):

  bash droid/franka/launch_gripper.sh
  python scripts/demo/robotiq_gripper_demo.py --local-gripper

Gripper commands follow DROID conventions (see droid/franka/robot.py):
  position 0.0 = fully open, 1.0 = fully closed
"""

import argparse
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
POLYMETIS_PYTHON = ROOT / "droid/fairo/polymetis/polymetis/python"
DEFAULT_MAX_WIDTH = 0.085


def load_gripper_interface():
    """Load GripperInterface from polymetis-local or via repo path (robot env)."""
    try:
        from polymetis import GripperInterface

        return GripperInterface
    except ModuleNotFoundError:
        pass

    if str(POLYMETIS_PYTHON) not in sys.path:
        sys.path.insert(0, str(POLYMETIS_PYTHON))

    try:
        from polymetis.gripper_interface import GripperInterface

        return GripperInterface
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Gripper client not available in this conda env.\n"
            "  Gripper only:  conda activate polymetis-local\n"
            "  With cameras:  bash scripts/setup/install_gripper_client_robot.sh\n"
            "                 conda activate robot"
        ) from exc


GripperInterface = None  # set in main()


def droid_position_to_width(position: float, max_width: float) -> float:
    """Map DROID gripper position [0, 1] to Robotiq finger width in meters."""
    return float(max_width * (1.0 - np.clip(position, 0.0, 1.0)))


def droid_width_to_position(width: float, max_width: float) -> float:
    return float(1.0 - (width / max_width))


def get_max_width(gripper) -> float:
    """DROID stores stroke on gripper metadata, not GripperState (see droid/franka/robot.py)."""
    metadata = getattr(gripper, "metadata", None)
    if metadata is None or metadata.max_width <= 0:
        raise RuntimeError(
            "Gripper metadata unavailable (max_width not set). "
            "Ensure launch_gripper.sh shows 'Activated.' and the modbus client is running."
        )
    return float(metadata.max_width)


def format_gripper_state(state, max_width: float) -> str:
    pos = droid_width_to_position(state.width, max_width)
    return (
        f"width={state.width:.4f} m  "
        f"max_width={max_width:.4f} m  "
        f"droid_position={pos:.3f}  "
        f"is_grasped={state.is_grasped}  "
        f"is_moving={state.is_moving}"
    )


def connect_gripper(ip_address: str, port: int, retries: int = 5):
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            gripper = GripperInterface(ip_address=ip_address, port=port)
            max_width = get_max_width(gripper)
            state = gripper.get_state()
            print(f"Connected to gripper at {ip_address}:{port}")
            print(f"Initial state: {format_gripper_state(state, max_width)}")
            return gripper, max_width
        except Exception as exc:
            last_err = exc
            print(f"Gripper connect attempt {attempt}/{retries} failed: {exc}")
            time.sleep(2.0)
    raise RuntimeError(
        "Could not connect to gripper server. "
        "On NUC: bash scripts/setup/openpi_start_gripper_nuc.sh\n"
        "On workstation (legacy): bash droid/franka/launch_gripper.sh"
    ) from last_err


class NucGripperProxy:
    """Robotiq gripper via NUC zerorpc (USB on NUC, gRPC localhost:50052 on NUC)."""

    def __init__(self, nuc_ip: str):
        from droid.misc.server_interface import ServerInterface

        self._robot = ServerInterface(ip_address=nuc_ip, launch=False)
        self._robot.launch_robot()
        self.max_width = DEFAULT_MAX_WIDTH
        state, _ = self._robot.get_robot_state()
        pos = float(state.get("gripper_position", 0.0))
        if pos > 0:
            self.max_width = DEFAULT_MAX_WIDTH

    def goto(self, width: float, speed: float, force: float, blocking: bool):
        position = droid_width_to_position(width, self.max_width)
        self._robot.update_gripper(position, velocity=False, blocking=blocking)

    def get_state(self):
        state, _ = self._robot.get_robot_state()
        pos = float(state["gripper_position"])
        width = droid_position_to_width(pos, self.max_width)
        return SimpleNamespace(width=width, is_moving=False, is_grasped=False)


def connect_gripper_via_nuc(nuc_ip: str, retries: int = 5):
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            gripper = NucGripperProxy(nuc_ip)
            state = gripper.get_state()
            print(f"Connected to gripper via NUC {nuc_ip}:4242")
            print(f"Initial state: {format_gripper_state(state, gripper.max_width)}")
            return gripper, gripper.max_width
        except Exception as exc:
            last_err = exc
            print(f"NUC gripper connect attempt {attempt}/{retries} failed: {exc}")
            time.sleep(2.0)
    raise RuntimeError(
        "Could not reach gripper via NUC. Ensure on NUC:\n"
        "  1. bash droid/franka/launch_gripper.sh  (or openpi_start_gripper_nuc.sh from workstation)\n"
        "  2. Polymetis + zerorpc :4242 running\n"
        "  3. Patched robot.py synced to NUC"
    ) from last_err


def move_gripper(gripper, max_width, position: float, speed: float, force: float, settle_s: float):
    width = droid_position_to_width(position, max_width)
    label = "OPEN" if position < 0.05 else "CLOSE" if position > 0.95 else f"pos={position:.2f}"
    print(f"\n→ {label}: goto width={width:.4f} m (speed={speed}, force={force})")
    gripper.goto(width=width, speed=speed, force=force, blocking=True)
    time.sleep(settle_s)
    state = gripper.get_state()
    print(f"  reached: {format_gripper_state(state, max_width)}")


def run_gripper_cycle(
    gripper,
    max_width,
    cycles: int,
    speed: float,
    force: float,
    settle_s: float,
    pause_s: float,
):
    """Open → close → open, repeated `cycles` times (same pattern as DROID teleop range)."""
    for i in range(cycles):
        print(f"\n=== Cycle {i + 1}/{cycles} ===")
        move_gripper(gripper, max_width, position=0.0, speed=speed, force=force, settle_s=settle_s)
        time.sleep(pause_s)
        move_gripper(gripper, max_width, position=1.0, speed=speed, force=force, settle_s=settle_s)
        time.sleep(pause_s)
        move_gripper(gripper, max_width, position=0.0, speed=speed, force=force, settle_s=settle_s)
        time.sleep(pause_s)


def _colorize_depth(depth_np, max_m=5.0):
    import cv2

    depth = np.nan_to_num(depth_np, nan=0.0, posinf=0.0, neginf=0.0)
    depth = np.clip(depth, 0.0, max_m)
    norm = (depth / max_m * 255.0).astype(np.uint8)
    return cv2.applyColorMap(norm, cv2.COLORMAP_TURBO)


class HandCameraPreview:
    """Single ZED-M hand camera at VGA — RGB + depth side by side."""

    def __init__(self, serial_number: str, width: int = 640, height: int = 480):
        import pyzed.sl as sl

        self.sl = sl
        self.width = width
        self.height = height
        self._last_frame = np.zeros((height, width * 2, 3), dtype=np.uint8)
        self._cam = sl.Camera()
        self._image = sl.Mat()
        self._depth = sl.Mat()
        self._runtime = sl.RuntimeParameters()

        init = sl.InitParameters()
        init.set_from_serial_number(int(serial_number))
        init.camera_resolution = sl.RESOLUTION.VGA
        init.camera_fps = 30
        init.depth_mode = sl.DEPTH_MODE.PERFORMANCE
        init.coordinate_units = sl.UNIT.METER
        init.depth_minimum_distance = 0.1
        init.depth_maximum_distance = 5.0

        status = self._cam.open(init)
        if status != sl.ERROR_CODE.SUCCESS:
            raise RuntimeError(f"Failed to open hand camera {serial_number}: {status}")

        print(f"Hand camera preview: ZED {serial_number} @ VGA 30fps (RGB + depth)")

    def read(self):
        import cv2

        if self._cam.grab(self._runtime) == self.sl.ERROR_CODE.SUCCESS:
            self._cam.retrieve_image(self._image, self.sl.VIEW.LEFT)
            rgb = self._image.get_data().copy()
            if rgb.shape[2] == 4:
                rgb = rgb[:, :, :3]
            if rgb.shape[:2] != (self.height, self.width):
                rgb = cv2.resize(rgb, (self.width, self.height))

            self._cam.retrieve_measure(self._depth, self.sl.MEASURE.DEPTH)
            depth_color = _colorize_depth(self._depth.get_data())
            if depth_color.shape[:2] != (self.height, self.width):
                depth_color = cv2.resize(depth_color, (self.width, self.height))

            cv2.putText(rgb, "RGB", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
            cv2.putText(depth_color, "Depth", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
            self._last_frame = np.hstack([rgb, depth_color])
        return self._last_frame

    def close(self):
        if self._cam.is_opened():
            self._cam.close()


class TeleopCamerasPreview:
    """VR teleop monitor: hand ZED (RGB+depth) + both third-person ZED 2i (RGB)."""

    def __init__(
        self,
        hand_serial: str,
        third_left_serial: str,
        third_right_serial: str,
        hand_w: int = 640,
        hand_h: int = 480,
        third_w: int = 640,
        third_h: int = 480,
        fps: int = 15,
    ):
        import cv2
        import pyzed.sl as sl

        self.sl = sl
        self.cv2 = cv2
        self.hand_h = hand_h
        self.third_h = third_h
        self.hand_w = hand_w
        self.third_w = third_w
        self._blank_hand = np.zeros((hand_h, hand_w * 2, 3), dtype=np.uint8)
        self._blank_third = np.zeros((third_h, third_w * 2, 3), dtype=np.uint8)
        self._last_hand = self._blank_hand.copy()
        self._last_third = self._blank_third.copy()

        def _open(serial: str, depth_mode, label: str):
            cam = sl.Camera()
            init = sl.InitParameters()
            init.set_from_serial_number(int(serial))
            init.camera_resolution = sl.RESOLUTION.VGA
            init.camera_fps = fps
            init.depth_mode = depth_mode
            init.coordinate_units = sl.UNIT.METER
            init.depth_minimum_distance = 0.1
            init.depth_maximum_distance = 5.0
            status = cam.open(init)
            if status != sl.ERROR_CODE.SUCCESS:
                raise RuntimeError(f"Failed to open {label} camera {serial}: {status}")
            print(f"Teleop preview: opened {label} ZED {serial}")
            return cam

        self._hand = _open(hand_serial, sl.DEPTH_MODE.PERFORMANCE, "hand")
        self._third_left = _open(third_left_serial, sl.DEPTH_MODE.NONE, "third-person L")
        self._third_right = _open(third_right_serial, sl.DEPTH_MODE.NONE, "third-person R")

        self._hand_image = sl.Mat()
        self._hand_depth = sl.Mat()
        self._third_l_image = sl.Mat()
        self._third_r_image = sl.Mat()
        self._hand_runtime = sl.RuntimeParameters()
        self._third_runtime = sl.RuntimeParameters()

        canvas_w = max(hand_w * 2, third_w * 2)
        self._canvas = np.zeros((hand_h + third_h, canvas_w, 3), dtype=np.uint8)

    def _grab_rgb(self, cam, image_mat, width, height):
        if cam.grab(self._third_runtime) != self.sl.ERROR_CODE.SUCCESS:
            return None
        cam.retrieve_image(image_mat, self.sl.VIEW.LEFT)
        rgb = image_mat.get_data().copy()
        if rgb.shape[2] == 4:
            rgb = rgb[:, :, :3]
        if rgb.shape[:2] != (height, width):
            rgb = self.cv2.resize(rgb, (width, height))
        return rgb

    def read(self):
        if self._hand.grab(self._hand_runtime) == self.sl.ERROR_CODE.SUCCESS:
            self._hand.retrieve_image(self._hand_image, self.sl.VIEW.LEFT)
            rgb = self._hand_image.get_data().copy()
            if rgb.shape[2] == 4:
                rgb = rgb[:, :, :3]
            if rgb.shape[:2] != (self.hand_h, self.hand_w):
                rgb = self.cv2.resize(rgb, (self.hand_w, self.hand_h))

            self._hand.retrieve_measure(self._hand_depth, self.sl.MEASURE.DEPTH)
            depth_color = _colorize_depth(self._hand_depth.get_data())
            if depth_color.shape[:2] != (self.hand_h, self.hand_w):
                depth_color = self.cv2.resize(depth_color, (self.hand_w, self.hand_h))

            self.cv2.putText(rgb, "Hand RGB", (8, 24), self.cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            self.cv2.putText(depth_color, "Hand depth", (8, 24), self.cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            self._last_hand = np.hstack([rgb, depth_color])

        left_rgb = self._grab_rgb(self._third_left, self._third_l_image, self.third_w, self.third_h)
        right_rgb = self._grab_rgb(self._third_right, self._third_r_image, self.third_w, self.third_h)
        if left_rgb is not None and right_rgb is not None:
            self.cv2.putText(left_rgb, "Third-person L", (8, 24), self.cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            self.cv2.putText(right_rgb, "Third-person R", (8, 24), self.cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            self._last_third = np.hstack([left_rgb, right_rgb])

        canvas_w = self._canvas.shape[1]
        self._canvas[: self.hand_h, : self.hand_w * 2] = self._last_hand
        self._canvas[self.hand_h :, : self.third_w * 2] = self._last_third
        return self._canvas

    def close(self):
        for cam in (self._hand, self._third_left, self._third_right):
            if cam.is_opened():
                cam.close()


def run_with_cameras(
    gripper,
    max_width,
    cycles,
    speed,
    force,
    settle_s,
    pause_s,
    all_cameras=False,
):
    try:
        import cv2
    except ModuleNotFoundError:
        print("ERROR: --show-cameras requires opencv.")
        print("  conda activate robot   # DROID env with cv2 + pyzed")
        print("  or: pip install opencv-python")
        sys.exit(1)

    try:
        import pyzed.sl  # noqa: F401
    except (ModuleNotFoundError, ImportError) as exc:
        print(f"ZED Python API not available ({exc}).")
        print("Install it once with:")
        print("  bash scripts/setup/install_zed_python_api.sh")
        print("Running gripper-only demo instead.\n")
        run_gripper_cycle(gripper, max_width, cycles, speed, force, settle_s, pause_s)
        return

    from droid.misc.parameters import hand_camera_id

    if not hand_camera_id:
        print("ERROR: hand_camera_id is empty in droid/misc/parameters.py")
        print("Run: python scripts/setup/list_zed_cameras.py")
        sys.exit(1)

    if all_cameras:
        window = "DROID gripper demo — all cameras RGB + depth (q to quit)"
        preview = _AllCamerasPreview()
    else:
        window = "DROID gripper demo — RGB + depth (q to quit)"
        preview = HandCameraPreview(hand_camera_id)

    cv2.namedWindow(window, cv2.WINDOW_AUTOSIZE)

    def refresh_frame(gripper_state_text=""):
        frame = preview.read()
        if gripper_state_text:
            cv2.putText(
                frame,
                gripper_state_text[:90],
                (8, frame.shape[0] - 12),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 220, 255),
                1,
                cv2.LINE_AA,
            )
        cv2.imshow(window, frame)
        return cv2.waitKey(30) & 0xFF

    def cleanup_and_exit(open_gripper=True):
        if open_gripper:
            try:
                gripper.goto(width=max_width, speed=speed, force=force, blocking=True)
            except Exception:
                pass
        preview.close()
        cv2.destroyAllWindows()
        sys.exit(0)

    def move_with_preview(position, label):
        width = droid_position_to_width(position, max_width)
        print(f"\n→ {label}: goto width={width:.4f} m")
        gripper.goto(width=width, speed=speed, force=force, blocking=False)
        t0 = time.time()
        while time.time() - t0 < settle_s + 2.0:
            state = gripper.get_state()
            key = refresh_frame(format_gripper_state(state, max_width))
            if key == ord("q"):
                cleanup_and_exit()
            if not state.is_moving and time.time() - t0 > settle_s:
                break
        state = gripper.get_state()
        print(f"  reached: {format_gripper_state(state, max_width)}")
        time.sleep(pause_s)

    try:
        for i in range(cycles):
            print(f"\n=== Cycle {i + 1}/{cycles} ===")
            move_with_preview(0.0, "OPEN")
            move_with_preview(1.0, "CLOSE")
            move_with_preview(0.0, "OPEN")

        refresh_frame("Demo complete — press q to close")
        print("\nDemo complete. Press q in the camera window to exit.")
        while refresh_frame() != ord("q"):
            pass
    finally:
        preview.close()
        cv2.destroyAllWindows()


class _AllCamerasPreview:
    """All ZEDs at VGA 15fps — one row per camera: RGB | depth."""

    def __init__(self, tile_w=320, tile_h=240):
        import cv2
        import pyzed.sl as sl

        self.sl = sl
        self.cv2 = cv2
        self.tile_w = tile_w
        self.tile_h = tile_h
        self._blank_pair = np.zeros((tile_h, tile_w * 2, 3), dtype=np.uint8)
        self._rows = []
        self._runtimes = []

        devices = list(sl.Camera.get_device_list())
        # Hand camera (ZED-M) first when identifiable
        from droid.misc.parameters import hand_camera_id

        def sort_key(dev):
            sn = str(dev.serial_number)
            if sn == hand_camera_id:
                return (0, sn)
            return (1, sn)

        devices.sort(key=sort_key)

        for dev in devices:
            cam = sl.Camera()
            init = sl.InitParameters()
            init.set_from_serial_number(int(dev.serial_number))
            init.camera_resolution = sl.RESOLUTION.VGA
            init.camera_fps = 15
            init.depth_mode = sl.DEPTH_MODE.PERFORMANCE
            init.coordinate_units = sl.UNIT.METER
            init.depth_minimum_distance = 0.1
            init.depth_maximum_distance = 5.0
            if cam.open(init) != sl.ERROR_CODE.SUCCESS:
                print(f"WARN: could not open {dev.serial_number}")
                continue
            label = f"{dev.camera_model} {dev.serial_number}"
            self._rows.append(
                {
                    "label": label,
                    "cam": cam,
                    "image": sl.Mat(),
                    "depth": sl.Mat(),
                    "last": self._blank_pair.copy(),
                }
            )
            self._runtimes.append(sl.RuntimeParameters())
            print(f"  opened {label} (RGB + depth)")

        if not self._rows:
            raise RuntimeError("No cameras opened for preview")

        self._canvas = np.zeros((tile_h * len(self._rows), tile_w * 2, 3), dtype=np.uint8)

    def read(self):
        for i, row in enumerate(self._rows):
            cam = row["cam"]
            y0 = i * self.tile_h
            if cam.grab(self._runtimes[i]) == self.sl.ERROR_CODE.SUCCESS:
                cam.retrieve_image(row["image"], self.sl.VIEW.LEFT)
                rgb = row["image"].get_data()
                if rgb.shape[2] == 4:
                    rgb = rgb[:, :, :3]
                rgb = self.cv2.resize(rgb, (self.tile_w, self.tile_h))

                cam.retrieve_measure(row["depth"], self.sl.MEASURE.DEPTH)
                depth_color = _colorize_depth(row["depth"].get_data())
                depth_color = self.cv2.resize(depth_color, (self.tile_w, self.tile_h))

                pair = np.hstack([rgb, depth_color])
                self.cv2.putText(pair, "RGB", (6, 20), self.cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                self.cv2.putText(pair, "Depth", (self.tile_w + 6, 20), self.cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                self.cv2.putText(pair, row["label"], (6, self.tile_h - 8), self.cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 220, 255), 1)
                row["last"] = pair

            self._canvas[y0 : y0 + self.tile_h, :] = row["last"]
        return self._canvas

    def close(self):
        for row in self._rows:
            cam = row["cam"]
            if cam.is_opened():
                cam.close()


def parse_args():
    parser = argparse.ArgumentParser(description="Robotiq 2F gripper demo (DROID-style)")
    parser.add_argument("--nuc-ip", default=None, help="NUC IP for gripper via zerorpc (default: parameters.nuc_ip)")
    parser.add_argument(
        "--local-gripper",
        action="store_true",
        help="Connect to local gRPC gripper (workstation USB) instead of NUC",
    )
    parser.add_argument("--gripper-ip", default="localhost", help="Local gripper gRPC server IP (--local-gripper only)")
    parser.add_argument("--gripper-port", type=int, default=50052, help="Local gripper gRPC port (--local-gripper only)")
    parser.add_argument("--cycles", type=int, default=2, help="Number of open/close/open cycles")
    parser.add_argument(
        "--speed",
        type=float,
        default=0.05,
        help="Gripper speed (matches droid/franka/robot.py default)",
    )
    parser.add_argument(
        "--force",
        type=float,
        default=0.1,
        help="Gripper force (matches droid/franka/robot.py default)",
    )
    parser.add_argument("--settle-s", type=float, default=1.0, help="Seconds to wait after each move")
    parser.add_argument("--pause-s", type=float, default=0.5, help="Pause between moves")
    parser.add_argument(
        "--show-cameras",
        action="store_true",
        help="Show live hand ZED-M feed while the gripper moves",
    )
    parser.add_argument(
        "--all-cameras",
        action="store_true",
        help="Show all ZEDs, each row RGB + depth (VGA 15fps; needs good USB bandwidth)",
    )
    return parser.parse_args()


def main():
    global GripperInterface
    GripperInterface = load_gripper_interface()

    args = parse_args()
    sys.path.insert(0, str(ROOT))
    from droid.misc.parameters import nuc_ip

    if args.local_gripper:
        gripper, max_width = connect_gripper(args.gripper_ip, args.gripper_port)
    else:
        target_nuc = args.nuc_ip or nuc_ip
        if not target_nuc:
            print("ERROR: nuc_ip not set — use --nuc-ip or set droid/misc/parameters.py")
            sys.exit(1)
        gripper, max_width = connect_gripper_via_nuc(target_nuc)

    print(
        f"\nStarting demo: {args.cycles} cycle(s), speed={args.speed}, force={args.force}"
    )
    if args.show_cameras:
        run_with_cameras(
            gripper,
            max_width,
            cycles=args.cycles,
            speed=args.speed,
            force=args.force,
            settle_s=args.settle_s,
            pause_s=args.pause_s,
            all_cameras=args.all_cameras,
        )
    else:
        run_gripper_cycle(
            gripper,
            max_width,
            cycles=args.cycles,
            speed=args.speed,
            force=args.force,
            settle_s=args.settle_s,
            pause_s=args.pause_s,
        )
        print("\nDone. Gripper left open.")


if __name__ == "__main__":
    main()
