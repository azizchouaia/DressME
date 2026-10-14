"""Accuracy of the verdict against labelled candidates.

Mock mode: demo candidates (usr_demo) + synthetic candidates (ml/data/bo5/synthetic, labels from
stylist rules + noise -> a sanity check, NOT a real result).
Real mode: ml/data/bo5/candidates/labels.csv (image,user_id,price_tnd,label) labelled by humans.
"""

import asyncio
import csv
from pathlib import Path

from modules.m06_smartbuy.agent import HERE, SmartBuyAgent


def rows(agent):
    if agent.config["use_mocks"]:
        for c in agent.clients.candidates.values():
            yield c["id"], c.get("user_id", "usr_demo"), c.get("price_tnd", 80.0), c["expected"]
    else:
        p = (HERE.parent.parent / agent.config["data_dir"] / "candidates" / "labels.csv").resolve()
        for r in csv.DictReader(p.open(encoding="utf-8")):
            yield r["image"], r["user_id"], float(r["price_tnd"] or 0) or None, r["label"]


def main(verbose=False):
    agent, ok, n, conf = SmartBuyAgent(), 0, 0, {}
    for img, user, price, lab in rows(agent):
        v = asyncio.run(agent({"user_id": user, "probe_image": img, "price_tnd": price}))["verdict"]
        n += 1
        ok += v == lab
        conf[(lab, v)] = conf.get((lab, v), 0) + 1
        if verbose or v != lab:
            print(f"{img:18} {user:10} expected {lab:5} got {v}")
    print(f"\naccuracy {ok}/{n} = {ok / max(n, 1):.0%}")
    print("            got:  buy  think  skip")
    for e in ("buy", "think", "skip"):
        print(f"expected {e:5} " + "".join(f"{conf.get((e, g), 0):6}" for g in ("buy", "think", "skip")))


if __name__ == "__main__":
    import sys
    main("-v" in sys.argv)
