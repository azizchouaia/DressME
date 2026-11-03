#!/usr/bin/env bash
# Fit the Kaggle shoe shell onto the same body as the shirt.
set -euo pipefail
REMU_HOME="${REMU_HOME:-$HOME/remu}"
REPO="$REMU_HOME/ReMu"
export PATH="$REMU_HOME/env/bin:$PATH"
export LD_LIBRARY_PATH="/usr/lib/wsl/lib:$REMU_HOME/env/lib:${LD_LIBRARY_PATH:-}"
export HF_HOME="$REMU_HOME/hf"
cd "$REPO"
python scripts/register/run_4ddress_registration.py \
  --recon sith \
  --backend knn_lbs \
  --subject 00127 \
  --gender male \
  --recon-dir /mnt/c/Users/NADHIR/Desktop/Dressme/avatar_studio/web/garments/saved/kaggle/meshes_384 \
  --params-dir "$REPO/outputs/bmvc/00127/data/smplx_params" \
  --layers Shoes \
  --body-model-root "$REPO/body_models" \
  --out-dir "$REPO/outputs/bmvc/00127/kaggle_reg_shoes" \
  --run-penetration \
  --prompts-json "$REPO/examples/prompts.json"
echo "SHOE_REG_DONE"
