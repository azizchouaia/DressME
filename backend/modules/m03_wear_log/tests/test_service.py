import datetime as dt

import pytest

from modules.m03_wear_log import service

T = dt.date.today()


def d(days: int) -> str:
    return (T - dt.timedelta(days=days)).isoformat()


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("M03_DATABASE_URL", f"sqlite:///{(tmp_path / 'm03.sqlite').as_posix()}")


def call(fn, **payload):
    return fn({"user_id": "u1", "payload": payload})["result"]


def by_id(items):
    return {x["item_id"]: x for x in items}


def test_worn_then_stats():
    call(service.worn, item_ids=["top", "jeans", "shoes"], date=d(10))
    call(service.worn, item_ids=["top", "skirt"], date=d(2))
    res = call(service.stats, item_ids=["top", "jeans", "shoes", "skirt", "coat"])
    st = by_id(res["items"])
    assert st["top"]["wear_count"] == 2 and st["top"]["days_since_worn"] == 2
    assert st["jeans"]["days_since_worn"] == 10
    assert st["coat"]["days_since_worn"] is None
    assert res["summary"]["never_worn"] == ["coat"]
    assert res["summary"]["worn_30d"] == 4 and res["summary"]["utilisation_30d"] == 0.8


def test_users_are_isolated():
    call(service.worn, item_ids=["top"])
    other = service.stats({"user_id": "u2", "payload": {}})["result"]
    assert other["items"] == []


def test_auto_laundry_only_for_clothes():
    cats = {"top": "top", "shoes": "shoes"}
    for k in range(3):
        r = call(
            service.worn,
            item_ids=["top", "shoes"],
            date=d(3 - k),
            auto_laundry_after=3,
            laundry_categories=cats,
        )
    assert r["moved_to_laundry"] == ["top"]
    states = call(service.states)
    assert states["unavailable"] == ["top"]
    st = by_id(states["items"])
    assert st["shoes"]["status"] == "available" and st["shoes"]["wears_since_wash"] == 3


def test_wearing_a_piece_brings_it_back():
    call(service.status, item_ids=["top"], status="laundry")
    call(service.worn, item_ids=["top", "jeans"])
    assert call(service.states)["unavailable"] == []


def test_unworn_undoes_the_log():
    e = call(service.worn, item_ids=["top", "jeans"])["entry"]
    assert call(service.unworn, entry_id=e["entry_id"])["removed"] is True
    assert call(service.history)["entries"] == []
    assert by_id(call(service.states)["items"])["top"]["wears_since_wash"] == 0


def test_lent_and_reminders():
    call(service.status, item_ids=["blazer"], status="lent", lent_to="Sarra", expected_back=d(1))
    call(service.status, item_ids=["hoodie"], status="laundry")
    st = by_id(call(service.states, today=(T + dt.timedelta(days=4)).isoformat())["items"])
    assert st["blazer"]["reminder"] == "lent_overdue" and st["blazer"]["lent_to"] == "Sarra"
    assert st["hoodie"]["reminder"] == "back_in_closet?"
    assert call(service.laundry_done)["back_in_closet"] == ["hoodie"]
    assert call(service.states)["unavailable"] == ["blazer"]


def test_history_filters_and_posted():
    call(service.worn, item_ids=["a", "b"], date=d(40))
    e = call(service.worn, item_ids=["a", "c"], date=d(5))["entry"]
    call(service.posted, entry_id=e["entry_id"])
    assert len(call(service.history, since=d(30))["entries"]) == 1
    assert len(call(service.history, item_id="a")["entries"]) == 2
    log = service.wear_log_for("u1")
    assert log[0]["date"] == T - dt.timedelta(days=5) and log[0]["posted"] is True
    assert log[0]["item_ids"] == ["a", "c"] and log[0]["outfit_key"] == "a+c"


def test_forgotten_most_dormant_first():
    call(service.worn, item_ids=["a"], date=d(100))
    call(service.worn, item_ids=["b"], date=d(70))
    call(service.worn, item_ids=["c"], date=d(3))
    out = call(service.forgotten, item_ids=["a", "b", "c", "z"], days=60)["items"]
    assert [x["item_id"] for x in out] == ["z", "a", "b"]


def test_recap_month():
    first = T.replace(day=1)
    prev = first - dt.timedelta(days=3)
    call(service.worn, item_ids=["a", "b"], date=prev.isoformat())
    call(service.worn, item_ids=["a", "b"], date=first.isoformat())
    call(service.worn, item_ids=["a", "b"], date=first.isoformat())
    call(service.worn, item_ids=["c"], date=first.isoformat(), posted=True)
    r = call(service.recap, month=first.strftime("%Y-%m"), item_ids=["a", "b", "c", "d"])
    assert r["wears"] == 5 and r["distinct_pieces"] == 3 and r["utilisation"] == 0.75
    assert r["first_time_worn"] == ["c"]
    assert r["repeated_outfits"] == [{"item_ids": ["a", "b"], "times": 2}]
    assert r["posted_looks"] == 1 and r["days_logged"] == 1


def test_seed_and_reset():
    n = service.seed("u1", [{"date": T, "item_ids": ["a", "b"]}, {"date": T, "item_ids": ["c"]}])
    assert n == 2 and service.has_data("u1")
    service.reset("u1")
    assert not service.has_data("u1")
