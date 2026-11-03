#!/bin/bash
grep -n "single_image\|sd3\|inpaint\|pretrained" /home/nadhir/remu/ReMu/src/data/base.py | head -n 40
echo ==== MODEL ====
grep -n "sd3\|from_pretrained\|medium\|inpaint" /home/nadhir/remu/ReMu/src/data/inpainting/model.py | head -n 40
echo ==== INIT ====
sed -n '1,80p' /home/nadhir/remu/ReMu/src/data/__init__.py
