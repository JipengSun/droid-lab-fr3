#!/usr/bin/env bash
# Stop half-started gripper, policy server, and rollout processes on the workstation.
set +e
exec 1>&2

echo "[openpi_kill_workstation] starting"

echo "=== Killing workstation OpenPI / gripper services ==="

# Use pgrep+kill (not pkill -f) so patterns in this script are not self-matched.
for pattern in launch_gripper.py launch_gripper.sh serve_policy.py serve_pi05_droid \
  openpi_pi05_rollout.py speech_command.py robotiq_gripper; do
  while read -r pid; do
    [[ -z "$pid" || "$pid" == "$$" ]] && continue
    echo "  kill $pattern: $pid"
    kill -9 "$pid" 2>/dev/null
  done < <(pgrep -f "$pattern" 2>/dev/null || true)
done

if command -v fuser >/dev/null 2>&1; then
  fuser -k 8000/tcp 2>/dev/null
  fuser -k 50052/tcp 2>/dev/null
fi

sleep 1
echo "=== Workstation ports (expect CLEAN) ==="
ss -tlnp 2>/dev/null | grep -E "50052|8000" || echo CLEAN
echo "=== Workstation processes (expect NO_PROCESSES) ==="
procs=$(pgrep -af "launch_gripper|serve_policy|openpi_pi05_rollout|speech_command" 2>/dev/null | head -5)
if [[ -z "$procs" ]]; then echo NO_PROCESSES; else echo "$procs"; fi

echo "[openpi_kill_workstation] done"
