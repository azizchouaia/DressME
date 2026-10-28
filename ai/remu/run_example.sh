#!/usr/bin/env bash
# Run the ReMu BMVC preset on the bundled 4D-Dress example and log GPU memory.
#
#   wsl -d Ubuntu -- bash /mnt/c/Users/NADHIR/Desktop/Dressme/ai/remu/run_example.sh [steps]
#
# steps defaults to "data,reconstruction" because later stages need the SMPL-X models.
set -euo pipefail

REMU_HOME="${REMU_HOME:-$HOME/remu}"
ENV_PREFIX="$REMU_HOME/env"
STEPS="${1:-data,reconstruction}"

export PATH="$ENV_PREFIX/bin:$PATH"
export CUDA_HOME="$ENV_PREFIX"
export CPATH="$ENV_PREFIX/targets/x86_64-linux/include:${CPATH:-}"
export LIBRARY_PATH="$ENV_PREFIX/targets/x86_64-linux/lib:$ENV_PREFIX/lib:${LIBRARY_PATH:-}"
export LD_LIBRARY_PATH="/usr/lib/wsl/lib:$ENV_PREFIX/lib:${LD_LIBRARY_PATH:-}"
export TORCH_CUDA_ARCH_LIST="12.0"
export HF_HOME="$REMU_HOME/hf"
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"

cd "$REMU_HOME/ReMu"
log_dir="$REMU_HOME/logs"
mkdir -p "$log_dir"
gpu_log="$log_dir/gpu-$(date +%H%M%S).csv"

nvidia-smi --query-gpu=timestamp,memory.used,utilization.gpu --format=csv,noheader -l 5 > "$gpu_log" &
gpu_pid=$!
trap 'kill $gpu_pid 2>/dev/null || true' EXIT

start=$(date +%s)
python scripts/run.py --preset bmvc --subject 00127 --gender male \
  --dataset-root examples/4d_dress_00127 --steps "$STEPS"
status=$?
end=$(date +%s)

echo
echo "steps: $STEPS"
echo "elapsed: $(( (end - start) / 60 )) min $(( (end - start) % 60 )) s"
echo "peak GPU memory (MiB): $(awk -F', ' '{gsub(/ MiB/,"",$2); if ($2>m) m=$2} END {print m}' "$gpu_log")"
echo "outputs:"
find "outputs/bmvc/00127" -maxdepth 2 -type f \( -name '*.obj' -o -name '*.png' \) 2>/dev/null | sort | head -40
exit $status
