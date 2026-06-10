# OpenPI π₀.5-DROID policy rollout (lab guide)

Run a **pre-trained language-conditioned manipulation policy** on this lab’s DROID stack (Franka FR3 + Robotiq + ZED).

| Item | Value |
|------|--------|
| Workstation | `pci-blenderman` (`192.168.1.6`) |
| NUC | `192.168.1.7` (Polymetis `:50051` + zerorpc `:4242`) |
| Robot | `192.168.1.11` (Desk / FCI) |
| DROID repo | `/home/pci/Desktop/DROID` |
| OpenPI repo | `/home/pci/Desktop/openpi` |
| Policy | [Physical Intelligence π₀.5-DROID](https://github.com/Physical-Intelligence/openpi) |

**Prerequisite reading:** [Lab workstation quickstart](lab-workstation-quickstart.md) (conda envs, ZED, NUC, gripper split).

> **Doc maintenance:** When setup commands, scripts, or lab wiring change, update **this file** in the same change (see [Changelog](#changelog) + [Lab code in this repo](#lab-code-in-this-repo)).

---

## New session startup (copy-paste)

Run these **in order** every time you start a fresh experiment. All shell commands are from the **workstation** unless noted.

**You need:** 1 browser tab (Desk) + **up to 4 terminal windows** on the workstation (A: NUC/verify, B: gripper, C: policy, D: rollout — you may reuse A for rollout).

---

### Step 0a — Clean slate (workstation terminal A)

Kill half-started processes from a prior session or crash. Safe if nothing is running.

```bash
cd ~/Desktop/DROID
bash scripts/setup/openpi_session_reset.sh
```

**Success:** NUC + workstation reports `CLEAN` / `NO_CLIENT` / `NO_SERVERS` / `NO_PROCESSES` (ports `:4242`, `:50051`, `:50052`, `:8000` not listening).

Individual scripts (optional):

```bash
bash scripts/setup/openpi_kill_workstation.sh   # gripper :50052, policy :8000, rollout
bash scripts/setup/openpi_kill_nuc.sh           # Polymetis :50051, zerorpc :4242
```

---

### Step 0 — Desk (browser, not terminal)

1. Open https://192.168.1.11/desk/
2. Unlock brakes, clear any faults
3. **Execution → Activate FCI**
4. Release external activation device (EAD) if the arm is safety-locked

Do this **before** starting Polymetis on the NUC.

---

### Step 1 — NUC status check (workstation terminal A)

```bash
cd ~/Desktop/DROID
bash scripts/setup/openpi_nuc_status.sh
```

**Healthy:** both `:50051` + `:4242` listening, `franka_panda_client` running, log shows **`Connected.`**

**Clean after reset:** no ports, `NO_CLIENT`, script summary **`CLEAN`** — old log errors are **stale** (ignore them).

**Unhealthy:** `:4242` only, client PID present, log has `ControlUpdate rpc failed` or `automaticErrorRecovery` → Polymetis never fully connected; **do not rollout** until step 2b passes.

On a **new session**, run steps **2a–3** anyway (stack is usually dead after overnight / User Stop).

---

### Step 2a — Start Polymetis on NUC (workstation terminal A)

Returns **immediately** (starts Polymetis in background on the NUC).

```bash
cd ~/Desktop/DROID
bash scripts/setup/openpi_start_polymetis.sh
```

> **Note:** NUC scripts use `ssh nuc 'bash -s' <<'REMOTE'` so `pkill -f launch_robot.py` does not kill the SSH shell (inline `ssh "…pkill…launch_robot…"` silently exits 255).

### Step 2b — Verify Polymetis (wait ~15 s after step 2a)

```bash
sleep 15
bash scripts/setup/openpi_verify_polymetis.sh
```

**Success:** log line **`Connected.`**, `franka_panda_client` PID, port **50051** listening.

**If it fails:** re-check Desk FCI, clear robot faults, repeat steps 2a + 2b.

---

### Step 3 — Start zerorpc on NUC (workstation terminal A)

```bash
bash scripts/setup/openpi_start_zerorpc.sh
```

**Success:** port **4242** listening.

---

### Step 4 — Verify arm (workstation terminal A)

```bash
nc -zv 192.168.1.7 4242
nc -zv 192.168.1.7 50051

conda activate robot
cd ~/Desktop/DROID
python scripts/demo/arm_smoke_test.py
```

**Must show `launch_robot OK`** before rollout. If not, see [NUC Polymetis recovery](#nuc-polymetis-recovery).

> If a Python demo prints nothing in the Cursor terminal, pull latest — `arm_smoke_test.py` and `openpi_pi05_rollout.py` redirect status to stderr (same fix as `exec 1>&2` in `openpi_*.sh`).

---

### Step 5 — Gripper server (workstation terminal B)

Leave this terminal open.

```bash
conda activate polymetis-local
cd ~/Desktop/DROID
bash droid/franka/launch_gripper.sh
```

Wait for: `Gripper server running at 0.0.0.0:50052`

```bash
nc -zv localhost 50052
```

---

### Step 6 — Policy server (workstation terminal C)

Leave this terminal open.

```bash
bash ~/Desktop/openpi/scripts/serve_pi05_droid.sh
```

Wait for: `server listening on 0.0.0.0:8000`

If port 8000 is busy, a server is already running — use it or stop the old process:

```bash
ss -tlnp | grep 8000
```

---

### Step 7 — Rollout (workstation terminal D, or reuse terminal A)

```bash
conda activate robot
cd ~/Desktop/DROID
```

**Dry run** (cameras + inference, no motion):

```bash
PYTHONUNBUFFERED=1 python scripts/demo/openpi_pi05_rollout.py --dry-run --no-reset
```

**Live rollout — voice:**

```bash
PYTHONUNBUFFERED=1 python scripts/demo/openpi_pi05_rollout.py \
  --external-camera left --no-reset --input-mode voice
```

**Live rollout — type command:**

```bash
PYTHONUNBUFFERED=1 python scripts/demo/openpi_pi05_rollout.py \
  --external-camera left --no-reset
```

**Live rollout — type or voice (default):**

```bash
PYTHONUNBUFFERED=1 python scripts/demo/openpi_pi05_rollout.py \
  --external-camera left --no-reset --input-mode both
```

---

### Step 8 — End of session (optional)

```bash
cd ~/Desktop/DROID
bash scripts/setup/openpi_session_reset.sh
# Lock joints from Desk if desired
```

---

### Session checklist (printable)

| Step | Where | Done? |
|------|-------|-------|
| 0a `openpi_session_reset.sh` | Workstation | ☐ CLEAN |
| 0 Desk → FCI | Browser | ☐ |
| 1 NUC status | Workstation SSH | ☐ |
| 2a Polymetis start | Workstation SSH | ☐ |
| 2b Polymetis verify | Workstation SSH | ☐ `Connected.` + `:50051` |
| 3 zerorpc | Workstation SSH | ☐ `:4242` |
| 4 `arm_smoke_test.py` | Workstation | ☐ `launch_robot OK` |
| 5 `launch_gripper.sh` | Terminal B | ☐ `:50052` |
| 6 `serve_pi05_droid.sh` | Terminal C | ☐ `:8000` |
| 7 Rollout | Terminal D | ☐ |

---

## What this experiment does

1. **Policy server** (GPU on workstation) loads π₀.5-DROID and listens on port **8000**.
2. **Rollout client** reads ZED cameras + arm/gripper state, sends a **language command**, receives action chunks.
3. **Arm** moves via NUC zerorpc; **gripper** is read and commanded **locally** on the workstation USB (not the NUC).

```
┌──────────── Workstation (192.168.1.6) ────────────┐
│  Terminal 2: OpenPI policy server  :8000 (GPU)    │
│  Terminal 1: Robotiq gripper       :50052 (USB)   │
│  Terminal 3: rollout client                       │
│     ├─ ZED cameras (USB)                          │
│     ├─ local gripper read/write  ◄── important     │
│     └─ zerorpc ──► NUC :4242 ──► Polymetis ──► FR3 │
└───────────────────────────────────────────────────┘
```

### Policy inputs

| Input | Source in this lab |
|-------|-------------------|
| External camera (one of two) | ZED 2i — `--external-camera left` or `right` |
| Wrist camera | ZED-M on gripper |
| Joint positions (7) | NUC → Franka state |
| Gripper position (0–1) | **Workstation** Robotiq (`0`=open, `1`=closed) |
| Language command | Typed or spoken (Whisper) |

### Policy outputs (per step)

π₀.5-DROID returns action chunks of shape **`(15, 8)`**:

- **Dims 0–6:** joint velocities (scaled ±1)
- **Dim 7:** gripper **position** target (binarized at 0.5 → open or closed)

The client re-queries the policy every **8 steps** (`open_loop_horizon`), then executes at **15 Hz**.

> **Lab-specific:** Do not send gripper commands only through NUC zerorpc — the Robotiq USB cable is on the workstation. The rollout script (`openpi_pi05_rollout.py`) handles local gripper read/write automatically.

---

## One-time setup

### 1. Clone and install OpenPI

```bash
export PATH="$HOME/.local/bin:$PATH"

cd ~/Desktop
git clone --recurse-submodules https://github.com/Physical-Intelligence/openpi.git
cd openpi
GIT_LFS_SKIP_SMUDGE=1 uv sync
```

First policy start downloads the checkpoint (~6–7 GB) to `~/.cache/openpi/`.

The lab launcher script is already in the repo:

```bash
~/Desktop/openpi/scripts/serve_pi05_droid.sh
```

### 2. OpenPI client in `robot` conda env

The rollout script runs in **`conda activate robot`** (Python 3.7). Install the websocket client without strict numpy pins:

```bash
conda activate robot
cd ~/Desktop/openpi/packages/openpi-client
pip install -e . --no-deps
pip install websockets msgpack dm-tree tyro moviepy pandas tqdm
```

### 3. Voice input (optional)

```bash
# System mic library (sudo once per machine)
sudo apt install portaudio19-dev libportaudio2

# STT in openpi env
cd ~/Desktop/openpi
uv pip install faster-whisper sounddevice soundfile
```

List microphones:

```bash
cd ~/Desktop/openpi
uv run python ~/Desktop/DROID/scripts/demo/speech_command.py --list-devices
```

| Device | Typical use |
|--------|----------------|
| **10** (default, PulseAudio) | USB headset, built-in mic |
| **3** (ALC897 Analog) | 3.5 mm jack mic |
| 0–2, 5–8 (HDMI) | No input — do not use |

Test voice standalone:

```bash
cd ~/Desktop/openpi
uv run python ~/Desktop/DROID/scripts/demo/speech_command.py
# Press Enter → speak 5s → printed transcript
```

### 4. Lab camera IDs

Current serials in `droid/misc/parameters.py`:

| Role | Serial | Model |
|------|--------|-------|
| Wrist (`hand_camera_id`) | `10163006` | ZED-M |
| Left external (`varied_camera_1_id`) | `38845842` | ZED 2i |
| Right external (`varied_camera_2_id`) | `38924636` | ZED 2i |

Verify USB cameras:

```bash
conda activate robot
cd ~/Desktop/DROID
python scripts/setup/list_zed_cameras.py
```

Update `parameters.py` if serials differ on your machine.

### 5. NUC SSH access (workstation)

All NUC commands below are run **from the workstation** — you do not need a monitor on the NUC.

```bash
ssh nuc    # ~/.ssh/config → pci@192.168.1.7
```

First-time SSH setup (if `ssh nuc` fails): `ssh-copy-id pci@192.168.1.7`

NUC repo: `/home/pci/Desktop/Franka/droid` · conda env: `polymetis-local`

---

## NUC arm stack (SSH from workstation)

The NUC runs Polymetis + zerorpc. The workstation never runs libfranka/FCI directly.

| Service | Port | Process |
|---------|------|---------|
| Polymetis gRPC | `50051` | `launch_robot.py` → `franka_panda_client` |
| DROID zerorpc | `4242` | `python scripts/server/run_server.py` |

Gripper is **not** on the NUC — Robotiq USB stays on the workstation.

### One-time: sync gripper-optional `robot.py` (workstation → NUC)

If `launch_robot` hangs or times out on zerorpc, the NUC may need the patched file that skips local gripper:

```bash
scp /home/pci/Desktop/DROID/droid/franka/robot.py \
    nuc:/home/pci/Desktop/Franka/droid/droid/franka/robot.py
```

Then restart zerorpc ([step 3](#step-3--start-zerorpc-on-nuc-workstation-terminal-a) in [New session startup](#new-session-startup-copy-paste)).

> **Every new session:** use [New session startup (copy-paste)](#new-session-startup-copy-paste) steps 0–8 — do not skip NUC steps 2–3 after overnight shutdown or User Stop.

More detail: [NUC agent instructions](nuc-agent-instructions.md) · `.cursor/skills/control-arm-via-nuc/nuc-admin.md`

---

## Scene prep (before rollout)

- Simple tabletop pick-and-place works best.
- Point the external camera so **all task objects** are visible.
- Stand near E-stop; use **`--no-reset`** unless you want the arm to home to the default DROID pose.
- Check `robot_camera_views.png` after dry-run.

### What to expect during rollout

- ZED init can take **30–60 s** — use `PYTHONUNBUFFERED=1`.
- Dry run should show `Policy inference OK — action chunk shape (15, 8)`.
- Voice flow: `Press Enter to start recording...` → speak 5 s → confirm transcript.
- **Ctrl+C** stops early; `Do one more eval? (y/n)` for another command without restarting servers.

### Policy server manual start (if launcher missing)

```bash
export PATH="$HOME/.local/bin:$PATH"
cd ~/Desktop/openpi
export XLA_PYTHON_CLIENT_PREALLOCATE=false
export XLA_PYTHON_CLIENT_ALLOCATOR=platform
export XLA_PYTHON_CLIENT_MEM_FRACTION=0.85
uv run scripts/serve_policy.py policy:checkpoint \
  --policy.config=pi05_droid \
  --policy.dir=gs://openpi-assets/checkpoints/pi05_droid
```

Harmless log noise: ROCm / TPU warnings on RTX 4090.

---

## Command cheat sheet

| Flag | Default | Meaning |
|------|---------|---------|
| `--external-camera left` | `left` | Third-person ZED `38845842` |
| `--external-camera right` | — | Third-person ZED `38924636` |
| `--no-reset` | off | Skip homing arm to default pose at start |
| `--input-mode both` | `both` | `text`, `voice`, or `both` |
| `--voice-duration 5` | 5 | Seconds of audio to record |
| `--whisper-model base` | `base` | `tiny` (fast) / `base` / `small` (accurate) |
| `--input-device 3` | PulseAudio default | ALSA mic index from `--list-devices` |
| `--debug-gripper` | off | Log raw/binarized gripper each step |
| `--gripper-force 0.3` | 0.1 | Stronger close if grasp slips |
| `--gripper-threshold 0.5` | 0.5 | Policy gripper dim > threshold → close |
| `--dry-run` | off | Policy + cameras only, no robot motion |

---

## How to write good commands

**Good:**

- `pick up the red block`
- `put the cup on the plate`
- `move the bottle into the box`

**Avoid:**

- Long multi-step plans in one sentence
- Vague goals: `clean up`, `help me`
- Objects not visible in the camera view

The policy is a **generalist** trained on DROID (mostly Panda setups); this lab uses **FR3**. It works best on simple tabletop manipulation. Expect ~0.5–1 s latency per action chunk.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| GPU OOM loading model | JAX preallocates VRAM | `serve_pi05_droid.sh`; close Slack/Cursor; `XLA_PYTHON_CLIENT_MEM_FRACTION=0.75` |
| `address already in use :8000` | Policy server already running | Use existing server or stop old PID |
| `Connection refused :8000` | Policy server not running | Start Terminal 2 |
| `Robot context not valid` | Polymetis up, **client dead** | [NUC Polymetis recovery](#nuc-polymetis-recovery) |
| `launch_robot` fails / timeout | FCI off or zerorpc down | Desk → FCI; `arm_smoke_test.py` |
| Gripper never moves | No local gripper server | Terminal 1: `launch_gripper.sh` |
| Policy “doesn’t grasp” | Weak force or wrong observation | `--gripper-force 0.3`; `--debug-gripper` |
| `AssertionError` shape `(10,8)` | Old script | π₀.5 uses `(15,8)` — use current rollout script |
| Missing camera frames | Wrong serials / USB | `list_zed_cameras.py`; update `parameters.py` |
| ZED depth clamped to 100 mm | SDK limit | Harmless warning |
| Gym unmaintained warning | Old `gym` in robot env | Harmless for rollout |
| Voice `PortAudio not found` | Missing system lib | `sudo apt install portaudio19-dev libportaudio2` |
| Voice `UnicodeDecodeError` | Old rollout script | Pull latest (UTF-8 subprocess fix) |
| ROCm / TPU warnings | No AMD/TPU GPU | Ignore on RTX 4090 |
| Reset / SSH returns **no output**, exit **255** | `pkill -f launch_robot.py` in inline `ssh "..."` kills the remote shell | Use `scripts/setup/openpi_*.sh` (heredoc over SSH) |
| SSH step 2 returns **no output** | Old single-block `&&` chain; non-interactive `conda` | Use **scripts** for steps 2a + 2b (this doc) |
| `NO_50051` but client running | Stale/crashed Polymetis gRPC | Repeat **2a + 2b**; confirm Desk FCI |
| `ControlUpdate rpc failed` / `automaticErrorRecovery` in log | FCI off, safety trip, or stale client | **Step 0** (Desk FCI + clear faults + release EAD), then **2a + 2b** |
| `:4242` up, `:50051` down | zerorpc OK, Polymetis not connected | Full **2a + 2b**; `arm_smoke_test` will fail until fixed |
| `NO_CLIENT` after 2a | Started too soon | Wait full 15 s, run **2b** again |

---

## NUC Polymetis recovery

Use when rollout fails with **`Robot context not valid`**, or `arm_smoke_test.py` lacks **`launch_robot OK`**.  
Common causes: User Stop, safety trip, FCI off, or `franka_panda_client` crashed while `:50051` still listens.

Run **step 0a** (`openpi_session_reset.sh`), then re-run **steps 0–4** (especially **2a + 2b**) from the workstation.  
Most common fix: Desk FCI off, or Polymetis client crashed while port 50051 still looked “up”.

---

## Script reference

| Script | Repo | Purpose |
|--------|------|---------|
| `scripts/setup/openpi_session_reset.sh` | DROID | **Step 0a / 8** — kill all residual NUC + workstation services |
| `scripts/setup/openpi_kill_nuc.sh` | DROID | NUC only: Polymetis `:50051`, zerorpc `:4242` |
| `scripts/setup/openpi_kill_workstation.sh` | DROID | Workstation only: gripper `:50052`, policy `:8000`, rollout |
| `scripts/setup/openpi_nuc_status.sh` | DROID | **Step 1** — NUC ports / client / log |
| `scripts/setup/openpi_start_polymetis.sh` | DROID | **Step 2a** — start Polymetis |
| `scripts/setup/openpi_verify_polymetis.sh` | DROID | **Step 2b** — verify `Connected.` + `:50051` |
| `scripts/setup/openpi_start_zerorpc.sh` | DROID | **Step 3** — start zerorpc `:4242` |
| `scripts/serve_pi05_droid.sh` | **openpi** | Policy server launcher (JAX memory env vars) |
| `scripts/demo/openpi_pi05_rollout.py` | DROID | Rollout client: NUC arm + local gripper + voice |
| `scripts/demo/speech_command.py` | DROID | Mic → text via faster-whisper (**run in openpi env**) |
| `scripts/demo/arm_smoke_test.py` | DROID | NUC arm check before rollout |
| `scripts/setup/list_zed_cameras.py` | DROID | ZED serial numbers |

---

## Lab code in this repo

Files added or changed for OpenPI rollout in this lab (keep in sync with this doc):

| File | Change |
|------|--------|
| `scripts/setup/openpi_session_reset.sh` | Step 0a / step 8 — kill residual NUC + workstation services |
| `scripts/demo/openpi_pi05_rollout.py` | Main rollout; **local Robotiq** read/write; voice via `speech_command.py`; accepts action shape `(N, 8)` e.g. `(15, 8)` |
| `scripts/demo/speech_command.py` | Whisper STT; run with `cd ~/Desktop/openpi && uv run python ...` |
| `droid/robot_env.py` | `ServerInterface(..., launch=False)` + `launch_robot()`; warns instead of crash if NUC Polymetis down |

**OpenPI repo** (not in DROID git): `~/Desktop/openpi/scripts/serve_pi05_droid.sh` — created for RTX 4090 OOM fix.

**NUC repo** (not workstation): `/home/pci/Desktop/Franka/droid` — Polymetis + zerorpc; optional gripper patch in `droid/franka/robot.py`.

### Architecture rules (do not regress)

1. **Arm** → workstation `zerorpc` → NUC `:4242` → Polymetis → Franka FCI  
2. **Gripper** → workstation USB only (`launch_gripper.sh` `:50052`); rollout script commands gripper **locally**  
3. **Policy** → workstation GPU `:8000`; rollout sends images + `prompt` over websocket  
4. **Desk / FCI** → workstation browser only, before NUC `launch_robot.py`  
5. **NUC SSH** → use `scripts/setup/openpi_*.sh` (heredoc over `ssh nuc 'bash -s'`) — never inline `pkill -f launch_robot.py` in the ssh command string  

---

## Changelog

| Date | Doc / lab change |
|------|------------------|
| 2026-06-09 | Initial OpenPI π₀.5 rollout; `openpi_pi05_rollout.py`, local gripper, `serve_pi05_droid.sh` |
| 2026-06-09 | Voice input: `speech_command.py`, `--input-mode voice/both` |
| 2026-06-09 | Action chunk fix: π₀.5 returns `(15, 8)` not `(10, 8)` |
| 2026-06-09 | `robot_env.py`: `launch=False` for NUC; optional `launch_robot` warning |
| 2026-06-10 | **New session startup** copy-paste checklist (steps 0–8) |
| 2026-06-10 | NUC commands: all via `ssh nuc` + `bash -lc`; Polymetis split **2a start / 2b verify** (fixes silent SSH failures) |
| 2026-06-10 | Step 1 unhealthy pattern: `:4242` only + `ControlUpdate rpc failed` → Desk FCI then 2a/2b |
| 2026-06-10 | **Step 0a** cleanup scripts: `openpi_session_reset.sh`, `openpi_kill_nuc.sh`, `openpi_kill_workstation.sh` |
| 2026-06-10 | Fix silent SSH exit 255: NUC scripts use heredoc; added `openpi_nuc_status`, `openpi_start_polymetis`, `openpi_verify_polymetis`, `openpi_start_zerorpc` |
| 2026-06-10 | Scripts print `[openpi_*] starting` to stderr; `set +e`; workstation kill uses pgrep+kill (no self-pkill) |
| 2026-06-10 | All `openpi_*.sh` use `exec 1>&2` so status lines show in IDE terminals that swallow stdout |
| 2026-06-10 | `openpi_nuc_status.sh` prints CLEAN / UNHEALTHY summary; marks log as possibly stale |
| 2026-06-10 | `arm_smoke_test.py`, `openpi_pi05_rollout.py`: `sys.stdout = sys.stderr` for IDE terminal visibility |

---

## Related docs

- [Lab workstation quickstart](lab-workstation-quickstart.md)
- [NUC agent instructions](nuc-agent-instructions.md)
- [OpenPI DROID example](https://github.com/Physical-Intelligence/openpi/blob/main/examples/droid/README.md)
- `.cursor/skills/control-arm-via-nuc/SKILL.md`
- `improvement.md` — agent notes from lab sessions
