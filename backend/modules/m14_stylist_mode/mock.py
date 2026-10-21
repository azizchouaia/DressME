"""Fixed M14 answers in the real contract shapes, for the other BOs' offline tests (no data, no model).

Each function has the shape of the matching endpoint's answer; tests check them against contract.py.
"""

_AT = "2026-10-21T10:00:00+00:00"


def pro() -> dict:
    return {
        "pro_id": "pro_demo0001",
        "type": "stylist",
        "name": "Amel (styliste, démo)",
        "city": "Tunis",
        "shop": None,
        "specialities": ["mariage", "traditionnel"],
        "languages": ["fr", "darija"],
        "bio": None,
        "style_vector": None,
        "verified": False,
        "available": True,
        "created_at": _AT,
    }


def brief() -> dict:
    return {
        "pro_id": "pro_demo0001",
        "client_id": "usr_042",
        "archetype": "minimaliste urbain",
        "likes": ["lin", "beige"],
        "dislikes": ["imprimés"],
        "wardrobe": {
            "n_items": 24,
            "per_category": {"top": 9, "bottom": 6, "shoes": 4, "dress": 2, "outerwear": 3},
            "top_colours": ["beige", "white", "navy"],
            "most_worn": ["Jean droit bleu", "Baskets blanches"],
            "never_worn": ["Robe rouge"],
            "price_range_tnd": [25.0, 240.0],
        },
        "gaps": ["chaussures habillées"],
        "recent_searches": ["sandales dorées mariage max 120 dt"],
        "summary": [
            "Style : minimaliste urbain (aime : lin, beige ; évite : imprimés).",
            "Garde-robe : 24 pièces, surtout top (9), bottom (6).",
            "Le plus porté : Jean droit bleu, Baskets blanches. Jamais porté : Robe rouge.",
            "Manque : chaussures habillées.",
            "A cherché récemment : sandales dorées mariage max 120 dt.",
        ],
        "sources": {"m1": "mock", "m3": "mock", "m5": "mock", "m7": "mock"},
    }


def review() -> dict:
    return {
        "review_id": "rev_demo0001",
        "pro_id": "pro_demo0001",
        "client_id": "usr_042",
        "before": {"archetype": "casual", "likes": ["lin"], "dislikes": [], "colours": ["beige"]},
        "corrections": {
            "archetype": "minimaliste urbain",
            "likes": ["lin"],
            "dislikes": [],
            "colours": ["beige"],
        },
        "changed": ["archetype"],
        "agreement": 0.75,
        "sent_to_m5": True,
        "note": None,
        "created_at": _AT,
        "sources": {"m5": "mock"},
    }


def look() -> dict:
    return {
        "look_id": "look_demo0001",
        "pro_id": "pro_demo0001",
        "client_id": "usr_042",
        "item_ids": ["itm_jean01"],
        "products": [
            {
                "product_id": "prd_2b7db627f3",
                "item": "Basket à plateforme femme",
                "shop": "Manuella",
                "price_tnd": 69.3,
                "image_url": "https://manuella.com.tn/cdn/shop/files/basket.jpg",
                "product_url": "https://manuella.com.tn/products/basket-a-plateforme",
            }
        ],
        "total_price_tnd": 69.3,
        "score": 0.82,
        "card_url": "/m10/cards/card_demo/image",
        "share_url": "https://dressme.tn/s/demo",
        "message": "Avec ton jean droit, pour samedi.",
        "created_at": _AT,
        "sources": {"m2": "mock", "m7": "mock", "m10": "mock"},
    }


def instore() -> dict:
    return {
        "pro_id": "pro_demo0002",
        "client_id": "usr_042",
        "product": look()["products"][0],
        "verdict": "buy",
        "score": 78,
        "reasons": ["Va avec 5 pièces de ta garde-robe", "Tu n'as pas de baskets blanches"],
        "explanation": "Bon achat : elle complète ta garde-robe sans doublon.",
        "sources": {"m6": "mock", "m7": "mock"},
    }


def dashboard(shop: str | None = "Manuella") -> dict:
    return {
        "shop": shop,
        "period_days": 30,
        "since": "2026-09-21T10:00:00+00:00",
        "until": _AT,
        "n_searches": 1240,
        "simulated_share": 1.0,
        "funnel": {"impressions": 3120, "views": 410, "clicks": 96, "ctr": 0.031, "rank": 4},
        "themes": [
            {
                "theme_id": "th_01",
                "label": "Sandales dorées · femme",
                "subcategory": "sandals",
                "color": "gold",
                "gender": "women",
                "n_searches": 132,
                "share": 0.106,
                "median_budget_tnd": 60.0,
                "top_cities": ["Sousse", "Tunis"],
                "examples": ["sandales dorées mariage", "sandale dorée max 60 dt"],
                "zero_result_rate": 0.41,
                "weak_answer_rate": 0.55,
            }
        ],
        "unmet": [
            {
                "theme_id": "th_01",
                "label": "Sandales dorées · femme",
                "n_searches": 132,
                "zero_result_rate": 0.41,
                "weak_answer_rate": 0.55,
                "products_in_shop": 0,
                "products_in_market": 3,
                "visual_coverage": 0.22,
                "opportunity": 103.0,
                "hint": "132 recherches « Sandales · Doré · femme », 0 chez vous (3 dans tout le catalogue), "
                "55 % des recherches sans pièce exacte.",
            }
        ],
        "prices": [
            {
                "subcategory": "sandals",
                "label": "Sandales",
                "n_budgets": 88,
                "demand_p25": 45.0,
                "demand_p50": 60.0,
                "demand_p75": 90.0,
                "shop_p25": 69.0,
                "shop_p50": 89.0,
                "shop_p75": 119.0,
                "served_share": 0.35,
            }
        ],
        "trends": [
            {
                "theme_id": "th_01",
                "label": "Sandales dorées · femme",
                "last_7_days": 58,
                "weekly_mean_before": 9.4,
                "z": 5.2,
                "growth": 5.17,
                "rising": True,
            }
        ],
        "not_understood": 31,
        "hidden_groups": 4,
        "method": {"themes": "mock"},
    }


def escalation() -> dict:
    return {"escalate": True, "score": 1.0, "reason": "asks_human", "signals": {"asks_human": 1.0}}


def handoff() -> dict:
    return {
        "handoff_id": "hof_demo0001",
        "user_id": "usr_042",
        "session_id": "chat_1",
        "status": "queued",
        "pro_id": "pro_demo0001",
        "candidates": [
            {
                "pro_id": "pro_demo0001",
                "name": "Amel (styliste, démo)",
                "city": "Tunis",
                "score": 0.86,
                "reasons": ["Spécialité : mariage", "Même ville : Tunis", "Parle fr"],
            }
        ],
        "escalation": escalation(),
        "occasion": "mariage",
        "budget_tnd": 300.0,
        "city": "Tunis",
        "summary": [
            "Demande : une tenue pour le mariage de ma sœur en juillet",
            "Occasion : mariage · budget : 300 TND · ville : Tunis",
            "Pourquoi un humain : demande à parler à un styliste",
            "A cherché : robe longue verte, sandales dorées",
        ],
        "created_at": _AT,
        "updated_at": _AT,
        "history": [{"status": "queued", "pro_id": "pro_demo0001", "at": _AT}],
    }
