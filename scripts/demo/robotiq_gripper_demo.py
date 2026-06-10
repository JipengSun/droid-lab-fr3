#!/usr/bin/env python3
"""
Demo: Robotiq 2F gripper open/close cycle (DROID-style), with optional hand camera preview.

The gripper server must already be running in another terminal:

  bash scripts/setup/install_polymetis_gripper.sh   # once, if polymetis-local missing
  conda activate polymetis-local
  cd /home/pci/Desktop/DROID
  bash droid/franka/launch_gripper.sh

If the gripper is on a different USB port, edit `gripper.comport` in that script
(or run launch_gripper.py manually with the correct port).

Then run the demo:

  conda activate polymetis-local
  cd /home/pci/Desktop/DROID
  python scripts/demo/robotiq_gripper_demo.py

With hand cameras (robot env — run install_gripper_client_robot.sh once first):

  bash scripts/setup/install_gripper_client_robot.sh
  conda activate robot
  cd /home/pci/Desktop/DROID
  python scripts/demo/robotiq_gripper_demo.py --show-cameras

Gripper commands follow DROID conventions (see droid/franka/robot.py):
  position 0.0 = fully open, 1.0 = fully closed
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
POLYMETIS_PYTHON = ROOT / "droid/fairo/polymetis/polymetis/python"


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
        "Start it first with: bash droid/franka/launch_gripper.sh"
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
    parser.add_argument("--gripper-ip", default="localhost", help="Gripper gRPC server IP")
    parser.add_argument("--gripper-port", type=int, default=50052, help="Gripper gRPC server port")
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
    gripper, max_width = connect_gripper(args.gripper_ip, args.gripper_port)

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
