#!/usr/bin/env bash
set -euo pipefail
REMU_HOME="${REMU_HOME:-$HOME/remu}"
REPO="$REMU_HOME/ReMu"
REG="$REPO/outputs/bmvc/00127/kaggle_reg_shoes"
export PATH="$REMU_HOME/env/bin:$PATH"
export LD_LIBRARY_PATH="/usr/lib/wsl/lib:$REMU_HOME/env/lib:${LD_LIBRARY_PATH:-}"
export HF_HOME="$REMU_HOME/hf"
cp -f "$REG/centered_meshes/00127-Shoes.obj" "$REG/M_displaced/00127_Shoes.obj"
cd "$REPO"
python scripts/refine/run_mesh.py \
  --config configs/remu.yaml \
  --subject 00127 \
  --reg-dir "$REG" \
  --out-dir "$REPO/outputs/bmvc/00127/kaggle_refine" \
  --layers Shoes \
  --profile
echo "SHOE_BAKE_DONE"
find "$REPO/outputs/bmvc/00127/kaggle_refine" -maxdepth 1 -name '*Shoes*' -printf '%s %f\n'
