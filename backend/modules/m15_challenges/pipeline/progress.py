"""Progress, streak, points and badges for one user in one challenge."""

POINTS_PER_VALID_DAY = 10
STREAK_BONUS = 5  # every 3 consecutive valid days
COMPLETION_BONUS = 20


def streak(entries: list[dict]) -> int:
    """Consecutive valid days ending at the latest logged day."""
    by_day = {e["day"]: e["valid"] for e in entries}
    if not by_day:
        return 0
    d, n = max(by_day), 0
    while by_day.get(d):
        n += 1
        d -= 1
    return n


def best_streak(entries: list[dict]) -> int:
    best = cur = 0
    by_day = {e["day"]: e["valid"] for e in entries}
    for d in range(1, (max(by_day) if by_day else 0) + 1):
        cur = cur + 1 if by_day.get(d) else 0
        best = max(best, cur)
    return best


def run(entries: list[dict], duration: int) -> dict:
    valid = sum(1 for e in entries if e["valid"])
    logged_days = {e["day"] for e in entries}
    best = best_streak(entries)
    completed = valid >= duration
    points = (
        valid * POINTS_PER_VALID_DAY + (best // 3) * STREAK_BONUS + (COMPLETION_BONUS if completed else 0)
    )
    badges = []
    if valid >= 1:
        badges.append("Starter")
    if best >= 3:
        badges.append("On a roll")
    if completed:
        badges.append("Finisher")
    next_day = next((d for d in range(1, duration + 1) if d not in logged_days), None)
    return {
        "days_logged": len(logged_days),
        "valid_days": valid,
        "streak": streak(entries),
        "completion": round(min(1.0, valid / duration), 3),
        "points": points,
        "badges": badges,
        "next_day": next_day,
    }
