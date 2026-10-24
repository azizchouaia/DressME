"""Fixed M14 answers in the real contract shapes, for the other BOs' offline tests (no data, no model).

Each function has the shape of the matching endpoint's answer; tests check them against contract.py.
"""

_AT = "2026-10-21T10:00:00+00:00"


def pro() -> dict:
    return {
        "pro_id": "pro_demo0001",
        "type": "stylist",
        "name": "Amel (stylist, demo)",
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
        "archetype": "urban minimalist",
        "likes": ["linen", "beige"],
        "dislikes": ["prints"],
        "wardrobe": {
            "n_items": 24,
            "per_category": {"top": 9, "bottom": 6, "shoes": 4, "dress": 2, "outerwear": 3},
            "top_colours": ["beige", "white", "navy"],
            "most_worn": ["Blue straight jeans", "White sneakers"],
            "never_worn": ["Robe rouge"],
            "price_range_tnd": [25.0, 240.0],
        },
        "gaps": ["dress shoes"],
        "recent_searches": ["sandales dorées mariage max 120 dt"],
        "summary": [
            "Style: urban minimalist (likes: linen, beige ; avoids: prints).",
            "Wardrobe: 24 pieces, mostly top (9), bottom (6).",
            "Most worn: Blue straight jeans, White sneakers. Never worn: Red dress.",
            "Missing: dress shoes.",
            "Recently searched: sandales dorées mariage max 120 dt.",
        ],
        "sources": {"m1": "mock", "m3": "mock", "m5": "mock", "m7": "mock"},
    }


def review() -> dict:
    return {
        "review_id": "rev_demo0001",
        "pro_id": "pro_demo0001",
        "client_id": "usr_042",
        "before": {"archetype": "casual", "likes": ["linen"], "dislikes": [], "colours": ["beige"]},
        "corrections": {
            "archetype": "urban minimalist",
            "likes": ["linen"],
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
        "message": "With your straight jeans, for Saturday.",
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
        "reasons": ["Goes with 5 pieces of your wardrobe", "You have no white sneakers"],
        "explanation": "Good buy: it completes your wardrobe without a duplicate.",
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
                "label": "Sandals · gold · women",
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
                "label": "Sandals · gold · women",
                "n_searches": 132,
                "zero_result_rate": 0.41,
                "weak_answer_rate": 0.55,
                "products_in_shop": 0,
                "products_in_market": 3,
                "visual_coverage": 0.22,
                "opportunity": 103.0,
                "hint": "132 searches for “Sandals · gold · women”, 0 in your shop "
                "(3 in the whole catalogue), 55 % of the searches without an exact piece.",
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
                "label": "Sandals · gold · women",
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
                "name": "Amel (stylist, demo)",
                "city": "Tunis",
                "score": 0.86,
                "reasons": ["Speciality: mariage", "Same city: Tunis", "Speaks fr"],
            }
        ],
        "escalation": escalation(),
        "occasion": "mariage",
        "budget_tnd": 300.0,
        "city": "Tunis",
        "summary": [
            "Request: une tenue pour le mariage de ma sœur en juillet",
            "Occasion: wedding · budget: 300 TND · city: Tunis",
            "Why a human: asked to talk to a stylist",
            "Searched the shops for: robe longue verte, sandales dorées",
        ],
        "created_at": _AT,
        "updated_at": _AT,
        "history": [{"status": "queued", "pro_id": "pro_demo0001", "at": _AT}],
    }


def loyalty_codes() -> list[dict]:
    return [
        {
            "shop": "Manuella",
            "pro_id": "pro_demo_manuella",
            "code": "MANUELLA-DEMO10",
            "discount_pct": 10,
            "until": None,
            "conditions": "Démo : code fictif",
        }
    ]


def local_challenge() -> dict:
    return {
        "challenge_id": "sim_chl_demo",
        "title": "7 jours avec Manuella",
        "description": "Porte au moins 1 pièce(s) de Manuella ou d'une autre marque tunisienne chaque jour "
        "pendant 7 jours, sans répéter une tenue.",
        "rules": [{"type": "local_brand", "params": {"min": 1}}, {"type": "no_repeat", "params": {}}],
        "duration_days": 7,
        "tags": ["local", "tunisie"],
        "sponsor": "Manuella",
        "participants": 0,
        "pro_id": "pro_demo_manuella",
        "shop": "Manuella",
        "pieces": [],
        "sources": {"m15": "mock", "m7": "real"},
        "created_at": _AT,
        "ends_on": "2026-10-27",
        "status": "active",
        "ended_at": None,
    }
