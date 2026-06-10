# NUC agent instructions: connecting to the Franka robot arm

Instructions for AI agents (and operators) running **on the NUC** — the machine on the lab Ethernet switch that runs the real-time arm controller.

**Read these first:**

1. [`improvement.md`](../improvement.md) — conda envs, gripper USB on laptop, grpc/protobuf pins
2. [`/home/pci/Desktop/Franka_Robot/docs/AGENT_ROBOT_CONTROL.md`](/home/pci/Desktop/Franka_Robot/docs/AGENT_ROBOT_CONTROL.md) — **authoritative** lab network, Desk, and FCI workflow

---

## Your role on the NUC

The NUC is the **control server**. It should be the machine that runs libfranka / Polymetis against the Franka control box in real time.

| Layer | What runs on NUC | Port |
|-------|------------------|------|
| Polymetis controller | `launch_robot.py robot_client=franka_hardware` | gRPC **50051** |
| DROID zerorpc server | `scripts/server/run_server.py` | TCP **4242** |

The **workstation PC** (`192.168.1.6`) connects to the NUC over the switch. It does **not** run the arm real-time loop during normal DROID operation.

```text
                    ┌─────────────┐
                    │   Switch    │
                    └──────┬──────┘
           ┌───────────────┼───────────────┐
           │               │               │
    [Workstation PC]   [NUC]      [Control box C2]
    192.168.1.6        192.168.1.7   192.168.1.11
         │                  │               │
         └── zerorpc :4242 ─►│               │
                            └── libfranka ──►│  (FCI)
```

Gripper note for this lab: the Robotiq RS485-USB adapter is on the **workstation**, not the NUC. Arm control still happens on the NUC. See [`improvement.md`](../improvement.md) and `droid/franka/launch_gripper.sh`.

---

## Lab network (this site)

FCI / libfranka uses the control box **C2** port (“shop floor LAN”), **not** the arm **X5** port. All three machines share one unmanaged switch. **Do not** put X5 on the switch during normal operation.

| Device | IP | Interface |
|--------|-----|-----------|
| Robot (C2) | `192.168.1.11` | control box LAN |
| Workstation PC | `192.168.1.6` | typically `enp4s0` |
| NUC (this machine) | `192.168.1.7` | `enp*` / `eth*` — find with `ip -br link` |

Robot C2 must be configured in Desk → Settings → Network:

1. **Uncheck “DHCP Client”** (switch has no DHCP; otherwise robot gets `169.254.x.x`).
2. Static `192.168.1.11`, netmask `255.255.255.0`.
3. **APPLY**, wait ~30 s.

No gateway or DNS on this isolated LAN.

---

## Step 1 — Wire up the NUC network

Run on the **NUC**. Replace `enp3s0` with the actual wired interface (`ip -br link`).

```bash
# One-time NetworkManager profile
sudo nmcli connection add type ethernet con-name Franka-LAN ifname enp3s0 \
  ipv4.method manual ipv4.addresses 192.168.1.7/24 \
  ipv4.gateway "" ipv4.dns "" ipv6.method ignore

sudo nmcli connection up Franka-LAN

# Desk hostname (once per machine)
echo '192.168.1.11 robot.franka.de' | sudo tee -a /etc/hosts
```

**Rules:**

- Use **wired Ethernet only** on the NUC for robot traffic (not Wi‑Fi + Ethernet at the same time).
- Cable: NUC → **switch** → control box **C2** (not X5).
- Only **one** machine (PC **or** NUC) may command FCI at a time.

---

## Step 2 — Verify reachability (do this before any software)

Do **not** assume the robot is reachable from loopback-only interfaces or from Wi‑Fi.

```bash
ip -br addr
ip route get 192.168.1.11
ping -c 3 192.168.1.11
curl -sk -o /dev/null -w "%{http_code}\n" https://192.168.1.11/desk/
```

**Success looks like:**

- NUC interface **UP** with `192.168.1.7/24`
- Route to `192.168.1.11` goes via the wired interface (not Wi‑Fi)
- Ping: 0% packet loss
- HTTPS Desk: `200`

**If ping fails**, check physical setup before touching Polymetis:

| Check | Action |
|-------|--------|
| Only `lo` in `ip -br addr` | Plug Ethernet into switch; bring up `Franka-LAN` |
| `enp*` DOWN / unavailable | Cable seated; control box powered; wait 1–2 min after boot |
| ARP incomplete for `.11` | C2 not on switch, or C2 still on DHCP/APIPA — re-apply static IP in Desk |
| Route via Wi‑Fi | Disable Wi‑Fi or ensure wired route wins for `192.168.1.0/24` |

On the workstation, the same check is:

```bash
cd /home/pci/Desktop/Franka_Robot
./scripts/fix_desk_network.sh
```

Run the equivalent `ping` / `curl` commands above on the NUC.

---

## Step 3 — Configure DROID for this lab

Update **both** files so they match `192.168.1.11` / `192.168.1.7` (not the upstream DROID default `172.16.0.x` layout).

**`droid/misc/parameters.py`**

| Field | This lab |
|-------|----------|
| `robot_ip` | `"192.168.1.11"` |
| `nuc_ip` | `"192.168.1.7"` |
| `laptop_ip` | `"192.168.1.6"` |
| `robot_type` | `"fr3"` or `"panda"` |
| `sudo_password` | NUC sudo password (needed by `FrankaRobot.launch_controller()`) |

**`config/<robot_type>/franka_hardware.yaml`**

```yaml
robot_client:
  executable_cfg:
    robot_ip: "192.168.1.11"
```

**libfranka version** (set by `scripts/setup/nuc_setup.sh`):

| Robot | libfranka |
|-------|-----------|
| Panda | 0.9.0 |
| FR3 | 0.10.0 |

Verify from the NUC after editing:

```bash
cd /path/to/DROID
ping -c 3 "$(python -c "from droid.misc.parameters import robot_ip; print(robot_ip)")"
```

---

## Step 4 — Conda environment

The NUC needs a full Polymetis build in conda env **`polymetis-local`** (not the lightweight gripper-only install on the workstation).

```bash
source ~/anaconda3/etc/profile.d/conda.sh   # or ~/miniconda3/...
conda activate polymetis-local
which launch_robot.py   # must resolve inside polymetis-local
```

If missing: [`docs/software-setup/host-installation.md`](software-setup/host-installation.md) (NUC section) or `sudo bash scripts/setup/nuc_setup.sh` (Docker path).

---

## Step 5 — Franka pre-flight (Desk)

Every session, before starting Polymetis:

1. Control box **powered**; arm **X1** cable seated.
2. **E-stop (X3.1)** released; clear **Recovery** in Desk if shown.
3. **X4** enable device in **middle** position.
4. Wait for boot — flashing yellow → solid yellow → unlock brakes in Desk → **solid blue**.
5. Desk reachable: **https://robot.franka.de/desk/**
6. For code control: Desk → **Activate FCI** (keep popup open while controlling).

| LED | Meaning |
|-----|---------|
| Flashing yellow | Booting — wait 1–2 min |
| Solid yellow | Brakes locked — unlock in Desk |
| Solid blue | Ready for Desk / FCI |
| Red / pattern | Fault — check Desk |

Read-only smoke test (no torques):

```bash
conda activate polymetis-local
launch_robot.py robot_client=franka_hardware robot_client.executable_cfg.readonly=true
```

Stop with Ctrl+C when joint states stream without errors.

---

## Step 6 — Connect the arm (manual)

Use when debugging outside Docker.

### Terminal 1 — Polymetis arm server

```bash
cd /path/to/DROID
source ~/anaconda3/etc/profile.d/conda.sh
conda activate polymetis-local

pkill -9 franka_panda_cl 2>/dev/null || true
pkill -9 run_server 2>/dev/null || true

launch_robot.py robot_client=franka_hardware
```

Leave running. `use_real_time` defaults to **true** on hardware and may prompt for sudo.

### Terminal 2 — DROID zerorpc server

```bash
cd /path/to/DROID
source ~/anaconda3/etc/profile.d/conda.sh
conda activate polymetis-local
python scripts/server/run_server.py
```

Exposes `FrankaRobot` on `tcp://0.0.0.0:4242`. The workstation connects with `nuc_ip = "192.168.1.7"`.

Shortcuts:

- Arm only: `bash droid/franka/launch_robot.sh`
- Full entrypoint: `bash scripts/server/launch_server.sh`

### Verify on NUC

```bash
conda activate polymetis-local
python - <<'PY'
from polymetis import RobotInterface
robot = RobotInterface(ip_address="localhost")
print("joints:", robot.get_joint_positions())
PY

ss -tlnp | grep -E '50051|4242'
```

---

## Step 7 — Connect the arm (Docker)

After `sudo bash scripts/setup/nuc_setup.sh`:

```bash
cd /path/to/DROID
export ROOT_DIR="$(git rev-parse --show-toplevel)"
docker compose -f .docker/nuc/docker-compose-nuc.yaml up -d
docker compose -f .docker/nuc/docker-compose-nuc.yaml logs -f
```

Ensure `parameters.py` and `config/<robot_type>/franka_hardware.yaml` are mounted with `robot_ip: 192.168.1.11` before relying on the container.

---

## How the workstation uses the NUC

On the PC (`192.168.1.6`), set `nuc_ip = "192.168.1.7"` in `parameters.py`.

```python
# droid/robot_env.py — workstation side
from droid.misc.server_interface import ServerInterface
robot = ServerInterface(ip_address=nuc_ip)  # → 192.168.1.7:4242
```

End-to-end test (on **workstation**):

```bash
conda activate robot
python scripts/tests/collect_trajectory.py
```

---

## Shutting down safely

1. Stop motion on the workstation (release VR enable / stop scripts).
2. NUC: Ctrl+C on `run_server.py` or `docker compose ... down`.
3. NUC: Ctrl+C on `launch_robot.py` or `pkill -9 franka_panda_cl`.
4. Optionally lock joints from Desk.

Prefer Ctrl+C over `kill -9` so libfranka disconnects cleanly.

---

## Troubleshooting

| Symptom | Likely cause | What to try |
|---------|--------------|-------------|
| Ping `192.168.1.11` fails | C2 not on switch, wrong subnet, robot off | Section 2; check Desk C2 static IP |
| Route via Wi‑Fi | Wrong default route | Wired only; `ip route get 192.168.1.11` |
| `Connection refused` :50051 | Polymetis not running | `launch_robot.py` in `polymetis-local` |
| `Connection refused` :4242 | zerorpc not running | `run_server.py` or Docker |
| libfranka connection failed | FCI not activated, yellow LED, X4 off | Desk → unlock → Activate FCI |
| FCI timeout | PC and NUC both commanding | Only one FCI client at a time |
| Wrong `robot_ip` in config | Still `172.16.0.x` | Set `192.168.1.11` in parameters + yaml |
| Version mismatch | PC/NUC Polymetis builds differ | Rebuild NUC env |
| Panda vs FR3 mismatch | Wrong libfranka | Match `robot_type` to hardware |

---

## Quick reference (NUC happy path)

```bash
# 1. Network
sudo nmcli connection up Franka-LAN
ping -c2 192.168.1.11

# 2. Desk: unlock brakes → Activate FCI

# 3. Software
source ~/anaconda3/etc/profile.d/conda.sh && conda activate polymetis-local
cd /path/to/DROID
launch_robot.py robot_client=franka_hardware          # terminal 1
python scripts/server/run_server.py                     # terminal 2

# 4. Smoke test
python -c "from polymetis import RobotInterface as R; print(R('localhost').get_joint_positions())"
```

---

## Further reading

| Doc | Topic |
|-----|-------|
| [`Franka_Robot/docs/AGENT_ROBOT_CONTROL.md`](/home/pci/Desktop/Franka_Robot/docs/AGENT_ROBOT_CONTROL.md) | Lab network, Desk, FCI, scripts |
| [`docs/software-setup/host-installation.md`](software-setup/host-installation.md) | Upstream DROID install (note `172.16.0.x` differs from this lab) |
| [`improvement.md`](../improvement.md) | Agent lessons |
| `droid/fairo/polymetis/docs/source/usage.md` | Polymetis usage |
| [`.docker/README.md`](../.docker/README.md) | Docker deployment |
