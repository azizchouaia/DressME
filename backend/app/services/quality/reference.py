"""Compare a reconstruction with a physical reference.

Centimetres in, centimetres out. The GLB coordinate rule for this project is
Y up, metres, feet at the origin. Convert mesh heights with `metres_to_cm`
before calling `compare_measurement`.
"""

from dataclasses import dataclass
from typing import Literal

Provenance = Literal["tape", "manufacturer", "user_confirmed", "model"]
ComparisonStatus = Literal["unmeasured", "compared"]

# These names match the quality dimensions that can be checked with a tape
# or a size chart. Geometry, texture, and drape stay human reviews.
BODY_DIMENSIONS = ("height", "shoulder", "chest", "waist", "hip", "inseam")
GARMENT_DIMENSIONS = (
    "garment_chest",
    "garment_length",
    "garment_shoulder",
    "garment_sleeve",
)

RELEASE_CHECKS = (
    "body_reconstruction",
    "garment_reconstruction",
    "size_recommendation",
    "cross_body_reuse",
    "pose_validation",
    "saved_version_integrity",
    "failure_handling",
    "performance_and_privacy",
)

CONFIRMED = frozenset({"tape", "manufacturer", "user_confirmed"})


@dataclass(frozen=True)
class Measurement:
    dimension: str
    centimeters: float
    provenance: Provenance


@dataclass(frozen=True)
class QualityComparison:
    dimension: str
    reference_cm: float | None
    estimated_cm: float | None
    error_cm: float | None
    threshold_cm: float | None
    passed: bool | None
    status: ComparisonStatus


def metres_to_cm(metres: float) -> float:
    return metres * 100.0


def compare_measurement(
    reference: Measurement | None,
    estimate: Measurement | None,
    threshold_cm: float | None = None,
) -> QualityComparison:
    """Return the absolute error. `passed` stays None until a threshold is given."""
    if reference is None or estimate is None:
        return QualityComparison(
            dimension=(reference or estimate).dimension if (reference or estimate) else "",
            reference_cm=reference.centimeters if reference else None,
            estimated_cm=estimate.centimeters if estimate else None,
            error_cm=None,
            threshold_cm=threshold_cm,
            passed=None,
            status="unmeasured",
        )
    if reference.dimension != estimate.dimension:
        raise ValueError(
            f"Cannot compare {reference.dimension} with {estimate.dimension}."
        )
    error = abs(estimate.centimeters - reference.centimeters)
    passed = None if threshold_cm is None else error <= threshold_cm
    return QualityComparison(
        dimension=reference.dimension,
        reference_cm=reference.centimeters,
        estimated_cm=estimate.centimeters,
        error_cm=error,
        threshold_cm=threshold_cm,
        passed=passed,
        status="compared",
    )


def prefer_confirmed(
    confirmed: Measurement | None,
    estimated: Measurement | None,
) -> Measurement | None:
    """A tape, manufacturer, or user-confirmed value is never replaced by a model."""
    if confirmed is not None and confirmed.provenance in CONFIRMED:
        return confirmed
    return estimated


def blank_release_checklist() -> dict[str, str]:
    """Every release check starts pending. Nothing in the repo has passed one yet."""
    return {name: "pending" for name in RELEASE_CHECKS}
