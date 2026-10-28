"""Bandit prior mean. A new user starts from a neutral prior: no question is asked before the swipes.

The only explicit input is the user's wishes (POST /preferences: "more classic, less streetwear"). The
mapping wishes -> prior weights is `build_prior` + the `prior` section of config.yaml. It only depends on
the stored answers, so the prior can be rebuilt for a new style list.
"""

import numpy as np

from .config import M05Config, get_config
from .features import Layout


def build_prior(layout: Layout, answers: dict, cfg: M05Config | None = None) -> np.ndarray:
    """answers: want_more, want_less (both optional). Empty answers -> the neutral prior (taste_sim only)."""
    cfg = cfg or get_config()
    p, mean = cfg.prior, np.zeros(layout.dim)
    known = set(layout.styles)
    for key, w in (("want_more", p.want_more), ("want_less", p.want_less)):
        for s in answers.get(key) or []:
            if s in known:
                mean[layout.style_index(s)] += w
    mean[layout.taste_index] += p.taste_sim
    return mean
