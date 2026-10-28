CARD = {
    "name": "recommend",
    "agent": "stylist",
    "version": "1.0.0",
    "owner": "BO1/BO2",
    "module": "M2",
    "role": "Skill of stylist. Ranks outfits from the user's own wardrobe for a day, an occasion, or the weather.",
    "rules": ["Only pieces the user owns", "Ask one question when the occasion is missing"],
    "when_to_use": ["What do I wear today?", "Complete this outfit", "Something for a wedding"],
    "when_not_to_use": ["Should I buy this? -> smartbuy", "Find a shop -> localshop", "Add a photo of my clothes -> wardrobe"],
    "skills": {
        "recommend": "M2 rank outfits",
        "wearlog": "M3 what was worn",
        "calendar": "M4 plan the week",
        "capsule": "M17 a small set of pieces that combine",
    },
    "handoff": [{"action": "show_on_me", "label": "Show it on me", "tool": "tryon", "args": {}}],
}
