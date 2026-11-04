"""Gaps of a real wardrobe: essentials missing in their usual colours, never fake data."""

from shared.wardrobe_gaps import gaps_for


def _it(sub, cat, colour):
    return {"subcategory": sub, "category": cat, "colors": [{"name": colour}]}


def test_gaps_follow_the_wardrobe():
    items = [_it("t-shirt", "top", "navy"), _it("chinos", "bottom", "tan"), _it("sneakers", "shoes", "black"),
             _it("chemise", "top", "white"), _it("jeans", "bottom", "denim")]
    gaps = [g["piece"] for g in gaps_for(items)]
    assert gaps[:2] == ["white t-shirt", "white sneakers"]  # a navy tee and black sneakers are not the essentials
    assert "beige chinos" not in gaps and "blue jeans" not in gaps and "white shirt" not in gaps


def test_a_full_capsule_has_no_gap_and_dresses_only_for_women():
    full = [_it("t-shirt", "top", "white"), _it("jeans", "bottom", "blue"), _it("shirt", "top", "white"),
            _it("sneakers", "shoes", "white"), _it("chinos", "bottom", "beige"), _it("blazer", "outerwear", "navy"),
            _it("sweater", "top", "grey"), _it("loafers", "shoes", "black"), _it("jacket", "outerwear", "black"),
            _it("coat", "outerwear", "black")]
    assert gaps_for(full, "male") == []
    assert [g["piece"] for g in gaps_for(full, "female")] == ["black dress"]
