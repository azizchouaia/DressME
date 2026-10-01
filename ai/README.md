# ai/

Offline / local AI work: experiments, training scripts, and model weights. Nothing here runs in the browser.

The backend reaches AI only through the interfaces in `backend/app/services/ai/base.py`:

| Interface | Planned implementation | Folder |
| --- | --- | --- |
| `ClothingAnalyzer` | PyTorch classifier for category / color / pattern / sleeve | `clothing/` |
| `SegmentationService` | Open-source garment segmentation (e.g. SAM, U²-Net) | `segmentation/` |
| `BodyAnalysisService` | MediaPipe pose landmarks to measurement estimates | `body/` |
| `OutfitRecommendationService` | Ranking over the user's own wardrobe | `inference/` |

`models/` holds downloaded weights and is git-ignored.

To add a model, implement the interface in `backend/app/services/ai/`, register it in `get_clothing_analyzer()` (or the equivalent factory), and select it with an env var such as `CLOTHING_ANALYZER`. Routes and the frontend don't change.

The current default, `local-heuristic`, is a placeholder. It estimates color from pixels only and does no ML.
