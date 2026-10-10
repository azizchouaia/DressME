from fastapi import APIRouter

from orchestrator.registry import AGENTS

router = APIRouter()


@router.get("/health")
def health():
    return {"api": "ok", "agents": [a.health() for a in AGENTS.values()]}
