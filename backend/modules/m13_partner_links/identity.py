CARD = {
    "name": "links",
    "version": "1.0.0",
    "owner": "BO5",
    "module": "M13",
    "agent": "smartbuy",
    "role": "Skill of smartbuy. Shop links and promo codes for a piece that was judged worth buying.",
    "rules": ["The orchestrator calls smartbuy, not this module."],
    "when_to_use": [],
    "when_not_to_use": ["Call smartbuy. A shop search with no verdict goes to localshop."],
    "skills": {"links": "M13 partner links"},
}
