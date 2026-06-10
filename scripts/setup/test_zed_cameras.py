#!/usr/bin/env python3
"""
Grab one frame from each connected ZED and save PNGs under /tmp/zed_test/.

  conda activate robot
  python scripts/setup/test_zed_cameras.py
  python scripts/setup/test_zed_cameras.py --preview   # live OpenCV window per camera
"""

import argparse
import sys
from pathlib import Path

import numpy as np


def main():
    parser = argparse.ArgumentParser(description="Test ZED camera capture")
    parser.add_argument("--preview", action="store_true", help="Show live preview (press q to next cam)")
    parser.add_argument("--out", default="/tmp/zed_test", help="Output directory for saved frames")
    args = parser.parse_args()

    try:
        import cv2
        import pyzed.sl as sl
    except ImportError as exc:
        print(f"ERROR: {exc}")
        print("Run: bash scripts/setup/install_zed_python_api.sh")
        sys.exit(1)

    devices = sl.Camera.get_device_list()
    if not devices:
        print("No ZED cameras found.")
        sys.exit(1)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    for dev in devices:
        serial = str(dev.serial_number)
        print(f"\nOpening ZED {serial}...")
        cam = sl.Camera()
        init = sl.InitParameters()
        init.set_from_serial_number(int(serial))
        init.camera_resolution = sl.RESOLUTION.VGA
        init.camera_fps = 30
        init.depth_mode = sl.DEPTH_MODE.NONE

        status = cam.open(init)
        if status != sl.ERROR_CODE.SUCCESS:
            print(f"  FAILED to open: {status}")
            continue

        runtime = sl.RuntimeParameters()
        if cam.grab(runtime) != sl.ERROR_CODE.SUCCESS:
            print("  FAILED to grab frame")
            cam.close()
            continue

        img = sl.Mat()
        cam.retrieve_image(img, sl.VIEW.LEFT)
        frame = img.get_data().copy()
        path = out_dir / f"{serial}_left.png"
        cv2.imwrite(str(path), frame)
        print(f"  Saved {path}  shape={frame.shape}")

        if args.preview:
            cv2.imshow(f"ZED {serial} (q = next)", frame)
            while cv2.waitKey(30) & 0xFF != ord("q"):
                if cam.grab(runtime) == sl.ERROR_CODE.SUCCESS:
                    cam.retrieve_image(img, sl.VIEW.LEFT)
                    frame = img.get_data().copy()
                    cv2.imshow(f"ZED {serial} (q = next)", frame)
            cv2.destroyAllWindows()

        cam.close()

    print(f"\nDone. Images in {out_dir}")


if __name__ == "__main__":
    main()
