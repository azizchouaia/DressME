CARD = {
    "name": "size",
    "version": "1.0.0",
    "owner": "BO5",
    "module": "M18",
    "agent": "smartbuy",
    "role": "Skill of smartbuy. Which size to take in a brand, from measurements or from how owned pieces fit.",
    "rules": ["The orchestrator calls smartbuy, not this module."],
    "when_to_use": [],
    "when_not_to_use": ["Call smartbuy."],
    "skills": {"advise": "M18 size advice"},
}
