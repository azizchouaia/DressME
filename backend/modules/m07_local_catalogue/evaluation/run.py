"""Evaluate M7 on the hand-written test set: request understanding + ranking quality, with ablations.

    cd backend
    python -m modules.m07_local_catalogue.evaluation.run            # -> evaluation/RESULTS.md
    python -m modules.m07_local_catalogue.evaluation.run --no-clip  # without FashionCLIP (fast)

Two levels:
1. Understanding (gold labels). For each request of queries.yaml the intent is written by hand; what
   parse.py understood is compared field by field (type, colour, gender, budget, city).
2. Ranking (silver labels). Each product gets a grade from the written intent and its attributes:
   2 = right type and every criterion asked is met; 1 = right type but a criterion is missing or unknown
   (colour, gender, city, material); 0 = wrong type, over budget or for the other gender.
   Metrics: nDCG@10, P@5 (grade 2), MRR (first grade 2), wrong@5 (grade 0 among the first 5 shown),
   zero-result rate, latency. Silver grades use the same attributes as the filters: they measure the
   ranking and the value of parsing against raw baselines, not what the photos show. Human grades:
   fill `human_rel` in ml/data/shops/eval/judgments_todo.csv, save it as judgments.csv and run again.

Variants (ablation): BM25 alone and FashionCLIP alone on the raw request (no parsing, no filters); the
pipeline without FashionCLIP, with the visual score only, without the darija lexicon, without gender;
the full pipeline.
"""

import argparse
import asyncio
import csv
import json
import math
import statistics
import time
from collections import defaultdict
from contextlib import ExitStack
from datetime import date
from pathlib import Path
from unittest import mock

import numpy as np
import yaml

from ..agent import LocalShopAgent
from ..paths import CATALOGUE_CSV, CONFIG, DATA_DIR, INDEX_DIR, model_source
from ..pipeline import filter as filter_module
from ..pipeline import parse as parse_module
from ..pipeline.catalogue import Catalogue
from ..pipeline.retrieve import tokenize
from ..scraper.normalize import fold
from ..taxonomy import OPPOSITE_GENDER, canonical_city, governorate

HERE = Path(__file__).resolve().parent
QUERIES = HERE / "queries.yaml"
RESULTS_MD = HERE / "RESULTS.md"
EVAL_DIR = DATA_DIR / "eval"
K = 10
FIELDS = ("type", "color", "gender", "max_price", "min_price", "city")
LANGS = ("fr", "en", "darija", "arabic")

VARIANTS = {
    "bm25_raw": "BM25 alone, raw request",
    "clip_raw": "FashionCLIP alone, raw request",
    "no_clip": "Pipeline without FashionCLIP",
    "visual_only": "Pipeline, visual score only",
    "no_darija": "Pipeline without darija lexicon",
    "no_gender": "Pipeline without gender",
    "soft_color": "Pipeline, colour as a soft score (before)",
    "full": "Full pipeline",
}
CLIP_VARIANTS = {"clip_raw", "visual_only"}


def load_queries(path: Path = QUERIES) -> list[dict]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# --- understanding --------------------------------------------------------------------------------


def understood(parsed: dict) -> dict:
    """What parse.py read, in the fields of queries.yaml."""
    return {
        "type": parsed.get("subcategory") or parsed.get("category"),
        "color": parsed.get("color"),
        "gender": parsed.get("gender"),
        "max_price": parsed.get("max_price_tnd"),
        "min_price": parsed.get("min_price_tnd"),
        "city": parsed.get("city"),
    }


def parse_scores(queries: list[dict], parsed_by_id: dict[str, dict]) -> dict:
    """Accuracy per field and exact match (every field right), overall and per language; plus the misses."""
    hits: dict[tuple[str, str], list[bool]] = defaultdict(list)
    misses = []
    for q in queries:
        got = understood(parsed_by_id[q["id"]])
        exact = True
        for field in FIELDS:
            expected = q["expect"].get(field)
            ok = got[field] == expected or (
                isinstance(expected, int | float) and got[field] is not None and float(got[field]) == expected
            )
            exact &= ok
            for group in ("all", q["lang"]):
                hits[group, field].append(ok)
            if not ok:
                misses.append(
                    {
                        "id": q["id"],
                        "query": q["query"],
                        "field": field,
                        "expected": expected,
                        "got": got[field],
                    }
                )
        for group in ("all", q["lang"]):
            hits[group, "exact"].append(exact)
    return {
        "accuracy": {f"{g}/{f}": sum(v) / len(v) for (g, f), v in hits.items()},
        "count": {g: len(hits[g, "exact"]) for g in ("all", *LANGS) if hits[g, "exact"]},
        "misses": misses,
    }


# --- relevance and metrics ------------------------------------------------------------------------


def relevance(product: dict, intent: dict) -> int:
    """Silver grade of one product for one written intent: 0 wrong, 1 partial, 2 perfect."""
    kind = intent.get("type")
    if kind and kind not in (product["subcategory"], product["category"]):
        return 0
    price = product.get("price_tnd")
    if price is not None:
        if intent.get("max_price") is not None and price > intent["max_price"]:
            return 0
        if intent.get("min_price") is not None and price < intent["min_price"]:
            return 0
    gender, asked = product.get("gender") or "", intent.get("gender")
    if asked and gender == OPPOSITE_GENDER.get(asked):
        return 0
    colour = product.get("color") or ""
    if intent.get("color") and colour and colour != intent["color"]:
        return 0  # a colour asked for is strict: another colour is a wrong answer
    soft = []
    if intent.get("max_price") is not None or intent.get("min_price") is not None:
        soft.append(price is not None)
    if intent.get("color"):
        soft.append(colour == intent["color"])  # unknown colour: partial
    if asked:
        soft.append(gender in (asked, "unisex"))
    if intent.get("city"):
        city = canonical_city(intent["city"]) or intent["city"]
        cities = set(filter(None, (product.get("city") or "").split("; ")))
        govs = set(filter(None, (product.get("governorate") or "").split("; ")))
        soft.append(city in cities or governorate(city) in govs)
    if intent.get("name_any"):
        name = fold(product.get("product_name") or "")
        soft.append(any(fold(w) in name for w in intent["name_any"]))
    return 2 if all(soft) else 1


def dcg(grades: list[int]) -> float:
    return sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(grades))


def metrics(ranked: list[int], ideal: list[int]) -> dict:
    """Metrics of one ranked list of grades; `ideal` = grades of every product that could be shown."""
    top = ranked[:K]
    idcg = dcg(sorted(ideal, reverse=True)[:K])
    shown5 = top[:5]
    return {
        "ndcg": dcg(top) / idcg if idcg else None,  # None: nothing relevant exists for this request
        "p5": sum(g == 2 for g in shown5) / 5,
        "mrr": next((1 / (i + 1) for i, g in enumerate(top) if g == 2), 0.0),
        "wrong5": sum(g == 0 for g in shown5) / len(shown5) if shown5 else None,
        "zero": not top,
    }


def mean(values) -> float | None:
    values = [v for v in values if v is not None]
    return statistics.fmean(values) if values else None


# --- runs -----------------------------------------------------------------------------------------


def raw_bm25(catalogue: Catalogue, query: str) -> list[int]:
    scores = catalogue.bm25.scores(tokenize(query)).astype(float)
    scores[~catalogue.available] = -np.inf
    order = [int(i) for i in np.argsort(-scores)[:K]]
    return [i for i in order if scores[i] > 0]


def raw_clip(catalogue: Catalogue, encoder, query: str) -> list[int]:
    scores = (catalogue.embeddings @ encoder.encode_texts([query])[0]).astype(float)
    scores[~(catalogue.available & catalogue.has_embedding)] = -np.inf
    return [int(i) for i in np.argsort(-scores)[:K]]


def _patches(variant: str) -> list:
    if variant == "no_darija":
        return [mock.patch.object(parse_module.darija, "translate", lambda text: None)]
    if variant == "no_gender":
        return [mock.patch.object(parse_module, "gender_from_query", lambda folded: None)]
    if variant == "soft_color":  # the colour no longer filters, it only ranks (behaviour before 2026-10-15)
        strict = filter_module.run
        return [
            mock.patch.object(
                filter_module, "run", lambda *args, **kwargs: strict(*args, **{**kwargs, "use_color": False})
            )
        ]
    return []


async def run_variant(variant: str, queries: list[dict], catalogue: Catalogue, encoder) -> dict[str, dict]:
    """query id -> {ids: product indexes shown, parsed, ms}."""
    row_of = {p["product_id"]: i for i, p in enumerate(catalogue.products)}
    out = {}
    if variant in ("bm25_raw", "clip_raw"):
        for q in queries:
            started = time.perf_counter()
            ids = (
                raw_bm25(catalogue, q["query"])
                if variant == "bm25_raw"
                else raw_clip(catalogue, encoder, q["query"])
            )
            out[q["id"]] = {"ids": ids, "parsed": None, "ms": 1000 * (time.perf_counter() - started)}
        return out
    config = dict(CONFIG)
    if variant == "visual_only":
        config["weights"] = {"visual": 1.0, "text": 0.0, "attributes": 0.0, "style": 0.0}
    agent = LocalShopAgent(config, catalogue, None if variant == "no_clip" else encoder)
    with ExitStack() as stack:
        for patch in _patches(variant):
            stack.enter_context(patch)
        for q in queries:
            started = time.perf_counter()
            res = await agent({"query": q["query"], "k": K})
            ms = 1000 * (time.perf_counter() - started)
            out[q["id"]] = {
                "ids": [row_of[r["product_id"]] for r in res["results"]],
                "parsed": res["parsed"],
                "ms": ms,
            }
    return out


async def evaluate(queries: list[dict], catalogue: Catalogue, encoder=None) -> dict:
    """All variants on all requests: grades, metrics, understanding (FashionCLIP ones need an encoder)."""
    grades = {q["id"]: np.array([relevance(p, q["expect"]) for p in catalogue.products]) for q in queries}
    ideal = {qid: g[catalogue.available].tolist() for qid, g in grades.items()}
    variants = [v for v in VARIANTS if encoder is not None or v not in CLIP_VARIANTS]
    runs, per_query = {}, defaultdict(dict)
    for variant in variants:
        runs[variant] = await run_variant(variant, queries, catalogue, encoder)
        for q in queries:
            shown = runs[variant][q["id"]]["ids"]
            per_query[q["id"]][variant] = metrics([int(grades[q["id"]][i]) for i in shown], ideal[q["id"]])

    def summary(variant: str, ids: list[str]) -> dict:
        rows = [per_query[i][variant] for i in ids]
        return {
            "ndcg": mean(r["ndcg"] for r in rows),
            "p5": mean(r["p5"] for r in rows),
            "mrr": mean(r["mrr"] for r in rows),
            "wrong5": mean(r["wrong5"] for r in rows),
            "zero": mean(float(r["zero"]) for r in rows),
            "n_ndcg": sum(r["ndcg"] is not None for r in rows),
        }

    by_lang = {lang: [q["id"] for q in queries if q["lang"] == lang] for lang in LANGS}
    latencies = sorted(r["ms"] for r in runs["full"].values())
    return {
        "date": date.today().isoformat(),
        "queries": len(queries),
        "catalogue": len(catalogue),
        "with_clip": encoder is not None,
        "photo_gender_share": mean(float(p.get("gender_source") == "photo") for p in catalogue.products),
        "summary": {v: summary(v, [q["id"] for q in queries]) for v in variants},
        "by_lang": {v: {lang: summary(v, ids) for lang, ids in by_lang.items() if ids} for v in variants},
        "parse": {
            v: parse_scores(queries, {qid: r["parsed"] for qid, r in runs[v].items()})
            for v in ("full", "no_darija", "no_gender")
        },
        "latency_ms": {
            "p50": latencies[len(latencies) // 2],
            "p95": latencies[int(0.95 * (len(latencies) - 1))],
        },
        "per_query": per_query,
        "runs": {v: {qid: r["ids"] for qid, r in runs[v].items()} for v in variants},
        "grades": {qid: g for qid, g in grades.items()},
    }


# --- human judgments ------------------------------------------------------------------------------

JUDGMENT_COLUMNS = [
    "query_id", "lang", "query", "product_id", "shop", "product_name", "price_tnd", "color", "gender",
    "image_url", "product_url", "silver_rel", "human_rel",
]  # fmt: skip


def write_judgments_todo(path: Path, queries: list[dict], catalogue: Catalogue, result: dict) -> int:
    """Pool of the top 10 of the raw baselines and the full pipeline, to grade by hand (0 / 1 / 2)."""
    rows = []
    for q in queries:
        pooled = dict.fromkeys(
            i
            for v in ("full", "bm25_raw", "clip_raw")
            if v in result["runs"]
            for i in result["runs"][v][q["id"]]
        )
        for i in pooled:
            p = catalogue.products[i]
            rows.append(
                {
                    "query_id": q["id"], "lang": q["lang"], "query": q["query"],
                    "product_id": p["product_id"],
                    "shop": p["shop_name"], "product_name": p["product_name"], "price_tnd": p["price_tnd"],
                    "color": p.get("color"), "gender": p.get("gender"), "image_url": p["image_url"],
                    "product_url": p["product_url"], "silver_rel": int(result["grades"][q["id"]][i]),
                    "human_rel": "",
                }
            )  # fmt: skip
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=JUDGMENT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def read_judgments(path: Path) -> dict[tuple[str, str], int]:
    """(query_id, product_id) -> human grade, for the rows where human_rel is 0, 1 or 2."""
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8-sig") as fh:
        return {
            (r["query_id"], r["product_id"]): int(r["human_rel"])
            for r in csv.DictReader(fh)
            if r.get("human_rel", "").strip() in ("0", "1", "2")
        }


def human_scores(queries: list[dict], catalogue: Catalogue, result: dict, judged: dict) -> dict:
    """nDCG@10 / P@5 with human grades (unjudged = 0) and agreement between silver and human grades."""
    pid = [p["product_id"] for p in catalogue.products]
    out = {}
    for variant, runs in result["runs"].items():
        rows = []
        for q in queries:
            pool = [g for (qid, _), g in judged.items() if qid == q["id"]]
            if not pool:
                continue
            ranked = [judged.get((q["id"], pid[i]), 0) for i in runs[q["id"]]]
            rows.append(metrics(ranked, pool))
        out[variant] = {
            "ndcg": mean(r["ndcg"] for r in rows),
            "p5": mean(r["p5"] for r in rows),
            "n": len(rows),
        }
    pairs = [
        (int(result["grades"][qid][pid.index(p)]), g)
        for (qid, p), g in judged.items()
        if qid in result["grades"] and p in pid
    ]
    agreement = sum(s == h for s, h in pairs) / len(pairs) if pairs else None
    # Cohen's kappa: agreement corrected for chance
    if pairs:
        expected = sum(
            (sum(s == c for s, _ in pairs) / len(pairs)) * (sum(h == c for _, h in pairs) / len(pairs))
            for c in (0, 1, 2)
        )
        kappa = (agreement - expected) / (1 - expected) if expected < 1 else None
    else:
        kappa = None
    return {"variants": out, "pairs": len(pairs), "agreement": agreement, "kappa": kappa}


# --- report ---------------------------------------------------------------------------------------


def _pct(x: float | None) -> str:
    return "–" if x is None else f"{100 * x:.1f} %"


def _num(x: float | None) -> str:
    return "–" if x is None else f"{x:.3f}"


def report(result: dict, human: dict | None, judgments_rows: int) -> str:
    s = result["summary"]
    lines = [
        "# M7 evaluation results",
        "",
        f"Run on {result['date']}: {result['queries']} hand-written requests (`queries.yaml`) against the "
        f"catalogue of {result['catalogue']} products. Generated by `evaluation/run.py`, "
        "do not edit by hand.",
        "",
        "## 1. Understanding the request (gold labels)",
        "",
        "Share of requests where `parse.py` read the field as written in `queries.yaml`. "
        "*Exact* = every field right.",
        "",
        "| Language | Requests | Type | Colour | Gender | Budget max | City | Exact "
        "| Exact without darija lexicon |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    acc, acc_nd = result["parse"]["full"]["accuracy"], result["parse"]["no_darija"]["accuracy"]
    for group in ("all", *LANGS):
        if group not in result["parse"]["full"]["count"]:
            continue
        cells = [_pct(acc[f"{group}/{f}"]) for f in ("type", "color", "gender", "max_price", "city", "exact")]
        name = "**All**" if group == "all" else group
        n = result["parse"]["full"]["count"][group]
        lines.append(f"| {name} | {n} | " + " | ".join(cells) + f" | {_pct(acc_nd[f'{group}/exact'])} |")
    misses = result["parse"]["full"]["misses"]
    lines += ["", f"Fields read wrong by the full pipeline ({len(misses)}):", ""]
    if misses:
        lines += ["| Request | Field | Expected | Understood |", "|---|---|---|---|"]
        lines += [f"| `{m['query']}` | {m['field']} | {m['expected']} | {m['got']} |" for m in misses]
    else:
        lines.append("none.")

    lines += [
        "",
        "## 2. Ranking quality (silver labels)",
        "",
        "Grade of each product from the written intent and the catalogue attributes: 2 = right type "
        "and every criterion met, 1 = right type but a criterion missing or unknown, 0 = wrong type, "
        "over budget or the other gender. nDCG@10 is averaged over the requests for which a relevant "
        "product exists.",
        "",
        "| Variant | nDCG@10 | P@5 | MRR | Wrong in top 5 | No result |",
        "|---|---|---|---|---|---|",
    ]
    for v, label in VARIANTS.items():
        if v in s:
            r = s[v]
            name = f"**{label}**" if v == "full" else label
            lines.append(
                f"| {name} | {_num(r['ndcg'])} | {_pct(r['p5'])} | {_num(r['mrr'])} "
                f"| {_pct(r['wrong5'])} | {_pct(r['zero'])} |"
            )
    lines += [
        "",
        "### Per language (nDCG@10 / P@5)",
        "",
        "| Variant | " + " | ".join(LANGS) + " |",
        "|---|" + "---|" * len(LANGS),
    ]
    for v in ("bm25_raw", "clip_raw", "no_darija", "full"):
        if v in result["by_lang"]:
            cells = [
                f"{_num(result['by_lang'][v][lang]['ndcg'])} / {_pct(result['by_lang'][v][lang]['p5'])}"
                if lang in result["by_lang"][v]
                else "–"
                for lang in LANGS
            ]
            lines.append(f"| {VARIANTS[v]} | " + " | ".join(cells) + " |")
    lat = result["latency_ms"]
    lines += [
        "",
        f"Latency of the full pipeline (one request, CPU, model loaded): p50 {lat['p50']:.0f} ms, "
        f"p95 {lat['p95']:.0f} ms.",
        "",
        "**Limits.** Silver grades come from the same attributes the filters use (type, price, colour, "
        "gender, city), so the pipeline is favoured on those criteria by construction; they show what "
        "parsing brings against raw baselines and how the ranking orders what passes the filters. They do "
        f"not look at the photos, and {_pct(result['photo_gender_share'])} of the genders are estimated "
        "from the photo (accuracy in `ml/data/shops/attributes_report.md`).",
        "",
        "## 3. Human grades",
        "",
    ]
    if human and human["pairs"]:
        lines += [
            f"{human['pairs']} products graded by hand (`ml/data/shops/eval/judgments.csv`). "
            f"Agreement with the silver grades: {_pct(human['agreement'])}, "
            f"Cohen's kappa {_num(human['kappa'])}.",
            "",
            "| Variant | nDCG@10 (human) | P@5 (human) | Requests |",
            "|---|---|---|---|",
        ]
        for v, label in VARIANTS.items():
            if v in human["variants"]:
                r = human["variants"][v]
                lines.append(f"| {label} | {_num(r['ndcg'])} | {_pct(r['p5'])} | {r['n']} |")
    else:
        lines += [
            f"Not done yet. `ml/data/shops/eval/judgments_todo.csv` lists the {judgments_rows} products "
            "shown by the full pipeline and the two raw baselines (top 10 each): fill `human_rel` with "
            "0 / 1 / 2 looking at the "
            "photo and the link, save the file as `judgments.csv` and run again.",
        ]
    return "\n".join(lines) + "\n"


def _jsonable(result: dict) -> dict:
    out = dict(result)
    out["grades"] = {
        qid: np.flatnonzero(g).tolist() for qid, g in result["grades"].items()
    }  # relevant indexes
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--queries", type=Path, default=QUERIES)
    parser.add_argument("--no-clip", action="store_true", help="skip FashionCLIP (text variants only)")
    args = parser.parse_args(argv)

    queries = load_queries(args.queries)
    catalogue = Catalogue.load(CATALOGUE_CSV, INDEX_DIR, CONFIG["embedding_dim"])
    encoder = None
    if not args.no_clip:
        from ..pipeline.encoder import FashionCLIP

        encoder = FashionCLIP(model_source())
    result = asyncio.run(evaluate(queries, catalogue, encoder))
    n_todo = write_judgments_todo(EVAL_DIR / "judgments_todo.csv", queries, catalogue, result)
    judged = read_judgments(EVAL_DIR / "judgments.csv")
    human = human_scores(queries, catalogue, result, judged) if judged else None
    (EVAL_DIR / "run.json").write_text(json.dumps(_jsonable(result), indent=1), encoding="utf-8")
    RESULTS_MD.write_text(report(result, human, n_todo), encoding="utf-8")
    full = result["summary"]["full"]
    print(
        f"full pipeline: nDCG@10 {_num(full['ndcg'])}, P@5 {_pct(full['p5'])}, "
        f"exact understanding {_pct(result['parse']['full']['accuracy']['all/exact'])} -> {RESULTS_MD}"
    )


if __name__ == "__main__":
    main()
