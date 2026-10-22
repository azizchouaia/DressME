"""Tips for a boutique, from the dashboard figures (F6, BO6 LLM).

The figures are computed by the dashboard (themes, unmet demand, prices, trends). The BO6 LLM (Qwen,
llm.py) only turns them into 2-3 short tips in English; a tip whose numbers are not in the figures is
dropped. Without the LLM, the same figures give rule-based tips, so the endpoint always answers.
"""

from modules.m07_local_catalogue.llm import numbers_ok

SYSTEM = (
    "You advise the owner of a clothing boutique in Tunisia. From the figures below, write 2 or 3 short, "
    "concrete tips in English, one per line, each starting with '- '. Each tip names one theme or product "
    "type from the figures, quotes one of its numbers exactly, and follows the line's Verdict (do not "
    "contradict it). Write no number that is not in the figures."
)


def facts(d: dict) -> list[str]:
    """The figures a tip may use, one line each (they are also returned, so every tip can be checked)."""
    # Every line carries a verdict made here, not by the LLM: it only words a verdict that is already right.
    out = []
    for u in d["unmet"][:3]:
        if u["products_in_shop"] == 0:
            verdict = "no piece at all: a gap to fill"
        elif u["products_in_shop"] < 5:
            verdict = "very few pieces: add more"
        elif u["weak_answer_rate"] >= 0.2:
            verdict = "pieces exist but often not the exact one asked: add the exact pieces"
        else:
            verdict = "well stocked: put these pieces forward"
        out.append(f"{u['hint']} Verdict: {verdict}.")
    for t in [t for t in d["trends"] if t["rising"]][:2]:
        out.append(
            f"Trend “{t['label']}”: {t['last_7_days']} searches in the last 7 days, "
            f"{t['weekly_mean_before']:g} per week before."
        )
    for p in d["prices"][:3]:
        if p.get("shop_p50") is not None:
            # served = share of the clients' budgets that can buy at least the cheapest piece
            served = round(100 * (p.get("served_share") or 0))
            if served < 80:
                verdict = (
                    f"{100 - served} % of the clients cannot afford even the cheapest piece: "
                    "add cheaper pieces"
                )
            elif p["shop_p50"] <= p["demand_p50"]:
                verdict = "prices well placed, under the clients' median budget"
            else:
                verdict = "most pieces cost more than the median budget: put the cheaper pieces forward"
            out.append(
                f"Prices “{p['label']}”: clients' median budget {p['demand_p50']:g} TND, "
                f"median price {p['shop_p50']:g} TND, {served} % of the budgets can buy the cheapest piece. "
                f"Verdict: {verdict}."
            )
    return out


def rule_tips(d: dict) -> list[str]:
    tips = []
    for u in d["unmet"][:2]:
        if u["products_in_shop"] == 0:
            tips.append(
                f"Consider offering “{u['label']}”: {u['n_searches']} searches, no piece in your shop."
            )
    for t in [t for t in d["trends"] if t["rising"]][:1]:
        tips.append(f"“{t['label']}” is rising: {t['last_7_days']} searches in the last 7 days.")
    return tips[:3]


async def build(d: dict, llm) -> dict:
    lines = facts(d)
    base = {"shop": d["shop"], "period_days": d["period_days"], "facts": lines}
    if lines and llm.on("insights"):
        text = await llm.text(SYSTEM, "\n".join(lines), max_tokens=220)
        if text:
            joined = "\n".join(lines)
            tips = [
                t.lstrip("-•* ").strip()
                for t in text.splitlines()
                if t.strip().startswith(("-", "•", "*")) and len(t) <= 260 and numbers_ok(t, joined)
            ]
            if tips:
                return base | {"insights": tips[:3], "source": "llm", "model": llm.model}
    return base | {"insights": rule_tips(d), "source": "rules", "model": None}
