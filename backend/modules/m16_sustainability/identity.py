CARD = {
    "name": "sustainability",
    "version": "1.0.0",
    "owner": "BO3",
    "module": "M16",
    "agent": "trips",
    "role": "Skill of trips. Cost per wear and the impact of using pieces the person already owns.",
    "rules": ["The orchestrator calls trips, not this module."],
    "when_to_use": [],
    "when_not_to_use": ["Call trips."],
    "skills": {"score": "M16 cost per wear"},
}
