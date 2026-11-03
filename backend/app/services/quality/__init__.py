"""Physical checks for a reconstruction.

A model score is not a result. A comparison stays unmeasured until a tape
or manufacturer number is present, and it stays undecided until a threshold
has been chosen from a measured baseline.
"""

from app.services.quality.reference import (
    RELEASE_CHECKS,
    Measurement,
    QualityComparison,
    blank_release_checklist,
    compare_measurement,
    prefer_confirmed,
)

__all__ = [
    "RELEASE_CHECKS",
    "Measurement",
    "QualityComparison",
    "blank_release_checklist",
    "compare_measurement",
    "prefer_confirmed",
]
