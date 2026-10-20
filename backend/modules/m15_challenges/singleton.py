"""One shared instance for the API and the orchestrator tool (same in-memory store)."""

from .agent import CONFIG, ChallengesAgent
from .wardrobe import PHOTOS, MockWardrobe

# The API instance reads real garment photos from bo/bo7_sharing/demo_wardrobe/ (BO7 demo) while M1 is mocked.
challenges_agent = (
    ChallengesAgent(wardrobe=MockWardrobe(photos_dir=PHOTOS))
    if CONFIG.get("wardrobe_source", "mock") == "mock"
    else ChallengesAgent()
)
