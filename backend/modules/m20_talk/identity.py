CARD = {
    "name": "talk",
    "version": "1.0.0",
    "owner": "BO8",
    "module": "M20",
    "role": "Discusses a look with one person and writes a stated preference back into that person's taste.",
    "rules": [
        "Groq chooses the words",
        "A score is quoted from taste and is never changed here",
        "A new preference is saved on this user only",
    ],
    "when_to_use": [
        "Why was this look chosen?",
        "Talk about what I like",
        "Remember that I want more linen",
    ],
    "when_not_to_use": [
        "Rank pieces from memory -> taste",
        "Build an outfit from owned clothes -> stylist",
        "Give the buy verdict and the price -> smartbuy",
        "Show it on the body -> tryon",
    ],
    "skills": {"discuss": "M20 explain from taste memory", "remember": "M20 write a stated like or dislike"},
    "handoff": [
        {"action": "rank", "label": "Rank with my taste", "tool": "taste", "args": {}},
        {"action": "build_outfit", "label": "Build the outfit", "tool": "stylist", "args": {}},
        {"action": "check_buy", "label": "Check the purchase", "tool": "smartbuy", "args": {}},
    ],
}
