"""Personal stylist.

The recommendation tools run locally. When LLM_BASE_URL, LLM_API_KEY, and
LLM_MODEL are set, a hosted OpenAI-compatible model speaks and calls those tools.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np

from recommender.engine import (
    Conditions,
    Event,
    EventLog,
    Outfit,
    Piece,
    Scored,
    compose,
    detect_slot,
    closest_taste,
    cosine,
    memory_view,
    recommend,
    taste_profile,
)
from recommender.explain import explain
from recommender.fashionclip import PROTOTYPE_TEXT
from recommender.hosted import chat_completion, tool_calls
from recommender.parse import merge_conditions, parse_request
from recommender.shops import retrieve_shops, shop_sentence

LIKE_WORDS = ("like", "love", "yes", "save", "perfect", "great")
DISLIKE_WORDS = ("dislike", "hate", "no", "not this", "don't", "dont", "skip")
OUTFIT_WORDS = ("outfit", "wear", "dress", "what should")


@dataclass
class Turn:
    reply: str
    recommendations: list[Scored] = field(default_factory=list)
    outfit: Outfit | None = None
    request: dict = field(default_factory=dict)
    shops: list[dict] = field(default_factory=list)
    memory: dict = field(default_factory=dict)


class Stylist:
    def __init__(self, embedder, log: EventLog) -> None:
        self.embedder = embedder
        self.log = log
        self._last: dict[str, list[str]] = {}
        self._prototypes: dict[str, np.ndarray] | None = None

    def prototypes(self) -> dict[str, np.ndarray]:
        if self._prototypes is None:
            self._prototypes = {slot: self.embedder.embed_text(text) for slot, text in PROTOTYPE_TEXT.items()}
        return self._prototypes

    def vectors(self, pieces: list[Piece]) -> dict[str, np.ndarray]:
        return {piece.id: piece.vector for piece in pieces}

    def context_vector(self, conditions: Conditions) -> np.ndarray | None:
        text = conditions.text()
        if not text:
            return None
        return self.embedder.embed_text(text)

    def get_recommendations(
        self,
        user_id: str,
        pieces: list[Piece],
        conditions: Conditions,
        query: np.ndarray | None = None,
        limit: int = 6,
    ) -> list[Scored]:
        profile = self._tastes(user_id, pieces)
        found = recommend(
            pieces,
            conditions,
            query,
            None,
            self.context_vector(conditions),
            limit=limit,
            tastes=profile.tastes,
            exploration=profile.exploration,
        )
        for item in found:
            self.log.append(user_id, Event("impression", item.piece.id))
        self._remember(user_id, [item.piece.id for item in found])
        return found

    def search_text(self, user_id: str, pieces: list[Piece], text: str, conditions: Conditions) -> list[Scored]:
        return self.get_recommendations(user_id, pieces, conditions, query=self.embedder.embed_text(text))

    def log_feedback(self, user_id: str, piece_id: str, kind: str, seconds: float = 0.0) -> None:
        self.log.append(user_id, Event(kind, piece_id, seconds))

    def make_outfit(
        self,
        user_id: str,
        pieces: list[Piece],
        conditions: Conditions,
        query: np.ndarray | None = None,
        anchor: Piece | None = None,
    ) -> Outfit:
        profile = self._tastes(user_id, pieces)
        outfit = compose(
            pieces,
            conditions,
            query,
            None,
            self.context_vector(conditions),
            anchor,
            tastes=profile.tastes,
        )
        self._remember(user_id, [item.piece.id for item in outfit.pieces])
        for item in outfit.pieces:
            if item.piece.id != "upload":
                self.log.append(user_id, Event("impression", item.piece.id))
        return outfit

    def anchor_from_image(self, data: bytes) -> tuple[np.ndarray, Piece]:
        vector = self.embedder.embed_image(data)
        slot = detect_slot(vector, self.prototypes())
        piece = Piece(id="upload", name="the piece in your photo", category=slot, vector=vector, stock=1)
        return vector, piece

    def chat(
        self,
        user_id: str,
        pieces: list[Piece],
        message: str,
        conditions: Conditions | None = None,
        image: bytes | None = None,
        llm_base_url: str = "",
        llm_api_key: str = "",
        llm_model: str = "",
    ) -> Turn:
        conditions = conditions or Conditions()
        parsed = merge_conditions(
            parse_request(message),
            conditions.weather,
            conditions.season,
            conditions.occasion,
            conditions.size,
            conditions.budget,
        )
        conditions = Conditions(
            weather=parsed["weather"],
            season=parsed["season"],
            occasion=parsed["occasion"],
            size=parsed["size"],
            budget=parsed["budget"],
        )
        if llm_base_url and llm_api_key and llm_model:
            spoken = self._hosted(
                user_id, pieces, message, conditions, image, llm_base_url, llm_api_key, llm_model
            )
            if spoken is not None:
                spoken.request = parsed
                spoken.memory = self.profile(user_id, pieces)
                return spoken
        turn = self._local(user_id, pieces, message, conditions, image, parsed)
        turn.request = parsed
        turn.memory = self.profile(user_id, pieces)
        return turn

    def _local(
        self,
        user_id: str,
        pieces: list[Piece],
        message: str,
        conditions: Conditions,
        image: bytes | None,
        parsed: dict | None = None,
    ) -> Turn:
        text = message.lower().strip()
        shown = self._shown(user_id, pieces)
        target = _mentioned(text, pieces) or (shown[0] if shown else None)
        if target is not None and any(word in text for word in DISLIKE_WORDS):
            self.log_feedback(user_id, target.id, "dislike")
            self.note_explore_reaction(user_id, target.id, pieces)
            outfit = self.make_outfit(user_id, pieces, conditions)
            return Turn(
                reply=f"Got it, I'll move away from {target.name}. {outfit.reason}",
                outfit=outfit,
                recommendations=outfit.pieces,
            )
        if target is not None and any(word in text for word in LIKE_WORDS):
            self.log_feedback(user_id, target.id, "like")
            self.note_explore_reaction(user_id, target.id, pieces)
            outfit = self.make_outfit(user_id, pieces, conditions)
            remembered = ", ".join(self.profile(user_id, pieces)["likes"]) or target.name
            return Turn(
                reply=f"Saved. I'll keep {remembered} on your profile and use it next time. {outfit.reason}",
                outfit=outfit,
                recommendations=outfit.pieces,
            )
        query = None
        anchor = None
        if image:
            query, anchor = self.anchor_from_image(image)
        wants_outfit = image is not None or any(word in text for word in OUTFIT_WORDS) or not text
        if wants_outfit:
            outfit = self.make_outfit(user_id, pieces, conditions, query, anchor)
            known = bool(self._tastes(user_id, pieces).tastes)
            reply = explain(outfit, conditions, known, image is not None)
            hits = retrieve_shops(" ".join(filter(None, [conditions.text(), message, " ".join(item.piece.name for item in outfit.pieces)])))
            extra = shop_sentence(hits)
            if extra:
                reply = f"{reply}\n{extra}"
            return Turn(reply=reply, outfit=outfit, recommendations=outfit.pieces, shops=hits, request=parsed or {})
        if text:
            found = self.search_text(user_id, pieces, message, conditions)
        else:
            found = self.get_recommendations(user_id, pieces, conditions, query)
        if not found:
            return Turn(reply="Nothing in the wardrobe passes those filters.")
        names = ", ".join(item.piece.name for item in found[:3])
        return Turn(reply=f"From your wardrobe, start with {names}.", recommendations=found)

    def profile(self, user_id: str, pieces: list[Piece]) -> dict:
        names = {piece.id: piece.name for piece in pieces}
        view = memory_view(self.log.load(user_id), names)
        tastes = self._tastes(user_id, pieces)
        view["tastes"] = [[names.get(piece_id, piece_id) for piece_id in group] for group in tastes.members]
        view["exploration"] = "nearby" if tastes.exploration is not None else ""
        path = self.log.path(user_id).with_suffix(".memory.json")
        path.write_text(json.dumps({"user_id": user_id, **view}), encoding="utf-8")
        return view

    def _tastes(self, user_id: str, pieces: list[Piece]):
        return taste_profile(self.log.load(user_id), self.vectors(pieces), seed=self._explore_seed(user_id))

    def _explore_seed(self, user_id: str) -> int:
        path = self.log.path(user_id).with_suffix(".explore.json")
        if path.is_file():
            return int(json.loads(path.read_text(encoding="utf-8")).get("seed") or 1)
        path.write_text(json.dumps({"seed": 1}), encoding="utf-8")
        return 1

    def note_explore_reaction(self, user_id: str, piece_id: str, pieces: list[Piece]) -> None:
        """A like or dislike on the probe picks a new nearby direction. The old one was answered."""

        profile = self._tastes(user_id, pieces)
        if profile.exploration is None:
            return
        vector = self.vectors(pieces).get(piece_id)
        if vector is None:
            return
        if closest_taste(vector, profile.tastes) >= cosine(vector, profile.exploration):
            return
        path = self.log.path(user_id).with_suffix(".explore.json")
        seed = self._explore_seed(user_id) + 1
        path.write_text(json.dumps({"seed": seed, "answered": piece_id}), encoding="utf-8")

    def _remember(self, user_id: str, ids: list[str]) -> None:
        self._last[user_id] = ids
        self.log.path(user_id).with_suffix(".last.json").write_text(json.dumps(ids), encoding="utf-8")

    def _shown(self, user_id: str, pieces: list[Piece]) -> list[Piece]:
        by_id = {piece.id: piece for piece in pieces}
        ids = self._last.get(user_id)
        if ids is None:
            path = self.log.path(user_id).with_suffix(".last.json")
            ids = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
            self._last[user_id] = ids
        return [by_id[item_id] for item_id in ids if item_id in by_id]

    def _hosted(
        self,
        user_id: str,
        pieces: list[Piece],
        message: str,
        conditions: Conditions,
        image: bytes | None,
        base_url: str,
        api_key: str,
        model: str,
    ) -> Turn | None:
        tools = [
            {"type": "function", "function": {"name": "get_recommendations", "description": "Rank this person's wardrobe.", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "search_text", "description": "Search the wardrobe with a phrase.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}},
            {"type": "function", "function": {"name": "log_feedback", "description": "Record a like or dislike.", "parameters": {"type": "object", "properties": {"piece_id": {"type": "string"}, "kind": {"type": "string"}}, "required": ["piece_id", "kind"]}}},
            {"type": "function", "function": {"name": "make_outfit", "description": "Build a complete outfit from the wardrobe.", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "find_shops", "description": "Find shops related to the request.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}},
        ]
        notes = " The user attached a photo. Call make_outfit." if image else ""
        messages = [
            {
                "role": "system",
                "content": (
                    "You are the Dressme stylist. Other models supply the clothes, the taste score, and the shops. "
                    "Call those tools. Recommend only ids they return. Explain why in plain sentences. "
                    "Follow this person's saved tastes. They can have more than one. "
                    "A newer like or dislike replaces the older one. "
                    "One recommendation may be a nearby exploration, not a taste they already have."
                    f" Memory: {json.dumps(self.profile(user_id, pieces))}. "
                    f"Conditions: {conditions.text() or 'none'}. Size {conditions.size or 'any'}. "
                    f"Budget {conditions.budget if conditions.budget is not None else 'any'}."
                    + notes
                ),
            },
            {"role": "user", "content": message or "Suggest an outfit."},
        ]
        query = None
        anchor = None
        if image:
            query, anchor = self.anchor_from_image(image)
        turn = Turn(reply="")
        for _ in range(4):
            reply = chat_completion(base_url, api_key, model, messages, tools)
            if reply is None:
                return None
            calls = tool_calls(reply)
            if not calls:
                turn.reply = reply.get("content") or turn.reply
                return turn if turn.reply else None
            messages.append(reply)
            for call in calls:
                result, turn = self._run_tool(call["name"], call["arguments"], user_id, pieces, conditions, query, anchor, turn)
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result)})
        return turn if turn.reply or turn.outfit or turn.recommendations else None

    def _run_tool(self, name, args, user_id, pieces, conditions, query, anchor, turn: Turn):
        if name == "log_feedback":
            self.log_feedback(user_id, str(args.get("piece_id")), str(args.get("kind") or "like"))
            return {"ok": True}, turn
        if name == "search_text":
            found = self.search_text(user_id, pieces, str(args.get("text") or ""), conditions)
            turn.recommendations = found
            return [_public(item) for item in found], turn
        if name == "make_outfit":
            outfit = self.make_outfit(user_id, pieces, conditions, query, anchor)
            turn.outfit = outfit
            turn.recommendations = outfit.pieces
            return {"reason": outfit.reason, "pieces": [_public(item) for item in outfit.pieces]}, turn
        if name == "find_shops":
            hits = retrieve_shops(str(args.get("text") or conditions.text() or ""))
            turn.shops = hits
            return hits, turn
        found = self.get_recommendations(user_id, pieces, conditions, query)
        turn.recommendations = found
        return [_public(item) for item in found], turn


def _mentioned(text: str, pieces: list[Piece]) -> Piece | None:
    for piece in pieces:
        if piece.name.lower() in text:
            return piece
    return None


def _public(item: Scored) -> dict[str, object]:
    return {"id": item.piece.id, "name": item.piece.name, "slot": item.piece.slot, "score": round(item.score, 4)}
