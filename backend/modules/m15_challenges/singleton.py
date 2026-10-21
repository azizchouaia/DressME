"""One shared instance for the API and the orchestrator tool.

Its memory is kept in SQLite (memory.py): challenges, participations, posts, likes, comments and what the
coach remembers survive a restart of the server. `BO7_MEMORY_PATH=:memory:` keeps everything in RAM (tests).
"""

from .agent import CONFIG, ChallengesAgent
from .memory import CoachMemory, SqliteChallengeStore, connect
from .wardrobe import PHOTOS, MockWardrobe

_con = connect()
# The API instance reads real garment photos from bo/bo7_sharing/demo_wardrobe/ (BO7 demo) while M1 is mocked.
challenges_agent = ChallengesAgent(
    wardrobe=MockWardrobe(photos_dir=PHOTOS) if CONFIG.get("wardrobe_source", "mock") == "mock" else None,
    store=SqliteChallengeStore(CONFIG.get("seed", []), con=_con),
    coach_memory=CoachMemory(_con),
)
