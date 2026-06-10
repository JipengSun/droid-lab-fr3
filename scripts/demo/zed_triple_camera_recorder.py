#!/usr/bin/env python3
"""
Live preview + record RGB and depth from all three DROID ZED cameras.

  conda activate robot
  cd /home/pci/Desktop/DROID
  python scripts/demo/zed_triple_camera_recorder.py

Controls:
  r / click RECORD button — start or stop recording
  q — quit (stops an active recording first)

Each session is saved under --output-dir (default: recordings/<timestamp>/):
  composite.mp4             — 3× RGB + 3× colorized depth grid (default, use --no-composite-video to skip)
  <serial>/rgb.mp4          — per-camera left RGB video (VGA)
  <serial>/depth/NNNNNN.npy — per-camera float32 depth in meters
  session.json              — metadata (serials, fps, frame counts)
"""

import argparse
import json
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def _colorize_depth(depth_np, max_m=5.0):
    import cv2

    depth = np.nan_to_num(depth_np, nan=0.0, posinf=0.0, neginf=0.0)
    depth = np.clip(depth, 0.0, max_m)
    norm = (depth / max_m * 255.0).astype(np.uint8)
    return cv2.applyColorMap(norm, cv2.COLORMAP_TURBO)


class _DepthWriter:
    """Background thread writes depth frames to numbered .npy files."""

    def __init__(self, depth_dir: Path):
        self.depth_dir = depth_dir
        self.depth_dir.mkdir(parents=True, exist_ok=True)
        self._queue = Queue(maxsize=120)
        self._stop = threading.Event()
        self._count = 0
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def submit(self, depth: np.ndarray):
        self._queue.put(depth.copy())

    def _run(self):
        while not self._stop.is_set() or not self._queue.empty():
            try:
                depth = self._queue.get(timeout=0.1)
            except Empty:
                continue
            path = self.depth_dir / f"{self._count:06d}.npy"
            np.save(path, depth.astype(np.float32))
            self._count += 1

    def close(self):
        self._stop.set()
        self._thread.join(timeout=30.0)
        return self._count


class _CameraRecording:
    def __init__(self, serial: str, label: str, cam_dir: Path, fps: int, width: int, height: int):
        import cv2

        self.serial = serial
        self.label = label
        self.cam_dir = cam_dir
        self.cam_dir.mkdir(parents=True, exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self._rgb_writer = cv2.VideoWriter(str(cam_dir / "rgb.mp4"), fourcc, fps, (width, height))
        self._depth_writer = _DepthWriter(cam_dir / "depth")
        self._rgb_frames = 0

    def write(self, rgb_bgr: np.ndarray, depth_m: np.ndarray):
        self._rgb_writer.write(rgb_bgr)
        self._depth_writer.submit(depth_m)
        self._rgb_frames += 1

    def close(self):
        self._rgb_writer.release()
        depth_frames = self._depth_writer.close()
        return {"serial": self.serial, "label": self.label, "rgb_frames": self._rgb_frames, "depth_frames": depth_frames}


class _CompositeVideoWriter:
    """2-row grid video: top = RGB tiles, bottom = colorized depth tiles."""

    def __init__(self, path: Path, fps: int, tile_w: int, tile_h: int, num_cams: int = 3):
        import cv2

        self._tile_w = tile_w
        self._tile_h = tile_h
        self._num_cams = num_cams
        self._size = (tile_w * num_cams, tile_h * 2)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self._writer = cv2.VideoWriter(str(path), fourcc, fps, self._size)
        self._frames = 0

    def write(self, rgb_tiles, depth_tiles, labels):
        import cv2

        blank = np.zeros((self._tile_h, self._tile_w, 3), dtype=np.uint8)
        rgb_row = []
        depth_row = []
        for i in range(self._num_cams):
            rgb = rgb_tiles[i] if i < len(rgb_tiles) else blank
            depth = depth_tiles[i] if i < len(depth_tiles) else blank
            label = labels[i] if i < len(labels) else ""
            cv2.putText(rgb, label, (6, self._tile_h - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 220, 255), 1)
            cv2.putText(depth, label, (6, self._tile_h - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 220, 255), 1)
            rgb_row.append(rgb)
            depth_row.append(depth)
        frame = np.vstack([np.hstack(rgb_row), np.hstack(depth_row)])
        self._writer.write(frame)
        self._frames += 1

    def close(self):
        self._writer.release()
        return self._frames


class TripleCameraRecorder:
    HEADER_H = 56
    BTN_X0, BTN_Y0, BTN_X1, BTN_Y1 = 12, 10, 180, 46

    def __init__(self, camera_ids, tile_w=320, tile_h=240, fps=15, save_composite_video=True):
        import cv2
        import pyzed.sl as sl

        from droid.misc.parameters import hand_camera_id

        self.cv2 = cv2
        self.sl = sl
        self.tile_w = tile_w
        self.tile_h = tile_h
        self.fps = fps
        self.save_composite_video = save_composite_video
        self._blank_tile = np.zeros((tile_h, tile_w, 3), dtype=np.uint8)
        self._rows = []
        self._runtimes = []
        self._recording = False
        self._session_dir = None
        self._writers = {}
        self._composite_writer = None
        self._session_started_at = None
        self._blink_on = True
        self._last_blink = time.time()
        self._output_root = ROOT / "recordings"

        devices = {str(d.serial_number): d for d in sl.Camera.get_device_list()}
        ordered_ids = []
        for cid in camera_ids:
            if cid and cid in devices:
                ordered_ids.append(cid)
            elif cid:
                print(f"WARN: camera {cid} not connected — skipping")

        if not ordered_ids:
            raise RuntimeError("No configured cameras are connected. Check USB and parameters.py IDs.")

        def sort_key(serial):
            return (0, serial) if serial == hand_camera_id else (1, serial)

        ordered_ids.sort(key=sort_key)

        for serial in ordered_ids:
            dev = devices[serial]
            cam = sl.Camera()
            init = sl.InitParameters()
            init.set_from_serial_number(int(serial))
            init.camera_resolution = sl.RESOLUTION.VGA
            init.camera_fps = fps
            init.depth_mode = sl.DEPTH_MODE.PERFORMANCE
            init.coordinate_units = sl.UNIT.METER
            init.depth_minimum_distance = 0.2
            init.depth_maximum_distance = 5.0
            if cam.open(init) != sl.ERROR_CODE.SUCCESS:
                print(f"WARN: could not open {serial}")
                continue
            label = f"{dev.camera_model} {serial}"
            self._rows.append(
                {
                    "serial": serial,
                    "label": label,
                    "cam": cam,
                    "image": sl.Mat(),
                    "depth": sl.Mat(),
                    "last_rgb": None,
                    "last_depth": None,
                    "last_rgb_tile": self._blank_tile.copy(),
                    "last_depth_tile": self._blank_tile.copy(),
                    "last_pair": np.zeros((tile_h, tile_w * 2, 3), dtype=np.uint8),
                }
            )
            self._runtimes.append(sl.RuntimeParameters())
            print(f"  opened {label} @ VGA {fps}fps (RGB + depth)")

        if not self._rows:
            raise RuntimeError("Failed to open any cameras")

        body_h = tile_h * len(self._rows)
        self._canvas = np.zeros((self.HEADER_H + body_h, tile_w * 2, 3), dtype=np.uint8)
        self._canvas[: self.HEADER_H] = (40, 40, 40)

    def _grab_frame(self, row, runtime):
        cam = row["cam"]
        if cam.grab(runtime) != self.sl.ERROR_CODE.SUCCESS:
            return None, None

        cam.retrieve_image(row["image"], self.sl.VIEW.LEFT)
        rgb = row["image"].get_data().copy()
        if rgb.shape[2] == 4:
            rgb_bgr = self.cv2.cvtColor(rgb, self.cv2.COLOR_BGRA2BGR)
        else:
            rgb_bgr = rgb[:, :, :3].copy()

        cam.retrieve_measure(row["depth"], self.sl.MEASURE.DEPTH)
        depth_m = row["depth"].get_data().copy()
        return rgb_bgr, depth_m

    def read(self):
        for i, row in enumerate(self._rows):
            y0 = self.HEADER_H + i * self.tile_h
            grabbed = self._grab_frame(row, self._runtimes[i])
            if grabbed[0] is not None:
                rgb_bgr, depth_m = grabbed
                row["last_rgb"] = rgb_bgr
                row["last_depth"] = depth_m

                rgb_show = self.cv2.resize(rgb_bgr, (self.tile_w, self.tile_h))
                depth_color = _colorize_depth(depth_m)
                depth_color = self.cv2.resize(depth_color, (self.tile_w, self.tile_h))
                row["last_rgb_tile"] = rgb_show
                row["last_depth_tile"] = depth_color
                pair = np.hstack([rgb_show, depth_color])
                self.cv2.putText(pair, "RGB", (6, 20), self.cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                self.cv2.putText(pair, "Depth", (self.tile_w + 6, 20), self.cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                self.cv2.putText(pair, row["label"], (6, self.tile_h - 8), self.cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 220, 255), 1)
                row["last_pair"] = pair

                if self._recording and row["serial"] in self._writers:
                    full_h, full_w = rgb_bgr.shape[:2]
                    self._writers[row["serial"]].write(rgb_bgr, depth_m)

            self._canvas[y0 : y0 + self.tile_h, :] = row["last_pair"]

        if self._recording and self._composite_writer is not None:
            rgb_tiles = [row["last_rgb_tile"] for row in self._rows]
            depth_tiles = [row["last_depth_tile"] for row in self._rows]
            labels = [row["label"] for row in self._rows]
            self._composite_writer.write(rgb_tiles, depth_tiles, labels)

        self._draw_header()
        return self._canvas

    def _draw_header(self):
        cv2 = self.cv2
        h = self.HEADER_H
        self._canvas[:h, :] = (40, 40, 40)

        btn_color = (0, 0, 180) if self._recording else (0, 140, 0)
        cv2.rectangle(self._canvas, (self.BTN_X0, self.BTN_Y0), (self.BTN_X1, self.BTN_Y1), btn_color, -1)
        cv2.rectangle(self._canvas, (self.BTN_X0, self.BTN_Y0), (self.BTN_X1, self.BTN_Y1), (220, 220, 220), 2)
        btn_label = "STOP" if self._recording else "RECORD"
        cv2.putText(self._canvas, btn_label, (self.BTN_X0 + 28, self.BTN_Y0 + 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        if self._recording:
            if time.time() - self._last_blink > 0.5:
                self._blink_on = not self._blink_on
                self._last_blink = time.time()
            if self._blink_on:
                cv2.circle(self._canvas, (200, 28), 10, (0, 0, 255), -1)
            cv2.putText(self._canvas, "REC", (215, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)
            if self._writers:
                n = next(iter(self._writers.values()))._rgb_frames
                cv2.putText(self._canvas, f"{n} frames", (270, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
            if self._session_dir:
                cv2.putText(
                    self._canvas,
                    str(self._session_dir.name),
                    (400, 34),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (160, 160, 160),
                    1,
                )
        else:
            cv2.putText(self._canvas, "r = record   q = quit", (200, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 1)

    def click(self, x, y):
        if self.BTN_X0 <= x <= self.BTN_X1 and self.BTN_Y0 <= y <= self.BTN_Y1:
            self.toggle_recording()

    def toggle_recording(self, output_root=None):
        if output_root is not None:
            self._output_root = output_root
        if self._recording:
            self.stop_recording()
        else:
            self.start_recording(self._output_root)

    def start_recording(self, output_root: Path):
        if self._recording:
            return
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self._session_dir = output_root / stamp
        self._session_dir.mkdir(parents=True, exist_ok=True)
        self._session_started_at = datetime.now().isoformat()
        self._writers = {}

        for row in self._rows:
            serial = row["serial"]
            cam_dir = self._session_dir / serial
            if row["last_rgb"] is not None:
                h, w = row["last_rgb"].shape[:2]
            else:
                h, w = 480, 640
            self._writers[serial] = _CameraRecording(serial, row["label"], cam_dir, self.fps, w, h)

        if self.save_composite_video:
            self._composite_writer = _CompositeVideoWriter(
                self._session_dir / "composite.mp4",
                self.fps,
                self.tile_w,
                self.tile_h,
                num_cams=3,
            )
            print("  composite video: composite.mp4 (3× RGB + 3× depth grid)")

        self._recording = True
        print(f"\n● Recording started → {self._session_dir}")

    def stop_recording(self):
        if not self._recording:
            return
        self._recording = False
        camera_stats = [w.close() for w in self._writers.values()]
        self._writers = {}

        composite_frames = None
        if self._composite_writer is not None:
            composite_frames = self._composite_writer.close()
            self._composite_writer = None

        meta = {
            "started_at": self._session_started_at,
            "ended_at": datetime.now().isoformat(),
            "fps": self.fps,
            "tile_preview": [self.tile_w, self.tile_h],
            "cameras": camera_stats,
        }
        if composite_frames is not None:
            meta["composite_video"] = {
                "path": "composite.mp4",
                "frames": composite_frames,
                "layout": "row1=rgb×3, row2=depth×3",
                "size": [self.tile_w * 3, self.tile_h * 2],
            }
        meta_path = self._session_dir / "session.json"
        meta_path.write_text(json.dumps(meta, indent=2))
        print(f"■ Recording stopped — saved to {self._session_dir}")
        for cam in camera_stats:
            print(f"    {cam['serial']}: {cam['rgb_frames']} rgb frames, {cam['depth_frames']} depth frames")
        if composite_frames is not None:
            print(f"    composite.mp4: {composite_frames} frames")
        print(f"    metadata: {meta_path}")

    def close(self):
        if self._recording:
            self.stop_recording()
        for row in self._rows:
            cam = row["cam"]
            if cam.is_opened():
                cam.close()


def parse_args():
    parser = argparse.ArgumentParser(description="Record RGB + depth from all 3 DROID ZED cameras")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "recordings",
        help="Root folder for recording sessions (default: DROID/recordings/)",
    )
    parser.add_argument("--fps", type=int, default=15, help="Camera capture FPS (default 15 for 3 cams on USB)")
    parser.add_argument(
        "--no-composite-video",
        action="store_true",
        help="Do not save composite.mp4 (3× RGB + 3× depth visualization grid)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        import cv2
        import pyzed.sl  # noqa: F401
    except ImportError as exc:
        print(f"ERROR: {exc}")
        print("  conda activate robot")
        print("  bash scripts/setup/install_zed_python_api.sh")
        sys.exit(1)

    sys.path.insert(0, str(ROOT))
    from droid.misc.parameters import hand_camera_id, varied_camera_1_id, varied_camera_2_id

    camera_ids = [hand_camera_id, varied_camera_1_id, varied_camera_2_id]
    print("Opening cameras:", ", ".join(camera_ids))

    try:
        recorder = TripleCameraRecorder(
            camera_ids,
            fps=args.fps,
            save_composite_video=not args.no_composite_video,
        )
        recorder._output_root = args.output_dir
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    window = "DROID ZED recorder"
    cv2.startWindowThread()
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)

    def on_mouse(event, x, y, _flags, _param):
        if event == cv2.EVENT_LBUTTONDOWN:
            recorder.click(x, y)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # OpenCV/Qt needs at least one imshow before setMouseCallback on some builds.
    first_frame = recorder.read()
    cv2.imshow(window, first_frame)
    cv2.waitKey(1)
    try:
        cv2.setMouseCallback(window, on_mouse)
    except cv2.error as exc:
        print(f"WARN: mouse clicks disabled ({exc}). Use 'r' to start/stop recording.")

    try:
        while True:
            frame = recorder.read()
            cv2.imshow(window, frame)
            key = cv2.waitKey(max(1, int(1000 / args.fps))) & 0xFF
            if key == ord("q"):
                break
            if key == ord("r"):
                recorder.toggle_recording(args.output_dir)
    finally:
        recorder.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
