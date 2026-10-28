"""Card of the stylist agent (BO1/BO2): the LLM agent that uses M2 / M3 / M4 / M9 / M17 as its tools."""

CARD = {
    "name": "stylist",
    "version": "1.0.0",
    "owner": "BO1/BO2",
    "module": "M2",
    "role": "Builds outfits from the user's own wardrobe for a day, an occasion, the weather or a mood; plans the week; "
            "logs what was worn; builds a capsule.",
    "rules": ["Only pieces the user owns", "Pieces in the laundry are excluded", "Ask one question when the occasion is missing"],
    "when_to_use": ["What do I wear today / tomorrow?", "Complete this outfit", "Something for a wedding",
                    "Plan my week", "I wore this", "Build me a capsule"],
    "when_not_to_use": ["Should I buy this? -> smartbuy", "Find a shop -> localshop", "Add a photo of my clothes -> wardrobe",
                        "Show it on my avatar -> tryon"],
    "skills": {
        "recommend": "M2 rank outfits",
        "wearlog": "M3 what was worn",
        "calendar": "M4 plan the week",
        "capsule": "M17 a small set of pieces that combine",
    },
    "handoff": [{"action": "show_on_me", "label": "Show it on me", "tool": "tryon", "args": {}}],
}
