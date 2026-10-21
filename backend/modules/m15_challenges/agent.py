import math
import uuid
from datetime import UTC, datetime
from pathlib import Path

import yaml

from modules.m10_share_cards.contract import PipelineStep
from shared.base_agent import AgentError, BaseAgent
from shared.schemas import Garment

from .contract import (
    Challenge,
    ChallengeDraft,
    ChallengesInput,
    ChallengesOutput,
    ChallengeView,
    Comment,
    EntryResult,
    EntryView,
    LeaderboardRow,
    Nudge,
    Post,
    Progress,
)
from .pipeline import (
    coach,
    completion,
    feasibility,
    leaderboard,
    moderation,
    outfit,
    progress,
    recommend,
    rules,
    suggest,
)
from .store import MemoryChallengeStore
from .wardrobe import HttpWardrobe, MockWardrobe, WardrobeProvider

CONFIG = yaml.safe_load((Path(__file__).parent / "config.yaml").read_text())
DEFAULT_STYLE_TAGS = {"casual", "minimal"}  # until M5 (style profile) is live


class ChallengesAgent(BaseAgent[ChallengesInput, ChallengesOutput]):
    name = "challenges"
    description = (
        "Community style challenges (e.g. '7 days, 7 outfits', monochrome week, traditional Friday, "
        "local brand week): list or recommend challenges, join, log a daily outfit and check it against "
        "the rules, show progress, leaderboard and challenge posts."
    )
    input_model = ChallengesInput
    output_model = ChallengesOutput

    def __init__(
        self,
        config: dict | None = None,
        wardrobe: WardrobeProvider | None = None,
        store: MemoryChallengeStore | None = None,
        share_agent=None,
        coach_memory=None,
    ):
        super().__init__(config or CONFIG)
        self.store = store or MemoryChallengeStore(self.config.get("seed", []))
        # what the coach remembers per user and challenge (memory.CoachMemory); in-memory SQLite by default
        if coach_memory is None:
            from .memory import CoachMemory, connect

            coach_memory = CoachMemory(connect(":memory:"))
        self.coach_memory = coach_memory
        if wardrobe is None:
            wardrobe = (
                HttpWardrobe(self.config["wardrobe_url"])
                if self.config.get("wardrobe_source") == "http"
                else MockWardrobe()
            )
        self.wardrobe = wardrobe
        self._share = share_agent

    # ------------------------------------------------------------------ orchestrator entry point
    async def run(self, inp: ChallengesInput) -> ChallengesOutput:
        a = inp.action
        if a == "list":
            return ChallengesOutput(challenges=self.list_challenges(inp.user_id))
        if a == "recommend":
            return ChallengesOutput(challenges=self.recommend(inp.user_id))
        if a == "create":
            if inp.draft is None:
                raise AgentError("action 'create' needs a draft")
            return ChallengesOutput(challenges=[self.create_challenge(inp.user_id, inp.draft)])
        cid = self._require(inp.challenge_id)
        if a == "join":
            return ChallengesOutput(progress=self.join(inp.user_id, cid))
        if a == "submit":
            entry = await self.submit(inp.user_id, cid, inp.item_ids, inp.day, inp.caption, inp.share)
            return ChallengesOutput(entry=entry, progress=entry.progress)
        if a == "progress":
            return ChallengesOutput(progress=self.progress(inp.user_id, cid))
        if a == "leaderboard":
            return ChallengesOutput(leaderboard=self.leaderboard(cid))
        return ChallengesOutput(posts=self.feed(cid))

    # ------------------------------------------------------------------ queries
    def _require(self, challenge_id: str | None) -> str:
        if not challenge_id or self.store.get_challenge(challenge_id) is None:
            raise AgentError(f"Unknown challenge {challenge_id!r}")
        return challenge_id

    def _rules(self, ch: Challenge) -> list[dict]:
        return [r.model_dump() for r in ch.rules]

    def _view(self, ch: Challenge, user_id: str, wardrobe: list[Garment]) -> ChallengeView:
        score, reason = feasibility.run(self._rules(ch), ch.duration_days, wardrobe)
        return ChallengeView(
            **ch.model_dump(),
            participants=len(self.store.participants(ch.challenge_id)),
            joined=self.store.get_participation(user_id, ch.challenge_id) is not None,
            feasibility=round(score, 2),
            reason=reason,
        )

    def list_challenges(self, user_id: str) -> list[ChallengeView]:
        wardrobe = self.wardrobe.items(user_id)
        return [self._view(c, user_id, wardrobe) for c in self.store.challenges.values()]

    def user_style_tags(self, user_id: str) -> set[str]:
        """TODO(M5): read the style profile; the demo uses fixed tags."""
        return DEFAULT_STYLE_TAGS

    def user_completion_rate(self, user_id: str) -> float:
        """Share of the user's challenges finished (≥ 80 % valid days), smoothed; 0.5 for a new user."""
        joined = finished = 0
        for (u, cid), part in self.store.participations.items():
            ch = self.store.get_challenge(cid)
            if u != user_id or ch is None:
                continue
            joined += 1
            valid = sum(e["valid"] for e in part["entries"])
            finished += valid >= math.ceil(0.8 * ch.duration_days)
        return recommend.completion_rate(finished, joined)

    def recommend(self, user_id: str) -> list[ChallengeView]:
        """ML ranking (models/recommender.json); falls back to the hand formula if the model is missing."""
        views = [v.model_dump() for v in self.list_challenges(user_id)]
        ranked = recommend.run(
            views,
            self.user_style_tags(user_id),
            tuple(self.config["recommend_weights"]),
            user_rate=self.user_completion_rate(user_id),
        )
        return [ChallengeView.model_validate(v) for v in ranked]

    def create_challenge(self, user_id: str, draft: ChallengeDraft) -> ChallengeView:
        """A user, a stylist (M14) or a sponsoring brand (BO6) publishes a challenge (validated rules)."""
        rule_dicts = [r.model_dump() for r in draft.rules]
        errors = rules.validate(rule_dicts, draft.duration_days)
        if errors:
            raise AgentError("Invalid challenge: " + "; ".join(errors))
        if any(c.title.lower() == draft.title.lower() for c in self.store.challenges.values()):
            raise AgentError(f"A challenge called {draft.title!r} already exists")
        slug = "".join(ch if ch.isalnum() else "_" for ch in draft.title.lower()).strip("_")[:18]
        ch = Challenge(
            challenge_id=f"ch_{slug}_{uuid.uuid4().hex[:4]}",
            created_by=user_id,
            **draft.model_dump(),
        )
        self.store.add_challenge(ch)
        return self._view(ch, user_id, self.wardrobe.items(user_id))

    # ------------------------------------------------------------------ participation
    def join(self, user_id: str, challenge_id: str) -> Progress:
        self._require(challenge_id)
        self.store.join(user_id, challenge_id)
        return self.progress(user_id, challenge_id)

    def _previous(
        self, user_id: str, entries: list[dict], wardrobe: dict[str, Garment]
    ) -> list[tuple[int, list]]:
        """Valid entries only: a rejected day does not count, so its pieces can be used again."""
        return [
            (e["day"], [wardrobe[i] for i in e["item_ids"] if i in wardrobe]) for e in entries if e["valid"]
        ]

    async def submit(
        self,
        user_id: str,
        challenge_id: str,
        item_ids: list[str],
        day: int | None = None,
        caption: str | None = None,
        share: bool = True,
    ) -> EntryResult:
        ch = self.store.get_challenge(self._require(challenge_id))
        part = self.store.get_participation(user_id, challenge_id)
        if part is None:
            raise AgentError("Join the challenge before logging an outfit.")
        if not item_ids:
            raise AgentError("Pick the pieces you wore today.")

        wardrobe = {g.item_id: g for g in self.wardrobe.items(user_id)}
        unknown = [i for i in item_ids if i not in wardrobe]
        if unknown:
            raise AgentError(f"Not in your wardrobe: {', '.join(unknown)}")

        logged = {e["day"] for e in part["entries"]}
        day = day or progress.run(part["entries"], ch.duration_days)["next_day"]
        if day is None:
            raise AgentError("This challenge is already complete.")
        if day > ch.duration_days:
            raise AgentError(f"This challenge lasts {ch.duration_days} days.")
        if day in logged:
            raise AgentError(f"Day {day} is already logged.")

        steps = [
            PipelineStep(
                stage="input",
                method="data",
                name="Daily entry",
                detail=f"day {day}, {len(item_ids)} piece(s): {', '.join(item_ids)} · garments read from M1",
            )
        ]
        today = [wardrobe[i] for i in item_ids]
        problems = outfit.check(today)  # if/else: one pair of shoes, one hat, top + bottom or a one-piece…
        if problems:
            raise AgentError("This outfit cannot be worn: " + "; ".join(problems))
        steps.append(
            PipelineStep(
                stage="code",
                method="if/else",
                name="Outfit check",
                detail="one piece per slot, body covered (top + bottom or a one-piece)",
            )
        )
        previous = self._previous(user_id, part["entries"], wardrobe)
        broken = rules.run_by_rule(self._rules(ch), today, previous)
        violations = [v for _, v in broken]
        valid = not violations
        steps.append(
            PipelineStep(
                stage="code",
                method="if/else",
                name="Rule engine",
                detail=f"{len(ch.rules)} rule(s) checked: "
                + ("all passed" if valid else "; ".join(violations)),
            )
        )

        entry = {"day": day, "item_ids": item_ids, "valid": valid, "violations": violations, "post_id": None}
        self.store.add_entry(user_id, challenge_id, entry)
        prog = self.progress(user_id, challenge_id)
        steps.append(
            PipelineStep(
                stage="code",
                method="if/else",
                name="Progress, streak, points",
                detail=f"{prog.valid_days}/{ch.duration_days} valid, streak {prog.streak}, {prog.points} pts",
            )
        )
        m = completion.model()["metrics"]
        m_name = completion.model()["model"].replace("_", " ")
        steps.append(
            PipelineStep(
                stage="code",
                method="ML",
                name=f"Completion prediction ({m_name})",
                detail=f"P(finish) = {prog.completion_probability} → {prog.risk} · model AUC {m['auc']}",
            )
        )

        post = None
        if valid and share:
            post = await self._make_post(ch, user_id, day, today, caption, prog)
            entry["post_id"] = post.post_id
            prog = self.progress(user_id, challenge_id)
            steps.append(
                PipelineStep(
                    stage="code",
                    method="M10",
                    name="Share card (Share agent)",
                    detail=f"post {post.post_id} with card {post.card_image_url or 'unavailable'}",
                )
            )

        finisher = None
        if prog.next_day is None:  # last day logged: finisher card for the whole challenge
            finisher = await self._finisher_card(ch, user_id, part["entries"], wardrobe, prog)
            steps.append(
                PipelineStep(
                    stage="code",
                    method="M10",
                    name="Finisher card",
                    detail=(
                        f"challenge over: {prog.valid_days}/{ch.duration_days} valid days → recap card"
                        if finisher
                        else "card service unavailable"
                    ),
                )
            )

        nxt = previous + ([(day, today)] if valid else [])
        hint = suggest.run(self._rules(ch), list(wardrobe.values()), nxt) if prog.next_day else []
        steps.append(
            PipelineStep(
                stage="code",
                method="if/else",
                name="Next-day suggestion (greedy)",
                detail=(", ".join(hint) if hint else "none")
                + " · least-worn pieces that keep the rules valid",
            )
        )

        names = [wardrobe[i].subcategory or i for i in hint]
        mem = self.coach_memory.recall(user_id, challenge_id)  # long-term + short-term memory of the coach
        steps.append(
            PipelineStep(
                stage="code",
                method="memory",
                name="Coach memory (SQLite)",
                detail=f"{len(mem['tips_given'])} tip(s) already given, "
                + (", ".join(f"{r} ×{n}" for r, n in mem["issues"].items()) or "no rule broken before")
                + f", last {len(mem['recent'])} day(s) in the prompt",
            )
        )
        tip = coach.advise(
            challenge=ch.title,
            rule_types=[r.type for r in ch.rules],
            day=day,
            valid=valid,
            violations=violations,
            suggestion=names,
            probability=prog.completion_probability or 0.5,
            risk=prog.risk or "at_risk",
            streak=prog.streak,
            memory=mem,
            broken_rules=[r for r, _ in broken],
        )
        self.coach_memory.remember(
            user_id, challenge_id, day, valid=valid, tip_ids=[d["id"] for d in tip["retrieved"]],
            broken=broken, message=tip["message"], source=tip["source"],
        )  # fmt: skip
        steps.append(
            PipelineStep(
                stage="code",
                method="LLM · RAG",
                name="Retrieve coaching tips",
                detail=", ".join(f"{d['id']} ({d['score']})" for d in tip["retrieved"]) or "no match",
            )
        )
        steps.append(
            PipelineStep(
                stage="code",
                method="LLM · PE",
                name="Coach prompt",
                detail=(
                    "LLM wrote the message"
                    if tip["source"] == "llm"
                    else "no LLM configured in infra/.env → template message (if/else fallback)"
                ),
            )
        )
        steps.append(
            PipelineStep(
                stage="output",
                method="data",
                name="Entry result",
                detail="valid / violations, progress, P(finish), coach message, post + card, suggestion",
            )
        )
        return EntryResult(
            day=day,
            valid=valid,
            violations=violations,
            post=post,
            suggestion=hint,
            progress=prog,
            coach_message=tip["message"],
            coach_source=tip["source"],
            completion_card_url=(finisher or {}).get("image_url"),
            completion_share_url=(finisher or {}).get("share_url"),
            pipeline=steps,
            retrieved=tip["retrieved"],
            prompt=tip["prompt"],
        )

    async def _make_post(
        self, ch: Challenge, user_id: str, day: int, items: list[Garment], caption: str | None, prog: Progress
    ) -> Post:
        card = None
        try:
            share = self._share
            if share is None:
                from modules.m10_share_cards.singleton import share_agent as share
            card = await share(
                {
                    "user_id": user_id,
                    "kind": "challenge",
                    "format": "post",
                    "title": f"{ch.title} · Day {day}",
                    "subtitle": f"{prog.valid_days}/{ch.duration_days} valid days",
                    "caption": caption,
                    "source_id": f"{ch.challenge_id}:{user_id}:{day}",
                    "items": [
                        {
                            "item_id": g.item_id,
                            "category": g.category.value,
                            "label": g.subcategory,
                            "image": g.image_cutout,
                            "color_hex": max(g.colors, key=lambda c: c.share).hex if g.colors else None,
                            "brand": g.local_tag,
                        }
                        for g in items
                    ],
                    "stats": [
                        {"label": "day streak", "value": str(prog.streak)},
                        {"label": "points", "value": str(prog.points)},
                    ],
                }
            )
        except Exception:  # noqa: BLE001 — the post still exists if the card service is down
            card = None
        post = Post(
            post_id=f"post_{uuid.uuid4().hex[:10]}",
            user_id=user_id,
            challenge_id=ch.challenge_id,
            day=day,
            item_ids=[g.item_id for g in items],
            caption=caption or (card or {}).get("caption"),
            card_image_url=(card or {}).get("image_url"),
            share_url=(card or {}).get("share_url"),
            created_at=datetime.now(UTC),
        )
        self.store.add_post(post)
        return post

    async def _finisher_card(
        self, ch: Challenge, user_id: str, entries: list[dict], wardrobe: dict[str, Garment], prog: Progress
    ) -> dict | None:
        """Recap of the challenge: the most-used pieces + stats, as one M10 card (BO7 acquisition moment)."""
        counts: dict[str, int] = {}
        for e in entries:
            if e["valid"]:
                for i in e["item_ids"]:
                    counts[i] = counts.get(i, 0) + 1
        top = [wardrobe[i] for i in sorted(counts, key=counts.get, reverse=True) if i in wardrobe][:4]
        likes = sum(p.likes for p in self.store.list_posts(ch.challenge_id) if p.user_id == user_id)
        best = progress.best_streak(entries)
        done = prog.valid_days >= ch.duration_days
        try:
            share = self._share
            if share is None:
                from modules.m10_share_cards.singleton import share_agent as share
            return await share(
                {
                    "user_id": user_id,
                    "kind": "challenge",
                    "format": "story",
                    "title": f"{ch.title} · {'completed!' if done else 'finished'}",
                    "subtitle": f"{prog.valid_days}/{ch.duration_days} valid days · {len(counts)} pieces",
                    "source_id": f"{ch.challenge_id}:{user_id}:finisher",
                    "items": [
                        {
                            "item_id": g.item_id,
                            "category": g.category.value,
                            "label": g.subcategory,
                            "image": g.image_cutout,
                            "color_hex": max(g.colors, key=lambda c: c.share).hex if g.colors else None,
                            "brand": g.local_tag,
                        }
                        for g in top
                    ],
                    "stats": [
                        {"label": "valid days", "value": f"{prog.valid_days}/{ch.duration_days}"},
                        {"label": "best streak", "value": str(best)},
                        {"label": "points", "value": str(prog.points)},
                        {"label": "likes", "value": str(likes)},
                    ],
                }
            )
        except Exception:  # noqa: BLE001
            return None

    def progress(self, user_id: str, challenge_id: str) -> Progress:
        ch = self.store.get_challenge(self._require(challenge_id))
        part = self.store.get_participation(user_id, challenge_id)
        entries = part["entries"] if part else []
        p = progress.run(entries, ch.duration_days)
        prob = risk = None
        if part:  # ML: only for users who joined
            fit, _ = feasibility.run(self._rules(ch), ch.duration_days, self.wardrobe.items(user_id))
            likes = sum(x.likes for x in self.store.list_posts(challenge_id) if x.user_id == user_id)
            x = completion.features(
                fit, p["valid_days"], p["days_logged"], p["streak"], ch.duration_days, likes
            )
            prob = completion.predict(x)
            risk = completion.risk(prob)
        return Progress(
            challenge_id=challenge_id,
            user_id=user_id,
            duration_days=ch.duration_days,
            **p,
            entries=[EntryView(**e) for e in sorted(entries, key=lambda e: e["day"])],
            completion_probability=prob,
            risk=risk,
        )

    # ------------------------------------------------------------------ community
    def leaderboard(self, challenge_id: str) -> list[LeaderboardRow]:
        self._require(challenge_id)
        rows = []
        for user in self.store.participants(challenge_id):
            entries = self.store.get_participation(user, challenge_id)["entries"]
            posts = [p for p in self.store.list_posts(challenge_id) if p.user_id == user]
            rows.append(
                {
                    "user_id": user,
                    "valid_days": sum(e["valid"] for e in entries),
                    "likes": sum(p.likes for p in posts),
                    "posts": len(posts),
                }
            )
        ranked = leaderboard.run(rows, self.config.get("leaderboard_prior_posts", 3))
        return [
            LeaderboardRow(**{k: r[k] for k in ("rank", "user_id", "valid_days", "likes", "score")})
            for r in ranked
        ]

    def feed(self, challenge_id: str | None = None) -> list[Post]:
        return self.store.list_posts(challenge_id)

    def comment(self, post_id: str, user_id: str, text: str) -> Comment:
        """Comment on a post after if/else moderation (pipeline/moderation.py)."""
        if post_id not in self.store.posts:
            raise AgentError(f"Unknown post {post_id}")
        ok, reason = moderation.check(text)
        if not ok:
            raise AgentError(f"Comment refused: {reason}")
        c = Comment(
            comment_id=f"cm_{uuid.uuid4().hex[:10]}",
            post_id=post_id,
            user_id=user_id,
            text=text.strip(),
            created_at=datetime.now(UTC),
        )
        self.store.add_comment(c)
        return c

    def comments(self, post_id: str) -> list[Comment]:
        if post_id not in self.store.posts:
            raise AgentError(f"Unknown post {post_id}")
        return self.store.list_comments(post_id)

    def nudges(self, challenge_id: str, include_on_track: bool = False) -> list[Nudge]:
        """ML: participants with the lowest P(finish) first, each with a valid outfit for their next day."""
        ch = self.store.get_challenge(self._require(challenge_id))
        out = []
        for user in self.store.participants(challenge_id):
            prog = self.progress(user, challenge_id)
            if prog.next_day is None or prog.completion_probability is None:
                continue
            if prog.risk == "on_track" and not include_on_track:
                continue
            wardrobe = {g.item_id: g for g in self.wardrobe.items(user)}
            entries = self.store.get_participation(user, challenge_id)["entries"]
            hint = suggest.run(
                self._rules(ch), list(wardrobe.values()), self._previous(user, entries, wardrobe)
            )
            names = [wardrobe[i].subcategory or i for i in hint]
            pct = round(prog.completion_probability * 100)
            msg = (
                f"Day {prog.next_day} of {ch.title} is waiting"
                + (f": try {' + '.join(names)}." if names else ".")
                + (
                    " You are close, keep the streak!"
                    if prog.streak >= 2
                    else f" ({pct}% chance to finish today)"
                )
            )
            out.append(
                Nudge(
                    user_id=user,
                    next_day=prog.next_day,
                    completion_probability=prog.completion_probability,
                    risk=prog.risk,
                    suggestion=hint,
                    suggestion_names=names,
                    message=msg,
                )
            )
        return sorted(out, key=lambda n: n.completion_probability)

    def like(self, post_id: str, user_id: str) -> int:
        if post_id not in self.store.posts:
            raise AgentError(f"Unknown post {post_id}")
        return self.store.toggle_like(post_id, user_id)
