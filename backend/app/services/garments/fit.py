"""Garment fitting.

Input:  BodyProfile + garment measurements + garment GLB
Output: fitted garment GLB (or, for the MVP, a transform to apply to it)

MVP strategy: garments are authored on the base avatar and inherit the
avatar's scene transform, so fitting is a no-op scale. Future strategies
(landmark-based deformation, mesh deformation) implement `GarmentFitStrategy`.
No cloth simulation is planned here.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.models.body_profile import BodyProfile


@dataclass
class FitResult:
    glb_url: str
    scale: tuple[float, float, float]
    notes: str


class GarmentFitStrategy(ABC):
    @abstractmethod
    def fit(
        self,
        body: BodyProfile | None,
        garment_measurements: dict[str, float] | None,
        garment_glb_url: str,
    ) -> FitResult: ...


class PredefinedScaleFit(GarmentFitStrategy):
    def fit(
        self,
        body: BodyProfile | None,
        garment_measurements: dict[str, float] | None,
        garment_glb_url: str,
    ) -> FitResult:
        return FitResult(
            glb_url=garment_glb_url,
            scale=(1.0, 1.0, 1.0),
            notes="Garment follows the avatar preset transform.",
        )


class GarmentFitService:
    def __init__(self, strategy: GarmentFitStrategy | None = None) -> None:
        self.strategy = strategy or PredefinedScaleFit()

    def fit(
        self,
        body: BodyProfile | None,
        garment_measurements: dict[str, float] | None,
        garment_glb_url: str,
    ) -> FitResult:
        return self.strategy.fit(body, garment_measurements, garment_glb_url)
