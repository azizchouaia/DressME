CARD = {
    "name": "boutique",
    "version": "1.0.0",
    "owner": "BO6",
    "module": "M14",
    "agent": "localshop",
    "role": "Skill of localshop. A shop's own stylist view of its clients.",
    "rules": ["The orchestrator calls localshop, not this module."],
    "when_to_use": [],
    "when_not_to_use": ["Call localshop."],
    "skills": {"clients": "M14 boutique clients"},
}
