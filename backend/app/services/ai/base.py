"""Interfaces for every AI capability. Implementations are swappable.

The rest of the backend depends only on these abstractions, so a local
heuristic, a PyTorch model, or a MediaPipe pipeline can be dropped in without
touching routes or business logic.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ClothingAnalysis:
    category: str | None = None
    subcategory: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    pattern: str | None = None
    sleeve_type: str | None = None
    brand: str | None = None
    confidence: float = 0.0
    analyzer: str = "unknown"


@dataclass
class SegmentationResult:
    """Garment mask as PNG bytes (white = garment) plus its bounding box."""

    mask_png: bytes
    bbox: tuple[int, int, int, int]


@dataclass
class BodyEstimate:
    """Estimated measurements. Must be confirmed by the user before saving."""

    measurements: dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0


class ClothingAnalyzer(ABC):
    name: str

    @abstractmethod
    async def analyze(self, image: bytes) -> ClothingAnalysis: ...


class SegmentationService(ABC):
    @abstractmethod
    async def segment(self, image: bytes) -> SegmentationResult: ...


class BodyAnalysisService(ABC):
    """Future: MediaPipe pose landmarks → measurement estimates."""

    @abstractmethod
    async def estimate(self, front_image: bytes, side_image: bytes | None) -> BodyEstimate: ...


class OutfitRecommendationService(ABC):
    """Future: recommend outfits from the user's wardrobe."""

    @abstractmethod
    async def recommend(self, user_id: str, context: dict[str, str]) -> list[dict[str, str]]: ...
