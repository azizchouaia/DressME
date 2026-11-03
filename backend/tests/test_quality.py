import pytest

from app.services.quality import (
    RELEASE_CHECKS,
    Measurement,
    blank_release_checklist,
    compare_measurement,
    prefer_confirmed,
)
from app.services.quality.reference import metres_to_cm


def test_missing_tape_measurement_is_unmeasured() -> None:
    estimate = Measurement("height", 180.0, "model")
    result = compare_measurement(None, estimate)
    assert result.status == "unmeasured"
    assert result.passed is None
    assert result.error_cm is None


def test_error_is_the_absolute_difference_and_does_not_pass_by_default() -> None:
    reference = Measurement("height", 178.0, "tape")
    estimate = Measurement("height", 181.5, "model")
    result = compare_measurement(reference, estimate)
    assert result.status == "compared"
    assert result.error_cm == pytest.approx(3.5)
    assert result.passed is None


def test_threshold_is_required_before_a_pass_or_fail() -> None:
    reference = Measurement("chest", 96.0, "tape")
    estimate = Measurement("chest", 99.0, "model")
    assert compare_measurement(reference, estimate, threshold_cm=2.0).passed is False
    assert compare_measurement(reference, estimate, threshold_cm=4.0).passed is True


def test_different_dimensions_are_rejected() -> None:
    with pytest.raises(ValueError):
        compare_measurement(
            Measurement("chest", 96.0, "tape"),
            Measurement("waist", 96.0, "model"),
        )


def test_confirmed_measurement_is_not_replaced_by_the_model() -> None:
    confirmed = Measurement("waist", 82.0, "user_confirmed")
    estimated = Measurement("waist", 90.0, "model")
    assert prefer_confirmed(confirmed, estimated) is confirmed
    assert prefer_confirmed(None, estimated) is estimated


def test_mesh_metres_convert_before_a_centimetre_comparison() -> None:
    reference = Measurement("height", 178.0, "tape")
    estimate = Measurement("height", metres_to_cm(1.80), "model")
    result = compare_measurement(reference, estimate)
    assert result.error_cm == pytest.approx(2.0)


def test_release_checklist_starts_entirely_pending() -> None:
    checklist = blank_release_checklist()
    assert list(checklist) == list(RELEASE_CHECKS)
    assert set(checklist.values()) == {"pending"}
