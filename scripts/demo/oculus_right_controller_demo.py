#!/usr/bin/env python3
"""
Live demo: Quest right controller drives a virtual target on screen.

Run (headset on, USB connected):
  export PATH="$HOME/platform-tools:$PATH"
  conda activate robot
  cd /home/pci/Desktop/DROID
  python scripts/demo/oculus_right_controller_demo.py

Controls (right controller):
  - Side grip (RG): enable movement — target follows controller delta from grab point
  - Index trigger: target size / gripper bar
  - A / B: panel turns green / red
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from oculus_reader.reader import OculusReader

RIGHT = "r"
WORKSPACE = 0.35


def trigger_value(buttons):
    val = buttons.get("rightTrig", 0.0)
    if isinstance(val, (tuple, list)):
        return float(val[0]) if val else 0.0
    return float(val)


def draw_frame(ax, mat, scale=0.07):
    origin = mat[:3, 3]
    rot = mat[:3, :3]
    for i, color in enumerate(["#e74c3c", "#2ecc71", "#3498db"]):
        tip = origin + rot[:, i] * scale
        ax.plot([origin[0], tip[0]], [origin[1], tip[1]], [origin[2], tip[2]], color=color, lw=2)


def draw_box(ax, center, size, color="#3498db", alpha=0.55):
    s = size / 2.0
    x, y, z = center
    corners = np.array(
        [
            [x - s, y - s, z - s],
            [x + s, y - s, z - s],
            [x + s, y + s, z - s],
            [x - s, y + s, z - s],
            [x - s, y - s, z + s],
            [x + s, y - s, z + s],
            [x + s, y + s, z + s],
            [x - s, y + s, z + s],
        ]
    )
    faces = [
        [corners[j] for j in (0, 1, 2, 3)],
        [corners[j] for j in (4, 5, 6, 7)],
        [corners[j] for j in (0, 1, 5, 4)],
        [corners[j] for j in (2, 3, 7, 6)],
        [corners[j] for j in (1, 2, 6, 5)],
        [corners[j] for j in (0, 3, 7, 4)],
    ]
    ax.add_collection3d(Poly3DCollection(faces, facecolors=color, edgecolors="k", alpha=alpha, linewidths=0.4))


class TeleopState:
    def __init__(self):
        self.movement_enabled = False
        self.ctrl_origin = None
        self.target_origin = np.zeros(3)


def setup_3d(ax):
    ax.set_xlim(-WORKSPACE, WORKSPACE)
    ax.set_ylim(-WORKSPACE, WORKSPACE)
    ax.set_zlim(-WORKSPACE, WORKSPACE)
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    ax.set_title("Right controller → blue target")
    ax.plot([0, 0.08], [0, 0], [0, 0], "r-", lw=1, alpha=0.4)
    ax.plot([0, 0], [0, 0.08], [0, 0], "g-", lw=1, alpha=0.4)
    ax.plot([0, 0], [0, 0], [0, 0.08], "b-", lw=1, alpha=0.4)


def draw_ui_panel(ax, trig, rg, pressed_a, pressed_b, target_pos):
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
    ax.add_patch(plt.Rectangle((0.1, 0.72), 0.8 * trig, 0.08, color="#3498db"))
    ax.add_patch(plt.Rectangle((0.1, 0.72), 0.8, 0.08, fill=False, edgecolor="#2c3e50", lw=1.5))
    ax.text(0.5, 0.65, f"{trig * 100:.0f}%", ha="center", fontsize=10)

    ax.text(0.5, 0.48, "Side grip (RG)", ha="center", fontsize=11, weight="bold")
    ax.add_patch(plt.Circle((0.5, 0.35), 0.07, color="#2ecc71" if rg else "#bdc3c7"))
    ax.text(0.5, 0.35, "ON" if rg else "off", ha="center", va="center", fontsize=9, color="white" if rg else "#555")

    ax.text(0.28, 0.12, "A", ha="center", fontsize=14, weight="bold", color="#27ae60" if pressed_a else "#aaa")
    ax.text(0.72, 0.12, "B", ha="center", fontsize=14, weight="bold", color="#c0392b" if pressed_b else "#aaa")

    if target_pos is not None:
        ax.text(
            0.5,
            0.02,
            f"target X={target_pos[0]:+.3f}  Y={target_pos[1]:+.3f}  Z={target_pos[2]:+.3f}",
            ha="center",
            fontsize=8,
            family="monospace",
        )


def main():
    print("Starting OculusReader — wear the headset and keep controllers visible.")
    reader = OculusReader()
    teleop = TeleopState()

    fig = plt.figure(figsize=(11, 5))
    fig.canvas.manager.set_window_title("DROID Oculus demo")
    ax3d = fig.add_subplot(121, projection="3d")
    ax_ui = fig.add_subplot(122)
    fig.subplots_adjust(wspace=0.25)

    def update(_frame):
        transforms, buttons = reader.get_transformations_and_buttons()

        ax3d.cla()
        ax_ui.cla()
        setup_3d(ax3d)

        if RIGHT not in transforms:
            ax3d.text2D(0.05, 0.92, "Waiting for right controller…", transform=ax3d.transAxes)
            draw_ui_panel(ax_ui, 0.0, False, False, False, None)
            return

        mat = transforms[RIGHT]
        ctrl_pos = mat[:3, 3].copy()
        rg = bool(buttons.get("RG", False))
        trig = trigger_value(buttons)
        pressed_a = bool(buttons.get("A", False))
        pressed_b = bool(buttons.get("B", False))

        if rg and not teleop.movement_enabled:
            teleop.movement_enabled = True
            teleop.ctrl_origin = ctrl_pos
            teleop.target_origin = np.zeros(3)
        elif not rg:
            teleop.movement_enabled = False

        if teleop.movement_enabled and teleop.ctrl_origin is not None:
            target_pos = teleop.target_origin + (ctrl_pos - teleop.ctrl_origin)
        else:
            target_pos = np.zeros(3)

        ax3d.scatter(*ctrl_pos, c="#e67e22", s=90, depthshade=True, label="controller")
        draw_frame(ax3d, mat)
        box_size = 0.04 + 0.12 * trig
        draw_box(ax3d, target_pos, box_size, color="#3498db" if teleop.movement_enabled else "#95a5a6")
        ax3d.scatter(*target_pos, c="#2980b9", s=25, depthshade=True)

        status = "MOVING" if teleop.movement_enabled else "idle (hold RG to move)"
        ax3d.text2D(
            0.02,
            0.02,
            f"{status}\ntrigger={trig:.2f}  target=({target_pos[0]:+.2f}, {target_pos[1]:+.2f}, {target_pos[2]:+.2f})",
            transform=ax3d.transAxes,
            fontsize=9,
            family="monospace",
        )

        draw_ui_panel(ax_ui, trig, rg, pressed_a, pressed_b, target_pos)

    ani = FuncAnimation(fig, update, interval=50, blit=False)
    plt.show()
    reader.stop()
    del ani


if __name__ == "__main__":
    main()
