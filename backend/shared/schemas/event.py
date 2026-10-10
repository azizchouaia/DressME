"""DATA CONTRACT — change only through a PR reviewed by M6."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class EventType(str, Enum):
    outfit_feedback = "outfit_feedback"
    worn = "worn"
    item_added = "item_added"
    item_deleted = "item_deleted"
    tryon_reaction = "tryon_reaction"
    builder_edit = "builder_edit"
    smartbuy_check = "smartbuy_check"
    chat_message = "chat_message"


class Event(BaseModel):
    event_id: str
    user_id: str
    type: EventType
    target_id: str | None = None
    value: str | None = None
    channel: str | None = None
    ts: datetime
