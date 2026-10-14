"""M4 scheduling logic with M2 mocked (no models needed), a real M3 and temporary SQLite files."""

import datetime as dt

import pytest

from modules.m04_scheduler import service, tunisia

T = dt.date(2026, 10, 14)  # a Wednesday


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("M02_USE_MOCK", "true")
    monkeypatch.setenv("M03_USE_MOCK", "false")
    monkeypatch.setenv("M03_DATABASE_URL", f"sqlite:///{(tmp_path / 'm3.sqlite').as_posix()}")
    monkeypatch.setenv("M04_DATABASE_URL", f"sqlite:///{(tmp_path / 'm4.sqlite').as_posix()}")
    monkeypatch.setattr(
        service, "_weather", lambda city, day: {"temp_c": 20.0, "condition": "clear", "source": "open-meteo"}
    )


def call(fn, **payload):
    return fn({"user_id": "u1", "payload": payload})["result"]


def at(hhmm: str, day: dt.date = T) -> str:
    return f"{day.isoformat()}T{hhmm}"


def jobs(res) -> list[str]:
    return [r["job"] for r in res["runs"]]


def test_prefs_defaults_update_and_validation():
    r = call(service.schedule, now=at("06:00"))
    assert r["prefs"]["morning_time"] == "05:00" and r["prefs"]["weekday_occasions"][5] == "casual"
    assert r["next_runs"]["notify"] == at("07:00") and r["next_runs"]["morning"] == at(
        "05:00", T + dt.timedelta(1)
    )
    r = call(service.schedule, set={"city": "Sousse", "notify_time": "06:30"})
    assert r["prefs"]["city"] == "Sousse" and r["prefs"]["notify_time"] == "06:30"
    with pytest.raises(ValueError):
        call(service.schedule, set={"weekday_occasions": ["gala"] * 7})


def test_jobs_run_once_in_their_window():
    call(service.schedule)
    assert jobs(call(service.run, job="due", now=at("04:30"))) == []
    assert jobs(call(service.run, job="due", now=at("05:05"))) == ["morning", "events"]
    assert jobs(call(service.run, job="due", now=at("05:40"))) == []  # already ran today
    assert jobs(call(service.run, job="due", now=at("07:01"))) == ["notify"]
    assert jobs(call(service.run, job="due", now=at("23:30"))) == []  # evening window (20:00-23:00) missed
    assert jobs(call(service.run, job="due", now=at("20:10"))) == ["evening"]
    n = call(service.notifications)
    assert [x["kind"] for x in n["notifications"]] == ["tomorrow", "daily"] and n["unread"] == 2


def test_today_is_cached_and_tomorrow_approval_is_locked():
    call(service.run, job="evening", now=at("20:00"))
    tom = T + dt.timedelta(days=1)
    call(service.approve, date=tom.isoformat())
    before = call(service.day, date=tom.isoformat())
    res = call(service.run, job="morning", now=at("05:00", tom))
    assert res["runs"][0]["result"]["kept"] == "approved the night before"
    after = call(service.day, date=tom.isoformat())
    assert after["computed_at"] == before["computed_at"] and after["approved"] is True


def test_occasion_priority_event_holiday_weekday():
    call(service.event_add, date="2026-10-16", title="Client meeting", occasion="work")
    call(service.event_add, date="2026-10-17", title="Cousin's wedding")
    days = {d["date"]: d for d in call(service.calendar, start=T.isoformat(), days=7)["days"]}
    assert (
        days["2026-10-14"]["occasion"] == "work"
        and days["2026-10-14"]["occasion_reason"] == "Wednesday default"
    )
    assert days["2026-10-15"]["occasion_reason"] == "Evacuation Day"  # Tunisian holiday
    assert days["2026-10-16"]["occasion_reason"] == "Client meeting"
    assert days["2026-10-17"]["occasion"] == "event"
    assert days["2026-10-18"]["occasion"] == "casual"  # Sunday


def test_aid_is_an_event_and_dates_are_right():
    h = {x["title"]: x["date"] for x in tunisia.holidays(dt.date(2026, 1, 1), dt.date(2026, 12, 31))}
    assert h["Aid el Fitr (day 1)"] == dt.date(2026, 3, 20)
    assert h["Aid el Kebir (Aid el Adha) (day 1)"] == dt.date(2026, 5, 27)
    assert h["Independence Day"] == dt.date(2026, 3, 20)
    day = call(service.calendar, start="2026-05-27", days=1)["days"][0]
    assert day["occasion"] == "event" and day["holidays"][0]["approximate"] is True


def test_change_cycles_options_then_recomputes():
    v = call(service.day, date=T.isoformat())
    n = v["options"]
    for k in range(1, n):
        assert call(service.change, date=T.isoformat())["choice"] == k
    assert call(service.change, date=T.isoformat())["choice"] == 0  # new options


def test_event_countdown_shortlist_refresh_reminder():
    ev = call(service.event_add, date="2026-10-19", title="Wedding", remind_days=5)["event"]
    steps = lambda r: [e["step"] for e in r["runs"][0]["result"]["events"]]  # noqa: E731
    assert (
        steps(call(service.run, job="events", now=at("05:00", dt.date(2026, 10, 13)))) == []
    )  # 6 days before
    assert steps(call(service.run, job="events", now=at("05:00", dt.date(2026, 10, 14)))) == ["shortlist"]
    assert steps(call(service.run, job="events", now=at("05:00", dt.date(2026, 10, 15)))) == []
    assert steps(call(service.run, job="events", now=at("05:00", dt.date(2026, 10, 17)))) == [
        "refreshed with the forecast"
    ]
    assert steps(call(service.run, job="events", now=at("05:00", dt.date(2026, 10, 18)))) == ["reminder"]
    assert steps(call(service.run, job="events", now=at("05:00", dt.date(2026, 10, 18)))) == []
    kinds = [n["kind"] for n in call(service.notifications)["notifications"]]
    assert kinds == ["event_reminder", "event_shortlist"]
    assert call(service.event_delete, event_id=ev["event_id"])["deleted"] is True


def test_notification_wear_logs_in_m3_and_change():
    from modules.m03_wear_log import service as m3

    call(service.run, job="notify", now=at("07:00"))
    n = call(service.notifications)["notifications"][0]
    assert n["actions"] == ["wear", "change"] and n["body"].startswith("Today: ")
    r = call(service.notification_action, notif_id=n["notif_id"], action="wear")
    assert r["approved"] is True and r["logged"]["entry"]["date"] == T.isoformat()
    assert m3.history({"user_id": "u1", "payload": {}})["result"]["entries"][0]["source"] == "scheduled"
    assert call(service.notifications, status="acted")["notifications"][0]["action_taken"] == "wear"


def test_weather_tip_and_laundry_reminder(monkeypatch):
    from modules.m03_wear_log import service as m3

    def weather(city, day):
        return (
            {"temp_c": 22.0, "condition": "clear", "source": "open-meteo"}
            if day == T
            else {"temp_c": 13.0, "condition": "rain", "source": "open-meteo"}
        )

    monkeypatch.setattr(service, "_weather", weather)
    m3.status({"user_id": "u1", "payload": {"item_ids": ["m_top2"], "status": "laundry"}})
    # M3 stamps the status with the real date; the reminder comes after 3 days
    later = dt.date.today() + dt.timedelta(days=4)
    res = call(service.run, job="evening", now=at("20:00", later))["runs"][0]["result"]
    assert "laundry" in res and res["laundry"]["data"]["item_ids"] == ["m_top2"]
    monkeypatch.setattr(service, "_weather", weather)
    res = call(service.run, job="evening", now=at("20:00"))["runs"][0]["result"]
    assert res["weather_tip"]["title"] == "Rain tomorrow"
    back = call(
        service.notification_action,
        notif_id=call(service.notifications, status="unread")["notifications"][-1]["notif_id"],
        action="dismiss",
    )
    assert back["status"] == "read"


def test_widget_and_week_shapes():
    w = call(service.widget)
    assert w["deep_link"].startswith("dressme://today") and w["items"]
    wk = call(service.week, start=T.isoformat(), days=3)
    assert [d["date"] for d in wk["days"]] == ["2026-10-14", "2026-10-15", "2026-10-16"]
    assert [d["occasion"] for d in wk["days"]] == ["work", "casual", "work"]
