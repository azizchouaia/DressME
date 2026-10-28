CARD = {
    "name": "wearlog",
    "version": "1.0.0",
    "owner": "BO1/BO2",
    "module": "M3",
    "agent": "stylist",
    "role": "Skill of stylist. Records what was worn and whether a piece is available.",
    "rules": ["The orchestrator calls stylist, not this module."],
    "when_to_use": [],
    "when_not_to_use": ["Call stylist."],
    "skills": {"worn": "M3 log a worn outfit", "stats": "M3 how often pieces are worn"},
}
