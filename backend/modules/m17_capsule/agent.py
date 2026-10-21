"""M17 agent: capsule wardrobe (the N pieces that make the most outfits) and its month plan."""

from shared.action_agent import Action, ActionAgent

from . import contract as c


def _impl(name: str):
    def call(req: dict) -> dict:
        from . import router

        return getattr(router._impl(), name)(req)

    return call


class CapsuleAgent(ActionAgent):
    name = "m17_capsule"
    description = (
        "Capsule wardrobe: choose the N pieces that combine into the most good outfits for a season and "
        "occasions (integer linear programming, outfits scored by M2), list them and plan a month of outfits."
    )
    depends_on = ("m02_recommendation", "m04_scheduler")

    def actions(self) -> dict[str, Action]:
        return {
            "capsule": Action(
                "build a capsule (size, season, occasions) + its outfits + plan",
                _impl("capsule"),
                c.CapsuleRequest,
            ),
            "plan": Action(
                "plan days with an existing capsule (item_ids)", _impl("plan_capsule"), c.PlanRequest
            ),
        }


agent = CapsuleAgent()
