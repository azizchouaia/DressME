"""Events the dashboard reads: M7's search / click log (real) and the simulator's log (simulated)."""

from datetime import datetime

from modules.m07_local_catalogue import events as m7_events

from ..paths import SIMULATED_LOG


def log_paths() -> dict:
    return {"real": m7_events.log_path(), "simulated": SIMULATED_LOG}


def load(sources: list[str], since: datetime, until: datetime) -> list[dict]:
    """Events of the chosen logs between since and until, each tagged with `_source`, oldest first."""
    out = []
    for source in sources:
        path = log_paths().get(source)
        if path is None:
            continue
        for event in m7_events.read(path, since):
            if datetime.fromisoformat(event["ts"]) <= until:
                out.append({**event, "_source": source})
    return sorted(out, key=lambda e: e["ts"])


def searches(events: list[dict]) -> list[dict]:
    """First pages only: 'show more' of the same request is not a new search."""
    return [e for e in events if e["type"] == "local_search" and not e["data"].get("offset")]
