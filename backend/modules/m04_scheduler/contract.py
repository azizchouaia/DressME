"""M4 input / output. Agree them on day 1, change only through a PR reviewed by the owner.

Every endpoint keeps the team envelope {user_id, payload} -> {result, mocked}; payloads are typed below.
M4 does not recommend anything itself: it decides WHEN and FOR WHICH DAY / OCCASION, calls M2 (outfits)
and M3 (wear log, laundry), caches the results and sends notifications.
"""

import datetime as dt

from pydantic import BaseModel, Field

OCCASIONS = ("work", "casual", "event")


class Prefs(BaseModel):
    city: str = "Tunis"
    timezone: str = "Africa/Tunis"
    morning_time: str = Field(default="05:00", pattern=r"^\d{2}:\d{2}$")  # compute today's outfit
    notify_time: str = Field(default="07:00", pattern=r"^\d{2}:\d{2}$")  # push it
    evening_time: str = Field(default="20:00", pattern=r"^\d{2}:\d{2}$")  # tomorrow's outfit + tips
    weekday_occasions: list[str] = [
        "work",
        "work",
        "work",
        "work",
        "work",
        "casual",
        "casual",
    ]  # Monday first
    jobs: dict[str, bool] = {
        "morning": True,
        "notify": True,
        "evening": True,
        "events": True,
        "weather_tips": True,
        "laundry": True,
        "season": True,
    }
    push_token: str | None = None  # FCM token of the phone (delivery when FCM is configured)


# ---------- payloads ----------
class SchedulePayload(BaseModel):
    """Read the preferences (empty payload) or update some of them (`set`)."""

    set: dict | None = None  # partial Prefs
    now: dt.datetime | None = None  # to compute next runs at another time (demo / tests)


class CalendarPayload(BaseModel):
    start: dt.date | None = None  # default today
    days: int = Field(default=30, ge=1, le=400)
    include_holidays: bool = True  # Tunisian public holidays + Islamic feasts


class EventAddPayload(BaseModel):
    date: dt.date
    title: str
    occasion: str = "event"  # work / casual / event
    dress_code: str | None = None
    notes: str | None = None
    remind_days: int = Field(default=5, ge=0, le=30)  # shortlist looks this many days before


class EventDeletePayload(BaseModel):
    event_id: str


class DayPayload(BaseModel):
    date: dt.date | None = None  # default today (local time of the user)
    refresh: bool = False  # recompute even if cached


class ChoicePayload(BaseModel):
    date: dt.date | None = None
    kind: str = "day"  # "day" or "event:<event_id>"


class WeekPayload(BaseModel):
    start: dt.date | None = None  # default today
    days: int = Field(default=7, ge=1, le=14)
    refresh: bool = False


class NotificationsPayload(BaseModel):
    status: str | None = None  # unread / read / acted
    limit: int = Field(default=30, ge=1, le=200)
    mark_read: list[str] = []


class NotificationActionPayload(BaseModel):
    notif_id: str
    action: str  # wear / change / approve / open / back_in_closet / dismiss


class RunPayload(BaseModel):
    """Run jobs now (demo, tests, or an external cron / Celery beat)."""

    job: str | None = None  # morning / notify / evening / events / season / due (= whatever is due)
    now: dt.datetime | None = None  # simulated local time, e.g. "2026-10-14T05:00"


# ---------- envelopes ----------
class _Req(BaseModel):
    user_id: str | None = None


class ScheduleRequest(_Req):
    payload: SchedulePayload = SchedulePayload()


class CalendarRequest(_Req):
    payload: CalendarPayload = CalendarPayload()


class EventAddRequest(_Req):
    payload: EventAddPayload


class EventDeleteRequest(_Req):
    payload: EventDeletePayload


class DayRequest(_Req):
    payload: DayPayload = DayPayload()


class ChoiceRequest(_Req):
    payload: ChoicePayload = ChoicePayload()


class WeekRequest(_Req):
    payload: WeekPayload = WeekPayload()


class NotificationsRequest(_Req):
    payload: NotificationsPayload = NotificationsPayload()


class NotificationActionRequest(_Req):
    payload: NotificationActionPayload


class RunRequest(_Req):
    payload: RunPayload = RunPayload()


class Response(BaseModel):
    result: dict = {}
    mocked: bool = True


# Names kept from the week-0 skeleton.
ScheduleResponse = CalendarResponse = Response
