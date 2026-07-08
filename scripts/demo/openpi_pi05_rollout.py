#!/usr/bin/env python3
"""Run π₀.5-DROID on this lab's Franka FR3 + ZED setup.

Prerequisites (workstation):
  1. NUC: Polymetis + zerorpc :4242 + gripper :50052 (FCI active in Desk)
     bash scripts/setup/openpi_start_gripper_nuc.sh
     bash scripts/setup/openpi_start_polymetis.sh && sleep 18 && bash scripts/setup/openpi_start_zerorpc.sh
  2. Policy server (separate terminal):
       bash ~/Desktop/openpi/scripts/serve_pi05_droid.sh

Usage:
  conda activate robot
  cd ~/Desktop/DROID
  python scripts/demo/openpi_pi05_rollout.py --external-camera left
  python scripts/demo/openpi_pi05_rollout.py --input-mode voice   # speak command via mic
  python scripts/demo/openpi_pi05_rollout.py --dry-run   # server + cameras only, no motion
"""

from __future__ import annotations

import contextlib
import dataclasses
import faulthandler
import importlib.util
import os
import signal
import subprocess
import sys
import time

# IDE terminals (e.g. Cursor) may swallow stdout from Python.
sys.stdout = sys.stderr
from pathlib import Path
from typing import Optional

import numpy as np
import tqdm
import tyro
from openpi_client import image_tools
from openpi_client import websocket_client_policy

from droid.misc.parameters import hand_camera_id, varied_camera_1_id, varied_camera_2_id
from droid.robot_env import RobotEnv

ROOT = Path(__file__).resolve().parents[2]
faulthandler.enable()

DROID_CONTROL_FREQUENCY = 15


@dataclasses.dataclass
class RolloutConfig:
    left_camera_id: str = varied_camera_1_id
    right_camera_id: str = varied_camera_2_id
    wrist_camera_id: str = hand_camera_id
    external_camera: str = "left"  # "left" or "right" third-person ZED 2i
    max_timesteps: int = 600
    open_loop_horizon: int = 8
    remote_host: str = "127.0.0.1"
    remote_port: int = 8000
    gripper_ip: str = "localhost"  # deprecated; gripper is on NUC via RobotEnv
    gripper_port: int = 50052
    gripper_speed: float = 0.05
    gripper_force: float = 0.1
    gripper_threshold: float = 0.5
    no_reset: bool = False
    dry_run: bool = False
    debug_gripper: bool = False
    input_mode: str = "both"  # text | voice | both
    voice_duration: float = 5.0
    whisper_model: str = "base"
    openpi_root: str = str(Path.home() / "Desktop/openpi")
    input_device: Optional[int] = None


def listen_for_command(args: RolloutConfig, log) -> str:
    """Record + transcribe via openpi env (faster-whisper on GPU)."""
    script = ROOT / "scripts" / "demo" / "speech_command.py"
    openpi_root = Path(args.openpi_root)
    if not openpi_root.is_dir():
        raise FileNotFoundError(f"openpi not found at {openpi_root}")

    env = os.environ.copy()
    env["PATH"] = f"{Path.home()}/.local/bin:" + env.get("PATH", "")

    cmd = [
        "uv",
        "run",
        "python",
        str(script),
        "--duration",
        str(args.voice_duration),
        "--model",
        args.whisper_model,
    ]
    if args.input_device is not None:
        cmd.extend(["--input-device", str(args.input_device)])
    input("Press Enter to start recording...")
    cmd.append("--auto-start")
    log(f"Recording {args.voice_duration}s (whisper={args.whisper_model})...")
    result = subprocess.run(
        cmd,
        cwd=str(openpi_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if result.stderr:
        log(result.stderr.strip())
    if result.returncode != 0:
        raise RuntimeError(
            "Speech transcription failed.\n"
            f"stderr: {result.stderr.strip()}\n"
            "Test standalone: cd ~/Desktop/openpi && uv run python "
            f"{script} --list-devices"
        )
    text = result.stdout.strip().splitlines()[-1].strip()
    log(f"Heard: {text!r}")
    confirm = input("Use this command? [Y/n/edit]: ").strip().lower()
    if confirm in ("", "y", "yes"):
        return text
    if confirm == "edit":
        return input("Type corrected command: ").strip()
    return listen_for_command(args, log)


def get_instruction(args: RolloutConfig, log) -> str:
    if args.input_mode not in ("text", "voice", "both"):
        raise ValueError("--input-mode must be text, voice, or both")

    if args.input_mode == "text":
        return input("Enter instruction (or Ctrl+C to quit): ").strip()
    if args.input_mode == "voice":
        return listen_for_command(args, log)

    typed = input("Enter instruction, or press Enter for voice (Ctrl+C to quit): ").strip()
    if typed:
        return typed
    return listen_for_command(args, log)


@contextlib.contextmanager
def prevent_keyboard_interrupt():
    interrupted = False
    original_handler = signal.getsignal(signal.SIGINT)

    def handler(signum, frame):
        nonlocal interrupted
        interrupted = True

    signal.signal(signal.SIGINT, handler)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, original_handler)
        if interrupted:
            raise KeyboardInterrupt


def _extract_observation(args: RolloutConfig, obs_dict, *, gripper_position=None, save_to_disk=False):
    image_observations = obs_dict["image"]
    left_image, right_image, wrist_image = None, None, None
    for key in image_observations:
        if args.left_camera_id in key and "left" in key:
            left_image = image_observations[key]
        elif args.right_camera_id in key and "left" in key:
            right_image = image_observations[key]
        elif args.wrist_camera_id in key and "left" in key:
            wrist_image = image_observations[key]

    if left_image is None or right_image is None or wrist_image is None:
        raise RuntimeError(
            "Missing camera frames. Check camera IDs and USB connections.\n"
            f"  left={args.left_camera_id} right={args.right_camera_id} wrist={args.wrist_camera_id}\n"
            f"  available keys: {list(image_observations.keys())}"
        )

    left_image = left_image[..., :3][..., ::-1]
    right_image = right_image[..., :3][..., ::-1]
    wrist_image = wrist_image[..., :3][..., ::-1]

    robot_state = obs_dict["robot_state"]
    joint_position = np.array(robot_state["joint_positions"])
    if gripper_position is None:
        gripper_position = np.array([robot_state["gripper_position"]])
    else:
        gripper_position = np.array([float(gripper_position)])

    if save_to_disk:
        from PIL import Image

        combined_image = np.concatenate([left_image, wrist_image, right_image], axis=1)
        Image.fromarray(combined_image).save("robot_camera_views.png")
        print("Saved robot_camera_views.png (left | wrist | right)")

    return {
        "left_image": left_image,
        "right_image": right_image,
        "wrist_image": wrist_image,
        "joint_position": joint_position,
        "gripper_position": gripper_position,
    }


def main(args: RolloutConfig):
    if args.external_camera not in ("left", "right"):
        raise ValueError(f"--external-camera must be 'left' or 'right', got {args.external_camera!r}")

    def log(msg):
        print(msg, flush=True)

    log("Lab camera IDs:")
    log(f"  left={args.left_camera_id}  right={args.right_camera_id}  wrist={args.wrist_camera_id}")
    log(f"  policy external view: {args.external_camera}")
    log(f"  policy server: ws://{args.remote_host}:{args.remote_port}")

    log("Connecting to policy server...")
    policy_client = websocket_client_policy.WebsocketClientPolicy(args.remote_host, args.remote_port)
    log("Connected to policy server: " + str(policy_client.get_server_metadata()))

    log("Starting RobotEnv (ZED cameras + NUC arm/gripper; may take 30-60s)...")
    env = RobotEnv(
        action_space="joint_velocity",
        gripper_action_space="position",
        do_reset=not args.no_reset,
    )
    log("DROID RobotEnv ready (arm + gripper via NUC zerorpc).")

    obs = _extract_observation(
        args,
        env.get_observation(),
        save_to_disk=True,
    )
    dummy_request = {
        "observation/exterior_image_1_left": image_tools.resize_with_pad(
            obs[f"{args.external_camera}_image"], 224, 224
        ),
        "observation/wrist_image_left": image_tools.resize_with_pad(obs["wrist_image"], 224, 224),
        "observation/joint_position": obs["joint_position"],
        "observation/gripper_position": obs["gripper_position"],
        "prompt": "pick up the block",
    }
    with prevent_keyboard_interrupt():
        pred = policy_client.infer(dummy_request)["actions"]
    if pred.ndim != 2 or pred.shape[1] != 8:
        raise ValueError(f"Expected action chunk shape (N, 8), got {pred.shape}")
    log(f"Policy inference OK — action chunk shape {pred.shape} (π₀.5 uses 15 steps; π₀-FAST uses 10)")

    if args.dry_run:
        print("Dry run complete (no robot motion). Remove --dry-run to execute rollouts.")
        return

    while True:
        instruction = get_instruction(args, log)
        if not instruction:
            log("Empty instruction, skipping.")
            continue
        actions_from_chunk_completed = 0
        pred_action_chunk = None
        bar = tqdm.tqdm(range(args.max_timesteps))
        print("Running rollout... press Ctrl+C to stop early.")
        for t_step in bar:
            start_time = time.time()
            try:
                gripper_pos = float(env.get_state()[0]["gripper_position"])
                curr_obs = _extract_observation(
                    args, env.get_observation(), gripper_position=gripper_pos
                )
                if actions_from_chunk_completed == 0 or actions_from_chunk_completed >= args.open_loop_horizon:
                    actions_from_chunk_completed = 0
                    request_data = {
                        "observation/exterior_image_1_left": image_tools.resize_with_pad(
                            curr_obs[f"{args.external_camera}_image"], 224, 224
                        ),
                        "observation/wrist_image_left": image_tools.resize_with_pad(
                            curr_obs["wrist_image"], 224, 224
                        ),
                        "observation/joint_position": curr_obs["joint_position"],
                        "observation/gripper_position": curr_obs["gripper_position"],
                        "prompt": instruction,
                    }
                    with prevent_keyboard_interrupt():
                        pred_action_chunk = policy_client.infer(request_data)["actions"]
                    if pred_action_chunk.ndim != 2 or pred_action_chunk.shape[1] != 8:
                        raise ValueError(f"Expected action chunk shape (N, 8), got {pred_action_chunk.shape}")

                action = pred_action_chunk[actions_from_chunk_completed]
                actions_from_chunk_completed += 1

                raw_gripper = float(action[-1])
                if raw_gripper > args.gripper_threshold:
                    gripper_cmd = 1.0
                else:
                    gripper_cmd = 0.0
                action = np.concatenate([action[:-1], np.array([gripper_cmd])])
                action = np.clip(action, -1, 1)

                if args.debug_gripper and t_step % 15 == 0:
                    log(f"step {t_step}: gripper raw={raw_gripper:.3f} -> cmd={gripper_cmd:.0f}  read={gripper_pos:.3f}")

                env.step(action)

                elapsed_time = time.time() - start_time
                if elapsed_time < 1 / DROID_CONTROL_FREQUENCY:
                    time.sleep(1 / DROID_CONTROL_FREQUENCY - elapsed_time)
            except KeyboardInterrupt:
                break

        if input("Do one more eval? (y/n) ").lower() != "y":
            break


if __name__ == "__main__":
    main(tyro.cli(RolloutConfig))
