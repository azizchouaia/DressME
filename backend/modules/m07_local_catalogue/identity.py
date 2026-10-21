CARD = {
    "name": "localshop",
    "version": "1.0.0",
    "owner": "BO6",
    "module": "M7",
    "role": "Finds pieces sold by Tunisian shops, with prices in dinars.",
    "rules": ["Only shops and prices returned by the catalogue", "Ask the city when the request could be anywhere"],
    "when_to_use": ["Where can I buy this in Tunis?", "A linen shirt under 80 dinars", "Shops near me"],
    "when_not_to_use": ["Should I buy it? -> smartbuy", "What should I wear from what I own? -> stylist"],
    "skills": {"search": "M7 catalogue search", "boutique": "M14 stylist mode for a shop's clients"},
    "handoff": [{"action": "judge", "label": "Should I buy one of these?", "tool": "smartbuy", "args": {}}],
}
