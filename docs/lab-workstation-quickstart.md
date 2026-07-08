# Lab workstation quickstart (Franka FR3 + Robotiq + ZED + Quest)

Guide for new labmates using **this lab’s** DROID workstation setup.  
Workstation: `pci-blenderman` (`192.168.1.6`) · NUC: `192.168.1.7` · Robot: `192.168.1.11`

Repo path: `/home/pci/Desktop/DROID`

---

## What runs where

| Component | Machine | Notes |
|-----------|---------|--------|
| Franka arm (FCI) | NUC → robot | Polymetis + zerorpc `:4242` on NUC |
| Robotiq 2F gripper | **NUC USB** | `launch_gripper.sh` on NUC (`:50052`) |
| 3× ZED cameras | Workstation USB | hand ZED-M + 2× ZED 2i |
| Quest 3 VR | Workstation USB | `oculus_reader` + teleop APK |
| Desk (FCI unlock) | **Workstation browser** | https://192.168.1.11/desk/ |

Gripper USB is on the **NUC**. Arm and gripper commands both go over zerorpc (`:4242`).

---

## One-time setup (new labmate)

### 1. Conda environments

```bash
cd /home/pci/Desktop/DROID

# Gripper server (polymetis-local)
bash scripts/setup/install_polymetis_gripper.sh
conda activate polymetis-local

# DROID client (robot) — VR, cameras, arm client
conda activate robot
bash scripts/setup/install_gripper_client_robot.sh   # gripper gRPC client in robot env
```

### 2. ZED cameras

```bash
conda activate robot
bash scripts/setup/install_zed_python_api.sh          # needs sudo once
bash scripts/setup/configure_zed_env.sh               # LD_LIBRARY_PATH hook
# Log out/in or: newgrp zed

python scripts/setup/list_zed_cameras.py
python scripts/setup/test_zed_cameras.py
```

Set serials in `droid/misc/parameters.py` if cameras differ from this lab.

### 3. Quest / adb

```bash
bash scripts/setup/quest3_adb_setup.sh
export PATH="$HOME/platform-tools:$PATH"
adb devices    # accept debugging prompt on headset once
python scripts/setup/test_oculus_reader.py
```

Quest 3 may need a newer teleop APK — see output of `test_oculus_reader.py`.

### 4. NUC arm (admin / first day)

- Confirm `droid/misc/parameters.py`: `nuc_ip = "192.168.1.7"`, `robot_type = "fr3"`.
- NUC must run Polymetis + `python scripts/server/run_server.py` (zerorpc).
- NUC must run Polymetis + zerorpc + gripper server (see `openpi_start_gripper_nuc.sh`).
- `droid/franka/robot.py` on NUC connects gripper on `localhost:50052` by default.

Details: `.cursor/skills/control-arm-via-nuc/SKILL.md` and `docs/nuc-agent-instructions.md`.

---

## Every session — pre-flight checklist

### A. Robot Desk (workstation browser)

1. Open https://192.168.1.11/desk/
2. **Unlock brakes**
3. **Execution → Activate FCI**

### B. Quick connectivity

```bash
ping -c 2 192.168.1.7
nc -zv 192.168.1.7 4242    # NUC zerorpc
nc -zv 192.168.1.7 50052   # NUC gripper (after openpi_start_gripper_nuc.sh)
```

### C. Arm smoke test

```bash
conda activate robot
cd /home/pci/Desktop/DROID
python scripts/demo/arm_smoke_test.py
```

Expect joint positions and EE pose within ~1 s. If timeout → see [Troubleshooting](#troubleshooting).

### D. Quest (required for VR teleop)

```bash
export PATH="$HOME/platform-tools:$PATH"
adb devices    # must show: <serial>    device
```

If empty or `unauthorized`: plug USB-C data cable, put on headset, tap **Allow USB debugging** → **Always allow**. First time: `bash scripts/setup/quest3_adb_setup.sh`.

Keep headset awake without wearing it (optional):

```bash
adb shell am broadcast -a com.oculus.vrpowermanager.prox_close
```

Quick diagnostic:

```bash
python scripts/setup/test_oculus_reader.py
```

---

## Workflows

**Featured demo:** [VR teleop (Quest → arm + gripper)](vr-teleop-demo.md) — `scripts/demo/vr_teleop_demo.py`

Always use **`conda activate robot`**. Always **`cd /home/pci/Desktop/DROID`** before running scripts.

---

### 1. Gripper only (via NUC)

Start gripper server on NUC, then run demo from workstation:

```bash
bash scripts/setup/openpi_start_gripper_nuc.sh
conda activate robot
cd /home/pci/Desktop/DROID
python scripts/demo/robotiq_gripper_demo.py
python scripts/demo/robotiq_gripper_demo.py --show-cameras
python scripts/demo/robotiq_gripper_demo.py --show-cameras --all-cameras
```

Legacy workstation USB gripper: `python scripts/demo/robotiq_gripper_demo.py --local-gripper` (requires local `launch_gripper.sh`).

---

### 2. Record all 3 cameras (RGB + depth)

```bash
conda activate robot
cd /home/pci/Desktop/DROID
python scripts/demo/zed_triple_camera_recorder.py
```

| Control | Action |
|---------|--------|
| **r** or click **RECORD** | Start / stop |
| **q** | Quit |

**Saved per session** under `recordings/<timestamp>/`:

- `composite.mp4` — 3× RGB + 3× depth grid (default)
- `<serial>/rgb.mp4` — per camera
- `<serial>/depth/*.npy` — float32 depth (meters)
- `session.json` — metadata

Skip composite: `--no-composite-video`

---

### 3. VR teleop — arm + gripper (primary demo)

**One command:**

```bash
cd ~/Desktop/DROID
bash scripts/demo/start_vr_teleop_demo.sh
```

**Full runbook:** [vr-teleop-demo.md](vr-teleop-demo.md)

#### Before you start

Complete the [every-session checklist](#every-session--pre-flight-checklist):

1. **Desk** — unlock brakes, **Activate FCI**
2. **NUC stack** — gripper + Polymetis + zerorpc:
   ```bash
   bash scripts/setup/openpi_start_gripper_nuc.sh
   bash scripts/setup/openpi_start_polymetis.sh && sleep 18 && bash scripts/setup/openpi_verify_polymetis.sh
   bash scripts/setup/openpi_start_zerorpc.sh
   ```
3. **Arm smoke test** — `python scripts/demo/arm_smoke_test.py`
4. **Quest USB** — `adb devices` shows `device`

```bash
export PATH="$HOME/platform-tools:$PATH"
adb devices    # must show Quest as "device" before starting
conda activate robot
cd /home/pci/Desktop/DROID
python scripts/demo/vr_teleop_demo.py
```

Optional — keep Quest awake without wearing it:

```bash
adb shell am broadcast -a com.oculus.vrpowermanager.prox_close
python scripts/demo/vr_teleop_demo.py
```

#### What happens on launch

The script runs in this order:

1. Connect NUC (`192.168.1.7:4242`) → `launch_robot OK` (arm + gripper)
2. **Quest preflight** — fails fast if `adb devices` has no `device`
3. **Home arm** to DROID default joints (blocking move)
4. **Open gripper** on NUC
5. Start `VRPolicy` / OculusReader thread → matplotlib status window

```
Connected to NUC at 192.168.1.7:4242
Quest adb OK (<serial>)
launch_robot OK
Arm connected. EE xyz=(...)
Resetting arm to DROID home pose (blocking)...
Arm home OK. ...
Opening gripper on NUC...
Starting VRPolicy (OculusReader thread) — keep right controller visible.
```

#### VR controls (right controller)

| Input | Effect |
|-------|--------|
| **RG** (side grip) | Enable teleop — hold while moving |
| **Move / rotate controller** | Arm EE follows relative 6-DOF delta |
| **Index trigger** | Gripper open (0) → closed (1) |
| **RJ** | Reset VR “forward” frame |
| **A / B** | UI indicators only (green/red panel) |

**Seeing the robot:** the Quest shows the **RAIL teleop VR app**, not passthrough. Watch the **physical arm** or a **monitor** (`--show-cameras`), not the headset view.

#### Useful flags

| Flag | Purpose |
|------|---------|
| `--show-cameras` | Hand RGB+depth + both third-person RGB on monitor |
| `--show-cameras --all-cameras` | All 3 ZEDs, RGB+depth each (heavy USB) |
| `--no-reset-arm` | Skip homing arm + opening gripper at startup |
| `--dry-run` | Log VR actions only; no arm/gripper commands |
| `--no-quest-preflight` | Skip adb check (not recommended) |
| `--nuc-ip <ip>` | Override `droid/misc/parameters.py` |

Examples:

```bash
python scripts/demo/vr_teleop_demo.py --show-cameras
python scripts/demo/vr_teleop_demo.py --show-cameras --all-cameras
python scripts/demo/vr_teleop_demo.py --no-reset-arm
python scripts/demo/vr_teleop_demo.py --dry-run
```

#### Quest / adb troubleshooting

| `adb devices` shows | Fix |
|---------------------|-----|
| (empty) | Plug USB-C **data** cable; headset on; run `adb kill-server && adb start-server` |
| `unauthorized` | Put on headset → **Allow USB debugging** → **Always allow** |
| `offline` | Unplug/replug; try another USB port |
| Serial + `device` | OK — run teleop |

If teleop exits with **Device not found**:

```bash
export PATH="$HOME/platform-tools:$PATH"
adb devices
python scripts/setup/test_oculus_reader.py
bash scripts/setup/quest3_adb_setup.sh   # first-time udev/plugdev
```

If arm preflight fails (`launch_robot` timeout / empty buffer): see [Troubleshooting](#troubleshooting) and `.cursor/skills/control-arm-via-nuc/nuc-admin.md`. You can still test gripper-only VR: [§4](#4-vr-gripper-only-no-nuc-arm).

---

### 4. VR gripper only (arm down)

Script: `scripts/demo/vr_gripper_teleop_demo.py` — Quest controls gripper only via NUC (no arm motion).

```bash
bash scripts/setup/openpi_start_gripper_nuc.sh   # NUC gripper server
export PATH="$HOME/platform-tools:$PATH"
adb devices
conda activate robot
cd /home/pci/Desktop/DROID
python scripts/demo/vr_gripper_teleop_demo.py
```

If controller data is empty: `python scripts/setup/test_oculus_reader.py`

---

### 5. VR / controller test (virtual target, no robot)

Good for learning RG + trigger **before** touching hardware (no gripper server, no NUC):

```bash
export PATH="$HOME/platform-tools:$PATH"
adb devices
conda activate robot
cd /home/pci/Desktop/DROID
python scripts/demo/oculus_right_controller_demo.py
```

---

### 6. OpenPI π₀.5-DROID policy rollout (language / voice commands)

**One command:**

```bash
cd ~/Desktop/DROID
bash scripts/demo/start_pi05_demo.sh
```

**Full guide:** [OpenPI policy rollout](openpi-policy-rollout.md)

Abbreviated (after NUC + Desk are up):

```bash
# T1 — gripper
conda activate polymetis-local && cd ~/Desktop/DROID && bash droid/franka/launch_gripper.sh

# T2 — policy server (GPU)
bash ~/Desktop/openpi/scripts/serve_pi05_droid.sh

# T3 — rollout
conda activate robot && cd ~/Desktop/DROID
PYTHONUNBUFFERED=1 python scripts/demo/openpi_pi05_rollout.py --external-camera left --no-reset --input-mode both
```

---

## Architecture diagram

```
┌──────────────── Workstation (192.168.1.6) ─────────────────┐
│  Quest USB ──► VRPolicy / OculusReader                      │
│  ZED USB   ──► zed_triple_camera_recorder                   │
│  Gripper USB ──► NUC launch_gripper.sh :50052              │
│       │                                                     │
│       └── zerorpc ──► NUC :4242 ──► Polymetis + gripper    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    Robot 192.168.1.11 (Desk / FCI)
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `ModuleNotFoundError: zerorpc` | Wrong conda env | `conda activate robot` |
| `launch_robot timed out` | NUC zerorpc stuck on gripper probe | Sync `robot.py` to NUC, restart zerorpc; see `nuc-admin.md` |
| `empty buffer` / arm timeout | FCI off or Polymetis dead | Desk → Activate FCI; relaunch Polymetis on NUC |
| Gripper connect failed | NUC gripper server not running | `bash scripts/setup/openpi_start_gripper_nuc.sh` |
| `import pyzed` fails | ZED SDK / group | `newgrp zed`, `configure_zed_env.sh` |
| No controller data | Quest asleep / wrong APK | `test_oculus_reader.py`, `prox_close` |
| `Device not found` / empty `adb devices` | Quest unplugged or not authorized | USB-C cable, headset on, Allow USB debugging; `quest3_adb_setup.sh` |
| OpenCV mouse crash on recorder | Qt window timing | Use **r** key; script auto-fixes imshow order |
| Arm moves at startup | Expected | `vr_teleop_demo.py` homes arm; use `--no-reset-arm` to skip |

**Arm recovery on NUC:** `.cursor/skills/control-arm-via-nuc/nuc-admin.md`  
**Agent notes / pitfalls:** `improvement.md` in repo root

---

## Script index

| Script | Purpose |
|--------|---------|
| `scripts/demo/arm_smoke_test.py` | Verify NUC arm read (`--move` for tiny joint test) |
| `scripts/demo/robotiq_gripper_demo.py` | Gripper open/close cycle |
| `scripts/demo/zed_triple_camera_recorder.py` | 3-camera record + composite video |
| `scripts/demo/vr_teleop_demo.py` | VR arm + gripper |
| `scripts/demo/vr_gripper_teleop_demo.py` | VR gripper only |
| `scripts/demo/oculus_right_controller_demo.py` | VR virtual target demo |
| `scripts/demo/openpi_pi05_rollout.py` | π₀.5-DROID policy rollout (see [openpi-policy-rollout.md](openpi-policy-rollout.md)) |
| `scripts/demo/speech_command.py` | Voice → text for policy commands |
| `scripts/setup/test_oculus_reader.py` | Quest / adb diagnostic |
| `scripts/setup/list_zed_cameras.py` | List ZED serials |

---

## Related docs

- **[VR teleop demo](vr-teleop-demo.md)** — primary Quest demo runbook
- [Agent model handoff](agent-model-handoff.md) — onboarding for new policies (tiptop, etc.)
- [NUC agent instructions](nuc-agent-instructions.md)
- [Workstation agent handoff](workstation-agent-handoff.md)
- [Host installation](software-setup/host-installation.md) — full DROID install
- [OpenPI policy rollout](openpi-policy-rollout.md) — π₀.5-DROID language/voice experiments
- Skill: `.cursor/skills/control-arm-via-nuc/SKILL.md`
