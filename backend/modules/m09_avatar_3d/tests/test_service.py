"""Pieces without photo and the render spec, no Blender / photo env needed."""

import pytest

from modules.m09_avatar_3d import service
from modules.m09_avatar_3d.contract import PieceSheet, RenderPayload


@pytest.fixture(autouse=True)
def data(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "DATA", tmp_path)


def test_piece_crud_and_spec():
    top = service.create_piece(
        "u1", PieceSheet(type="t-shirt", size="XXXL", fit="oversize", color="#3b6db3"), None, None
    )
    skirt = service.create_piece("u1", PieceSheet(type="skirt", size="S", length="mini", gsm=220), None, None)
    pieces = service.list_pieces("u1")["result"]["pieces"]
    assert len(pieces) == 2 and service.list_pieces("u2")["result"]["pieces"] == []
    ids = [top["result"]["piece"]["piece_id"], skirt["result"]["piece"]["piece_id"]]
    spec = service._spec("u1", RenderPayload(sex="female", height_cm=150, weight_kg=40, piece_ids=ids))
    t, s, shoes = spec["outfit"]
    assert t == {"type": "t-shirt", "size": "XXXL", "fit": "oversize", "color": "#3b6db3"}
    assert s["length"] == "mini" and s["gsm"] == 220 and s["color"] == "#808080"  # no photo, no colour: grey
    assert shoes["type"] == "shoes"  # shoes added when the outfit has none
    service.update_piece("u1", ids[0], PieceSheet(type="t-shirt", size="S", color="#3b6db3"))
    assert service._spec("u1", RenderPayload(piece_ids=ids[:1]))["outfit"][0]["size"] == "S"
    assert service.delete_piece("u1", ids[0])["result"]["deleted"] is True
    with pytest.raises(ValueError):
        service._spec("u1", RenderPayload(piece_ids=[ids[0]]))


def test_options_lists_types():
    o = service.options()
    assert "t-shirt" in o["types"] and "skirt" in o["types"] and "XXXL" in o["sizes"]
