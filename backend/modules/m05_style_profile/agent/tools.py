"""Tools of the style coach. Thin wrappers over service.py: the LLM decides, M5 computes.

The tools are built per request with the user id bound in a closure: the LLM never chooses whose profile it
reads or changes. Every tool answers short text for the LLM; recommend_outfits also returns the cards as
an artifact, which the endpoint sends to the client.
"""

from langchain_core.tools import StructuredTool, tool

from .. import m01_client, service, styles
from ..config import get_config
from ..contract import ChooseRequest, Context, InvalidAnswerError, PreferencesRequest, ProfileNotFoundError

NO_PROFILE = "The user has no style profile yet: ask them to swipe the first cards (Mon style) first."


def _pct(x: float) -> str:
    return f"{round(x * 100)}%"


def _piece(item) -> str:
    colour = item.colors[0].name if item.colors else ""
    return " ".join(x for x in (colour, item.subcategory or item.category.value) if x)


def build_tools(user_id: str) -> list[StructuredTool]:
    @tool
    async def get_style_profile() -> str:
        """Read the user's current style profile: dominant styles, families, wishes and how much was learnt."""
        try:
            p = await service.profile(user_id)
        except ProfileNotFoundError:
            return NO_PROFILE
        labels = (await styles.get_space()).labels()
        a = p.answers
        return "\n".join(
            [
                "dominant styles: " + ", ".join(f"{labels[t.style]} {_pct(t.share)}" for t in p.top_styles),
                "families: " + ", ".join(f"{f} {_pct(v)}" for f, v in list(p.families.items())[:3]),
                "asked for more: " + (", ".join(a.get("want_more") or []) or "none"),
                "asked for less: " + (", ".join(a.get("want_less") or []) or "none"),
                f"reactions learnt: {p.n_feedback}",
            ]
        )

    @tool
    async def explain_my_recommendations(log_id: str | None = None) -> str:
        """Why the app shows these outfits: the strongest rules the recommender learnt from the user's swipes.
        Give log_id only to explain one specific card."""
        try:
            e = await service.explain(user_id, log_id, k=4)
        except ProfileNotFoundError:
            return NO_PROFILE
        lines = [f"rules learnt from {e.n_feedback} reactions (weight, + = shown more, - = shown less):"]
        lines += [f"+ {r.label} ({r.weight:+.2f})" for r in e.positive]
        lines += [f"- {r.label} ({r.weight:+.2f})" for r in e.negative]
        if e.card:
            lines.append("this card scored because: " + "; ".join(f"{r.label} ({r.weight:+.2f})" for r in e.card))
        return "\n".join(lines)

    @tool
    async def update_style_preferences(more: list[str] | None = None, less: list[str] | None = None) -> str:
        """Change the profile when the user wants more or less of some styles. Use style ids of the catalogue,
        e.g. more=["classic"], less=["streetwear"]. Learning from past swipes is kept."""
        space = await styles.get_space()
        labels = space.labels()
        try:
            before = await service.profile(user_id)
            after = await service.adjust_styles(PreferencesRequest(user_id=user_id, more=more or [], less=less or []))
        except ProfileNotFoundError:
            return NO_PROFILE
        except (InvalidAnswerError, ValueError) as e:
            return f"Not applied: {e}. Valid style ids: {', '.join(space.ids)}"
        changed = [*(more or []), *(less or [])]
        moves = ", ".join(
            f"{labels[s]} {_pct(before.style_mix.get(s, 0.0))} -> {_pct(after.style_mix.get(s, 0.0))}" for s in changed
        )
        return (
            f"Applied. More: {', '.join(labels[s] for s in more or []) or 'none'}; "
            f"less: {', '.join(labels[s] for s in less or []) or 'none'}. Style shares: {moves}. "
            "The recommender now favours these wishes and keeps what it learnt from swipes."
        )

    @tool(response_format="content_and_artifact")
    async def recommend_outfits(
        occasion: str = "casual", temp_c: float = 22.0, rain: bool = False, weekend: bool | None = None
    ) -> tuple[str, list[dict]]:
        """Pick the best outfits for the user right now from their own wardrobe, ranked by their learnt style.
        occasion: work, casual, event, sport or uni. temp_c: temperature in Celsius."""
        try:
            ctx = Context(occasion=occasion, temp_c=temp_c, rain=rain, weekend=weekend)
        except ValueError as e:
            return f"Invalid context: {e}", []
        cards = await service.choose(
            ChooseRequest(user_id=user_id, context=ctx, k=get_config().agent.recommend_k, explore=False)
        )
        if not cards.cards:
            return "No outfit found in the wardrobe for this situation.", []
        labels = (await styles.get_space()).labels()
        items = {i.item_id: i for i in await m01_client.items(user_id)}
        lines = []
        for n, c in enumerate(cards.cards, 1):
            pieces = ", ".join(_piece(items[i]) for i in c.item_ids if i in items)
            mix = ", ".join(f"{labels.get(s.style, s.style)} {_pct(s.share)}" for s in c.top_styles[:2])
            lines.append(f"{n}. {pieces} (style: {mix})")
        return "\n".join(lines), [c.model_dump(mode="json") for c in cards.cards]

    return [get_style_profile, explain_my_recommendations, update_style_preferences, recommend_outfits]
