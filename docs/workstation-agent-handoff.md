# Workstation agent handoff — NUC status report

**Generated:** 2026-06-09  
**From:** NUC agent (this machine)  
**To:** Workstation agent (`192.168.1.6`)  
**Purpose:** Connect the workstation to the arm via the NUC. The workstation does **not** run libfranka/FCI directly.

---

## Executive summary

| Item | Status |
|------|--------|
| NUC → robot network | **OK** (`192.168.1.7` ↔ `192.168.1.11`) |
| NUC ↔ workstation network | **OK** (`192.168.1.7` ↔ `192.168.1.6`) |
| Polymetis (FCI arm control) | **RUNNING** — `Connected.` on port **50051** |
| DROID zerorpc server | **RUNNING** — port **4242** |
| Robot model | **Franka Research 3 (FR3)** — not Panda |
| Real-time kernel | **Not installed** — running `use_real_time=false` |
| FCI prerequisite | Robot must have **FCI activated** from Desk on **workstation** |

**Workstation action:** Point DROID at `nuc_ip = "192.168.1.7"`, verify `nc 192.168.1.7 4242`, run smoke test below. Use Desk only on the workstation — never on the NUC.

---

## Lab network

```text
                    ┌─────────────┐
                    │   Switch    │
                    └──────┬──────┘
           ┌───────────────┼───────────────┐
           │               │               │
    [Workstation]      [NUC]         [Robot C2]
    192.168.1.6        192.168.1.7     192.168.1.11
         │                  │               │
         └── zerorpc :4242 ─►│               │
                            └── libfranka ──►│  FCI :1337
```

| Device | IP | Role |
|--------|-----|------|
| Workstation | `192.168.1.6` | Desk, cameras, VR, DROID client code |
| NUC | `192.168.1.7` | Polymetis + zerorpc (arm real-time loop) |
| Robot (C2) | `192.168.1.11` | Franka control box; Desk at `https://192.168.1.11/desk/` |

This lab uses **192.168.1.0/24**, not upstream DROID default `172.16.0.x`.

---

## What is running on the NUC right now

| Service | Port | Process | Status |
|---------|------|---------|--------|
| Polymetis gRPC | **50051** | `run_server` + `franka_panda_client` | Listening; FCI connected |
| DROID zerorpc | **4242** | `python scripts/server/run_server.py` | Listening on `0.0.0.0` |
| `launch_robot.py` | — | `robot_client=franka_hardware use_real_time=false` | Parent of Polymetis stack |

**NUC interface:** `enp86s0` — NetworkManager profile **`Franka-LAN`**, address `192.168.1.7/24`.

**Logs on NUC:**

| Path | Contents |
|------|----------|
| `/tmp/polymetis_connect.log` | Polymetis launch; last line: `Connected.` |
| `/tmp/droid_zerorpc.log` | DROID zerorpc server |

---

## `parameters.py` (sync on workstation)

Ensure the workstation copy of `droid/misc/parameters.py` matches:

```python
nuc_ip = "192.168.1.7"
robot_ip = "192.168.1.11"
laptop_ip = "192.168.1.6"
robot_type = "fr3"
sudo_password = ""  # only needed if launch_controller relaunches arm on NUC
```

`RobotEnv` reads `nuc_ip` and connects via `ServerInterface` → `tcp://192.168.1.7:4242`.

---

## Workstation: pre-flight (Desk on robot)

Do this in a browser on the **workstation** only:

1. Open `https://192.168.1.11/desk/`
2. **Unlock brakes**
3. Mode → **Execution**
4. **Activate FCI** (green LED on FR3 is normal)
5. In **Watchman**: no active rules using **Inside/Outside Area** (SLP-C) or **Maximum Velocity** (SLS-C) — these block FCI. Assist mode should stay off for FCI.

Do **not** open Desk in a browser on the NUC while Polymetis is running.

---

## Workstation: connectivity check

```bash
ping -c 2 192.168.1.7
nc -zv 192.168.1.7 4242    # DROID zerorpc — must succeed
nc -zv 192.168.1.7 50051   # Polymetis gRPC (optional check)
```

---

## Workstation: smoke test (arm only)

Polymetis is **already running** on the NUC. Use **`launch=False`** so the workstation does not try to relaunch the arm (which would `pkill` the current session).

```bash
cd /path/to/droid
conda activate robot   # or polymetis-local if that is your workstation env

python - <<'PY'
from droid.misc.server_interface import ServerInterface
from droid.misc.parameters import nuc_ip

robot = ServerInterface(ip_address=nuc_ip, launch=False)
robot.launch_robot()
print("joints:", robot.get_joint_positions())
print("ee_pose:", robot.get_ee_pose())
PY
```

**Success:** joint positions and EE pose print without error.

---

## Workstation: how control flows

```text
Workstation Python
  └─ ServerInterface(ip="192.168.1.7")     # zerorpc client
       └─ tcp://192.168.1.7:4242
            └─ FrankaRobot (on NUC)
                 └─ RobotInterface("localhost")  # Polymetis
                      └─ franka_panda_client → FCI → 192.168.1.11
```

- **Arm commands:** workstation → NUC:4242 → Polymetis:50051 → robot
- **Workstation does not need** libfranka 0.19 or FCI TCP to the robot for normal DROID use
- **Gripper:** Robotiq USB is on the **workstation** in this lab, not the NUC. `FrankaRobot.launch_controller()` tries to start gripper on the NUC (`/dev/ttyUSB0`) and will fail here. For arm-only testing, always use `launch=False`. Gripper integration is a separate follow-up.

---

## Workstation: full DROID session (when VR/cameras ready)

```bash
conda activate robot
python scripts/tests/collect_trajectory.py
```

**Caution:** `RobotEnv()` uses `ServerInterface(launch=True)`, which remotely calls `launch_controller()` and will **kill and relaunch** Polymetis on the NUC plus attempt NUC gripper launch. Coordinate with the NUC operator before using `RobotEnv()` as-is, or patch to `launch=False` until gripper path is sorted.

---

## NUC technical notes (for debugging)

| Topic | Value |
|-------|-------|
| DROID repo on NUC | `/home/pci/Desktop/Franka/droid` |
| Conda env | `polymetis-local` (Python 3.8) |
| Conda root | `/home/pci/miniconda3` |
| libfranka | **0.19** built to `droid/.local/libfranka-0.19` (FR3 firmware FCI server v10) |
| Polymetis launch | `use_real_time=false` (no PREEMPT_RT kernel) |
| Kernel | `6.8.0-124-generic` — **not** PREEMPT_RT |
| Polymetis log says "Franka Emika" | Legacy client name; hardware is **FR3** |

**Relaunch arm on NUC** (only if Polymetis dies):

```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate polymetis-local
source /home/pci/Desktop/Franka/droid/scripts/nuc/env.sh
cd /home/pci/Desktop/Franka/droid
pkill -9 franka_panda_cl 2>/dev/null; pkill -9 run_server 2>/dev/null
launch_robot.py robot_client=franka_hardware use_real_time=false
```

**Relaunch zerorpc on NUC** (only if :4242 dies):

```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate polymetis-local
source /home/pci/Desktop/Franka/droid/scripts/nuc/env.sh
cd /home/pci/Desktop/Franka/droid
python scripts/server/run_server.py
```

---

## Safe shutdown order

1. Stop motion on workstation (release VR enable / stop scripts).
2. NUC: Ctrl+C on `run_server.py` (zerorpc :4242).
3. NUC: Ctrl+C on `launch_robot.py` (or `pkill franka_panda_cl`).
4. Optionally lock joints from Desk on workstation.

Prefer Ctrl+C over `kill -9` so libfranka disconnects cleanly.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `Connection refused` `:4242` | zerorpc not on NUC | Start `python scripts/server/run_server.py` on NUC |
| `Connection refused` `:50051` | Polymetis dead | Relaunch `launch_robot.py` on NUC |
| `FCI refused` | FCI not activated | Desk on workstation → Activate FCI |
| `Get Robot Model` error | Watchman SLP-C/SLS-C rules active | Delete/disable rules in Watchman; Commit |
| Arm moves then stops | FCI deactivated or second client | One FCI client only; keep Desk on workstation |
| Desk UI spam / refresh | Desk open on NUC | Close NUC browser; use workstation only |
| `launch_controller` kills connection | `RobotEnv()` default `launch=True` | Use `ServerInterface(..., launch=False)` |
| `Cannot retrieve robot state from empty buffer!` | Polymetis gRPC up but `franka_panda_client` not streaming (FCI off, client crashed, or stale session) | Desk → Activate FCI; on NUC relaunch `launch_robot.py` and `run_server.py`; check `/tmp/polymetis_connect.log` for `Connected.` |
| `GripperInterface` has no `metadata` | No gripper server on NUC (USB on workstation) | Sync patched `droid/franka/robot.py` to NUC; restart zerorpc |

---

## Related docs on NUC repo

- `docs/nuc-agent-instructions.md` — full NUC operator guide
- `improvement.md` — lab-specific fixes (libfranka 0.19, Watchman, Desk-on-NUC)
- `scripts/nuc/connect_robot.sh` — NUC connect wrapper
- `scripts/nuc/close_desk_browser.sh` — close Desk tabs on NUC

---

## Checklist for workstation agent

- [ ] `parameters.py`: `nuc_ip = "192.168.1.7"`, `robot_type = "fr3"`
- [ ] `ping 192.168.1.7` and `nc -zv 192.168.1.7 4242`
- [ ] Desk: Execution + FCI activated (workstation browser only)
- [ ] Smoke test with `ServerInterface(..., launch=False)` + `launch_robot()`
- [ ] Do not use `RobotEnv()` / `launch=True` until gripper + relaunch behavior agreed with NUC operator
