"""What the BO6 LLM adds to M7 on requests the rules do not understand (evaluation/queries_llm.yaml).

    cd backend && python -m modules.m07_local_catalogue.evaluation.llm_eval qwen2.5:7b [qwen2.5:3b ...]

For each request: rules alone vs rules + LLM (understand.py, with its checks). Measured: the piece type is
understood and is one of the expected ones, the budget / city asked are right, the catalogue has pieces
for what was understood, and the LLM latency (CPU). Writes evaluation/RESULTS_LLM.md.
"""

import argparse
import asyncio
import statistics
import time
from pathlib import Path

import yaml

from ..contract import ParsedQuery
from ..llm import LLM
from ..paths import CATALOGUE_CSV, CONFIG, INDEX_DIR
from ..pipeline import filter, parse, understand
from ..pipeline.catalogue import Catalogue
from ..taxonomy import SUBCATEGORIES

HERE = Path(__file__).parent


def understood_type(parsed: ParsedQuery) -> str | None:
    return parsed.subcategory or parsed.category


def score(parsed: ParsedQuery, expect: dict, catalogue) -> dict:
    kind = understood_type(parsed)
    allowed = expect.get("type") or []
    # A subcategory must be one of the expected ones; a bare category (no subcategory) must contain one.
    # ("dress" is both a subcategory and a category: compare like with like.)
    if parsed.subcategory:
        type_ok = parsed.subcategory in allowed
    else:
        type_ok = bool(kind) and any(SUBCATEGORIES.get(a, (None,))[0] == kind for a in allowed)
    budget_ok = expect.get("max_price") is None or parsed.max_price_tnd == expect["max_price"]
    city_ok = expect.get("city") is None or parsed.city == expect["city"]
    pieces = int(filter.run(catalogue, parsed).sum()) if kind else 0
    return {"type": type_ok, "budget": budget_ok, "city": city_ok, "pieces": pieces, "kind": kind}


async def with_llm(llm: LLM, query: str) -> tuple[ParsedQuery, float, dict | None]:
    started = time.perf_counter()
    slots = await understand.run(llm, query)
    seconds = time.perf_counter() - started
    if not slots:
        return parse.parse(query), seconds, None
    parsed = parse.parse(slots.get("query", query))
    for key in ("subcategory", "color", "gender", "max_price_tnd", "city"):
        if slots.get(key) is not None:
            setattr(parsed, key, slots[key])
    if slots.get("subcategory"):
        parsed.category = SUBCATEGORIES[slots["subcategory"]][0]
    return parsed, seconds, slots


async def main(models: list[str]) -> None:
    queries = yaml.safe_load((HERE / "queries_llm.yaml").read_text(encoding="utf-8"))
    catalogue = Catalogue.load(CATALOGUE_CSV, INDEX_DIR, CONFIG["embedding_dim"])
    rows = {"rules": []}
    for q in queries:
        rows["rules"].append(
            score(parse.parse(q["query"]), q["expect"], catalogue) | {"id": q["id"], "s": 0.0}
        )
    details = {}
    for model in models:
        llm = LLM({**CONFIG["llm"], "enabled": True, "model": model, "timeout_s": 300})
        await llm.json(understand.SYSTEM, "warm up", understand.SCHEMA, 5)  # load the model once
        rows[model] = []
        for q in queries:
            parsed, seconds, slots = await with_llm(llm, q["query"])
            rows[model].append(score(parsed, q["expect"], catalogue) | {"id": q["id"], "s": seconds})
            details.setdefault(q["id"], {})[model] = (slots or {}).get("query", "-")
            print(f"{model:12} {q['id']} {seconds:5.1f}s {rows[model][-1]['kind']!s:12} {slots}")

    n = len(queries)
    lines = [
        "# BO6 LLM in M7 — requests the rules do not understand",
        "",
        f"{n} hand-written requests (`queries_llm.yaml`, FR / EN / darija / Arabic) where `parse.py` "
        "finds no piece, colour or photo. Rules alone vs rules + LLM (`pipeline/understand.py`, with "
        "its checks). CPU only (Intel i7-1165G7, no GPU).",
        "",
        "| | type understood and right | budget / city right | pieces found | LLM latency (median) |",
        "|---|---|---|---|---|",
    ]
    for name, r in rows.items():
        right = sum(x["type"] for x in r)
        bc = sum(x["budget"] and x["city"] for x in r)
        found = sum(x["pieces"] > 0 for x in r)
        lat = f"{statistics.median(x['s'] for x in r):.1f} s" if name != "rules" else "-"
        lines.append(f"| {name} | {right}/{n} | {bc}/{n} | {found}/{n} | {lat} |")
    lines += [
        "",
        "## Per request (French rewrite by the LLM)",
        "",
        "| id | request | " + " | ".join(models) + " |",
        "|---|---|" + "---|" * len(models),
    ]
    for q in queries:
        cells = []
        for m in models:
            r = next(x for x in rows[m] if x["id"] == q["id"])
            mark = "✅" if r["type"] else "❌"
            cells.append(f"{mark} {details[q['id']][m]} → {r['kind'] or '-'}")
        lines.append(f"| {q['id']} | {q['query']} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "Caveat: the requests and their intent were written by the same team as the system; a set "
        "written by someone else would give a fairer figure.",
    ]
    (HERE / "RESULTS_LLM.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:12]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("models", nargs="+")
    asyncio.run(main(ap.parse_args().models))
