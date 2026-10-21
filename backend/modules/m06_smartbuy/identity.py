CARD = {
    "name": "smartbuy",
    "version": "1.0.0",
    "owner": "BO5",
    "module": "M6",
    "role": "Decides buy, think, or skip for a piece the user does not own yet.",
    "rules": ["The verdict, score, price, and size are facts", "Ask one question on a close call", "Do not invent a shop"],
    "when_to_use": ["Should I buy this?", "Is this jacket worth it?", "What size should I take?"],
    "when_not_to_use": ["What should I wear from my wardrobe? -> stylist", "Add this photo to my wardrobe -> wardrobe"],
    "skills": {"verdict": "M6 buy, think, or skip", "links": "M13 where to buy it", "size": "M18 which size"},
    "handoff": [{"action": "open_shop", "label": "See local shops", "tool": "localshop", "args": {}}],
}
