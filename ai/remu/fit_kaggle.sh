#!/usr/bin/env bash
set -euo pipefail
REMU_HOME="${REMU_HOME:-$HOME/remu}"
export PATH="$REMU_HOME/env/bin:$PATH"
export LD_LIBRARY_PATH="/usr/lib/wsl/lib:$REMU_HOME/env/lib:${LD_LIBRARY_PATH:-}"
python /mnt/c/Users/NADHIR/Desktop/Dressme/ai/remu/fit_demo.py
