"""BO7 business KPIs: does sharing bring new users for free?

  click-through rate   CTR = link opens / cards shared
  conversion           CR  = sign-ups / link opens
  invites per sharer   i   = cards shared / distinct sharers
  viral coefficient    K   = i × CTR × CR  (= new users brought by one sharing user)

K > 1 means each user brings more than one new user: growth feeds itself.
`project_growth` gives the expected user base after n viral cycles (geometric series of a branching process).
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ShareMetrics:
    cards: int
    sharers: int
    opens: int
    signups: int
    ctr: float
    conversion: float
    invites_per_sharer: float
    k_factor: float
    channels: list[dict] = field(default_factory=list)  # per channel: opens, signups, conversion
    best_channel: str | None = None  # highest conversion with at least MIN_OPENS opens


MIN_OPENS = 3  # below this a conversion rate is noise


def by_channel(opens: list[dict], signups: list[dict]) -> tuple[list[dict], str | None]:
    names = sorted(
        {o.get("channel", "direct") for o in opens} | {s.get("channel", "direct") for s in signups}
    )
    rows = []
    for ch in names:
        o = sum(1 for x in opens if x.get("channel", "direct") == ch)
        s = len({x["new_user_id"] for x in signups if x.get("channel", "direct") == ch})
        rows.append({"channel": ch, "opens": o, "signups": s, "conversion": round(s / o, 4) if o else 0.0})
    rows.sort(key=lambda r: (r["signups"], r["opens"]), reverse=True)
    eligible = [r for r in rows if r["opens"] >= MIN_OPENS]
    best = max(eligible, key=lambda r: (r["conversion"], r["signups"]))["channel"] if eligible else None
    return rows, best


def compute(cards: list[dict], opens: list[dict], signups: list[dict]) -> ShareMetrics:
    """cards [{card_id, user_id, short_code}], opens [{short_code}], signups [{short_code, new_user_id}]"""
    n_cards = len(cards)
    sharers = len({c["user_id"] for c in cards})
    n_open = len(opens)
    n_signup = len({s["new_user_id"] for s in signups})
    ctr = n_open / n_cards if n_cards else 0.0
    cr = n_signup / n_open if n_open else 0.0
    inv = n_cards / sharers if sharers else 0.0
    channels, best = by_channel(opens, signups)
    return ShareMetrics(
        cards=n_cards,
        sharers=sharers,
        opens=n_open,
        signups=n_signup,
        ctr=round(ctr, 4),
        conversion=round(cr, 4),
        invites_per_sharer=round(inv, 3),
        k_factor=round(inv * ctr * cr, 4),
        channels=channels,
        best_channel=best,
    )


TIERS = [(20, "DressMe star"), (5, "Style influencer"), (1, "Ambassador")]  # sign-ups brought → title
POINTS_PER_SIGNUP = 50


def ambassadors(cards: list[dict], opens: list[dict], signups: list[dict], top: int = 10) -> list[dict]:
    """Who brings new users? Ranks sharers by attributed sign-ups (if/else tiers + reward points)."""
    owner = {c["short_code"]: c["user_id"] for c in cards}
    rows: dict[str, dict] = {}
    for c in cards:
        rows.setdefault(c["user_id"], {"user_id": c["user_id"], "cards": 0, "opens": 0, "signups": 0})[
            "cards"
        ] += 1
    for o in opens:
        if o["short_code"] in owner:
            rows[owner[o["short_code"]]]["opens"] += 1
    for s in signups:
        if s["short_code"] in owner:
            rows[owner[s["short_code"]]]["signups"] += 1
    out = []
    for r in rows.values():
        tier = next((name for need, name in TIERS if r["signups"] >= need), None)
        nxt = next((need for need, _ in reversed(TIERS) if r["signups"] < need), None)
        out.append(
            {
                **r,
                "tier": tier,
                "points": r["signups"] * POINTS_PER_SIGNUP,
                "to_next_tier": (nxt - r["signups"]) if nxt else 0,
            }
        )
    out.sort(key=lambda r: (r["signups"], r["opens"], r["cards"]), reverse=True)
    return [{"rank": i + 1, **r} for i, r in enumerate(out[:top])]


def project_growth(seed_users: int, k: float, cycles: int) -> list[int]:
    """Expected cumulative users after each viral cycle: seed × (1 + k + k² + … + kⁿ)."""
    total, gen, out = float(seed_users), float(seed_users), []
    for _ in range(cycles):
        gen *= k
        total += gen
        out.append(round(total))
    return out
