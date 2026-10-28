"""Memory of the agents: SQLite long-term memory (survives a restart) and the coach's user memory."""

from modules.m10_share_cards.memory import SqliteShareStore
from modules.m15_challenges.agent import CONFIG, ChallengesAgent
from modules.m15_challenges.memory import CoachMemory, SqliteChallengeStore, connect
from modules.m15_challenges.pipeline import coach


class FakeShare:
    async def __call__(self, payload: dict) -> dict:
        return {"image_url": "/m10/cards/c/image", "share_url": "https://dressme.tn/s/c", "caption": "ok"}


def _agent(path):
    con = connect(str(path))
    return ChallengesAgent(
        store=SqliteChallengeStore(CONFIG.get("seed", []), con=con), coach_memory=CoachMemory(con),
        share_agent=FakeShare(),
    )  # fmt: skip


async def test_progress_survives_a_restart(tmp_path):
    db = tmp_path / "memory.sqlite"
    a = _agent(db)
    w = {g.item_id: g for g in a.wardrobe.items("amen")}
    outfit = [next(i for i, g in w.items() if g.category.value == c) for c in ("top", "bottom", "shoes")]
    await a({"user_id": "amen", "action": "join", "challenge_id": "ch_7x7"})
    assert (await a.submit("amen", "ch_7x7", outfit)).valid
    b = _agent(db)  # "server restarted": a new agent on the same database
    assert b.progress("amen", "ch_7x7").valid_days == 1
    assert len(b.store.list_posts("ch_7x7")) == 1
    assert b.coach_memory.recall("amen", "ch_7x7")["recent"][0]["day"] == 1


def test_coach_skips_tips_already_given_and_names_recurring_problems(monkeypatch):
    from modules.m10_share_cards.pipeline import llm

    monkeypatch.setattr(llm, "complete", lambda *a, **k: None)
    kw = dict(challenge="Monochrome week", rule_types=["color_theme"], day=3, valid=False,
              violations=["red chechia is red, not in the theme"], suggestion=[], probability=0.3,
              risk="high_risk", streak=0)  # fmt: skip
    first = coach.advise(**kw)
    given = [d["id"] for d in first["retrieved"]]
    recent = [{"day": 2, "valid": False, "message": "x"}]
    mem = {"tips_given": given, "issues": {"color_theme": 2}, "recent": recent}
    second = coach.advise(**kw, memory=mem, broken_rules=["color_theme"])
    assert not set(given) & {d["id"] for d in second["retrieved"]} or len(second["retrieved"]) == 1
    assert "3 times" in second["message"]
    assert "Memory (earlier days" in second["prompt"] and "broken 3 times" in second["prompt"]


def test_share_memory_survives_a_restart(tmp_path):
    db = str(tmp_path / "share.sqlite")
    s = SqliteShareStore(db)
    s.save_card({"card_id": "c1", "short_code": "abc1234", "user_id": "u"}, b"png")
    s.add_open("abc1234", "whatsapp")
    s.add_signup("abc1234", "friend1")
    t = SqliteShareStore(db)
    cards, opens, signups = t.events()
    assert len(cards) == 1 and len(opens) == 1 and signups[0]["channel"] == "whatsapp"
    assert t.get_png("c1") == b"png"
