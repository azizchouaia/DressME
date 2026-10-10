from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class ChatState(TypedDict):
    user_id: str
    messages: Annotated[list, add_messages]
    intent: str | None
    cards: list[dict]          # outfits / results to show in the app
