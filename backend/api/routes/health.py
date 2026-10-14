from fastapi import APIRouter

from orchestrator.registry import tool_names

router = APIRouter()


@router.get("/health")
def health():
    return {"api": "ok", "tools": tool_names()}
