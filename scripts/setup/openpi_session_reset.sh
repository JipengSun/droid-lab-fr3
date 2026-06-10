#!/usr/bin/env bash
# Full clean slate before a new OpenPI rollout session (workstation + NUC).
set +e
exec 1>&2

echo "[openpi_session_reset] starting"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FAILED=0

bash "$ROOT/scripts/setup/openpi_kill_workstation.sh" || FAILED=1
echo ""
if bash "$ROOT/scripts/setup/openpi_kill_nuc.sh"; then
  :
else
  echo ""
  echo "ERROR: NUC cleanup failed. Run: ssh -o ConnectTimeout=5 nuc echo ok"
  FAILED=1
fi
echo ""
if [[ "$FAILED" -eq 0 ]]; then
  echo "Clean slate ready -> Step 0 (Desk FCI) -> Step 1 (openpi_nuc_status.sh) -> Steps 2a-7."
else
  echo "Cleanup incomplete -- fix errors above before continuing."
  exit 1
fi
