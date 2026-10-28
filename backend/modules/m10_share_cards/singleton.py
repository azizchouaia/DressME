"""One shared instance, so the API, the orchestrator tool and the challenges agent use the same store.

Its memory is kept in SQLite (memory.py): cards, link opens and sign-ups survive a restart of the server.
`BO7_SHARE_MEMORY_PATH=:memory:` keeps everything in RAM (tests).
"""

from .agent import CONFIG, ShareAgent
from .memory import SqliteShareStore

share_agent = ShareAgent(store=SqliteShareStore(use_s3=CONFIG.get("storage") == "s3"))
