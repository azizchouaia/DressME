"""One shared instance, so the API, the orchestrator tool and the challenges agent use the same store."""

from .agent import ShareAgent

share_agent = ShareAgent()
