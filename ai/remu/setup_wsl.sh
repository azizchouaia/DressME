#!/usr/bin/env bash
# Install ReMu (eth-ait/ReMu, BMVC preset) inside WSL Ubuntu without sudo.
#
# Upstream pins torch 2.5.1 + CUDA 12.1, which has no kernels for RTX 50-series
# (sm_120). This uses torch 2.8.0 + CUDA 12.8 and the matching kaolin / torch_scatter
# wheels instead. nvcc comes from conda-forge so nvdiffrast can JIT-compile.
#
#   wsl -d Ubuntu -- bash /mnt/c/Users/NADHIR/Desktop/Dressme/ai/remu/setup_wsl.sh
set -euo pipefail

REMU_HOME="${REMU_HOME:-$HOME/remu}"
ENV_PREFIX="$REMU_HOME/env"
REPO="$REMU_HOME/ReMu"
MAMBA="$HOME/.local/bin/micromamba"
export MAMBA_ROOT_PREFIX="$REMU_HOME/mamba"
export HF_HOME="$REMU_HOME/hf"
export PIP_NO_CACHE_DIR=1

step() { echo; echo "==> $*"; }

mkdir -p "$REMU_HOME" "$HOME/.local/bin"

if [ ! -x "$MAMBA" ]; then
  step "Installing micromamba"
  curl -L --fail -o "$MAMBA" \
    https://github.com/mamba-org/micromamba-releases/releases/latest/download/micromamba-linux-64
  chmod +x "$MAMBA"
  "$MAMBA" --version
fi

if [ ! -x "$ENV_PREFIX/bin/python" ]; then
  step "Creating Python 3.12 + CUDA 12.8 toolchain env"
  "$MAMBA" create -y -p "$ENV_PREFIX" -c conda-forge \
    python=3.12 cuda-nvcc=12.8 cuda-cudart-dev=12.8 cuda-cccl=12.8 \
    cuda-libraries-dev=12.8 cuda-version=12.8 gxx_linux-64=13 gcc_linux-64=13 \
    libgl libegl libglu ffmpeg git
fi

export PATH="$ENV_PREFIX/bin:$PATH"
export CUDA_HOME="$ENV_PREFIX"
export CPATH="$ENV_PREFIX/targets/x86_64-linux/include:${CPATH:-}"
export LIBRARY_PATH="$ENV_PREFIX/targets/x86_64-linux/lib:$ENV_PREFIX/lib:${LIBRARY_PATH:-}"
export LD_LIBRARY_PATH="/usr/lib/wsl/lib:$ENV_PREFIX/lib:${LD_LIBRARY_PATH:-}"
export TORCH_CUDA_ARCH_LIST="12.0"
PY="$ENV_PREFIX/bin/python"

if [ ! -d "$REPO/.git" ]; then
  step "Cloning ReMu"
  git clone --depth 1 https://github.com/eth-ait/ReMu.git "$REPO"
fi
cd "$REPO"

if ! "$PY" -c "import torch, sys; sys.exit(torch.__version__ != '2.8.0+cu128')" 2>/dev/null; then
  step "Installing torch 2.8.0 (CUDA 12.8)"
  "$PY" -m pip install --upgrade pip wheel setuptools
  "$PY" -m pip install torch==2.8.0 torchvision==0.23.0 --index-url https://download.pytorch.org/whl/cu128
fi

step "Installing ReMu requirements (rebased on torch 2.8.0 / cu128 wheels)"
sed -e 's#torch-2.5.1_cu121#torch-2.8.0_cu128#' \
    -e 's#torch-2.5.1+cu121#torch-2.8.0+cu128#' \
    -e 's#^sympy==1.13.1#sympy>=1.13.3#' \
    requirements.txt > "$REMU_HOME/requirements-cu128.txt"
"$PY" -m pip install -r "$REMU_HOME/requirements-cu128.txt" \
  torch==2.8.0 torchvision==0.23.0 --extra-index-url https://download.pytorch.org/whl/cu128

step "Building nvdiffrast"
"$PY" -m pip install --no-build-isolation git+https://github.com/NVlabs/nvdiffrast.git

step "Installing segmentation packages without dependency resolution"
"$PY" -m pip install --no-deps supervision==0.25.1
SAM2_BUILD_CUDA=0 "$PY" -m pip install --no-deps git+https://github.com/facebookresearch/sam2.git
"$PY" -m pip install --no-deps git+https://github.com/luca-medeiros/lang-segment-anything.git

step "Fetching example inputs and the SiTH checkpoint"
[ -f configs/paths.local.yaml ] || cp configs/paths.example.yaml configs/paths.local.yaml
[ -d examples/4d_dress_00127 ] || "$PY" scripts/download_data.py --subset examples
mkdir -p checkpoints/sith body_models/smplx
[ -s checkpoints/sith/recon_model.pth ] || \
  curl -L --fail -o checkpoints/sith/recon_model.pth https://files.ait.ethz.ch/projects/SiTH/recon_model.pth

step "Checking the GPU stack"
"$PY" - <<'PY'
import torch, kaolin, torch_scatter, nvdiffrast.torch as dr
print("torch", torch.__version__, "cuda", torch.version.cuda, "available", torch.cuda.is_available())
print("device", torch.cuda.get_device_name(0), "capability", torch.cuda.get_device_capability(0))
x = torch.randn(1024, 1024, device="cuda")
print("matmul ok", float((x @ x).sum()) == float((x @ x).sum()))
print("kaolin", kaolin.__version__)
ctx = dr.RasterizeCudaContext()
print("nvdiffrast cuda rasterizer ok")
PY

missing=0
for g in MALE FEMALE NEUTRAL; do
  [ -f "body_models/smplx/SMPLX_${g}.npz" ] || { echo "missing body_models/smplx/SMPLX_${g}.npz"; missing=1; }
done
if [ "$missing" = 1 ]; then
  echo
  echo "SMPL-X is licensed per user. Register at https://smpl-x.is.tue.mpg.de, download"
  echo "the SMPL-X .npz models, and copy SMPLX_MALE/FEMALE/NEUTRAL.npz into:"
  echo "  $REPO/body_models/smplx/"
fi
echo
echo "ReMu setup finished."
