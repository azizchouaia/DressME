"""Photo → 3D garment pipeline (future).

Planned flow: segmentation → template garment selection → Blender script
(`blender/scripts/export_garment.py`) projects the texture onto a template
mesh → GLB written to storage. Not implemented in the first milestone; the
null processor reports that clearly instead of pretending to work.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.models.clothing_item import ClothingItem


@dataclass
class ProcessingResult:
    status: str
    message: str


class Garment3DProcessor(ABC):
    @abstractmethod
    def submit(self, item: ClothingItem) -> ProcessingResult: ...


class UnavailableGarmentProcessor(Garment3DProcessor):
    def submit(self, item: ClothingItem) -> ProcessingResult:
        if item.glb_url:
            return ProcessingResult(status="ready", message="This item already has a 3D model.")
        return ProcessingResult(
            status=item.status,
            message="Automatic 3D garment creation is not available yet.",
        )


def get_garment_processor() -> Garment3DProcessor:
    return UnavailableGarmentProcessor()
