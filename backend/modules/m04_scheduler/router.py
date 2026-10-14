"""HTTP endpoints of M4. Included automatically by api/main.py."""

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from shared.config import settings

from . import mock, scheduler, service
from .contract import (
    CalendarRequest,
    ChoiceRequest,
    DayRequest,
    EventAddRequest,
    EventDeleteRequest,
    NotificationActionRequest,
    NotificationsRequest,
    Response,
    RunRequest,
    ScheduleRequest,
    WeekRequest,
)

DEMO = Path(__file__).parent / "demo"


def _impl():
    """M04_USE_MOCK overrides the global USE_MOCKS, so M4 can run for real while other modules stay mocked."""
    flag = os.environ.get("M04_USE_MOCK")
    use_mock = settings.use_mocks if flag is None else flag.lower() in ("1", "true", "yes")
    return mock if use_mock else service


def _start_scheduler():
    if _impl() is service:
        scheduler.start()


router = APIRouter(
    prefix="/m04",
    tags=["M4 Scheduler, notifications + outfit calendar"],
    on_startup=[_start_scheduler],
    on_shutdown=[scheduler.stop],
)


def _call(name: str, req) -> dict:
    try:
        return getattr(_impl(), name)(req.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/schedule", response_model=Response)
def schedule(req: ScheduleRequest):
    """Scheduling preferences (city, times, weekday occasions, jobs on/off, push token) + next runs."""
    return _call("schedule", req)


@router.post("/calendar", response_model=Response)
def calendar(req: CalendarRequest):
    """Days with their occasion (personal event > festive holiday > weekday default), events, Tunisian
    holidays and seasons, cached outfit."""
    return _call("calendar", req)


@router.post("/events/add", response_model=Response)
def event_add(req: EventAddRequest):
    return _call("event_add", req)


@router.post("/events/delete", response_model=Response)
def event_delete(req: EventDeleteRequest):
    return _call("event_delete", req)


@router.post("/today", response_model=Response)
def today(req: DayRequest):
    """Outfit of the day from the cache (computed at 05:00; on demand if missing). `date` for another day."""
    return _call("day", req)


@router.post("/tomorrow", response_model=Response)
def tomorrow(req: DayRequest):
    """Tomorrow's outfit (computed at 20:00 with tomorrow's forecast and occasion)."""
    return _call("tomorrow", req)


@router.post("/approve", response_model=Response)
def approve(req: ChoiceRequest):
    """Lock the outfit shown for that day / event (not recomputed in the morning)."""
    return _call("approve", req)


@router.post("/change", response_model=Response)
def change(req: ChoiceRequest):
    """Next option; after the last one, new options without the pieces already shown."""
    return _call("change", req)


@router.post("/wear", response_model=Response)
def wear(req: ChoiceRequest):
    """Log the shown outfit as worn in M3."""
    return _call("wear", req)


@router.post("/week", response_model=Response)
def week(req: WeekRequest):
    """Outfits for the next days, no top / bottom / dress twice."""
    return _call("week", req)


@router.post("/widget", response_model=Response)
def widget(req: DayRequest):
    """Compact payload for the home-screen widget."""
    return _call("widget", req)


@router.post("/notifications", response_model=Response)
def notifications(req: NotificationsRequest):
    """Notification outbox of the user (the app polls it; FCM delivery when configured)."""
    return _call("notifications", req)


@router.post("/notifications/action", response_model=Response)
def notification_action(req: NotificationActionRequest):
    """A notification button: wear / change / approve / back_in_closet / open / dismiss."""
    return _call("notification_action", req)


@router.post("/run", response_model=Response)
def run(req: RunRequest):
    """Run a job now (morning / notify / evening / events / season, or "due") at an optional time."""
    return _call("run", req)


@router.get("/status")
def status():
    return {
        "result": {
            "scheduler_running": scheduler.running(),
            "tick_minutes": scheduler.TICK_MINUTES,
            "mocked": _impl() is mock,
        },
        "mocked": _impl() is mock,
    }


# ---- demo page: http://localhost:8000/m04/demo ----
@router.get("/demo", include_in_schema=False)
def demo_page():
    return FileResponse(DEMO / "index.html")


@router.post("/demo/reset/{user_id}", include_in_schema=False)
def demo_reset(user_id: str):
    service.reset(user_id)
    return {"result": {"user_id": user_id, "reset": True}, "mocked": False}
