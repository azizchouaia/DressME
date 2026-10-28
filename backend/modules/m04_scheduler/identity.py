CARD = {
    "name": "calendar",
    "version": "1.0.0",
    "owner": "BO1/BO2",
    "module": "M4",
    "agent": "stylist",
    "role": "Skill of stylist. Plans outfits on a calendar and sends reminders.",
    "rules": ["The orchestrator calls stylist, not this module."],
    "when_to_use": [],
    "when_not_to_use": ["Call stylist."],
    "skills": {"schedule": "M4 reminders", "calendar": "M4 outfit days"},
}
