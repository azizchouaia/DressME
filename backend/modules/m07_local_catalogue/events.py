"""Search and click log of M7: one JSON line per event, read by the boutique dashboard (M14).

    python -m modules.m07_local_catalogue.events             # summary of the log
    python -m modules.m07_local_catalogue.events --days 7    # last 7 days only

Each line has the fields of the shared `Event` schema (event_id, user_id, type, target_id, value, channel,
ts) plus a `data` object, so it can move to the shared event store once M6 adds the types:
- `local_search`  target_id = search_id, value = the request; data = explicit filters, how the request was
  understood (parsed), number of matches, the results shown (product, shop, match, price), note, latency.
- `product_view`  the user opened a result; `shop_click` the user went to the shop's website.
  target_id = product_id; data = search_id, shop, rank in the list.

The log lives in ml/data/logs/ (never git). No IP or device data is kept; user_id only when the caller
gives it. Writing never breaks a search: errors are logged and ignored.
"""

import argparse
import json
import logging
import threading
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .paths import CONFIG, REPO_ROOT

log = logging.getLogger("m07.events")
_lock = threading.Lock()
CLICK_TYPES = ("product_view", "shop_click")


def log_path() -> Path | None:
    """JSONL file of the events, None when logging is off (config `log_events: false`)."""
    if not CONFIG.get("log_events", True):
        return None
    return REPO_ROOT / CONFIG.get("log_dir", "ml/data/logs") / "m07_events.jsonl"


def _write(event: dict, path: Path | None = None) -> None:
    path = path or log_path()
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, ensure_ascii=False)
        with _lock, path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError as exc:
        log.warning("could not write the M7 event log %s: %s", path, exc)


def _event(
    type_: str,
    user_id: str | None,
    target_id: str | None,
    value: str | None,
    channel: str,
    data: dict,
    ts: datetime | None = None,
):
    return {
        "event_id": f"evt_{uuid.uuid4().hex[:16]}",
        "user_id": user_id,
        "type": type_,
        "target_id": target_id,
        "value": value,
        "channel": channel,
        "ts": (ts or datetime.now(UTC)).isoformat(timespec="milliseconds"),
        "data": data,
    }


_FILTERS = ("city", "max_price_tnd", "min_price_tnd", "category", "subcategory", "color", "gender")


def log_search(
    req: dict,
    out: dict,
    latency_ms: float,
    channel: str = "api",
    ts: datetime | None = None,
    path: Path | None = None,
) -> str:
    """Write one `local_search` event; returns its id (the `search_id` given back to the caller).

    `ts` and `path` are for M14's traffic simulator (past dates, its own file); the API never sets them.
    """
    search_id = f"srch_{uuid.uuid4().hex[:16]}"
    parsed = out.get("parsed") or {}
    data = {
        "query": req.get("query") or "",
        "gap": req.get("gap"),
        "filters": {k: req[k] for k in _FILTERS if req.get(k) is not None},
        "has_image": req.get("image_embedding") is not None,
        "has_style": req.get("style_vector") is not None,
        "k": req.get("k"),
        "offset": req.get("offset") or 0,  # > 0: the user asked for more results of the same search
        "parsed": {
            k: parsed.get(k)
            for k in (
                "category",
                "subcategory",
                "color",
                "gender",
                "max_price_tnd",
                "min_price_tnd",
                "city",
                "governorate",
                "translated",
                "corrected",
            )
        },
        "total_matches": out.get("total_matches", 0),
        "results": [
            {
                "product_id": r["product_id"],
                "shop": r["shop"],
                "match": r["match"],
                "price_tnd": r.get("price_tnd"),
            }
            for r in out.get("results", [])
        ],
        "note": out.get("note"),
        "latency_ms": round(latency_ms, 1),
    }
    value = " ".join(t for t in (req.get("query"), req.get("gap")) if t) or None
    event = _event("local_search", req.get("user_id"), search_id, value, channel, data, ts)
    event["event_id"] = search_id
    _write(event, path)
    return search_id


def log_click(
    type_: str,
    product_id: str,
    search_id: str | None = None,
    shop: str | None = None,
    rank: int | None = None,
    user_id: str | None = None,
    channel: str = "app",
    ts: datetime | None = None,
    path: Path | None = None,
) -> str:
    """Write one `product_view` / `shop_click` event; returns its id."""
    if type_ not in CLICK_TYPES:
        raise ValueError(f"unknown event type {type_!r}")
    event = _event(
        type_, user_id, product_id, None, channel, {"search_id": search_id, "shop": shop, "rank": rank}, ts
    )
    _write(event, path)
    return event["event_id"]


def read(path: Path | None = None, since: datetime | None = None) -> list[dict]:
    """Events of the log (oldest first), optionally only those after `since`; bad lines are skipped."""
    path = path or log_path()
    if path is None or not path.is_file():
        return []
    events = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if since is None or datetime.fromisoformat(event["ts"]) >= since:
                events.append(event)
    return events


def summary(events: list[dict]) -> dict:
    """What M14's dashboard starts from: volume, unmet demand, and per shop impressions / views / clicks."""
    searches = [e for e in events if e["type"] == "local_search"]
    empty = [e for e in searches if not e["data"]["results"]]
    impressions = Counter(r["shop"] for e in searches for r in e["data"]["results"])
    views = Counter(e["data"].get("shop") for e in events if e["type"] == "product_view")
    clicks = Counter(e["data"].get("shop") for e in events if e["type"] == "shop_click")
    latencies = sorted(e["data"]["latency_ms"] for e in searches)
    return {
        "searches": len(searches),
        "users": len({e["user_id"] for e in searches if e["user_id"]}),
        "zero_result_rate": len(empty) / len(searches) if searches else 0.0,
        "darija_share": sum(bool(e["data"]["parsed"].get("translated")) for e in searches) / len(searches)
        if searches
        else 0.0,
        "latency_ms_p50": latencies[len(latencies) // 2] if latencies else None,
        "top_queries": Counter((e["value"] or "").lower() for e in searches).most_common(10),
        "top_unmet": Counter((e["value"] or "").lower() for e in empty).most_common(10),
        "top_subcategories": Counter(
            e["data"]["parsed"].get("subcategory") or e["data"]["parsed"].get("category") or "?"
            for e in searches
        ).most_common(10),
        "shops": {
            shop: {"impressions": n, "views": views[shop], "clicks": clicks[shop], "ctr": clicks[shop] / n}
            for shop, n in impressions.most_common()
        },
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--days", type=int, help="only the last N days")
    args = parser.parse_args(argv)
    since = datetime.now(UTC) - timedelta(days=args.days) if args.days else None
    print(json.dumps(summary(read(since=since)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
