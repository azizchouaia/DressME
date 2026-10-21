"""M9 agent: the 3D avatar and the user's pieces in 3D (photo -> sewn 3D garment), for other agents."""

from pydantic import BaseModel

from shared.action_agent import Action, ActionAgent

from . import contract as c


class _Req(BaseModel):
    user_id: str | None = None
    payload: dict = {}


def _user(req: dict) -> str:
    from . import service

    return service._uid(req.get("user_id"))


def _render(req: dict) -> dict:
    from . import router

    return router._impl().render(req)


def _pieces(req: dict) -> dict:
    from . import service

    return service.list_pieces(req.get("user_id"))


def _wardrobe3d(req: dict) -> dict:
    from . import wardrobe3d

    return {"result": wardrobe3d.state(req.get("user_id")), "mocked": False}


def _outfit3d(req: dict) -> dict:
    from . import wardrobe3d

    p = req.get("payload") or {}
    return {
        "result": wardrobe3d.outfit(req.get("user_id"), p.get("piece_ids", []), bool(p.get("animate"))),
        "mocked": False,
    }


def _set_body(req: dict) -> dict:
    from . import wardrobe3d

    user = _user(req)
    wardrobe3d.set_profile(user, c.Body.model_validate(req.get("payload") or {}))
    wardrobe3d.request(user)
    return {"result": wardrobe3d.state(user), "mocked": False}


def _items(req: dict) -> dict:
    from . import wardrobe3d

    return {"result": {"items": wardrobe3d.wardrobe_items(_user(req))}, "mocked": False}


class AvatarAgent(ActionAgent):
    name = "m09_avatar_3d"
    description = (
        "3D try-on: the user's faceless avatar from height / weight, their pieces turned into 3D garments "
        "from phone photos (sewn from their pattern with cloth physics), outfits worn together and the turn "
        "animation as GLB files; the pieces as M1 Garment items (FashionCLIP vectors) for recommendations."
    )

    def actions(self) -> dict[str, Action]:
        return {
            "render": Action(
                "one GLB of body + piece_ids (sex, height_cm, weight_kg, piece_ids)", _render, c.RenderRequest
            ),
            "pieces": Action("the user's pieces with their sheet and photo urls", _pieces, _Req),
            "wardrobe3d": Action(
                "body GLB + every piece's ready-to-wear GLB / build status", _wardrobe3d, _Req
            ),
            "outfit3d": Action(
                "piece_ids worn together (cloth physics), animate for the turn animation", _outfit3d, _Req
            ),
            "set_body": Action(
                "save sex / height_cm / weight_kg; avatar and pieces rebuilt", _set_body, _Req
            ),
            "items": Action("the user's pieces as M1 Garment items with FashionCLIP vectors", _items, _Req),
        }


agent = AvatarAgent()
