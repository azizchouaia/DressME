CARD = {
    "name": "taste",
    "version": "1.0.0",
    "owner": "BO8",
    "module": "M19",
    "role": "Remembers what this person likes and ranks an outfit or a purchase from that memory.",
    "rules": [
        "One FashionCLIP model for every user",
        "Each user has their own memory",
        "A score from this agent stays as returned",
    ],
    "when_to_use": [
        "What fits what I already like?",
        "Rank these pieces for me",
        "Does this purchase match my taste?",
    ],
    "when_not_to_use": [
        "Build an outfit only from clothes I own -> stylist",
        "Give the buy verdict and the price -> smartbuy",
        "Show it on my body -> tryon",
    ],
    "skills": {},
    "handoff": [
        {"action": "build_outfit", "label": "Build the outfit", "tool": "stylist", "args": {}},
        {"action": "check_buy", "label": "Check the purchase", "tool": "smartbuy", "args": {}},
    ],
}
