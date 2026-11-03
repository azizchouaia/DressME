from pathlib import Path

text = Path("/mnt/c/Users/NADHIR/Desktop/Dressme/avatar_studio/web/garments/saved/auto_test/v17_inbox/data.log").read_text(encoding="utf-8", errors="replace")
lines = [line for line in text.replace("\r", "\n").splitlines() if line.strip() and "it/s" not in line and "MB/s" not in line and "%|" not in line]
print("\n".join(lines[-30:]))
