from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class ChatState(TypedDict, total=False):
    user_id: str
    session_id: str
    messages: Annotated[list, add_messages]
    intent: str | None
    cards: list[dict]  # raw agent results for the app
    tool_calls: int
    pending_question: str | None
    last_agent: str | None
    pending: dict | None     # the open question: {agent, question, question_key}
    answering: dict | None   # set for the turn that answers it
