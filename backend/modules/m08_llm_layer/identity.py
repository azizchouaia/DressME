CARD = {
    "name": "llm",
    "version": "1.0.0",
    "owner": "BO8",
    "module": "M8",
    "agent": "orchestrator",
    "role": "Turns a sentence into JSON and writes the explanation. The orchestrator uses it. It is not an agent the planner calls.",
    "rules": ["The model chooses words", "It does not choose the verdict, the score, the price, or the size"],
    "when_to_use": [],
    "when_not_to_use": ["Any user need is an agent: wardrobe, stylist, profile, smartbuy, localshop, share, challenges, trips, tryon"],
    "skills": {"parse": "M8 sentence to JSON", "explain": "M8 why this result"},
}
