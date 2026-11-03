#!/usr/bin/env bash
# Demo-only SiTH reconstruction at the coarse grid that fits this laptop GPU.
# The fine grid (512) crashes WSL, so this stays at 192.
set -euo pipefail

REMU_HOME="${REMU_HOME:-$HOME/remu}"
REPO="$REMU_HOME/ReMu"
ENV_PREFIX="$REMU_HOME/env"
SRC="$REPO/outputs/bmvc/00127/recon"
DEMO="$REPO/outputs/bmvc/00127/demo"

export PATH="$ENV_PREFIX/bin:$PATH"
export LD_LIBRARY_PATH="/usr/lib/wsl/lib:$ENV_PREFIX/lib:${LD_LIBRARY_PATH:-}"
export HF_HOME="$REMU_HOME/hf"

rm -rf "$DEMO"
mkdir -p "$DEMO/meshes"
ln -s "$SRC/images" "$DEMO/images"
ln -s "$SRC/back_images" "$DEMO/back_images"
ln -s "$SRC/smplx" "$DEMO/smplx"

echo "images: $(ls "$DEMO/images" | wc -l)"
echo "backs: $(ls "$DEMO/back_images" | wc -l)"
nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader

cd "$REPO/third_party/sith"
python reconstruct.py \
  --test_folder "$DEMO" \
  --config "$REPO/third_party/sith/recon/config.yaml" \
  --resume "$REPO/checkpoints/sith/recon_model.pth" \
  --grid_size 192

echo "demo meshes:"
ls -lh "$DEMO/meshes"
