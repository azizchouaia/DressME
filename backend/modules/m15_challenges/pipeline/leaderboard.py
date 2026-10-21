"""Leaderboard that rewards consistency first and popularity second, without being gamed by one viral post.

score = 10 × valid_days + 5 × bayes_likes
bayes_likes = (likes + m × C) / (posts + m)
  C = mean likes per post over the challenge, m = prior weight (default 3 posts).
The like average of a user with few posts is pulled towards the community mean (Bayesian average, as used by
rating sites), so one lucky viral post cannot beat a week of steady, valid entries.
"""


def bayes_average(likes: int, posts: int, mean: float, m: float = 3.0) -> float:
    return (likes + m * mean) / (posts + m) if posts + m else 0.0


def run(rows: list[dict], m: float = 3.0) -> list[dict]:
    """rows: [{"user_id", "valid_days", "likes", "posts"}] → ranked rows with "score" and "rank"."""
    total_posts = sum(r["posts"] for r in rows)
    mean = sum(r["likes"] for r in rows) / total_posts if total_posts else 0.0
    scored = []
    for r in rows:
        avg = bayes_average(r["likes"], r["posts"], mean, m)
        score = 10 * r["valid_days"] + 5 * avg
        scored.append({**r, "score": round(score, 2)})
    scored.sort(key=lambda r: (-r["score"], -r["valid_days"], r["user_id"]))
    for i, r in enumerate(scored, 1):
        r["rank"] = i
    return scored
