"""Simulation (from dressme_bandit.py): does the bandit learn a fake user's hidden rules?

Sarah: classic at work, bohemian at the weekend, dislikes warm clothes when hot, likes them when cold.
Each day: ~20 random candidate outfits, the bandit shows one, Sarah reacts; a random pick is the baseline.

    cd backend && python -m modules.m05_style_profile.scripts.simulate [--days 300] [--seed 0]
"""

import argparse

import numpy as np

from modules.m05_style_profile.bandit import LinearTS
from modules.m05_style_profile.config import get_config, load_styles
from modules.m05_style_profile.features import Layout


def random_outfit(layout: Layout, rng: np.random.Generator) -> np.ndarray:
    mix = rng.dirichlet(np.ones(layout.S) * 0.3)  # outfit dominated by 1-2 styles
    return layout.outfit_vector(mix, rng.random(), rng.random(), rng.random(), rng.uniform(-0.2, 0.8))


def fake_user_reward(layout: Layout, info, out: np.ndarray, rng: np.random.Generator) -> float:
    temp, _rain, weekend, occ = info
    s = dict(zip(layout.styles, out[: layout.S], strict=True))
    warmth = out[layout.S + 1]
    p = 0.15
    p += 0.7 * s.get("classic", 0) if occ == "work" else 0
    p += 0.7 * s.get("bohemian", 0) if weekend else 0
    p -= 0.4 * warmth if temp > 25 else 0
    p += 0.3 * warmth if temp < 10 else 0
    return float(rng.random() < np.clip(p, 0, 1))


def simulate(days: int = 300, n_candidates: int = 20, seed: int = 0, verbose: bool = True):
    """Returns (bandit hits, random hits), one 0/1 per day."""
    cfg = get_config()
    layout = Layout.build(load_styles().ids, cfg.context)
    rng = np.random.default_rng(seed)
    model = LinearTS(layout.dim, v=cfg.bandit.v)
    hits_bandit, hits_random = [], []
    for day in range(days):
        weekend = day % 7 >= 5
        info = (rng.uniform(0, 35), rng.random() < 0.2, weekend, "casual" if weekend else "work")
        ctx = layout.context_vector(*info[:2], weekend, info[3])
        outfits = [random_outfit(layout, rng) for _ in range(n_candidates)]
        X = np.array([layout.features(ctx, o) for o in outfits])
        order, _ = model.choose(X, k=1, rng=rng)
        i = int(order[0])
        r = fake_user_reward(layout, info, outfits[i], rng)
        model.update(X[i], r)
        hits_bandit.append(r)
        hits_random.append(fake_user_reward(layout, info, outfits[rng.integers(n_candidates)], rng))
    if verbose:
        print(f"styles: {layout.S}  DIM: {layout.dim}  v: {cfg.bandit.v}")
        for start in range(0, days, 50):
            sl = slice(start, start + 50)
            print(
                f"days {start:3d}-{start + 49:3d}  bandit liked: {np.mean(hits_bandit[sl]):.0%}"
                f"   random liked: {np.mean(hits_random[sl]):.0%}"
            )
    return hits_bandit, hits_random


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=300)
    ap.add_argument("--candidates", type=int, default=20)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    simulate(a.days, a.candidates, a.seed)
