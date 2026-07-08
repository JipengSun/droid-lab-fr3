#!/usr/bin/env bash
# Stop half-started Polymetis + zerorpc on the NUC (run from workstation).
# Uses ssh heredoc so pkill patterns do not match the ssh command line itself.
set +e
exec 1>&2

echo "[openpi_kill_nuc] starting"

echo "=== Killing NUC robot stack (Polymetis + zerorpc) ==="
ssh -o ConnectTimeout=10 -o BatchMode=yes nuc 'bash -s' <<'REMOTE'
set +e
echo "=== remote: killing processes ==="
pkill -f "python scripts/server/run_server.py" 2>/dev/null
pkill -9 franka_panda_cl 2>/dev/null
pkill -9 -f launch_robot.py 2>/dev/null
pkill -9 -f "run_server -s" 2>/dev/null
pkill -9 run_server 2>/dev/null
pkill -f launch_gripper.py 2>/dev/null
pkill -f launch_gripper.sh 2>/dev/null
sleep 2
echo "=== NUC ports (expect CLEAN) ==="
ss -tlnp | grep -E "4242|50051|50052" || echo CLEAN
echo "=== NUC client (expect NO_CLIENT) ==="
pgrep -a franka_panda_cl || echo NO_CLIENT
echo "=== NUC servers (expect NO_SERVERS) ==="
pgrep -af "run_server.py|launch_robot" | head -3 || echo NO_SERVERS
REMOTE
rc=$?
echo "[openpi_kill_nuc] ssh exit=$rc"
exit $rc
