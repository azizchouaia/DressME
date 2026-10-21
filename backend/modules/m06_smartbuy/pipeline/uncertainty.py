"""Idea 3 — 'I'm not sure' zone: when the decision is borderline, ask ONE question instead of guessing."""


def check(dec: dict, facts: dict, cfg: dict, ai_confidence: float | None) -> dict:
    band = cfg.get("uncertain_band", 5)
    s = dec["score"]
    reasons = []
    if ai_confidence is not None and ai_confidence < cfg.get("min_ai_confidence", 0.5):
        return {"uncertain": True, "question_key": "confirm_type",
                "question": f"I'm not sure about the photo: is it really a {facts['colour']} {facts['subcategory']}?"}
    if facts["red"]["is_duplicate"]:
        return {"uncertain": False, "question": None, "question_key": None}
    if dec["probabilities"]:
        top = max(dec["probabilities"].values())
        if top < cfg.get("min_probability", 0.55):
            reasons.append("close call")
    elif abs(s - cfg["buy_threshold"]) < band or abs(s - cfg["skip_threshold"]) < band:
        reasons.append("close call")
    if not reasons:
        return {"uncertain": False, "question": None, "question_key": None}
    if not facts["gap"] and not facts.get("need_for_occasion"):
        return {"uncertain": True, "question_key": "need_for_occasion",
                "question": "It's a close call. Do you need it for a specific event or occasion?"}
    return {"uncertain": True, "question_key": None,
            "question": "It's a close call: sleep on it, and check if you'll wear it at least twice a month."}
