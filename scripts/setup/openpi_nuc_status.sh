#!/usr/bin/env bash
# Step 1 — NUC status check (run from workstation).
set +e
exec 1>&2

echo "[openpi_nuc_status] starting"

echo "=== ping NUC ==="
ping -c 2 -W 2 192.168.1.7
ping_rc=$?
if [[ "$ping_rc" -ne 0 ]]; then
  echo "WARN: NUC ping failed (exit $ping_rc). Continuing SSH check..."
fi

ssh -o ConnectTimeout=10 -o BatchMode=yes nuc 'bash -s' <<'REMOTE'
ports=$(ss -tlnp | grep -E "4242|50051|50052" || true)
client=$(pgrep -a franka_panda_cl || true)
zerorpc=$(pgrep -af run_server.py | head -2 || true)
gripper=$(pgrep -af launch_gripper | head -2 || true)
log_tail=$(tail -3 /tmp/polymetis_connect.log 2>/dev/null || true)

echo "=== ports ==="
[[ -n "$ports" ]] && echo "$ports" || echo "(none — expected after reset)"
echo "=== client ==="
[[ -n "$client" ]] && echo "$client" || echo NO_CLIENT
echo "=== zerorpc ==="
[[ -n "$zerorpc" ]] && echo "$zerorpc" || echo "(none — expected after reset)"
echo "=== gripper ==="
[[ -n "$gripper" ]] && echo "$gripper" || echo "(none)"
echo "=== log (may be stale) ==="
[[ -n "$log_tail" ]] && echo "$log_tail" || echo NO_LOG

echo "=== summary ==="
if [[ -z "$ports" && -z "$client" && -z "$zerorpc" ]]; then
  echo "CLEAN — safe to start: openpi_start_gripper_nuc.sh -> openpi_start_polymetis.sh -> verify -> openpi_start_zerorpc.sh"
elif echo "$ports" | grep -q 50052 && echo "$ports" | grep -q 50051 && echo "$log_tail" | grep -q "Connected\."; then
  echo "READY — gripper :50052 + Polymetis Connected. (start zerorpc if :4242 missing)"
elif echo "$ports" | grep -q 50051 && echo "$log_tail" | grep -q "Connected\."; then
  echo "POLYMETIS_OK — :50051 up and Connected. in log"
elif echo "$ports" | grep -q 4242; then
  echo "ZERORPC_UP — :4242 listening (check Polymetis if :50051 missing)"
else
  echo "UNHEALTHY — run openpi_session_reset.sh, Desk FCI, then openpi_start_polymetis.sh"
fi
REMOTE
echo "[openpi_nuc_status] ssh exit=$?"
