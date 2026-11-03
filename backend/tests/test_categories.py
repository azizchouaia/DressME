from app.services.garments.categories import category_from_classification, ready_message


def test_clear_garment_photo_gets_a_slot_category() -> None:
    assert category_from_classification("jeans", 0.42) == "jeans"
    assert category_from_classification("jacket", 0.2) == "jacket"
    assert "Outerwear" in ready_message("jacket")


def test_uncertain_or_non_clothing_photo_does_not_change_category() -> None:
    assert category_from_classification("other", 0.91) is None
    assert category_from_classification("jeans", 0.05) is None
    assert category_from_classification(None, 1) is None
    assert "Open Avatar" in ready_message(None)
