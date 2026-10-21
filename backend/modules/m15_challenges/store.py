"""Challenges, participations, posts and likes. Memory store for week-1 mocks; a Postgres store can replace it
later with the same methods (tables: challenge, participation, entry, post, post_like)."""

from datetime import UTC, datetime

from .contract import Challenge, Comment, Post


class MemoryChallengeStore:
    def __init__(self, seed: list[dict] | None = None):
        self.challenges: dict[str, Challenge] = {}
        self.participations: dict[tuple[str, str], dict] = {}
        self.posts: dict[str, Post] = {}
        self.likes: dict[str, set[str]] = {}
        self.comments: dict[str, list[Comment]] = {}
        for c in seed or []:
            self.add_challenge(Challenge.model_validate(c))

    # challenges
    def add_challenge(self, ch: Challenge) -> None:
        self.challenges[ch.challenge_id] = ch

    def get_challenge(self, challenge_id: str) -> Challenge | None:
        return self.challenges.get(challenge_id)

    def participants(self, challenge_id: str) -> list[str]:
        return [u for (u, c) in self.participations if c == challenge_id]

    # participation
    def get_participation(self, user_id: str, challenge_id: str) -> dict | None:
        return self.participations.get((user_id, challenge_id))

    def join(self, user_id: str, challenge_id: str) -> dict:
        key = (user_id, challenge_id)
        if key not in self.participations:
            self.participations[key] = {"joined_at": datetime.now(UTC), "entries": []}
        return self.participations[key]

    def add_entry(self, user_id: str, challenge_id: str, entry: dict) -> None:
        self.participations[(user_id, challenge_id)]["entries"].append(entry)

    # posts
    def add_post(self, post: Post) -> None:
        self.posts[post.post_id] = post
        self.likes[post.post_id] = set()

    def toggle_like(self, post_id: str, user_id: str) -> int:
        s = self.likes[post_id]
        s.symmetric_difference_update({user_id})
        self.posts[post_id] = self.posts[post_id].model_copy(update={"likes": len(s)})
        return len(s)

    def add_comment(self, c: Comment) -> int:
        self.comments.setdefault(c.post_id, []).append(c)
        n = len(self.comments[c.post_id])
        self.posts[c.post_id] = self.posts[c.post_id].model_copy(update={"comments": n})
        return n

    def list_comments(self, post_id: str) -> list[Comment]:
        return list(self.comments.get(post_id, []))

    def list_posts(self, challenge_id: str | None = None) -> list[Post]:
        posts = [p for p in self.posts.values() if challenge_id is None or p.challenge_id == challenge_id]
        return sorted(posts, key=lambda p: p.created_at, reverse=True)
