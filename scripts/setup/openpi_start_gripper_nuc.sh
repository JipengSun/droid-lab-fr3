#!/usr/bin/env bash
# Start Robotiq gripper server on NUC (run from workstation).
# Gripper USB must be plugged into the NUC.
set +e
exec 1>&2

echo "[openpi_start_gripper_nuc] starting"
echo "=== Starting gripper server on NUC ==="
ssh -o ConnectTimeout=10 nuc 'bash -s' <<'REMOTE'
set +e
source ~/miniconda3/etc/profile.d/conda.sh
conda activate polymetis-local
cd /home/pci/Desktop/Franka/droid

pkill -f launch_gripper.py 2>/dev/null
pkill -f launch_gripper.sh 2>/dev/null
sleep 1

nohup bash droid/franka/launch_gripper.sh >> /tmp/droid_gripper.log 2>&1 &
sleep 6
echo "=== 50052 ==="
ss -tlnp | grep 50052 || echo NO_50052
echo "=== log tail ==="
tail -5 /tmp/droid_gripper.log 2>/dev/null || echo NO_LOG
REMOTE
