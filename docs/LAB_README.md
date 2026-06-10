# Princeton FR3 lab — DROID workstation setup

Fork/customization of [droid-dataset/droid](https://github.com/droid-dataset/droid) for this lab's Franka FR3 + Robotiq + 3× ZED + Quest 3 stack.

**Start here:** [lab-workstation-quickstart.md](lab-workstation-quickstart.md)

## What's in this repo (beyond upstream DROID)

| Area | Location |
|------|----------|
| Lab IPs, camera serials | `droid/misc/parameters.py` |
| NUC gripper-optional arm server | `droid/franka/robot.py` |
| Workstation → NUC client (no relaunch) | `droid/robot_env.py`, `droid/misc/server_interface.py` |
| Setup scripts | `scripts/setup/` |
| Demos (VR teleop, OpenPI, cameras) | `scripts/demo/` |
| NUC runbook | `docs/nuc-agent-instructions.md` |
| OpenPI π₀.5 rollout | `docs/openpi-policy-rollout.md` |

## Network layout (this lab)

| Host | IP | Role |
|------|-----|------|
| Workstation | 192.168.1.6 | Gripper USB, ZED USB, Quest, Desk browser |
| NUC | 192.168.1.7 | Polymetis + zerorpc `:4242` |
| Franka FR3 | 192.168.1.11 | FCI |

Update IPs in `parameters.py` if your network differs.

## Reproduce on a fresh machine

1. Clone this repo (with submodules):

   ```bash
   git clone --recurse-submodules git@github.com:<YOUR_ORG>/droid-lab-fr3.git
   cd droid-lab-fr3
   ```

2. Follow [lab-workstation-quickstart.md](lab-workstation-quickstart.md) — conda envs, ZED, Quest, NUC sync.

3. Clone OpenPI separately (not vendored): `~/Desktop/openpi` — see [openpi-policy-rollout.md](openpi-policy-rollout.md).

## Upstream

Based on [droid-dataset/droid](https://github.com/droid-dataset/droid) @ `main`. Lab patches are on branch `lab-fr3-setup`.
