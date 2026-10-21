"""M2 agent: outfit recommendations for other agents and the orchestrator (same results as /m02/*)."""

from shared.action_agent import Action, ActionAgent

from . import contract as c


def _impl(name: str):
    def call(req: dict) -> dict:
        from . import router

        return getattr(router._impl(), name)(req)

    return call


class RecommendationAgent(ActionAgent):
    name = "m02_recommendation"
    description = (
        "Outfit recommendations from the user's wardrobe: outfits for a day / occasion (work, casual, "
        "event) / mood (comfy, bold, classy) and the weather, remix of an outfit, complete an outfit around "
        "chosen pieces, swap one piece, score outfits. Pretrained OutfitTransformer + FashionCLIP, wear log "
        "from M3."
    )
    depends_on = ("m03_wear_log",)

    def actions(self) -> dict[str, Action]:
        return {
            "recommend": Action(
                "top-n outfits for the context (outfit of the day = n 1)",
                _impl("recommend"),
                c.RecommendRequest,
            ),
            "remix": Action(
                "an alternative sharing at most one piece with base_item_ids", _impl("remix"), c.RemixRequest
            ),
            "complete": Action(
                "keep pinned_item_ids, fill the empty slots", _impl("complete"), c.CompleteRequest
            ),
            "swap": Action("best replacements for one slot of item_ids", _impl("swap"), c.SwapRequest),
            "score": Action(
                "score given outfits (lists of item ids): compatibility, weather, occasion",
                _impl("score"),
                c.ScoreRequest,
            ),
        }


agent = RecommendationAgent()
