#!/usr/bin/env bash
set -u
export PATH="$HOME/remu/env/bin:$PATH"
echo "PY=$(which python)"
python - <<'PY'
import torch
print("torch", torch.__version__, "cuda", torch.cuda.is_available())
if torch.cuda.is_available():
    print("gpu", torch.cuda.get_device_name(0))
    print("arch", torch.cuda.get_device_capability(0))
PY
python - <<'PY'
try:
    import kaolin
    print("kaolin", getattr(kaolin, "__version__", "ok"))
except Exception as e:
    print("kaolin FAIL", type(e).__name__, e)
try:
    import nvdiffrast
    print("nvdiffrast ok")
except Exception as e:
    print("nvdiffrast FAIL", type(e).__name__, e)
PY
echo "--- checkpoints ---"
find "$HOME/remu/ReMu/checkpoints" -maxdepth 3 \( -type d -o -name 'recon_model.pth' -o -name '*.pth' -o -name '*.safetensors' \) | head -60
echo "--- sith reconstruct ---"
ls -l "$HOME/remu/ReMu/third_party/sith/recon/reconstruct.py" 2>/dev/null || echo "no reconstruct.py"
