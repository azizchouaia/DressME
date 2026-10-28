"""Simulated shopping traffic for the boutique dashboard (no real users before the demo).

    cd backend && python -m modules.m14_stylist_mode.simulate.traffic --users 300 --weeks 12

N synthetic Tunisian users (city, gender, budget) write requests in FR / EN (templates) and darija /
Arabic (the hand-written requests of M7's evaluation set), spread over the last weeks. Every request goes
through the REAL M7 search, so results, zero-result searches and matches are the real ones; views and
shop clicks follow the rank of the results. Everything is written to its own log
(ml/data/logs/m14_simulated_events.jsonl), never mixed with the real one, and the dashboard reports the
simulated share. Two known signals are injected to check the dashboard finds them (evaluation):
  - gold sandals for weddings, rising in the last 2 weeks in the Sahel (trend + unmet demand);
  - men's suits for weddings, steady (a type few shops sell).
"""

import argparse
import asyncio
import random
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

from modules.m07_local_catalogue import events as m7_events

from ..paths import SIMULATED_LOG

CITIES = {
    "Tunis": 28,
    "Ariana": 8,
    "Ben Arous": 6,
    "La Marsa": 4,
    "Sousse": 12,
    "Sfax": 12,
    "Nabeul": 7,
    "Monastir": 6,
    "Bizerte": 5,
    "Kairouan": 4,
    "Gabès": 4,
    "Mahdia": 4,
}
# type: (French noun, feminine?, English noun, typical price TND, share of requests by women, weight)
PIECES = {
    "dress": ("robe", True, "dress", 100, 1.0, 10),
    "sneakers": ("baskets", True, "sneakers", 100, 0.55, 9),
    "sandals": ("sandales", True, "sandals", 70, 0.85, 6),
    "shirt": ("chemise", True, "shirt", 70, 0.45, 7),
    "jeans": ("jean", False, "jeans", 65, 0.5, 7),
    "trousers": ("pantalon", False, "trousers", 70, 0.5, 5),
    "bag": ("sac", False, "bag", 120, 0.95, 8),
    "jacket": ("veste", True, "jacket", 110, 0.5, 5),
    "heels": ("escarpins", False, "heels", 90, 1.0, 4),
    "tshirt": ("t-shirt", False, "t-shirt", 45, 0.5, 6),
    "traditional": ("jebba", True, "traditional outfit", 150, 0.6, 3),
    "necklace": ("collier", False, "necklace", 35, 1.0, 4),
    "boots": ("bottes", True, "boots", 180, 0.85, 3),
    "coat": ("manteau", False, "coat", 170, 0.55, 3),
    "sweater": ("pull", False, "sweater", 65, 0.55, 4),
    "hijab": ("hijab", False, "hijab", 15, 1.0, 2),
}
# colour: (masculine, feminine, English)
COLOURS = {
    "black": ("noir", "noire", "black"),
    "white": ("blanc", "blanche", "white"),
    "beige": ("beige", "beige", "beige"),
    "red": ("rouge", "rouge", "red"),
    "blue": ("bleu", "bleue", "blue"),
    "green": ("vert", "verte", "green"),
    "pink": ("rose", "rose", "pink"),
    "gold": ("doré", "dorée", "gold"),
    "navy": ("bleu marine", "bleu marine", "navy"),
    "brown": ("marron", "marron", "brown"),
}
FR = [
    "{piece} {colour}",
    "{piece} {colour} {gender}",
    "je cherche {piece} {colour} à {city}",
    "{piece} {colour} max {budget} dt",
    "{piece} pas cher moins de {budget} dinars",
    "{piece} {gender} {city}",
    "{piece} {gender}",
    "{piece} {colour} {gender} à {city} max {budget} dt",
]
EN = [
    "{colour} {piece}",
    "{colour} {piece} under {budget} TND",
    "{gender} {piece} in {city}",
    "{piece} for {gender}",
]
GENDER = {"fr": {"women": "femme", "men": "homme"}, "en": {"women": "women", "men": "men"}}
EVAL_SET = Path(__file__).resolve().parents[2] / "m07_local_catalogue" / "evaluation" / "queries.yaml"


def _pick(rng: random.Random, weights: dict) -> str:
    return rng.choices(list(weights), weights=list(weights.values()))[0]


def users(n: int, rng: random.Random) -> list[dict]:
    return [
        {
            "user_id": f"sim_{i:04d}",
            "city": _pick(rng, CITIES),
            "women": rng.random() < 0.65,
            "budget": rng.lognormvariate(0, 0.35),
            "lang": _pick(rng, {"fr": 60, "en": 12, "local": 28}),
        }
        for i in range(n)
    ]


def request(user: dict, rng: random.Random, local: list[str]) -> str:
    """One request as this user would type it."""
    if user["lang"] == "local" and local:
        return rng.choice(local)
    lang = "en" if user["lang"] == "en" else "fr"
    gender = "women" if user["women"] else "men"
    pool = {k: v for k, v in PIECES.items() if (v[4] > 0 if gender == "women" else v[4] < 1)}
    sub = _pick(rng, {k: v[5] for k, v in pool.items()})
    noun, feminine, noun_en, price, _, _ = PIECES[sub]
    colour = COLOURS[_pick(rng, dict.fromkeys(COLOURS, 1))]
    budget = int(round(price * user["budget"] * rng.uniform(0.7, 1.2), -1)) or 10
    template = rng.choice(FR if lang == "fr" else EN)
    text = template.format(
        piece=noun if lang == "fr" else noun_en,
        colour=(colour[1] if feminine else colour[0]) if lang == "fr" else colour[2],
        gender=GENDER[lang][gender],
        city=user["city"],
        budget=budget,
    )
    return " ".join(text.split())


def injected(rng: random.Random, until: datetime) -> list[tuple[datetime, str, str]]:
    """Known signals (date, user_id, request) the dashboard should find."""
    out = []
    for week in range(12):  # gold sandals for weddings: a few a week, then a wave in the last 2 weeks
        n = 3 if week >= 2 else 28
        for _ in range(n):
            at = until - timedelta(days=7 * week + rng.uniform(0, 7))
            city = rng.choice(["Sousse", "Monastir", "Mahdia", "Sousse"])
            text = rng.choice(
                [
                    "sandales dorées mariage",
                    f"sandale dorée à {city}",
                    f"sandales dorées femme max {rng.choice([60, 70, 80])} dt",
                    "sandales dorées pour un mariage",
                ]
            )
            out.append((at, f"sim_w{rng.randrange(60):03d}", text))
    for week in range(12):  # men's suits for weddings, steady
        for _ in range(4):
            at = until - timedelta(days=7 * week + rng.uniform(0, 7))
            out.append(
                (
                    at,
                    f"sim_s{rng.randrange(40):03d}",
                    rng.choice(
                        ["costume homme mariage", "costume bleu marine homme", "costume homme max 300 dt"]
                    ),
                )
            )
    return out


async def run(
    n_users: int, weeks: int, seed: int, agent=None, path: Path = SIMULATED_LOG, until=None
) -> dict:
    rng = random.Random(seed)
    until = until or datetime.now(UTC)
    if agent is None:
        from modules.m07_local_catalogue import service as m7

        agent = await m7.get_agent()
    local = [
        q["query"]
        for q in yaml.safe_load(EVAL_SET.read_text(encoding="utf-8"))
        if q["lang"] in ("darija", "arabic")
    ]
    plan = []
    for user in users(n_users, rng):
        for _ in range(max(1, int(rng.expovariate(1 / 5)))):
            at = until - timedelta(days=rng.uniform(0, 7 * weeks))
            plan.append((at, user["user_id"], request(user, rng, local)))
    plan += injected(rng, until)
    plan.sort()

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")  # one simulation = one fresh file
    stats = {"searches": 0, "views": 0, "clicks": 0, "zero_results": 0}
    for at, user_id, text in plan:
        req = {"query": text, "k": 10, "user_id": user_id}
        started = time.perf_counter()
        out = await agent({"query": text, "k": 10})  # anonymous for the agent: no memory file per sim user
        search_id = m7_events.log_search(
            req, out, 1000 * (time.perf_counter() - started), "simulated", at, path
        )
        stats["searches"] += 1
        stats["zero_results"] += not out["results"]
        if out["results"] and rng.random() < 0.35:  # opens one result, top ones more often
            ranks = range(1, len(out["results"]) + 1)
            rank = rng.choices(list(ranks), weights=[1 / r for r in ranks])[0]
            hit = out["results"][rank - 1]
            seen = at + timedelta(seconds=rng.uniform(5, 60))
            m7_events.log_click(
                "product_view",
                hit["product_id"],
                search_id,
                hit["shop"],
                rank,
                user_id,
                "simulated",
                seen,
                path,
            )
            stats["views"] += 1
            if rng.random() < 0.45:
                m7_events.log_click(
                    "shop_click",
                    hit["product_id"],
                    search_id,
                    hit["shop"],
                    rank,
                    user_id,
                    "simulated",
                    seen + timedelta(seconds=rng.uniform(5, 40)),
                    path,
                )
                stats["clicks"] += 1
    return stats | {"users": n_users, "weeks": weeks, "file": str(path)}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--users", type=int, default=300)
    parser.add_argument("--weeks", type=int, default=12)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)
    print(asyncio.run(run(args.users, args.weeks, args.seed)))


if __name__ == "__main__":
    main()
