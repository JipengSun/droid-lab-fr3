#!/usr/bin/env bash
# Step 2b — Verify Polymetis on NUC (run from workstation, ~15s after openpi_start_polymetis.sh).
set +e
exec 1>&2

echo "[openpi_verify_polymetis] starting"
ssh -o ConnectTimeout=10 -o BatchMode=yes nuc 'bash -s' <<'REMOTE'
echo "=== log ==="
tail -8 /tmp/polymetis_connect.log 2>/dev/null || echo NO_LOG
echo "=== client ==="
pgrep -a franka_panda_cl || echo NO_CLIENT
echo "=== 50051 ==="
ss -tlnp | grep 50051 || echo NO_50051
REMOTE
