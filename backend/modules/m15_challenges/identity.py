CARD = {
    "name": "challenges",
    "version": "1.0.0",
    "owner": "BO7",
    "module": "M15",
    "role": "Lists style challenges, lets the user join, and checks a daily outfit against the rules.",
    "rules": ["Points and the leaderboard come from the challenge rules", "Do not mark a day complete if the rules fail"],
    "when_to_use": ["What challenges can I join?", "Log today's outfit", "Show the leaderboard"],
    "when_not_to_use": ["Share a picture -> share", "What should I wear? -> stylist"],
    "skills": {"challenges": "M15 join, log, progress, leaderboard"},
    "handoff": [{"action": "share", "label": "Share this entry", "tool": "share", "args": {}}],
}
