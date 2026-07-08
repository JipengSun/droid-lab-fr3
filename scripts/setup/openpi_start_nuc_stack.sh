#!/usr/bin/env bash
# Start full NUC robot stack for VR teleop (run from workstation after Desk FCI).
set +e
exec 1>&2

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

echo "[openpi_start_nuc_stack] Desk FCI must be active (nc -zv 192.168.1.11 1337)"
nc -zv -w 2 192.168.1.11 1337 2>&1 || echo "WARN: FCI port 1337 not open — activate FCI in Desk first"

bash "$ROOT/scripts/setup/openpi_start_gripper_nuc.sh" || exit 1
sleep 2
bash "$ROOT/scripts/setup/openpi_start_polymetis.sh" || exit 1
echo "Waiting 18s for Polymetis..."
sleep 18
bash "$ROOT/scripts/setup/openpi_verify_polymetis.sh" || exit 1
bash "$ROOT/scripts/setup/openpi_start_zerorpc.sh" || exit 1

echo ""
echo "=== Stack ready — verify from workstation ==="
echo "  nc -zv 192.168.1.7 4242"
echo "  python scripts/demo/arm_smoke_test.py"
echo "  python scripts/demo/vr_teleop_demo.py --show-cameras"
