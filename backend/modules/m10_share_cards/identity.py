CARD = {
    "name": "share",
    "version": "1.0.0",
    "owner": "BO7",
    "module": "M10",
    "role": "Makes a card the user can send of an outfit, a try-on, or a recap.",
    "rules": ["The card shows only pieces and stats the caller passed", "Do not change the outfit"],
    "when_to_use": ["Share this look", "Make a card of this outfit", "A recap I can send"],
    "when_not_to_use": ["Join a challenge -> challenges", "What should I wear? -> stylist"],
    "skills": {"card": "M10 image, caption, and referral link"},
    "handoff": [{"action": "challenge", "label": "Enter a challenge", "tool": "challenges", "args": {}}],
}
