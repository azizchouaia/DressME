"""Ranking and the stylist, with a stand-in embedder instead of FashionCLIP."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from recommender.assistant import Stylist
from recommender.hosted import message_from, tool_calls
from recommender.parse import parse_request
from recommender.shops import retrieve_shops
from recommender.engine import (
    Conditions,
    Event,
    EventLog,
    Piece,
    compose,
    cosine,
    maybe_train_ranker,
    memory_view,
    recommend,
    taste_profile,
    taste_vector,
    two_tower_status,
)


def vec(*values: float) -> np.ndarray:
    array = np.asarray(values, dtype=np.float32)
    return array / np.linalg.norm(array)


class TableEmbedder:
    def __init__(self) -> None:
        self.texts = {
            "a photo of a shirt or t-shirt": vec(1, 0, 0),
            "a photo of pants jeans or shorts": vec(0, 1, 0),
            "a photo of a jacket or coat": vec(0, 0, 1),
            "a photo of shoes": vec(0, 0.2, 0.8),
            "rainy autumn office": vec(0.2, 0.2, 0.9),
            "black shirt": vec(0.9, 0.1, 0),
        }

    def embed_text(self, text: str) -> np.ndarray:
        return self.texts.get(text, vec(0.3, 0.3, 0.3))

    def embed_image(self, data: bytes) -> np.ndarray:
        return vec(1, 0, 0) if data[:1] == b"s" else vec(0, 1, 0)


def wardrobe() -> list[Piece]:
    return [
        Piece("tee", "Black T-shirt", "t-shirt", vec(1, 0, 0), size="M", price=25, stock=2),
        Piece("white", "White T-shirt", "t-shirt", vec(0.8, 0.2, 0), size="S", price=25, stock=2),
        Piece("jeans", "Blue jeans", "jeans", vec(0, 1, 0), size="32", price=60, stock=1),
        Piece("shorts", "Sand shorts", "pants", vec(0.1, 0.9, 0), size="32", price=40, stock=0),
        Piece("jacket", "Black jacket", "jacket", vec(0, 0, 1), size="M", price=90, stock=1),
        Piece("sneakers", "White sneakers", "shoes", vec(0.1, 0.2, 0.7), size="42", price=70, stock=1),
    ]


class EngineTests(unittest.TestCase):
    def test_filters_and_taste(self) -> None:
        pieces = wardrobe()
        vectors = {piece.id: piece.vector for piece in pieces}
        events = [Event("like", "tee"), Event("dislike", "white")]
        taste = taste_vector(events, vectors)
        self.assertIsNotNone(taste)
        ranked = recommend(pieces, Conditions(size="M", budget=80), query=vec(1, 0, 0), taste=taste, slot="top")
        self.assertEqual(ranked[0].piece.id, "tee")
        self.assertNotIn("white", [item.piece.id for item in ranked])
        self.assertTrue(all(item.piece.price is None or item.piece.price <= 80 for item in ranked))

    def test_outfit_uses_photo_and_skips_out_of_stock(self) -> None:
        outfit = compose(wardrobe(), Conditions(weather="rainy", season="autumn"), query=vec(1, 0, 0))
        slots = {item.piece.slot for item in outfit.pieces}
        self.assertIn("top", slots)
        self.assertIn("bottom", slots)
        self.assertIn("outer", slots)
        self.assertNotIn("shorts", [item.piece.id for item in outfit.pieces])
        self.assertGreater(outfit.compatibility, 0)

    def test_stylist_learns_a_like(self) -> None:
        with TemporaryDirectory() as tmp:
            stylist = Stylist(TableEmbedder(), EventLog(Path(tmp)))
            pieces = wardrobe()
            first = stylist.chat("ada", pieces, "what should I wear", Conditions(weather="rainy"))
            self.assertIsNotNone(first.outfit)
            liked = first.outfit.pieces[0].piece
            follow = stylist.chat("ada", pieces, f"I love the {liked.name}")
            self.assertIn(liked.name, follow.reply)
            kinds = [event.kind for event in stylist.log.load("ada")]
            self.assertIn("like", kinds)

    def test_memory_follows_the_user_and_a_later_opinion_wins(self) -> None:
        pieces = wardrobe()
        vectors = {piece.id: piece.vector for piece in pieces}
        day = 86400
        events = [
            Event("like", "white", at=1),
            Event("dislike", "white", at=1 + 90 * day),
            Event("like", "tee", at=1 + 90 * day),
        ]
        taste = taste_vector(events, vectors)
        self.assertGreater(cosine(taste, vectors["tee"]), cosine(taste, vectors["white"]))
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = Stylist(TableEmbedder(), EventLog(root))
            first.log_feedback("ada", "tee", "like")
            second = Stylist(TableEmbedder(), EventLog(root))
            remembered = second.profile("ada", pieces)
            self.assertEqual(remembered["likes"], ["Black T-shirt"])
            self.assertEqual(memory_view(second.log.load("ada"), {"tee": "Black T-shirt"})["likes"], ["Black T-shirt"])

    def test_several_tastes_and_a_nearby_exploration(self) -> None:
        pieces = wardrobe()
        vectors = {piece.id: piece.vector for piece in pieces}
        events = [Event("like", "tee", at=10), Event("like", "jeans", at=11), Event("like", "jacket", at=12)]
        profile = taste_profile(events, vectors, seed=7)
        self.assertGreaterEqual(len(profile.tastes), 2)
        self.assertIsNotNone(profile.exploration)
        center = np.mean(np.stack(profile.tastes), axis=0)
        self.assertGreater(cosine(profile.exploration, center), 0.85)
        again = taste_profile(events, vectors, seed=7)
        self.assertAlmostEqual(cosine(profile.exploration, again.exploration), 1.0, places=5)
        moved = taste_profile(events, vectors, seed=8)
        self.assertLess(cosine(profile.exploration, moved.exploration), 0.999)

    def test_photo_becomes_the_top(self) -> None:
        with TemporaryDirectory() as tmp:
            stylist = Stylist(TableEmbedder(), EventLog(Path(tmp)))
            turn = stylist.chat("ada", wardrobe(), "make an outfit with this", image=b"shirt-bytes")
            self.assertIsNotNone(turn.outfit)
            self.assertEqual(turn.outfit.pieces[0].piece.slot, "top")
            self.assertIn("photo", turn.reply)

    def test_message_becomes_json_and_finds_a_shop(self) -> None:
        parsed = parse_request("what should I wear to the office in the rainy autumn, size M, under $80")
        self.assertEqual(parsed["intent"], "outfit")
        self.assertEqual(parsed["weather"], "rainy")
        self.assertEqual(parsed["season"], "autumn")
        self.assertEqual(parsed["occasion"], "office")
        self.assertEqual(parsed["size"], "M")
        self.assertEqual(parsed["budget"], 80.0)
        hits = retrieve_shops("rainy autumn office jacket")
        self.assertTrue(hits)
        self.assertIn("name", hits[0])

    def test_hosted_tool_call_is_openai_shaped(self) -> None:
        message = message_from(
            {
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {"id": "call_1", "function": {"name": "make_outfit", "arguments": "{}"}}
                            ],
                        }
                    }
                ]
            }
        )
        calls = tool_calls(message)
        self.assertEqual(calls[0]["name"], "make_outfit")
        self.assertEqual(calls[0]["id"], "call_1")

    def test_later_stages_stay_off_without_data(self) -> None:
        self.assertTrue(two_tower_status({"ada"}).startswith("waiting"))
        state = maybe_train_ranker([Event("like", "tee")], {"tee": vec(1, 0, 0)})
        self.assertFalse(state.ready)


if __name__ == "__main__":
    unittest.main()
