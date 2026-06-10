# DROID Lab — Agent Handoff (for new policy models)

**Purpose:** Onboard agents working on new policies (e.g. tiptop) to this lab's DROID stack.  
**Repo:** `/home/pci/Desktop/DROID`  
**Last updated:** 2026-06-10

| Machine | Hostname | IP | Role |
|---------|----------|-----|------|
| Workstation | `pci-blenderman` | `192.168.1.6` | Desk, cameras, VR, gripper, policy GPU, DROID client |
| NUC | `pci-NUC15CRKU7` | `192.168.1.7` | Polymetis + zerorpc (arm real-time loop) |
| Robot (C2) | — | `192.168.1.11` | Franka Research 3 (FR3); Desk at `https://192.168.1.11/desk/` |

This lab uses **192.168.1.0/24**, not upstream DROID's default `172.16.0.x`.

**Read first:** `improvement.md` (lab-specific pitfalls from past sessions).

---

## 1. Architecture — what runs where

```text
┌──────────── Workstation (192.168.1.6) ────────────┐
│  Quest USB      → VR teleop (oculus_reader)      │
│  3× ZED USB     → cameras (hand ZED-M + 2× 2i)  │
│  Robotiq USB    → launch_gripper.sh :50052       │
│  GPU (RTX 4090) → policy servers (e.g. OpenPI)   │
│  Desk browser   → FCI unlock (ONLY here)         │
│       │                                          │
│       └── zerorpc client ──► NUC :4242          │
└──────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────── NUC (192.168.1.7) ──────────────────┐
│  Polymetis gRPC :50051                           │
│  DROID zerorpc  :4242  (run_server.py)           │
│  franka_panda_client → FCI → 192.168.1.11       │
└──────────────────────────────────────────────────┘
```

| Component | Machine | Port / path |
|-----------|---------|-------------|
| Arm (FCI) | NUC → robot | Polymetis `:50051`, zerorpc `:4242` |
| Gripper (Robotiq 2F) | **Workstation USB** | `launch_gripper.sh` → `:50052` |
| Cameras (3× ZED) | Workstation USB | serials in `parameters.py` |
| Quest 3 VR | Workstation USB | `oculus_reader` + adb |
| Desk / FCI | **Workstation browser only** | `https://192.168.1.11/desk/` |
| Policy server | Workstation GPU | e.g. OpenPI `:8000` |

**Critical lab rule:** gripper USB is on the workstation, not the NUC. Arm commands go over the network; gripper read/write stays local.

### Architecture rules (do not regress)

1. **Arm** → workstation `zerorpc` → NUC `:4242` → Polymetis → Franka FCI
2. **Gripper** → workstation USB only (`launch_gripper.sh` `:50052`); rollout scripts command gripper **locally**
3. **Policy** → workstation GPU (e.g. `:8000`); rollout sends images + prompt over websocket/HTTP
4. **Desk / FCI** → workstation browser only, before NUC `launch_robot.py`
5. **NUC SSH** → use `scripts/setup/openpi_*.sh` (heredoc over `ssh nuc 'bash -s'`) — never inline `pkill -f launch_robot.py` in the ssh command string

---

## 2. Conda environments

| Env | Python | Purpose |
|-----|--------|---------|
| `robot` | 3.7 | DROID client: arm, ZED, VR, rollout scripts |
| `polymetis-local` | 3.8 | Gripper server only (`launch_gripper.sh`) |

**One-time setup scripts:**

```bash
cd /home/pci/Desktop/DROID
bash scripts/setup/install_polymetis_gripper.sh      # polymetis-local env
conda activate robot
bash scripts/setup/install_gripper_client_robot.sh   # gripper client in robot env
bash scripts/setup/install_zed_python_api.sh         # needs sudo once
bash scripts/setup/configure_zed_env.sh              # LD_LIBRARY_PATH hook; newgrp zed
```

**External repo (not in DROID git):**

- OpenPI at `~/Desktop/openpi` — installed with `uv sync`; policy server for π₀.5-DROID

---

## 3. Key config — `droid/misc/parameters.py`

```python
nuc_ip = "192.168.1.7"
robot_ip = "192.168.1.11"
laptop_ip = "192.168.1.6"
robot_type = "fr3"  # not 'panda'

hand_camera_id = "10163006"      # ZED-M wrist
varied_camera_1_id = "38845842"  # ZED 2i left external
varied_camera_2_id = "38924636"  # ZED 2i right external
```

NUC repo mirror: `/home/pci/Desktop/Franka/droid` (must stay in sync for `robot.py` patch).

---

## 4. Lab-specific code patches

| File | Change | Why |
|------|--------|-----|
| `droid/robot_env.py` | `ServerInterface(..., launch=False)` + `launch_robot()` | Don't relaunch Polymetis from workstation |
| `droid/franka/robot.py` | Gripper optional unless `DROID_GRIPPER_LOCAL=1` | NUC has no gripper USB; prevents zerorpc hang |
| `scripts/demo/openpi_pi05_rollout.py` | Local gripper read/write; websocket policy client | Gripper bypasses NUC |

**Sync `robot.py` to NUC after changes:**

```bash
scp ~/Desktop/DROID/droid/franka/robot.py \
    nuc:/home/pci/Desktop/Franka/droid/droid/franka/robot.py
# then restart zerorpc on NUC (see nuc-admin.md)
```

---

## 5. Golden rules

| Do | Don't |
|----|-------|
| `ServerInterface(ip=nuc_ip, launch=False)` | `launch=True` or default `RobotEnv()` with relaunch — kills NUC Polymetis |
| Desk + FCI on **workstation** browser | Open Desk on NUC while Polymetis runs |
| Command gripper **locally** (`:50052`) | Expect NUC `get_gripper_position()` to work (always 0 without USB) |
| Pass **numpy arrays** to `update_joints()` | Pass `.tolist()` |
| Use `scripts/setup/openpi_*.sh` for NUC SSH | Inline `ssh "pkill -f launch_robot.py"` — kills the SSH shell (exit 255) |
| `conda activate robot` before DROID scripts | Wrong env → missing `zerorpc` / `pyzed` |
| Ask user before non-trivial arm motion | Move arm without approval |

---

## 6. Session pre-flight (every experiment)

1. **Desk** (workstation): unlock brakes → Execution → Activate FCI
2. **Connectivity:**

   ```bash
   nc -zv 192.168.1.7 4242   # NUC zerorpc
   nc -zv 192.168.1.7 50051  # Polymetis (optional)
   ```

3. **Arm smoke test:**

   ```bash
   conda activate robot && cd ~/Desktop/DROID
   python scripts/demo/arm_smoke_test.py
   ```

4. **Gripper** (if needed):

   ```bash
   conda activate polymetis-local
   cd ~/Desktop/DROID
   bash droid/franka/launch_gripper.sh   # → :50052
   ```

**NUC recovery:** `.cursor/skills/control-arm-via-nuc/nuc-admin.md`  
**SSH:** `ssh nuc` → `pci@192.168.1.7` (key auth via `~/.ssh/config`)

**Full OpenPI session checklist:** [openpi-policy-rollout.md](openpi-policy-rollout.md) steps 0–8.

---

## 7. What's implemented in this repo

### Robot control

| Script | Purpose |
|--------|---------|
| `scripts/demo/arm_smoke_test.py` | NUC arm read (`--move` for tiny joint-7 nudge) |
| `scripts/demo/robotiq_gripper_demo.py` | Gripper open/close |
| `scripts/demo/vr_teleop_demo.py` | Full VR arm + gripper @ 15 Hz |
| `scripts/demo/vr_gripper_teleop_demo.py` | VR gripper only |
| `scripts/demo/oculus_right_controller_demo.py` | Quest mapping test (no robot) |

### Cameras

| Script | Purpose |
|--------|---------|
| `scripts/setup/list_zed_cameras.py` | List ZED serials |
| `scripts/setup/test_zed_cameras.py` | Verify all 3 cameras |
| `scripts/demo/zed_triple_camera_recorder.py` | Record RGB + depth + composite video |

### OpenPI π₀.5-DROID (reference policy integration)

| Script | Purpose |
|--------|---------|
| `scripts/setup/openpi_session_reset.sh` | Kill stale NUC + workstation processes |
| `scripts/setup/openpi_nuc_status.sh` | Check NUC health |
| `scripts/setup/openpi_start_polymetis.sh` | Start Polymetis on NUC |
| `scripts/setup/openpi_verify_polymetis.sh` | Verify `Connected.` |
| `scripts/setup/openpi_start_zerorpc.sh` | Start zerorpc `:4242` |
| `scripts/demo/openpi_pi05_rollout.py` | **Main rollout client** |
| `scripts/demo/speech_command.py` | Voice → text (run in openpi env) |
| `~/Desktop/openpi/scripts/serve_pi05_droid.sh` | Policy server (JAX memory tuning) |

---

## 8. How to integrate a new policy model (e.g. tiptop)

There is **no tiptop code in this repo yet**. Use the OpenPI rollout as the template.

### A. Reuse the hardware stack (unchanged)

Any new policy needs the same multi-terminal pattern:

| Terminal | Service | Port |
|----------|---------|------|
| A | NUC arm (Polymetis + zerorpc) | `:50051`, `:4242` |
| B | Gripper server | `:50052` |
| C | **Your policy server** | e.g. `:8000` |
| D | **Your rollout client** | — |

Start with `bash scripts/setup/openpi_session_reset.sh`, then NUC steps, then gripper.

### B. Rollout client pattern (`openpi_pi05_rollout.py`)

Copy/adapt this structure for tiptop:

1. **`RobotEnv`** with `action_space="joint_velocity"`, `launch=False` (via patched `robot_env.py`)
2. **`LocalGripper`** — read position from workstation `:50052`, command locally (do not use NUC gripper)
3. **Observation extraction** — 3 ZED RGB frames + 7 joint positions + 1 gripper position
4. **Policy client** — websocket/HTTP/gRPC to your server
5. **Control loop** — 15 Hz; re-query policy every `open_loop_horizon` steps (default 8)

### C. OpenPI observation / action contract (baseline)

**Request keys** (π₀.5-DROID):

```python
{
    "observation/exterior_image_1_left": <224×224 RGB>,  # left OR right external cam
    "observation/wrist_image_left":      <224×224 RGB>,
    "observation/joint_position":        <7,>,
    "observation/gripper_position":      <1,>,  # 0=open, 1=closed
    "prompt":                            <str>,  # language command
}
```

**Action chunk:** shape `(N, 8)` where N=15 for π₀.5, N=10 for π₀-FAST:

- Dims 0–6: joint velocities (±1 scaled)
- Dim 7: gripper position target (binarized at 0.5)

**For tiptop:** confirm its own observation keys, image sizes, action space, and chunk length. Adapt `_extract_observation()` and the action execution loop accordingly.

### D. Gripper convention (DROID standard)

```python
# 0 = open, 1 = closed
width_meters = max_width * (1 - position)
```

See `droid/franka/robot.py` and `scripts/demo/robotiq_gripper_demo.py`.

### E. Python API for direct arm control (no policy)

```python
import numpy as np
from droid.misc.parameters import nuc_ip
from droid.misc.server_interface import ServerInterface

robot = ServerInterface(ip_address=nuc_ip, launch=False)
robot.launch_robot()
joints = robot.get_joint_positions()
robot.update_command(command, action_space="cartesian_velocity")  # teleop-style
```

### F. New model checklist

- [ ] Policy server script with GPU memory env vars if using JAX
- [ ] Rollout client in `scripts/demo/<model>_rollout.py`
- [ ] Confirm action space matches `RobotEnv` (`joint_velocity` vs `cartesian_velocity`)
- [ ] Local gripper read/write (not NUC)
- [ ] Camera IDs from `parameters.py`
- [ ] `--dry-run` mode for inference-only testing
- [ ] Doc in `docs/` + changelog section
- [ ] Update `improvement.md` with any new pitfalls

---

## 9. Control frequency & timing

- DROID control: **15 Hz** (`DROID_CONTROL_FREQUENCY = 15` in rollout script)
- VR teleop: 15 Hz (same as `collect_trajectory`)
- Policy open-loop horizon: 8 steps before re-inference (configurable via `--open-loop-horizon`)

---

## 10. Common failures

| Symptom | Fix |
|---------|-----|
| `empty buffer` / arm timeout | Desk → FCI; relaunch Polymetis on NUC |
| `launch_robot` timeout | Sync `robot.py` to NUC; restart zerorpc |
| Gripper always 0 on NUC | Expected — use local gripper server |
| `import pyzed` fails | `newgrp zed`, run `configure_zed_env.sh` |
| SSH step silent exit 255 | Use `openpi_*.sh` scripts, not inline pkill |
| IDE terminal shows no output | Scripts use `exec 1>&2`; Python uses `sys.stdout = sys.stderr` |
| GPU OOM (OpenPI) | `serve_pi05_droid.sh` JAX env vars |
| `Connection refused` `:4242` | Start `run_server.py` on NUC |
| `FCI refused` in NUC log | Desk pre-flight on workstation, then relaunch Polymetis |

---

## 11. Agent skills & docs index

| Resource | Path |
|----------|------|
| **Primary skill** | `.cursor/skills/control-arm-via-nuc/SKILL.md` |
| NUC admin commands | `.cursor/skills/control-arm-via-nuc/nuc-admin.md` |
| Lab quickstart | [lab-workstation-quickstart.md](lab-workstation-quickstart.md) |
| NUC operator guide | [nuc-agent-instructions.md](nuc-agent-instructions.md) |
| Workstation ↔ NUC handoff | [workstation-agent-handoff.md](workstation-agent-handoff.md) |
| OpenPI rollout (template) | [openpi-policy-rollout.md](openpi-policy-rollout.md) |
| Agent lessons / pitfalls | `improvement.md` (read every session) |

---

## Changelog

| Date | Change |
|------|--------|
| 2026-06-10 | Initial agent handoff doc for new policy models (tiptop, etc.) |
