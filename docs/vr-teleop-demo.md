# VR teleop demo (Quest → arm + gripper)

**Script:** `scripts/demo/vr_teleop_demo.py`  
**What it does:** DROID `VRPolicy` @ 15 Hz — Quest right controller drives Franka arm **and** Robotiq gripper, both via NUC zerorpc.

| Input (right controller) | Effect |
|--------------------------|--------|
| **RG** (side grip) | Enable teleop — hold while moving |
| **Move / rotate controller** | Arm end-effector follows relative 6-DOF delta |
| **Index trigger** | Gripper open (0) → closed (1) |
| **RJ** | Reset VR “forward” frame |
| **A / B** | UI indicators only (green/red panel) |

The Quest shows the **RAIL teleop VR app**, not passthrough. Watch the **physical arm** or a **monitor** (`--show-cameras`).

---

## Architecture

```text
┌──────────── Workstation (192.168.1.6) ────────────┐
│  Quest USB  →  VRPolicy / OculusReader            │
│  ZED USB    →  optional --show-cameras preview    │
│       │                                           │
│       └── zerorpc :4242 ──► NUC (192.168.1.7)     │
│              arm (Polymetis :50051 → FCI)         │
│              gripper (launch_gripper.sh :50052)   │
└───────────────────────────────────────────────────┘
```

Arm and gripper commands both go through **one** NUC zerorpc connection. No `launch_gripper.sh` on the workstation.

---

## New session — copy-paste checklist

**One command (fresh start everything + demo):**

```bash
cd ~/Desktop/DROID
bash scripts/demo/start_vr_teleop_demo.sh
```

Manual steps below if you prefer step-by-step.

### 0. Desk (browser)

1. https://192.168.1.11/desk/
2. **Unlock brakes**
3. **Execution → Activate FCI**

Verify FCI (optional):

```bash
nc -zv 192.168.1.11 1337    # should succeed when FCI is active
```

### 1. Start NUC stack (one command)

```bash
cd /home/pci/Desktop/DROID
bash scripts/setup/openpi_start_nuc_stack.sh
```

This starts gripper → Polymetis → zerorpc in order. If you changed `robot.py`, sync first:

```bash
scp droid/franka/robot.py nuc:/home/pci/Desktop/Franka/droid/droid/franka/robot.py
bash scripts/setup/openpi_start_zerorpc.sh
```

Or step by step:

```bash
bash scripts/setup/openpi_nuc_status.sh
# expect :50052 (gripper), :50051 + franka_panda_client, :4242 (zerorpc)
```

If you changed `droid/franka/robot.py`, sync to NUC and restart zerorpc:

```bash
scp droid/franka/robot.py nuc:/home/pci/Desktop/Franka/droid/droid/franka/robot.py
bash scripts/setup/openpi_start_zerorpc.sh
```

### 2. Smoke tests (workstation)

```bash
conda activate robot
cd /home/pci/Desktop/DROID

python scripts/demo/arm_smoke_test.py
python scripts/demo/robotiq_gripper_demo.py --cycles 1
```

### 3. Quest USB

```bash
export PATH="$HOME/platform-tools:$PATH"
adb devices    # must show: <serial>    device
```

If `unauthorized`: put on headset → **Allow USB debugging** → **Always allow**.

Keep awake without wearing (optional):

```bash
adb shell am broadcast -a com.oculus.vrpowermanager.prox_close
```

Diagnostic:

```bash
python scripts/setup/test_oculus_reader.py
```

### 4. Run VR teleop

```bash
export PATH="$HOME/platform-tools:$PATH"
adb devices
conda activate robot
cd /home/pci/Desktop/DROID
python scripts/demo/vr_teleop_demo.py
```

**With camera preview on monitor:**

```bash
python scripts/demo/vr_teleop_demo.py --show-cameras
python scripts/demo/vr_teleop_demo.py --show-cameras --all-cameras
```

---

## What happens on launch

1. **Quest preflight** — exits if `adb devices` has no authorized `device`
2. Connect NUC (`192.168.1.7:4242`) → `launch_robot OK` (arm + gripper)
3. **Home arm** to DROID default joints (blocking move)
4. **Open gripper** on NUC
5. Start `VRPolicy` / OculusReader → matplotlib status window

Expected console output (abbreviated):

```text
Quest adb OK (<serial>)
Connecting to NUC arm at 192.168.1.7:4242 ...
launch_robot OK
Arm connected. EE xyz=(...)
Resetting arm to DROID home pose (blocking)...
Arm home OK.
Opening gripper on NUC...
Starting VRPolicy (OculusReader thread) — keep right controller visible.
```

Skip homing if arm is already in a good pose:

```bash
python scripts/demo/vr_teleop_demo.py --no-reset-arm
```

---

## Useful flags

| Flag | Purpose |
|------|---------|
| `--show-cameras` | Hand RGB+depth + both third-person RGB on monitor |
| `--show-cameras --all-cameras` | All 3 ZEDs, RGB+depth per camera (heavy USB) |
| `--no-reset-arm` | Skip homing arm + opening gripper at startup |
| `--dry-run` | Log VR mapping only; **no** arm/gripper commands |
| `--no-quest-preflight` | Skip adb check (not recommended) |
| `--nuc-ip <ip>` | Override `droid/misc/parameters.py` |

### Dry-run (Quest mapping, no robot motion)

Good for checking Quest + controller before homing the arm:

```bash
python scripts/demo/vr_teleop_demo.py --dry-run
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `no Quest visible to adb` | USB / not authorized | Plug cable, accept debugging on headset |
| `launch_robot timed out` | NUC stack not started or gripper gRPC hung | `bash scripts/setup/openpi_start_nuc_stack.sh`; sync `robot.py` to NUC |
| `empty buffer` / arm timeout | FCI off or Polymetis dead | Desk → Activate FCI; relaunch Polymetis on NUC |
| Arm moves at startup | Expected | `--no-reset-arm` to skip homing |
| No controller data | Quest asleep / wrong APK | `test_oculus_reader.py`, `prox_close` |
| Gripper does not move | NUC gripper activation / USB | On NUC: `ls /dev/ttyUSB*`; restart `openpi_start_gripper_nuc.sh` |

**NUC recovery:** `.cursor/skills/control-arm-via-nuc/nuc-admin.md`  
**Gripper-only VR** (arm down): `python scripts/demo/vr_gripper_teleop_demo.py`  
**Controller test** (no robot): `python scripts/demo/oculus_right_controller_demo.py`

---

## Clean shutdown

```bash
bash scripts/setup/openpi_session_reset.sh
```

Then lock joints from Desk if leaving the lab.

---

## Related

- [Lab workstation quickstart](lab-workstation-quickstart.md) — full lab runbook
- [NUC admin](../.cursor/skills/control-arm-via-nuc/nuc-admin.md) — relaunch commands
- `improvement.md` — lab pitfalls
