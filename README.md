# droid-lab-fr3

Lab fork of the [DROID robot platform](https://github.com/droid-dataset/droid) for our **Franka FR3 + Robotiq 2F + 3× ZED + Quest 3** stack. It adds setup scripts, runbooks, and code patches needed to run teleop, data collection, and OpenPI policy rollouts in this lab—not the generic upstream install guide.

**Primary doc:** [Lab workstation quickstart](docs/lab-workstation-quickstart.md)

---

## What this repo is

Upstream [droid-dataset/droid](https://github.com/droid-dataset/droid) targets a monolithic NUC setup (arm + gripper on one box). In our lab the **gripper USB is on the NUC**; **cameras and VR headset are on the workstation**. The NUC runs Polymetis, zerorpc, and the gripper server.

| Piece | Where it runs |
|-------|----------------|
| Franka FR3 (FCI) | NUC → robot over Ethernet |
| Robotiq gripper | **NUC USB** (`launch_gripper.sh` on NUC) |
| 3× ZED (hand + 2 third-person) | Workstation USB |
| Quest 3 VR teleop | Workstation USB |
| Franka Desk (unlock / FCI) | Workstation browser |

**Primary demo:** [VR teleop](docs/vr-teleop-demo.md) — `python scripts/demo/vr_teleop_demo.py`

Default branch: **`lab-fr3-setup`**

---

## Network (this lab)

| Host | IP | Role |
|------|-----|------|
| Workstation | `192.168.1.6` | Gripper, ZED, Quest, Desk |
| NUC | `192.168.1.7` | Polymetis + zerorpc `:4242` |
| Franka FR3 | `192.168.1.11` | Robot controller |

IPs and camera serials live in `droid/misc/parameters.py`. Change them if your network differs.

---

## Quick start

### 1. Clone

```bash
git clone --recurse-submodules git@github.com:JipengSun/droid-lab-fr3.git
cd droid-lab-fr3
git checkout lab-fr3-setup   # default branch; skip if already checked out
bash scripts/setup/apply_lab_patches.sh   # polymetis patch inside fairo submodule
```

### 2. One-time setup

Follow [docs/lab-workstation-quickstart.md](docs/lab-workstation-quickstart.md):

- Conda envs: `polymetis-local` (gripper server), `robot` (client / VR / cameras)
- ZED SDK + Python API
- Quest / adb
- Sync patched `droid/franka/robot.py` to the NUC

### 3. Every session (VR teleop)

1. Desk → unlock brakes → **Activate FCI**
2. NUC stack: `openpi_start_gripper_nuc.sh` → Polymetis → zerorpc (see [VR teleop demo](docs/vr-teleop-demo.md))
3. `adb devices` → Quest shows `device`
4. Smoke test: `python scripts/demo/arm_smoke_test.py`
5. **VR teleop:** `python scripts/demo/vr_teleop_demo.py`

Full checklist: [lab-workstation-quickstart.md](docs/lab-workstation-quickstart.md) · **VR runbook:** [vr-teleop-demo.md](docs/vr-teleop-demo.md)

---

## Lab-specific changes (vs upstream DROID)

| Area | Files |
|------|--------|
| Lab IPs, camera IDs, robot type | `droid/misc/parameters.py` |
| NUC: gripper on USB, arm via Polymetis | `droid/franka/robot.py` |
| Workstation client: no Polymetis relaunch | `droid/robot_env.py`, `droid/misc/server_interface.py` |
| Gripper launch / COM port autodetect | `droid/franka/launch_gripper.sh` |
| Setup & session scripts | `scripts/setup/` |
| Demos (VR, OpenPI, cameras, gripper) | `scripts/demo/` |

Key patches and install helpers are under `scripts/setup/`; polymetis lazy-import is applied via `scripts/setup/apply_lab_patches.sh`.

---

## Documentation

| Doc | Purpose |
|-----|---------|
| [vr-teleop-demo.md](docs/vr-teleop-demo.md) | **Primary demo** — Quest VR arm + gripper |
| [lab-workstation-quickstart.md](docs/lab-workstation-quickstart.md) | Main runbook for labmates |
| [nuc-agent-instructions.md](docs/nuc-agent-instructions.md) | NUC Polymetis / zerorpc admin |
| [openpi-policy-rollout.md](docs/openpi-policy-rollout.md) | π₀.5-DROID policy server + rollout |
| [agent-model-handoff.md](docs/agent-model-handoff.md) | Onboarding for new policy integrations |
| [workstation-agent-handoff.md](docs/workstation-agent-handoff.md) | Workstation-side agent notes |

OpenPI itself is **not** vendored here—clone [openpi](https://github.com/Physical-Intelligence/openpi) separately (see openpi doc).

---

## Common commands

```bash
# VR teleop — fresh start (reset + NUC stack + demo)
conda activate robot && cd ~/Desktop/DROID
bash scripts/demo/start_vr_teleop_demo.sh

# π₀.5 policy — fresh start (reset + NUC stack + policy server + rollout)
bash scripts/demo/start_pi05_demo.sh
bash scripts/demo/start_pi05_demo.sh --dry-run   # inference only, no motion

# Arm read-only smoke test
python scripts/demo/arm_smoke_test.py

# Clean shutdown
bash scripts/setup/openpi_session_reset.sh
```

---

## Upstream DROID

This repo is based on [droid-dataset/droid](https://github.com/droid-dataset/droid). For the original platform overview, dataset, and generic hardware docs:

- [DROID homepage](https://droid-dataset.github.io)
- [Upstream documentation](https://droid-dataset.github.io/droid)
- [DROID paper](https://arxiv.org/abs/2403.12945)
- [Policy learning repo](https://github.com/droid-dataset/droid_policy_learning)

Issues with **lab-specific** setup: open an issue on this repo. Upstream DROID bugs belong on [droid-dataset/droid](https://github.com/droid-dataset/droid).
