"""Smart Buy extra features (BO5).

1. Wishlist price watch: a THINK piece is saved with a target price; we watch local shop prices (M13 / M7)
   and alert when it is worth buying.
2. Better alternative: same type, cheaper, same colour first, from local shops.
3. Wear check-in: ~30 days after a purchase we ask "did you wear it?"; the answer becomes a REAL label
   (buy / think / skip) to retrain the decision model instead of synthetic data.

All state lives in the agent memory (one JSON per user).
"""

import json
import os
import re
import time
import uuid
from datetime import datetime
from pathlib import Path

from modules.m13_partner_links import service as partners

DEFAULT_DROP = 0.15       # target = 15% under the price the user saw
ALT_MIN_SAVING = 0.15     # an alternative must be at least 15% cheaper


# ---------------------------------------------------------------- 1. wishlist
def _offers(shops: list[dict], subcategory: str, colour: str | None, product_id: str | None = None) -> list[dict]:
    """Current local offers for this piece: the same product if we know it, else same type + colour."""
    out = []
    for s in shops:
        for it in s["items"]:
            same = (product_id and it.get("product_id") == product_id) or (
                not product_id and it["subcategory"] == subcategory and (not colour or it["colour"] == colour))
            if same:
                out.append({"shop": s["name"], "city": s.get("city"), "item": it["name"], "price_tnd": it["price_tnd"],
                            "url": it["url"], "promo_code": s.get("promo_code"), "product_id": it.get("product_id")})
    return sorted(out, key=lambda o: o["price_tnd"])


def wishlist_add(memory, user_id: str, subcategory: str, colour: str, price_tnd: float,
                 target_tnd: float | None = None, product_id: str | None = None, decision_id: str | None = None) -> dict:
    m = memory.load(user_id)
    item = {"id": f"wish_{uuid.uuid4().hex[:8]}", "subcategory": subcategory, "colour": colour,
            "price_tnd": price_tnd, "target_tnd": round(target_tnd or price_tnd * (1 - DEFAULT_DROP), 1),
            "product_id": product_id, "decision_id": decision_id, "added": time.strftime("%Y-%m-%d"), "alerted_at": None}
    m.setdefault("wishlist", []).insert(0, item)
    memory._save(user_id)
    return item


def wishlist(memory, user_id: str) -> list[dict]:
    return memory.load(user_id).get("wishlist", [])


def wishlist_remove(memory, user_id: str, wish_id: str) -> bool:
    m = memory.load(user_id)
    before = len(m.get("wishlist", []))
    m["wishlist"] = [w for w in m.get("wishlist", []) if w["id"] != wish_id]
    memory._save(user_id)
    return len(m["wishlist"]) < before


def wishlist_check(memory, user_id: str, shops: list[dict]) -> list[dict]:
    """-> alerts: wished pieces now at or under the target price somewhere."""
    alerts = []
    for w in wishlist(memory, user_id):
        offers = _offers(shops, w["subcategory"], w["colour"], w.get("product_id"))
        if not offers:
            continue
        best = offers[0]
        if best["price_tnd"] <= w["target_tnd"] and best["price_tnd"] != w.get("alerted_price"):
            saved = round(w["price_tnd"] - best["price_tnd"], 1)
            alerts.append({"wish_id": w["id"], "subcategory": w["subcategory"], "colour": w["colour"],
                           "was_tnd": w["price_tnd"], "now_tnd": best["price_tnd"], "saved_tnd": saved,
                           "offer": best,
                           "message": f"{w['colour']} {w['subcategory']} is now {best['price_tnd']:g} TND at "
                                      f"{best['shop']} ({saved:g} TND less). Check again with Smart Buy?",
                           "next_action": {"action": "recheck", "tool": "smartbuy",
                                           "args": {"price_tnd": best["price_tnd"]}}})
            w["alerted_at"], w["alerted_price"] = time.strftime("%Y-%m-%d"), best["price_tnd"]
    if alerts:
        memory._save(user_id)
    return alerts


# ---------------------------------------------------------------- 2. better alternative
NEAR = {"black": {"navy", "grey"}, "navy": {"black", "blue"}, "white": {"beige", "cream"},
        "beige": {"cream", "white", "brown"}, "grey": {"black", "white"}, "blue": {"navy"},
        "brown": {"beige", "olive"}, "olive": {"brown", "green"}, "green": {"olive"}}


def alternatives(shops: list[dict], subcategory: str, colour: str, price_tnd: float, k: int = 3,
                 min_saving: float = ALT_MIN_SAVING) -> list[dict]:
    """Same type, at least min_saving cheaper; same colour first, then close colours; one per shop."""
    limit = price_tnd * (1 - min_saving)
    found = []
    for s in shops:
        for it in s["items"]:
            if it["subcategory"] != subcategory or it["price_tnd"] > limit:
                continue
            match = 2 if it["colour"] == colour else 1 if it["colour"] in NEAR.get(colour, ()) else 0
            if not match:
                continue
            found.append((match, -it["price_tnd"], {
                "shop": s["name"], "city": s.get("city"), "item": it["name"], "colour": it["colour"],
                "price_tnd": it["price_tnd"], "saved_tnd": round(price_tnd - it["price_tnd"], 1),
                "saved_pct": round(100 * (1 - it["price_tnd"] / price_tnd)), "url": it["url"],
                "promo_code": s.get("promo_code"), "image_url": it.get("image_url"),
                "same_colour": match == 2}))
    # best colour match first, then the closest price (most similar quality), one per shop
    found.sort(key=lambda x: (x[0], x[1]), reverse=True)
    seen, res = set(), []
    for _, _, o in found:
        if o["shop"] not in seen:
            seen.add(o["shop"])
            res.append(o)
        if len(res) == k:
            break
    return res


# ---------------------------------------------------------------- 3. wear check-in
WORDS = [  # (pattern, times worn) — EN / FR / Tunisian
    (r"\b(never|not once|jamais|pas une fois|ma lbesthech|ma lbesthouch|mal?bsthech)\b", 0),
    (r"\b(once|one time|une fois|mara|marra)\b", 1),
    (r"\b(twice|two times|deux fois|marten|martin)\b", 2),
    (r"\b(every day|daily|tous les jours|kol nhar)\b", 20),
    (r"\b(every week|weekly|often|a lot|all the time|souvent|chaque semaine|beaucoup|barcha|barsha|dima)\b", 8),
    (r"\b(sometimes|parfois|a few times|quelques fois|sa3at)\b", 3),
]
REGRET = r"\b(regret|waste|return|returned|rembours|regrette|ndemt|too tight|trop serr|doesn.?t fit)\b"


def parse_wear(text: str) -> dict:
    """Free answer -> {times_worn, regret}. Rules first (fast, offline), the LLM only if they find nothing."""
    low = (text or "").lower()
    times = None
    num = re.search(r"\b(\d{1,3})\s*(x|times|fois|mrat|marat)\b", low) or re.fullmatch(r"\s*(\d{1,3})\s*", low)
    if num:
        times = int(num.group(1))
    else:
        for pat, n in WORDS:
            if re.search(pat, low):  # first match wins (never before once)
                times = n
                break
    regret = bool(re.search(REGRET, low))
    if times is None:
        llm = _parse_wear_llm(text)
        if llm:
            return llm
    return {"times_worn": times, "regret": regret, "method": "rules"}


def _parse_wear_llm(text: str, timeout: float = 20.0) -> dict | None:
    try:
        import httpx
        prompt = ('How many times did the user wear the piece, and do they regret buying it? Answer ONLY JSON '
                  '{"times_worn": int|null, "regret": true|false}. Text: """' + text + '"""')
        r = httpx.post(os.environ.get("OLLAMA_URL", "http://localhost:11434") + "/api/chat", timeout=timeout, json={
            "model": os.environ.get("OLLAMA_MODEL", "llama3.1:8b"), "stream": False, "format": "json",
            "options": {"temperature": 0}, "messages": [{"role": "user", "content": prompt}]})
        d = json.loads(r.json()["message"]["content"])
        t = d.get("times_worn")
        if t is not None and not (isinstance(t, int) and 0 <= t <= 365):
            return None
        return {"times_worn": t, "regret": bool(d.get("regret")), "method": "llm"} if t is not None else None
    except Exception:  # noqa: BLE001 - the LLM is optional
        return None


def wear_label(times_worn: int, regret: bool) -> str:
    """What the right verdict WAS, seen 30 days later."""
    if regret or times_worn == 0:
        return "skip"
    return "buy" if times_worn >= 3 else "think"


def checkins_due(memory, user_id: str, days: int = 30, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now()
    due = []
    for h in memory.history(user_id, 50):
        if not (h.get("feedback") or {}).get("bought") or h.get("wear"):
            continue
        age = (now - datetime.strptime(h["at"], "%Y-%m-%d %H:%M")).days
        if age >= days:
            due.append({"decision_id": h["decision_id"], "piece": h.get("piece"), "days": age,
                        "question": f"You bought the {h.get('piece') or 'piece'} {age} days ago. How many times did you wear it?"})
    return due


def checkin_answer(memory, user_id: str, decision_id: str, text: str) -> dict:
    m = memory.load(user_id)
    h = next((x for x in m["history"] if x["decision_id"] == decision_id), None)
    if not h:
        raise ValueError(f"unknown decision {decision_id}")
    parsed = parse_wear(text)
    if parsed["times_worn"] is None:
        return {"saved": False, "question": "Sorry, how many times did you wear it? (a number is fine)"}
    label = wear_label(parsed["times_worn"], parsed["regret"])
    h["wear"] = {**parsed, "label": label, "answer": text, "at": time.strftime("%Y-%m-%d")}
    memory._save(user_id)
    right = label == h["verdict"]
    return {"saved": True, **h["wear"], "smartbuy_said": h["verdict"], "advice_was_right": right}


def real_labels(folder: Path | None) -> list[dict]:
    """All wear check-ins of all users: the real training data for learn.py."""
    rows = []
    if not folder or not Path(folder).exists():
        return rows
    for p in sorted(Path(folder).glob("*.json")):
        for h in json.loads(p.read_text(encoding="utf-8")).get("history", []):
            if h.get("wear"):
                rows.append({"user_id": p.stem, "decision_id": h["decision_id"], "piece": h.get("piece"),
                             "price_tnd": h.get("price_tnd"), "said": h["verdict"], "label": h["wear"]["label"]})
    return rows


def accuracy(rows: list[dict]) -> dict:
    """How often Smart Buy was right, measured on real wear (the honest KPI)."""
    n = len(rows)
    return {"labels": n, "accuracy": round(sum(r["said"] == r["label"] for r in rows) / n, 3) if n else None}
