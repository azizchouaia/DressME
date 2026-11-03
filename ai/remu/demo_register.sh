#!/usr/bin/env bash
# Register the demo SiTH meshes and remove penetration so they can sit on the body.
set -euo pipefail

REMU_HOME="${REMU_HOME:-$HOME/remu}"
REPO="$REMU_HOME/ReMu"
ENV_PREFIX="$REMU_HOME/env"

export PATH="$ENV_PREFIX/bin:$PATH"
export LD_LIBRARY_PATH="/usr/lib/wsl/lib:$ENV_PREFIX/lib:${LD_LIBRARY_PATH:-}"
export HF_HOME="$REMU_HOME/hf"

cd "$REPO"
python scripts/register/run_4ddress_registration.py \
  --recon sith \
  --backend knn_lbs \
  --subject 00127 \
  --gender male \
  --recon-dir "$REPO/outputs/bmvc/00127/demo/meshes" \
  --params-dir "$REPO/outputs/bmvc/00127/data/smplx_params" \
  --layers Outer,Inner,Lower \
  --body-model-root "$REPO/body_models" \
  --out-dir "$REPO/outputs/bmvc/00127/demo_reg" \
  --run-penetration \
  --prompts-json "$REPO/examples/prompts.json"

echo "registration meshes:"
find "$REPO/outputs/bmvc/00127/demo_reg/G_displaced" -type f -name '*.obj' -printf '%f %s\n'
