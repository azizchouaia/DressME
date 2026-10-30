#!/usr/bin/env bash
# Bake photo color, print, and fabric normals onto the registered garments.
set -euo pipefail
REMU_HOME="${REMU_HOME:-$HOME/remu}"
REPO="$REMU_HOME/ReMu"
export PATH="$REMU_HOME/env/bin:$PATH"
export LD_LIBRARY_PATH="/usr/lib/wsl/lib:$REMU_HOME/env/lib:${LD_LIBRARY_PATH:-}"
export HF_HOME="$REMU_HOME/hf"
cd "$REPO"
python scripts/refine/run_mesh.py \
  --config configs/remu.yaml \
  --subject 00127 \
  --reg-dir "$REPO/outputs/bmvc/00127/kaggle_reg" \
  --out-dir "$REPO/outputs/bmvc/00127/kaggle_refine" \
  --layers Inner Lower Outer \
  --profile
echo "BAKE_DONE"
find "$REPO/outputs/bmvc/00127/kaggle_refine" -type f \( -name '*.obj' -o -name '*.png' -o -name '*.mtl' \) -printf '%f %s\n'
