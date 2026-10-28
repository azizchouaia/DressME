"""BO7 · Monte-Carlo simulation of the sharing loop (organic acquisition).

Each active user shares N ~ Poisson(cards_per_user) cards per cycle; each card gets
Poisson(opens_per_card) opens; each open converts with probability p. New users join the next cycle.
This is a Galton-Watson branching process: the expected viral coefficient is
    K = cards_per_user × opens_per_card × p
and growth is self-sustaining only when K > 1.

Usage:
    python ml/scripts/bo7_viral_simulation.py --seed-users 200 --cards 2 --opens 3 --conversion 0.08
The defaults are assumptions to replace with the real values from GET /share/metrics once users exist.
"""

import argparse

import numpy as np


def simulate(
    seed_users: int,
    cards: float,
    opens: float,
    conversion: float,
    cycles: int,
    runs: int = 2000,
    rng_seed: int = 7,
) -> np.ndarray:
    rng = np.random.default_rng(rng_seed)
    totals = np.zeros((runs, cycles + 1), dtype=np.int64)
    for r in range(runs):
        active, total = seed_users, seed_users
        totals[r, 0] = total
        for c in range(1, cycles + 1):
            n_cards = rng.poisson(cards, size=active).sum() if active else 0
            n_opens = rng.poisson(opens, size=n_cards).sum() if n_cards else 0
            new = rng.binomial(n_opens, conversion) if n_opens else 0
            total += new
            active = new  # only newcomers are "fresh" sharers in this simple model
            totals[r, c] = total
    return totals


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed-users", type=int, default=200)
    ap.add_argument("--cards", type=float, default=2.0, help="cards shared per user per cycle")
    ap.add_argument("--opens", type=float, default=3.0, help="link opens per card")
    ap.add_argument("--conversion", type=float, default=0.08, help="sign-ups per open")
    ap.add_argument("--cycles", type=int, default=8)
    a = ap.parse_args()

    k = a.cards * a.opens * a.conversion
    t = simulate(a.seed_users, a.cards, a.opens, a.conversion, a.cycles)
    p10, p50, p90 = np.percentile(t[:, -1], [10, 50, 90])
    verdict = "self-sustaining" if k > 1 else "decays"
    theory = a.seed_users * sum(k**i for i in range(a.cycles + 1))
    print(f"K = {a.cards} × {a.opens} × {a.conversion} = {k:.2f}  ({verdict})")
    print(f"Expected users after {a.cycles} cycles (theory): {theory:.0f}")
    print(f"Simulated users after {a.cycles} cycles: median {p50:.0f}  (P10 {p10:.0f} · P90 {p90:.0f})")
    print("cycle  median_users")
    for c in range(a.cycles + 1):
        print(f"{c:>5}  {np.median(t[:, c]):>12.0f}")


if __name__ == "__main__":
    main()
