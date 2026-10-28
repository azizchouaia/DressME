CARD = {
    "name": "profile",
    "version": "1.0.0",
    "owner": "BO4",
    "module": "M5",
    "role": "Remembers this person's taste, the gaps in the wardrobe, and how that taste changes.",
    "rules": ["A newer like or dislike replaces the older one on the same piece", "A person can keep more than one taste"],
    "when_to_use": ["What is my style?", "What am I missing?", "I loved this, remember it"],
    "when_not_to_use": ["What should I wear tomorrow? -> stylist", "Should I buy this? -> smartbuy"],
    "skills": {"profile": "M5 taste and goals", "gaps": "M5 missing types", "evolution": "M12 how the style changed"},
    "handoff": [{"action": "show_outfits", "label": "Dress in this taste", "tool": "stylist", "args": {}}],
}
