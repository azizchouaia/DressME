#!/bin/bash
export PATH="$HOME/remu/env/bin:$PATH"
export HF_HOME="$HOME/remu/hf"
if [ -f "$HOME/.cache/huggingface/token" ] || [ -f "$HF_HOME/token" ]; then
  echo TOKEN_FILE_PRESENT
else
  echo TOKEN_FILE_MISSING
fi
huggingface-cli whoami
