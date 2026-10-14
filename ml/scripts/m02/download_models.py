"""Download the pretrained models M2 uses (nothing is trained in this project).

    python ml/scripts/m02/download_models.py            # models only (~400 MB + FashionCLIP ~600 MB cache)
    python ml/scripts/m02/download_models.py --eval     # + Polyvore test data for eval_pretrained.py

* OutfitTransformer CP + CIR checkpoints -> ml/models/m02/outfit_transformer/
  (huggingface.co/FlorindoDev/OutfitTransformer-weights, Polyvore Outfits nondisjoint)
* FashionCLIP patrickjohncyh/fashion-clip -> Hugging Face cache (~/.cache/huggingface)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[3]
HF = "https://huggingface.co"
OT = f"{HF}/FlorindoDev/OutfitTransformer-weights/resolve/main"
PV = f"{HF}/datasets/owj0421/polyvore-outfits/resolve/main"


def fetch(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"ok   {dest.relative_to(ROOT)}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"get  {dest.relative_to(ROOT)}", flush=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with httpx.stream("GET", url, follow_redirects=True, timeout=120) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)
    tmp.replace(dest)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", action="store_true", help="also fetch the Polyvore test data")
    a = ap.parse_args()

    out = ROOT / "ml/models/m02/outfit_transformer"
    for kind in ("cp", "cir"):
        run = f"{OT}/checkpoints/nondisjoint/{kind}_precomputed-flashionclip"
        fetch(f"{run}/best.pt", out / f"{kind}_best.pt")
        fetch(f"{run}/config.json", out / f"{kind}_config.json")

    from transformers import CLIPModel, CLIPProcessor

    CLIPModel.from_pretrained("patrickjohncyh/fashion-clip")
    CLIPProcessor.from_pretrained("patrickjohncyh/fashion-clip")
    print("ok   patrickjohncyh/fashion-clip (HF cache)")

    if a.eval:
        data = ROOT / "ml/data/polyvore"
        emb = f"{OT}/precomputed_embeddings/nondisjoint/fashionCLIP/test"
        fetch(f"{emb}/manifest.json", data / "ot_test/manifest.json")
        for i in range(5):
            fetch(f"{emb}/shard-{i:05d}.pt", data / f"ot_test/shard-{i:05d}.pt")
        for split in ("nondisjoint_compatibility", "nondisjoint_fill_in_the_blank", "nondisjoint_default"):
            fetch(f"{PV}/{split}/test.json", data / f"meta/{split}/test.json")


if __name__ == "__main__":
    main()
