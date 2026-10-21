CARD = {
    "name": "trips",
    "version": "1.0.0",
    "owner": "BO3",
    "module": "M11",
    "role": "Packs outfits for a trip and can score the cost and impact of wearing what the person already owns.",
    "rules": ["Prefer pieces the user already owns", "Ask the destination and the dates when they are missing"],
    "when_to_use": ["What do I pack for Tunis this weekend?", "A week in a cold city", "How costly is this habit to wear?"],
    "when_not_to_use": ["What should I wear today at home? -> stylist", "Should I buy a new coat? -> smartbuy"],
    "skills": {"plan": "M11 trip outfits", "sustainability": "M16 cost per wear"},
    "handoff": [{"action": "show_outfits", "label": "Pack from my wardrobe", "tool": "stylist", "args": {}}],
}
