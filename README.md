# droid-lab-fr3

Lab fork of the [DROID robot platform](https://github.com/droid-dataset/droid) for our **Franka FR3 + Robotiq 2F + 3× ZED + Quest 3** stack. It adds setup scripts, runbooks, and code patches needed to run teleop, data collection, and OpenPI policy rollouts in this lab—not the generic upstream install guide.

**Primary doc:** [Lab workstation quickstart](docs/lab-workstation-quickstart.md)

---

## What this repo is

Upstream [droid-dataset/droid](https://github.com/droid-dataset/droid) targets a monolithic NUC setup (arm + gripper on one box). In our lab the **gripper USB, cameras, and VR headset are on the workstation**; the **NUC only runs Polymetis + zerorpc** for the arm. This repo captures that split and the scripts we use day to day.

| Piece | Where it runs |
|-------|----------------|
| Franka FR3 (FCI) | NUC → robot over Ethernet |
| Robotiq gripper | Workstation USB (`launch_gripper.sh`) |
| 3× ZED (hand + 2 third-person) | Workstation USB |
| Quest 3 teleop | Workstation USB |
| Franka Desk (unlock / FCI) | Workstation browser |

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

### 3. Every session

1. Desk → unlock brakes → **Activate FCI**
2. NUC: Polymetis + `run_server.py` (zerorpc on `:4242`)
3. Workstation: `bash droid/franka/launch_gripper.sh`
4. Smoke test: `python scripts/demo/arm_smoke_test.py`

Full checklist and demos: [lab-workstation-quickstart.md](docs/lab-workstation-quickstart.md).

---

## Lab-specific changes (vs upstream DROID)

| Area | Files |
|------|--------|
| Lab IPs, camera IDs, robot type | `droid/misc/parameters.py` |
| NUC: optional gripper (workstation has USB) | `droid/franka/robot.py` |
| Workstation client: no Polymetis relaunch | `droid/robot_env.py`, `droid/misc/server_interface.py` |
| Gripper launch / COM port autodetect | `droid/franka/launch_gripper.sh` |
| Setup & session scripts | `scripts/setup/` |
| Demos (VR, OpenPI, cameras, gripper) | `scripts/demo/` |

Key patches and install helpers are under `scripts/setup/`; polymetis lazy-import is applied via `scripts/setup/apply_lab_patches.sh`.

---

## Documentation

| Doc | Purpose |
|-----|---------|
| [lab-workstation-quickstart.md](docs/lab-workstation-quickstart.md) | Main runbook for labmates |
| [nuc-agent-instructions.md](docs/nuc-agent-instructions.md) | NUC Polymetis / zerorpc admin |
| [openpi-policy-rollout.md](docs/openpi-policy-rollout.md) | π₀.5-DROID policy server + rollout |
| [agent-model-handoff.md](docs/agent-model-handoff.md) | Onboarding for new policy integrations |
| [workstation-agent-handoff.md](docs/workstation-agent-handoff.md) | Workstation-side agent notes |

OpenPI itself is **not** vendored here—clone [openpi](https://github.com/Physical-Intelligence/openpi) separately (see openpi doc).

---

## Common commands

```bash
# Arm read-only smoke test
conda activate robot && python scripts/demo/arm_smoke_test.py

# VR teleop (arm + gripper)
python scripts/demo/vr_teleop_demo.py

# OpenPI π₀.5 rollout (after policy server is up)
python scripts/demo/openpi_pi05_rollout.py --dry-run

# Reset half-started NUC/workstation processes
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
