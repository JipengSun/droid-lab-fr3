# Lab workstation quickstart (Franka FR3 + Robotiq + ZED + Quest)

Guide for new labmates using **this lab’s** DROID workstation setup.  
Workstation: `pci-blenderman` (`192.168.1.6`) · NUC: `192.168.1.7` · Robot: `192.168.1.11`

Repo path: `/home/pci/Desktop/DROID`

---

## What runs where

| Component | Machine | Notes |
|-----------|---------|--------|
| Franka arm (FCI) | NUC → robot | Polymetis + zerorpc `:4242` on NUC |
| Robotiq 2F gripper | **Workstation USB** | `launch_gripper.sh` on laptop |
| 3× ZED cameras | Workstation USB | hand ZED-M + 2× ZED 2i |
| Quest 3 VR | Workstation USB | `oculus_reader` + teleop APK |
| Desk (FCI unlock) | **Workstation browser** | https://192.168.1.11/desk/ |

Gripper is **not** on the NUC. Arm commands go over the network; gripper commands stay local.

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
- Patched `droid/franka/robot.py` on NUC skips local gripper (gripper is on workstation).

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
nc -zv localhost 50052     # local gripper (after launch_gripper.sh)
```

### C. Arm smoke test

```bash
conda activate robot
cd /home/pci/Desktop/DROID
python scripts/demo/arm_smoke_test.py
```

Expect joint positions and EE pose within ~1 s. If timeout → see [Troubleshooting](#troubleshooting).

### D. Quest awake (optional, if not wearing headset)

```bash
export PATH="$HOME/platform-tools:$PATH"
adb shell am broadcast -a com.oculus.vrpowermanager.prox_close
```

---

## Workflows

Always use **`conda activate robot`** (or `polymetis-local` for gripper server only).  
Always **`cd /home/pci/Desktop/DROID`** before running scripts.

---

### 1. Gripper only (no arm)

**Terminal 1 — gripper server:**
```bash
conda activate polymetis-local
cd /home/pci/Desktop/DROID
bash droid/franka/launch_gripper.sh
# wait for: Activated. + Gripper server running at 0.0.0.0:50052
```

**Terminal 2 — demo:**
```bash
conda activate robot
cd /home/pci/Desktop/DROID
python scripts/demo/robotiq_gripper_demo.py
python scripts/demo/robotiq_gripper_demo.py --show-cameras
python scripts/demo/robotiq_gripper_demo.py --show-cameras --all-cameras
```

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

### 3. VR teleop — arm + gripper (full setup)

**Terminal 1 — gripper server** (same as above)

**Terminal 2 — VR teleop:**
```bash
export PATH="$HOME/platform-tools:$PATH"
conda activate robot
cd /home/pci/Desktop/DROID
python scripts/demo/vr_teleop_demo.py
```

On launch the script **homes the arm** (DROID default joints) and **opens the gripper**.  
Skip with `--no-reset-arm`.

**With camera preview on monitor:**
```bash
python scripts/demo/vr_teleop_demo.py --show-cameras
python scripts/demo/vr_teleop_demo.py --show-cameras --all-cameras
```

**Test Quest mapping without moving arm:**
```bash
python scripts/demo/vr_teleop_demo.py --dry-run
```

#### VR controls (right controller)

| Input | Effect |
|-------|--------|
| **RG** (side grip) | Enable teleop — hold while moving |
| **Move / rotate controller** | Arm EE follows relative delta (6-DOF) |
| **Index trigger** | Gripper open → closed |
| **RJ** | Reset VR “forward” frame |
| **A / B** | UI indicators only |

**Seeing the robot:** the Quest shows a **virtual teleop app**, not passthrough. Watch the **physical arm** or a **monitor** (`--show-cameras`), not the headset view.

---

### 4. VR gripper only (no NUC arm)

```bash
export PATH="$HOME/platform-tools:$PATH"
conda activate robot
cd /home/pci/Desktop/DROID
# gripper server must still be running in Terminal 1
python scripts/demo/vr_gripper_teleop_demo.py
```

---

### 5. VR / controller test (virtual target, no robot)

```bash
conda activate robot
cd /home/pci/Desktop/DROID
python scripts/demo/oculus_right_controller_demo.py
```

Good for learning RG + trigger before touching hardware.

---

### 6. OpenPI π₀.5-DROID policy rollout (language / voice commands)

Run a pre-trained VLA policy on the real robot. Requires OpenPI installed at `~/Desktop/openpi`.

**Full guide:** [OpenPI policy rollout](openpi-policy-rollout.md) — see **New session startup (copy-paste)** for the full checklist.

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
│  Gripper USB ──► launch_gripper.sh :50052                   │
│       │                                                     │
│       └── zerorpc ──► NUC :4242 ──► Polymetis ──► FR3 FCI  │
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
| Gripper connect failed | Server not running | Terminal 1: `launch_gripper.sh` |
| `import pyzed` fails | ZED SDK / group | `newgrp zed`, `configure_zed_env.sh` |
| No controller data | Quest asleep / wrong APK | `test_oculus_reader.py`, `prox_close` |
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

- [Agent model handoff](agent-model-handoff.md) — onboarding for new policies (tiptop, etc.)
- [NUC agent instructions](nuc-agent-instructions.md)
- [Workstation agent handoff](workstation-agent-handoff.md)
- [Host installation](software-setup/host-installation.md) — full DROID install
- [OpenPI policy rollout](openpi-policy-rollout.md) — π₀.5-DROID language/voice experiments
- Skill: `.cursor/skills/control-arm-via-nuc/SKILL.md`
