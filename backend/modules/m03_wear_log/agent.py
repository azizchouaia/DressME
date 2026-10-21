"""M3 agent: wear log, laundry / lent status and wear statistics for other agents (same results as /m03/*)."""

from shared.action_agent import Action, ActionAgent

from . import contract as c


def _impl(name: str):
    def call(req: dict) -> dict:
        from . import router

        return getattr(router._impl(), name)(req)

    return call


class WearLogAgent(ActionAgent):
    name = "m03_wear_log"
    description = (
        "What the user wore and the state of each piece: log worn outfits, laundry / lent / available "
        "status, pieces unavailable today (to exclude from suggestions), wear counts, days since worn, "
        "forgotten pieces, monthly recap."
    )

    def actions(self) -> dict[str, Action]:
        return {
            "worn": Action("log item_ids as worn (today by default)", _impl("worn"), c.WornRequest),
            "unworn": Action("undo a wear log entry", _impl("unworn"), c.UnwornRequest),
            "posted": Action(
                "mark a logged look as posted on social media", _impl("posted"), c.PostedRequest
            ),
            "status": Action("set item_ids to available / laundry / lent", _impl("status"), c.StatusRequest),
            "laundry_done": Action("laundry back in the closet", _impl("laundry_done"), c.LaundryDoneRequest),
            "states": Action(
                "status of every piece, `unavailable` list, reminders", _impl("states"), c.StatesRequest
            ),
            "stats": Action(
                "per piece wear counts / last worn + wardrobe utilisation", _impl("stats"), c.StatsRequest
            ),
            "history": Action("wear log entries, newest first", _impl("history"), c.HistoryRequest),
            "forgotten": Action("pieces not worn for N days", _impl("forgotten"), c.ForgottenRequest),
            "recap": Action("month recap: wears, top pieces, repeats", _impl("recap"), c.RecapRequest),
        }


agent = WearLogAgent()
