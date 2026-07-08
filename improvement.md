# Agent improvement notes

## 2026-06-04 — DROID laptop env setup

- Do not `pip install pyzed` for DROID; PyPI `pyzed` 1.3.0 is unrelated to Stereolabs. Use `/usr/local/zed/get_python_api.py` with the `robot` conda Python (requires sudo read of `/usr/local/zed`).
- ZED SDK may already be on the machine (`ldconfig` shows `libsl_zed.so`) while `/usr/local/zed` is root-only; plan for a user-run sudo step instead of assuming the agent can install pyzed.
- Check for existing partial setup (e.g. `zed_viewer` env, ZED installer under `Franka_Robot/downloads/`) before reinstalling SDK.
- `improvement.md` did not exist in this repo; create it when the user rule references it.

## 2026-06-05 — Robotiq gripper demo

- Gripper server needs `polymetis-local` conda env — install with `bash scripts/setup/install_polymetis_gripper.sh` (not the full NUC polymetis build).
- `launch_gripper.sh` auto-detects `/dev/ttyUSB*` or `/dev/ttyACM*`; override with `GRIPPER_COMPORT=/dev/ttyUSB1`.
- If no serial device appears, the RS485-USB adapter is not plugged into this machine (ZED/Oculus on USB does not include the gripper).
- DROID gripper position is normalized: 0 = open, 1 = closed; width in meters is `max_width * (1 - position)` (see `droid/franka/robot.py`).
- Demo script: `scripts/demo/robotiq_gripper_demo.py`; use `--show-cameras` for ZED hand-camera preview during motion.
- `install_polymetis_gripper.sh` must pin `grpcio`, `grpcio-tools`, and `protobuf` to the same generation (1.46.0 / 3.20.3) **before** running `grpc_tools.protoc`; newer grpcio-tools writes stubs that require protobuf 5.x and break with polymetis.

## 2026-06-05 — ZED camera setup

- Camera setup flow: `install_zed_python_api.sh` (sudo) → `list_zed_cameras.py` → set `hand_camera_id` in `parameters.py` → `test_zed_cameras.py`.
- Do not `pip install pyzed`; use `/usr/local/zed/get_python_api.py` with the `robot` env Python.
- If `import pyzed` fails with missing `libsl_zed.so`, set `LD_LIBRARY_PATH=/usr/local/zed/lib`.
- ZED-M is typically hand camera; ZED 2i are third-person (`varied_camera_*_id`).
- `set -o pipefail` + `ldconfig | grep -q` falsely fails SDK detection (SIGPIPE exit 141); cache ldconfig output before grep.
- `/usr/local/zed` is `root:zed` mode 770 — user must be in group `zed` and **log out/in** (or `newgrp zed`) before `import pyzed` works.
- Run `bash scripts/setup/configure_zed_env.sh` to add `LD_LIBRARY_PATH` hook to the robot conda env.

## 2026-06-05 — VR arm + gripper teleop

- Full DROID teleop: `scripts/demo/vr_teleop_demo.py` — `VRPolicy` + NUC `ServerInterface` @ 15 Hz; arm + gripper both via zerorpc.
- RG enables arm + gripper in one `update_command` (cartesian_velocity + gripper position).
- Gripper-only: `scripts/demo/vr_gripper_teleop_demo.py` (NUC gripper via zerorpc).
- Pre-flight: FCI on Desk, NUC stack (`openpi_start_gripper_nuc.sh` + Polymetis + zerorpc), Quest `adb devices`.
- Runbook: `docs/vr-teleop-demo.md`.
- `--dry-run` tests Quest mapping without robot motion; Quest must be `adb device` unless `--no-quest-preflight`.

## 2026-06-09 — Workstation agent skill (arm via NUC)

- Project skill: `.cursor/skills/control-arm-via-nuc/SKILL.md` — pre-flight, `ServerInterface(launch=False)`, smoke test, SSH NUC admin, troubleshooting.
- Companion: `.cursor/skills/control-arm-via-nuc/nuc-admin.md` for relaunch commands.

## 2026-06-09 — SSH to NUC from workstation

- NUC SSH: `ssh nuc` → `pci@192.168.1.7` (host `pci-NUC15CRKU7`). Workstation `~/.ssh/config` has `Host nuc`; key auth via `ssh-copy-id`. Do **not** store the NUC password in repo files.
- Remote NUC admin: `ssh pci@192.168.1.7`, or Cursor **Remote-SSH** → open `/home/pci/Desktop/Franka/droid`.
- Sync gripper-optional `robot.py`: `scp ~/Desktop/DROID/droid/franka/robot.py pci@192.168.1.7:/home/pci/Desktop/Franka/droid/droid/franka/robot.py` then restart `run_server.py` on NUC.
- Polymetis log `FCI refused` = activate FCI in Desk on **workstation** before `launch_robot.py` on NUC.

## 2026-06-10 — OpenPI session reset scripts

- Before rollout: `bash scripts/setup/openpi_session_reset.sh` (step 0a in `docs/openpi-policy-rollout.md`) kills half-started NUC Polymetis/zerorpc and workstation gripper/policy/rollout.
- End of session: same script replaces manual `pkill` blocks.
- **Never** put `pkill -f launch_robot.py` (or `run_server.py`) inside an inline `ssh nuc "..."` one-liner — the pattern matches the SSH command line and kills the remote shell (silent exit 255, no output). Use `scripts/setup/openpi_*.sh` (heredoc over `ssh nuc 'bash -s'`).
- OpenPI setup scripts use `exec 1>&2` — some IDE terminals only display stderr from nested `bash` scripts.
- Python demos (`arm_smoke_test.py`, `openpi_pi05_rollout.py`) use `sys.stdout = sys.stderr` for the same reason.

## 2026-06-10 — Agent model handoff doc

- `docs/agent-model-handoff.md` — onboarding for agents integrating new policies (tiptop, etc.); reuse OpenPI rollout pattern, hardware split, golden rules.

## 2026-07-08 — VR teleop pipeline test notes

- Primary demo doc: `docs/vr-teleop-demo.md` — copy-paste session checklist for `vr_teleop_demo.py`.
- Pipeline test needs: NUC reachable, FCI active (`nc -zv 192.168.1.11 1337`), NUC stack up, Quest `adb devices` shows `device` (not `unauthorized`).
- `--dry-run` still starts OculusReader — unauthorized Quest fails before UI opens.
- Demo launchers: `scripts/demo/start_vr_teleop_demo.sh`, `scripts/demo/start_pi05_demo.sh` — one command fresh-starts NUC stack + demo.


## 2026-07-08 — Gripper moved to NUC

- Robotiq USB is on the **NUC** (not workstation). `launch_gripper.sh` runs on NUC → `:50052`.
- `droid/franka/robot.py`: gripper connects by default; `DROID_GRIPPER_SKIP=1` to opt out.
- Workstation demos use NUC zerorpc for gripper (`robotiq_gripper_demo.py`, `vr_teleop_demo.py`, `RobotEnv`).
- Start from workstation: `bash scripts/setup/openpi_start_gripper_nuc.sh`.
- Legacy workstation gripper: `--local-gripper` flag on gripper demos.

## 2026-06-10 — GitHub repo for lab setup

- Lab branch `lab-fr3-setup` holds scripts/docs/patches; do **not** push using another user's SSH key — confirm `ssh -T git@github.com` shows the intended account before `git push`.
- Polymetis lazy-import patch lives in `scripts/setup/patches/`; apply with `bash scripts/setup/apply_lab_patches.sh`.

## 2026-06-10 — Doc sync rule

- When changing OpenPI rollout setup (scripts, NUC SSH commands, gripper/arm wiring, flags), update `docs/openpi-policy-rollout.md` in the **same** change and add a row to its **Changelog** section.
- NUC Polymetis over SSH: use `ssh nuc "bash -lc '...'"` and split **2a start / 2b verify** — single-block `&&` + `pgrep` often prints nothing.

## 2026-06-09 — OpenPI π₀.5-DROID on workstation

- Clone OpenPI to `~/Desktop/openpi`; install with `uv sync` (needs `~/.local/bin` on PATH).
- RTX 4090 loads `pi05_droid` checkpoint; cache at `~/.cache/openpi/openpi-assets/checkpoints/pi05_droid`.
- Policy server: use `bash ~/Desktop/openpi/scripts/serve_pi05_droid.sh` (port 8000). Plain `uv run scripts/serve_policy.py` can OOM on RTX 4090 when JAX preallocates GPU memory alongside Xorg/Cursor — set `XLA_PYTHON_CLIENT_PREALLOCATE=false`, `XLA_PYTHON_CLIENT_ALLOCATOR=platform`, `XLA_PYTHON_CLIENT_MEM_FRACTION=0.85`.
- `robot` conda is Python 3.7 — cannot `pip install openpi-client` normally (numpy>=1.22). Use `pip install -e . --no-deps` in `openpi/packages/openpi-client` plus `websockets msgpack dm-tree tyro moviepy`.
- Lab rollout script: `scripts/demo/openpi_pi05_rollout.py` — camera IDs from `parameters.py`, `--dry-run` for inference-only, `--no-reset` to skip homing. π₀.5-DROID returns action chunks of shape `(15, 8)`, not `(10, 8)`.
- `RobotEnv` with `nuc_ip` must use `ServerInterface(..., launch=False)` + `launch_robot()` — do not relaunch Polymetis from workstation.
- Pre-flight for rollout: Desk FCI, NUC `:4242`, gripper `launch_gripper.sh` (polymetis-local), 3× ZED USB. OpenPI rollout must use **local workstation gripper** for read/write — NUC `get_gripper_position()` is always 0 without USB.
- Voice commands: `--input-mode voice` on rollout; STT is `speech_command.py` (faster-whisper in openpi env). One-time: `sudo apt install portaudio19-dev libportaudio2`; `cd ~/Desktop/openpi && uv pip install faster-whisper sounddevice soundfile`.

## 2026-06-09 — Workstation arm control via NUC

- NUC zerorpc + Polymetis reachable from workstation (`192.168.1.7:4242`, `:50051`); set `parameters.py` to lab IPs (`nuc_ip=192.168.1.7`, `robot_type=fr3`).
- `launch_robot()` on NUC fails when no gripper server is running (`GripperInterface.metadata` missing). Gripper USB is on workstation — patch `droid/franka/robot.py` to make gripper optional and sync that file to the NUC repo (`/home/pci/Desktop/Franka/droid`).
- `Cannot retrieve robot state from empty buffer!` means Polymetis `:50051` listens but `franka_panda_client` is not streaming — fix on NUC (FCI + relaunch `launch_robot.py`), not on workstation.
- Until NUC has the gripper patch, `launch_robot()` over zerorpc fails; state reads only work when Polymetis client is actively connected.
- Always use `ServerInterface(..., launch=False)` — `launch=True` kills and relaunches Polymetis on NUC.
- Arm smoke script: `scripts/demo/arm_smoke_test.py` (read-only default; `--move` for small joint-7 nudge).

## 2026-06-08 — NUC agent instructions

- `docs/nuc-agent-instructions.md` is the NUC runbook; cross-link `Franka_Robot/docs/AGENT_ROBOT_CONTROL.md` for authoritative lab IPs (`192.168.1.11` robot, `192.168.1.7` NUC, `192.168.1.6` PC) — not upstream DROID `172.16.0.x`.
- Always verify `ping 192.168.1.11` from the wired interface before Polymetis; loopback-only or Wi‑Fi routes mean failure.
- Gripper USB is on the workstation, not the NUC. Only one machine may command FCI at a time.
- `parameters.py` and `config/<robot_type>/franka_hardware.yaml` must both set `robot_ip` to `192.168.1.11` for this lab.

## 2026-06-05 — Triple ZED recorder UI

- `scripts/demo/zed_triple_camera_recorder.py`: live 3-camera RGB+depth preview; **r** or click **RECORD** to start/stop; saves `recordings/<timestamp>/<serial>/rgb.mp4` + `depth/NNNNNN.npy` (float32 meters) + `session.json`.
- Default 15fps VGA for USB bandwidth with 3 ZEDs; depth writes run in a background thread so preview stays smooth.
- OpenCV 4.6 + Qt: call `imshow`/`waitKey(1)` before `setMouseCallback`; otherwise NULL window handler crash. Fallback to **r** key if mouse setup fails.
- ZED clamps `depth_minimum_distance` below 0.2 m — use 0.2 in init to avoid warning.
- `--save-composite-video` writes `composite.mp4`: top row 3× RGB, bottom row 3× colorized depth (960×480 at default tile size). **Now on by default**; use `--no-composite-video` to skip.
