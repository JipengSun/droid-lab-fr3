#!/usr/bin/env python3
"""List Stereolabs ZED cameras connected to this machine."""

import sys


def format_model(sl, camera_model):
    if isinstance(camera_model, str):
        return camera_model
    if hasattr(sl, "MODEL"):
        try:
            return str(sl.MODEL(camera_model))
        except (ValueError, TypeError):
            pass
    return str(camera_model)


def format_device(sl, dev):
    lines = [
        f"  serial={dev.serial_number}  model={format_model(sl, dev.camera_model)}",
    ]
    path = getattr(dev, "path", None) or getattr(dev, "camera_path", None)
    if path is not None:
        lines.append(f"  path={path}")
    if hasattr(dev, "camera_state"):
        lines.append(f"  state={dev.camera_state}")
    if hasattr(dev, "input_type"):
        lines.append(f"  input_type={dev.input_type}")
    return "\n".join(lines)


def main():
    try:
        import pyzed.sl as sl
    except ImportError as exc:
        print("ERROR: pyzed is not installed in this Python environment.")
        print(f"  ({exc})")
        print("\nInstall with:")
        print("  bash scripts/setup/install_zed_python_api.sh")
        sys.exit(1)

    try:
        devices = sl.Camera.get_device_list()
    except Exception as exc:
        print(f"ERROR: Could not enumerate ZED devices: {exc}")
        sys.exit(1)

    if not devices:
        print("No ZED cameras detected.")
        print("Check USB cables and that the cameras are powered.")
        sys.exit(1)

    print(f"Found {len(devices)} ZED camera(s):\n")
    for i, dev in enumerate(devices):
        print(f"[{i}]")
        print(format_device(sl, dev))
        print()

    print("Add camera serials to droid/misc/parameters.py, e.g.:")
    print('  hand_camera_id = "12345678"       # ZED-M on gripper')
    print('  varied_camera_1_id = "23456789"   # ZED 2i')
    print('  varied_camera_2_id = "34567890"   # ZED 2i')


if __name__ == "__main__":
    main()
