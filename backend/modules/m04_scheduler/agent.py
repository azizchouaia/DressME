"""M4 agent: when and for which day / occasion, cached outfit of the day, calendar, notifications."""

from shared.action_agent import Action, ActionAgent

from . import contract as c


def _impl(name: str):
    def call(req: dict) -> dict:
        from . import router

        return getattr(router._impl(), name)(req)

    return call


class SchedulerAgent(ActionAgent):
    name = "m04_scheduler"
    description = (
        "Time and calendar: outfit of today / tomorrow (cached, occasion from the calendar), approve or "
        "change it, week plan, personal events and Tunisian holidays, notifications, schedule preferences."
    )
    depends_on = ("m02_recommendation", "m03_wear_log")

    def actions(self) -> dict[str, Action]:
        return {
            "today": Action("outfit of the day (occasion, weather, reason)", _impl("day"), c.DayRequest),
            "tomorrow": Action("tomorrow's outfit with tomorrow's forecast", _impl("tomorrow"), c.DayRequest),
            "approve": Action("lock the proposed outfit", _impl("approve"), c.ChoiceRequest),
            "change": Action("next option for that day / event", _impl("change"), c.ChoiceRequest),
            "wear": Action("wear the proposed outfit (logged in M3)", _impl("wear"), c.ChoiceRequest),
            "week": Action("next 7 days planned, no piece repeated", _impl("week"), c.WeekRequest),
            "calendar": Action(
                "days with occasion, events, holidays, cached outfits", _impl("calendar"), c.CalendarRequest
            ),
            "event_add": Action(
                "add a personal event (date, title, occasion)", _impl("event_add"), c.EventAddRequest
            ),
            "event_delete": Action("delete a personal event", _impl("event_delete"), c.EventDeleteRequest),
            "schedule": Action(
                "read / set preferences (city, times, weekday occasions)",
                _impl("schedule"),
                c.ScheduleRequest,
            ),
            "widget": Action(
                "compact today payload for the home-screen widget", _impl("widget"), c.DayRequest
            ),
            "notifications": Action("notification outbox", _impl("notifications"), c.NotificationsRequest),
            "notification_action": Action(
                "press a notification button", _impl("notification_action"), c.NotificationActionRequest
            ),
            "run": Action("run a scheduled job now", _impl("run"), c.RunRequest),
        }


agent = SchedulerAgent()
