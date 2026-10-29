"""Taste vector by Rocchio (config `ranking: rocchio`, the default): no context, no bandit.

The user's taste is a point of M1's FashionCLIP space, built from the cards they reacted to:

    taste = normalise( mean(liked) - reject_weight * mean(rejected)
                       + wish_weight * (sum of want_more style vectors - sum of want_less style vectors) )

Cards are ranked by cosine(card, taste). Each batch keeps `explore_cards` cards picked away from the taste
(the lower half of the remaining candidates), so the user still discovers other styles.
The contextual bandit (bandit.py, `ranking: bandit`) is kept, unused, for a taste that depends on the context.
"""

import random

import numpy as np

from .config import M05Config, get_config


def unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def accumulate(total: list[float] | None, count: float, emb: np.ndarray, weight: float):
    """Adds one card embedding (weighted by its source) to a running sum: (new sum, new count)."""
    base = np.zeros(len(emb)) if total is None else np.asarray(total)
    return [float(x) for x in base + weight * emb], count + weight


def taste(
    liked_sum: list[float] | None,
    n_liked: float,
    rejected_sum: list[float] | None,
    n_rejected: float,
    more: list[np.ndarray] = (),
    less: list[np.ndarray] = (),
    cfg: M05Config | None = None,
) -> np.ndarray | None:
    """None until there is something to like: a first liked card or a 'more of' wish."""
    cfg = cfg or get_config()
    r = cfg.rocchio
    if not (n_liked > 0 or len(more)):
        return None
    q = np.zeros(len(liked_sum if liked_sum is not None else more[0]))
    if n_liked > 0:
        q += np.asarray(liked_sum) / n_liked
    if n_rejected > 0:
        q -= r.reject_weight * np.asarray(rejected_sum) / n_rejected
    for v in more:
        q += r.wish_weight * v
    for v in less:
        q -= r.wish_weight * v
    return unit(q)


def pick(sims: np.ndarray, k: int, n_explore: int, rng: random.Random) -> list[tuple[int, bool]]:
    """(candidate index, is exploration) of one batch: the k - n_explore closest to the taste, plus
    n_explore drawn from the lower half of the rest, inserted at random places."""
    order = [int(i) for i in np.argsort(-sims, kind="stable")]
    k = min(k, len(order))
    n_explore = min(n_explore, len(order) - (k - n_explore)) if k > n_explore else 0
    exploit = order[: k - n_explore]
    rest = order[k - n_explore :]
    far = rest[len(rest) // 2 :] if len(rest) > n_explore else rest
    chosen = [(i, False) for i in exploit]
    for i in rng.sample(far, n_explore):
        chosen.insert(rng.randint(0, len(chosen)), (i, True))
    return chosen
