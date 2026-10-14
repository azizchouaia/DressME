"""Check that M2 loads the pretrained OutfitTransformer correctly. Evaluation only, nothing is trained.

Uses the precomputed FashionCLIP test embeddings published with the weights and the Polyvore Outfits
(nondisjoint) test questions. If our loader is right we should land near the published numbers
(validation AUC 0.952, FITB 68.3 %).

Input : ml/data/polyvore/ot_test/{manifest.json, shard-*.pt}   (FlorindoDev/OutfitTransformer-weights)
        ml/data/polyvore/meta/nondisjoint_{compatibility,fill_in_the_blank,default}/test.json
Output: ml/models/m02/eval_metrics.json

    python ml/scripts/m02/eval_pretrained.py --n 2000
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
from modules.m02_recommendation.engine import artifacts  # noqa: E402
from modules.m02_recommendation.engine.outfit_transformer import OutfitTransformer  # noqa: E402

PV = ROOT / "ml/data/polyvore"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000, help="questions per task (random sample)")
    a = ap.parse_args()
    rng = random.Random(0)

    vec: dict[str, np.ndarray] = {}
    for f in sorted((PV / "ot_test").glob("shard-*.pt")):
        s = torch.load(f, weights_only=False)
        vec.update(zip(s["item_ids"], s["embeddings"].numpy(), strict=True))
    sets = {
        o["set_id"]: {str(i["index"]): i["item_id"] for i in o["items"]}
        for o in json.load(open(PV / "meta/nondisjoint_default/test.json"))
    }

    def resolve(ref):
        if "_" not in ref:
            return None
        s, idx = ref.rsplit("_", 1)
        iid = sets.get(s, {}).get(idx)
        return vec.get(iid) if iid else None

    ot = OutfitTransformer()
    t0 = time.time()

    comp = []
    for q in json.load(open(PV / "meta/nondisjoint_compatibility/test.json")):
        items = [v for v in map(resolve, q["items"]) if v is not None]
        if len(items) >= 2:
            comp.append((np.stack(items), int(q["label"])))
    comp = rng.sample(comp, min(a.n, len(comp)))
    p = ot.compatibility([c[0] for c in comp])
    labels = [c[1] for c in comp]
    auc = roc_auc_score(labels, p)
    acc = float(np.mean((p > 0.5) == np.array(labels)))

    fitb = []
    for q in json.load(open(PV / "meta/nondisjoint_fill_in_the_blank/test.json")):
        items = [resolve(r) for r in q["items"]]
        cands = [resolve(r) for r in q["candidates"]]
        if all(v is not None for v in items + cands):
            fitb.append((np.stack(items), np.stack(cands), q["label"]))
    fitb = rng.sample(fitb, min(a.n, len(fitb)))
    hit_cir = hit_cp = 0
    for k in range(0, len(fitb), 128):
        chunk = fitb[k : k + 128]
        qv = ot.query([c[0] for c in chunk])
        for (items, cands, label), q in zip(chunk, qv, strict=True):
            d = np.linalg.norm(ot.item_space(cands) - q, axis=1)
            hit_cir += int(np.argmin(d) == label)
            s = ot.compatibility([np.vstack([items, c[None]]) for c in cands])
            hit_cp += int(np.argmax(s) == label)

    metrics = {
        "what": "pretrained OutfitTransformer weights loaded by M2, Polyvore Outfits nondisjoint TEST",
        "compatibility": {
            "auc": round(float(auc), 4),
            "accuracy@0.5": round(acc, 4),
            "outfits": len(comp),
            "published_validation_auc": 0.9518,
            "chance_auc": 0.5,
        },
        "fill_in_the_blank": {
            "cir_accuracy": round(hit_cir / len(fitb), 4),
            "cp_accuracy": round(hit_cp / len(fitb), 4),
            "questions": len(fitb),
            "published_validation_cir_accuracy": 0.683,
            "chance": 0.25,
        },
        "seconds": round(time.time() - t0, 1),
    }
    print(json.dumps(metrics, indent=2))
    json.dump(metrics, open(artifacts.EVAL_METRICS, "w"), indent=2)


if __name__ == "__main__":
    main()
