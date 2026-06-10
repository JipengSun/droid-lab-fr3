#!/usr/bin/env bash
# Step 3 — Start zerorpc on NUC (run from workstation).
set +e
exec 1>&2

echo "[openpi_start_zerorpc] starting"
echo "=== Starting zerorpc on NUC ==="
ssh -o ConnectTimeout=10 nuc 'bash -s' <<'REMOTE'
set +e
pkill -f "python scripts/server/run_server.py" 2>/dev/null
sleep 2
source ~/miniconda3/etc/profile.d/conda.sh
conda activate polymetis-local
cd /home/pci/Desktop/Franka/droid
nohup python scripts/server/run_server.py >> /tmp/droid_zerorpc.log 2>&1 &
sleep 4
echo "=== 4242 ==="
ss -tlnp | grep 4242 || echo NO_4242
REMOTE
