"""One shared instance for the API and the orchestrator tool.

The API reads the real wardrobe from M1 (`wardrobe_source: m1`, default). For the demo users, an empty M1
wardrobe is filled once with the BO7 demo garments (bo/bo7_sharing/m01_seed.py, through M1's API).
Its memory is kept in SQLite (memory.py): challenges, participations, posts, likes, comments and what the
coach remembers survive a restart of the server. `BO7_MEMORY_PATH=:memory:` keeps everything in RAM (tests).
"""

from .agent import CONFIG, ChallengesAgent
from .memory import CoachMemory, SqliteChallengeStore, connect
from .wardrobe import PHOTOS, M1Wardrobe, MockWardrobe


def _wardrobe():
    source = CONFIG.get("wardrobe_source", "m1")
    if source == "m1":
        try:
            from bo.bo7_sharing import m01_seed

            return M1Wardrobe(
                seeder=m01_seed.seed,
                seed_users=m01_seed.DEMO_USERS,
                local_brands=m01_seed.local_brands(),
                resolve=m01_seed.resolve,
            )
        except ImportError:  # BO7 folder absent: plain M1 wardrobe
            return M1Wardrobe()
    if source == "mock":
        return MockWardrobe(photos_dir=PHOTOS)
    return None  # http: the agent builds HttpWardrobe from config.yaml


_con = connect()
challenges_agent = ChallengesAgent(
    wardrobe=_wardrobe(),
    store=SqliteChallengeStore(CONFIG.get("seed", []), con=_con),
    coach_memory=CoachMemory(_con),
)
