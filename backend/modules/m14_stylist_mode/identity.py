"""M14 is a skill of the BO6 agent `localshop` (one agent per BO): the orchestrator calls localshop, never
this module, so M14 ships no tool.py. The card says so; it is served at GET /m14/identity.
"""

CARD = {
    "name": "boutique",
    "version": "1.0.0",
    "owner": "BO6",
    "module": "M14",
    "agent": "localshop",
    "role": "Skill of localshop. The professional side: stylists and Tunisian boutiques, their clients "
    "(with consent), the boutique demand dashboard and the hand-off from the assistant to a human stylist.",
    "rules": [
        "The orchestrator calls localshop, not this module.",
        "A pro sees a client's data only after the client accepted; the client can revoke it.",
        "The dashboard shows aggregates only (no user id, groups under min_group hidden).",
        "The BO6 LLM (qwen2.5:7b) writes the stylist's summary sentence and the boutique tips; numbers stay "
        "from the code.",
    ],
    "when_to_use": [],
    "when_not_to_use": ["Call localshop."],
    "skills": {
        "accounts": "F1 stylist / boutique accounts (a boutique = a shop of the M7 catalogue)",
        "clients": "F2 client link with consent + client brief",
        "review": "F3 stylist corrections of the style profile -> M5",
        "looks": "F4 stylist sends a look to a client (M2 score + M10 card)",
        "instore": "F5 in-store sales assistant (M6 verdict on the client's wardrobe)",
        "dashboard": "F6 boutique demand dashboard (themes, unmet demand, prices, trends)",
        "handoff": "F7 hand-off from the assistant to a human stylist",
    },
}
