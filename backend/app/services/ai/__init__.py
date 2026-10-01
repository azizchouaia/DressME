from functools import lru_cache

from app.core.config import get_settings
from app.services.ai.base import (
    BodyAnalysisService,
    ClothingAnalysis,
    ClothingAnalyzer,
    OutfitRecommendationService,
    SegmentationService,
)
from app.services.ai.local_heuristic import LocalHeuristicAnalyzer


@lru_cache
def get_clothing_analyzer() -> ClothingAnalyzer:
    analyzers: dict[str, type[ClothingAnalyzer]] = {
        LocalHeuristicAnalyzer.name: LocalHeuristicAnalyzer,
    }
    return analyzers[get_settings().clothing_analyzer]()


__all__ = [
    "BodyAnalysisService",
    "ClothingAnalysis",
    "ClothingAnalyzer",
    "OutfitRecommendationService",
    "SegmentationService",
    "get_clothing_analyzer",
]
