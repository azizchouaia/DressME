#!/usr/bin/env bash
# Same sequence as from_photo.sh, pointed at the yellow-shirt photo.
set -u
REMU_HOME=/home/nadhir/remu
REPO="$REMU_HOME/ReMu"
INBOX="/mnt/c/Users/NADHIR/Desktop/Dressme/avatar_studio/web/garments/saved/auto_test/v17_inbox"
STATUS="$INBOX/status.txt"
DATA="$INBOX/dataset"
WORK="$INBOX/work"
export PATH="$REMU_HOME/env/bin:$PATH"
export LD_LIBRARY_PATH="/usr/lib/wsl/lib:$REMU_HOME/env/lib:${LD_LIBRARY_PATH:-}"
export HF_HOME="$REMU_HOME/hf"
export CUDA_VISIBLE_DEVICES=0
export PYTHONUNBUFFERED=1

mkdir -p "$DATA/input_img" "$DATA/smplx_params" "$WORK"
cp -f "$INBOX/outer.jpg" "$DATA/input_img/00127_Outer.jpg"
python - <<'PY'
from PIL import Image
from pathlib import Path
src = Path("/mnt/c/Users/NADHIR/Desktop/Dressme/avatar_studio/web/garments/saved/auto_test/v17_inbox/dataset/input_img/00127_Outer.jpg")
image = Image.open(src).convert("RGB")
side = max(image.size)
framed = Image.new("RGB", (side, side), (146, 112, 92))
framed.paste(image, ((side - image.width) // 2, (side - image.height) // 2))
dest = src.with_suffix(".png")
framed.save(dest)
print("outer png", dest, framed.size)
PY
cp -a "$REPO/examples/4d_dress_00127/smplx_params/." "$DATA/smplx_params/" 2>/dev/null || true
cp -f "$INBOX/prompts.json" "$DATA/prompts.json"

cd "$REPO"
echo "Inventing the shirt and pants layers from the photo, and a back view." > "$STATUS"
python scripts/data/run_data.py \
  --config /mnt/c/Users/NADHIR/Desktop/Dressme/avatar_studio/web/garments/saved/auto_test/v17_inbox/remu_fast.yaml \
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
  echo "The layer step stopped. See v17_inbox/data.log." > "$STATUS"
  exit "$code"
fi
echo "Layers are ready." > "$STATUS"
