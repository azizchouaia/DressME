#!/usr/bin/env bash
# One photo -> invented inner layers, a back view, then SiTH or UP2You.
set -u
REMU_HOME="${REMU_HOME:-$HOME/remu}"
REPO="$REMU_HOME/ReMu"
INBOX="/mnt/c/Users/NADHIR/Desktop/Dressme/avatar_studio/web/garments/saved/one_photo"
STATUS="$INBOX/status.txt"
BUILDER="$(cat "$INBOX/builder.txt" 2>/dev/null || echo sith)"
DATA="$INBOX/dataset"
WORK="$INBOX/work"
export PATH="$REMU_HOME/env/bin:$PATH"
export LD_LIBRARY_PATH="/usr/lib/wsl/lib:$REMU_HOME/env/lib:${LD_LIBRARY_PATH:-}"
export HF_HOME="$REMU_HOME/hf"

mkdir -p "$DATA/input_img" "$DATA/smplx_params" "$WORK"
cp -f "$INBOX/outer.jpg" "$DATA/input_img/00127_Outer.jpg"
# Reuse the example body parameters so the new layers share this avatar's pose.
cp -a "$REPO/examples/4d_dress_00127/smplx_params/." "$DATA/smplx_params/" 2>/dev/null || true
cp -f "$REPO/examples/prompts.json" "$DATA/prompts.json" 2>/dev/null || true

cd "$REPO"
echo "Inventing the shirt and shorts from the outer photo, and a back view." > "$STATUS"
python scripts/data/run_data.py \
  --config configs/remu.yaml \
  --backend single_image \
  --dataset-root "$DATA" \
  --out-dir "$WORK/data" \
  --subjects 00127 \
  --materialize \
  --hallucinate-back \
  --sith-repo third_party/sith \
  --diffusion-model "$REPO/checkpoints/sith/diffusion" \
  --diffusion-resolution 512 \
  > "$INBOX/data.log" 2>&1
code=$?
if [ "$code" -ne 0 ]; then
  echo "The layer step stopped. See one_photo/data.log. Stable Diffusion 3 has to be accepted on Hugging Face before a single photo can invent the inner layers." > "$STATUS"
  exit "$code"
fi

echo "Layers are ready. Building the meshes with ${BUILDER}." > "$STATUS"
if [ "$BUILDER" = "up2you" ]; then
  python scripts/recon/run_up2you.py \
    --image-dir "$WORK/data" \
    --out-dir "$WORK/recon" \
    --repo third_party/up2you \
    --weights-dir "$REPO/checkpoints/up2you/pretrained_models" \
    --human-models "$REPO/checkpoints/up2you/human_models" \
    --base-model "$REPO/checkpoints/up2you/sd21" \
    --per-layer --subject 00127 \
    > "$INBOX/recon.log" 2>&1
else
  echo "SiTH still needs the prepared images, back images, and body mesh copied into a test folder before reconstruct.py. The back view and layers are in $WORK/data." > "$STATUS"
  exit 0
fi
code=$?
if [ "$code" -ne 0 ]; then
  echo "UP2You stopped. See one_photo/recon.log. Its weights live in checkpoints/up2you." > "$STATUS"
  exit "$code"
fi
echo "UP2You meshes are in $WORK/recon." > "$STATUS"
