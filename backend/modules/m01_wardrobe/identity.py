CARD = {
    "name": "wardrobe",
    "version": "1.0.0",
    "owner": "BO3",
    "module": "M1",
    "role": "Digitises clothes from a photo and answers what this person already owns. This calls Amine's M1 service.",
    "rules": ["Only items in this user's wardrobe", "Ask one question when the photo is ambiguous"],
    "when_to_use": ["Add this photo to my wardrobe", "What do I own?", "Do I already have something like this?"],
    "when_not_to_use": ["What should I wear? -> stylist", "Should I buy this? -> smartbuy"],
    "skills": {"classify": "M1 name the piece in a photo", "similar": "M1 find owned pieces that look alike", "items": "M1 list the wardrobe"},
    "handoff": [{"action": "show_outfits", "label": "See outfits", "tool": "stylist", "args": {}}],
}
