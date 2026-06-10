#!/usr/bin/env bash
# Step 2a — Start Polymetis on NUC (run from workstation). Then wait 15s and run openpi_verify_polymetis.sh.
set +e
exec 1>&2

echo "[openpi_start_polymetis] starting"
echo "=== Starting Polymetis on NUC ==="
ssh -o ConnectTimeout=10 nuc 'bash -s' <<'REMOTE'
set +e
source ~/miniconda3/etc/profile.d/conda.sh
conda activate polymetis-local
source /home/pci/Desktop/Franka/droid/scripts/nuc/env.sh
cd /home/pci/Desktop/Franka/droid

pkill -9 -f "run_server -s" 2>/dev/null
pkill -9 franka_panda_cl 2>/dev/null
pkill -9 -f launch_robot.py 2>/dev/null
sleep 2

nohup launch_robot.py robot_client=franka_hardware use_real_time=false > /tmp/polymetis_connect.log 2>&1 &
echo "Polymetis starting... wait 15s then run: bash scripts/setup/openpi_verify_polymetis.sh"
REMOTE
