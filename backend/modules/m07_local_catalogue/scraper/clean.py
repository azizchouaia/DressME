"""Clean the scraped catalogue into the knowledge base used by M7.

    cd backend
    python -m modules.m07_local_catalogue.scraper.clean   # local_catalogue.csv -> local_catalogue_clean.csv
    python -m modules.m07_local_catalogue.scraper.clean --no-url-check

Steps (each one is counted in ml/data/shops/cleaning_report.md):
1. prices: numeric, > 0, in TND (every adapter only keeps TND prices); outliers are flagged, not changed
2. foreign labels and children's pieces that slipped through the scraper are dropped
3. categories -> shared contract (GarmentCategory) + subcategory; colours -> code + French name + hex;
   gender when the name or URL says it (women / men / unisex, gender_source=text; the photo fills the
   rest later, pipeline/attributes.py); sizes -> one notation, sorted; cities -> canonical names + governorate
4. duplicates: same photo (perceptual hash) + same name + same price, within a shop or across shops
5. URLs: every product page and image URL is requested; dead product pages (404/410, redirect to the
   home page) are dropped, other failures are flagged
6. missing values stay empty and are listed in `missing_fields`; nothing is guessed
"""

import argparse
import csv
import hashlib
import json
import logging
import re
import statistics
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image

from ..paths import DATA_DIR as DATA
from ..taxonomy import COLORS, canonical_city, classify, gender_from_text, governorate
from .client import Http
from .normalize import KIDS, categorize, fold, is_non_fashion, origin_type
from .shops import SHOPS

NAME_ONLY_SHOPS = {shop.name for shop in SHOPS if shop.options.get("name_only")}

COLUMNS = [
    "product_id",
    "shop_name",
    "shop_url",
    "product_name",
    "category",
    "subcategory",
    "label_fr",
    "color",
    "color_fr",
    "color_hex",
    "gender",
    "gender_source",
    "size",
    "size_type",
    "price_tnd",
    "currency",
    "city",
    "governorate",
    "available",
    "origin_type",
    "image_url",
    "image_path",
    "product_url",
    "last_checked",
    "product_url_status",
    "image_url_status",
    "missing_fields",
    "quality_flags",
]
LETTER_ORDER = ["XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL", "XXXXL"]
_LETTER_RANK = {s: i for i, s in enumerate(LETTER_ORDER)}

log = logging.getLogger("localcatalogue.clean")


# --- sizes ----------------------------------------------------------------------------------------


def _norm_size_token(token: str) -> str:
    token = token.strip().upper().replace(",", ".")
    token = re.sub(r"\b([2-4])XL\b", lambda m: "X" * int(m.group(1)) + "L", token)
    if token in ("ST", "STANDARD", "TU", "UNIQUE", "TAILLE UNIQUE", "ONE SIZE"):
        return "Taille unique"
    if m := re.fullmatch(r"(\d+)\s*CM", token):
        return f"{m.group(1)} cm"
    return token


def _size_key(token: str) -> tuple:
    first = re.split(r"[/-]", token)[0]
    if first in _LETTER_RANK:
        return (0, _LETTER_RANK[first], token)
    if re.fullmatch(r"\d+(\.\d+)?", first):
        return (1, float(first), token)
    return (2, 0, token)


def normalize_sizes(raw: str) -> tuple[str, str, bool]:
    """'M, S, 2XL' -> ('S, M, XXL', 'letter', False). Third value: children's ages ('12 ANS') found."""
    tokens = [_norm_size_token(t) for t in raw.split(",") if t.strip()]
    kids = any(re.fullmatch(r"\d{1,2}\s*ANS?", t) for t in tokens)
    tokens = sorted(dict.fromkeys(tokens), key=_size_key)
    if not tokens:
        return "", "", kids
    kinds = set()
    for t in tokens:
        if t == "Taille unique":
            kinds.add("one_size")
        elif all(p in _LETTER_RANK for p in re.split(r"[/-]", t)):
            kinds.add("letter")
        elif re.fullmatch(r"\d+(\.\d+)?([/-]\d+(\.\d+)?)?", t):
            kinds.add("numeric")
        elif re.fullmatch(r"\d{2,3}[A-H]", t):
            kinds.add("bra")
        else:
            kinds.add("other")
    return ", ".join(tokens), kinds.pop() if len(kinds) == 1 else "mixed", kids


# --- duplicates -----------------------------------------------------------------------------------


def dhash(path: Path) -> int | None:
    """64-bit difference hash: identical or re-encoded photos get the same (or a very close) value."""
    try:
        img = Image.open(path).convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    except OSError:
        return None
    px = list(img.getdata())
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (px[row * 9 + col] > px[row * 9 + col + 1])
    return bits


def find_duplicates(rows: list[dict], max_distance: int = 4) -> dict[int, int]:
    """Index of each duplicate row -> index of the row kept. Same name + price, near-identical photo."""
    groups: dict[tuple, list[int]] = defaultdict(list)
    for i, row in enumerate(rows):
        groups[(re.sub(r"\W+", "", fold(row["product_name"])), row["price_tnd"])].append(i)
    duplicate_of: dict[int, int] = {}
    for members in groups.values():
        if len(members) < 2:
            continue
        # Keep the most useful copy first: in stock, then with the most sizes.
        members.sort(key=lambda i: (rows[i]["available"] != "true", -len(rows[i]["size"].split(","))))
        kept: list[int] = []
        for i in members:
            h = rows[i]["_dhash"]
            twin = next(
                (
                    k
                    for k in kept
                    if h is not None
                    and rows[k]["_dhash"] is not None
                    and bin(h ^ rows[k]["_dhash"]).count("1") <= max_distance
                ),
                None,
            )
            if twin is None:
                kept.append(i)
            else:
                duplicate_of[i] = twin
    return duplicate_of


# --- URLs -----------------------------------------------------------------------------------------


def url_status(code: int, requested: str, final: str) -> str:
    if code == -1:
        return "robots_disallowed"
    if code == 0:
        return "unreachable"
    if code in (404, 410):
        return "dead"
    if 200 <= code < 300:
        requested_path, final_path = urlsplit(requested).path.strip("/"), urlsplit(final).path.strip("/")
        if requested_path and final_path in ("", "fr", "en"):  # product page now redirects to the home page
            return "dead"
        return "ok"
    return f"http_{code}"


def check_urls(urls: list[str], http: Http, cache_file: Path, max_age_days: int = 7) -> dict[str, str]:
    """Status of each URL. Conclusive checks (ok/dead) younger than `max_age_days` are reused, so a re-run
    (new rules, next day) does not request 13,000 URLs again; failed or old checks are redone."""
    today = date.today().isoformat()
    oldest = (date.today() - timedelta(days=max_age_days)).isoformat()
    cache: dict = json.loads(cache_file.read_text(encoding="utf-8")) if cache_file.exists() else {}
    todo = [
        u
        for u in dict.fromkeys(urls)
        if cache.get(u, {}).get("date", "") < oldest or cache[u]["status"] not in ("ok", "dead")
    ]
    by_host: dict[str, list[str]] = defaultdict(list)
    for url in todo:
        by_host[urlsplit(url).netloc].append(url)

    def work(host_urls: list[str]) -> None:
        for url in host_urls:
            code, final = http.check(url)
            cache[url] = {"status": url_status(code, url, final), "code": code, "date": today}

    log.info("checking %d URLs on %d hosts (%d cached)", len(todo), len(by_host), len(set(urls)) - len(todo))
    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(work, by_host.values()))
    cache_file.write_text(json.dumps(cache, indent=0), encoding="utf-8")
    return {u: cache[u]["status"] for u in urls}


# --- main -----------------------------------------------------------------------------------------


def stable_id(product_url: str) -> str:
    return "prd_" + hashlib.sha1(product_url.encode()).hexdigest()[:10]


def clean(
    rows: list[dict], data_dir: Path, url_check: bool, http: Http | None = None
) -> tuple[list[dict], Counter]:
    report: Counter = Counter(input=len(rows))
    out: list[dict] = []
    for row in rows:
        name = row["product_name"].strip()
        try:
            price = round(float(row["price_tnd"]), 3)
        except ValueError:
            report["dropped_bad_price"] += 1
            continue
        if price <= 0:
            report["dropped_bad_price"] += 1
            continue
        if origin_type(row["origin_type"], name) == "international_brand":
            report["dropped_international_brand"] += 1
            continue
        if is_non_fashion(name):
            report["dropped_not_fashion"] += 1
            continue
        size, size_type, kids_sizes = normalize_sizes(row["size"])
        if kids_sizes or KIDS.search(fold(name)):
            report["dropped_children"] += 1
            continue
        # Current keyword rules on the name first, so rule fixes apply without re-scraping;
        # the scraper's label (built from the shop's own categories) when the name says nothing.
        # Marketplaces (shops.py, name_only): the name alone must say it is a piece of clothing.
        label = categorize(name) or ("" if row["shop_name"] in NAME_ONLY_SHOPS else row["category"])
        taxonomy = classify(label, name)
        if taxonomy is None:
            report["dropped_unknown_category"] += 1
            continue
        category, subcategory, label_fr = taxonomy
        color_code, color_hex = COLORS.get(row["color"], ("", ""))
        cities = [c for c in (canonical_city(x) or x.strip() for x in row["city"].split(",")) if c]
        govs = list(dict.fromkeys(g for g in map(governorate, cities) if g))
        image_path = row.get("image_path", "")
        gender = gender_from_text(name, row["product_url"])
        out.append(
            {
                "product_id": stable_id(row["product_url"]),
                "shop_name": row["shop_name"].strip(),
                "shop_url": row["shop_url"].rstrip("/"),
                "product_name": name,
                "category": category,
                "subcategory": subcategory,
                "label_fr": label_fr,
                "color": color_code,
                "color_fr": row["color"] if color_code else "",
                "color_hex": color_hex,
                "gender": gender,
                "gender_source": "text" if gender else "",
                "size": size,
                "size_type": size_type,
                "price_tnd": price,
                "currency": "TND",
                "city": "; ".join(cities),
                "governorate": "; ".join(govs),
                "available": "true" if row["available"] == "true" else "false",
                "origin_type": row["origin_type"],
                "image_url": row["image_url"],
                "image_path": image_path,
                "product_url": row["product_url"],
                "last_checked": row["last_checked"],
                "_dhash": dhash(data_dir / image_path) if image_path else None,
            }
        )

    duplicate_of = find_duplicates(out)
    for i, j in duplicate_of.items():
        kind = "same_shop" if out[i]["shop_name"] == out[j]["shop_name"] else "cross_shop"
        report[f"dropped_duplicate_{kind}"] += 1
    out = [r for i, r in enumerate(out) if i not in duplicate_of]

    if url_check:
        http = http or Http(delay=1.0, timeout=20)  # gentle: Shopify answers 429 below ~1 request/s
        status = check_urls(
            [r["product_url"] for r in out] + [r["image_url"] for r in out],
            http,
            data_dir / "url_checks.json",
        )
    else:
        status = {}
    kept = []
    for r in out:
        r["product_url_status"] = status.get(r["product_url"], "not_checked")
        r["image_url_status"] = status.get(r["image_url"], "not_checked")
        if r["product_url_status"] == "dead":
            report["dropped_dead_product_page"] += 1
            continue
        kept.append(r)
    out = kept

    # Price outliers per subcategory: flagged for a human look, never modified.
    by_sub: dict[str, list[float]] = defaultdict(list)
    for r in out:
        by_sub[r["subcategory"]].append(r["price_tnd"])
    medians = {sub: statistics.median(prices) for sub, prices in by_sub.items()}
    for r in out:
        flags = []
        median = medians[r["subcategory"]]
        if r["price_tnd"] < median / 5:
            flags.append("price_very_low")
        elif r["price_tnd"] > median * 5:
            flags.append("price_very_high")
        if r["product_url_status"] not in ("ok", "not_checked"):
            flags.append(f"product_url_{r['product_url_status']}")
        if r["image_url_status"] not in ("ok", "not_checked"):
            flags.append(f"image_url_{r['image_url_status']}")
        if not r["image_path"]:
            flags.append("no_local_photo")
        r["quality_flags"] = "; ".join(flags)
        r["missing_fields"] = "; ".join(f for f in ("color", "size", "city") if not r[f])
        for f in ("color", "size", "city"):
            if not r[f]:
                report[f"missing_{f}"] += 1
        report[f"gender_text_{r['gender'] or 'unknown'}"] += 1
        report.update(f"flag_{f}" for f in flags)
        del r["_dhash"]

    report["output"] = len(out)
    return sorted(
        out, key=lambda r: (r["shop_name"], r["category"], r["subcategory"], r["product_name"])
    ), report


def write_report(report: Counter, rows: list[dict], path: Path) -> None:
    lines = [f"# Cleaning report — {date.today().isoformat()}", "", "| Step | Count |", "|---|---|"]
    lines += [
        f"| {k} | {v} |"
        for k, v in sorted(report.items(), key=lambda kv: (not kv[0].startswith("input"), kv[0]))
    ]
    lines += ["", "## Products per shop", "", "| Shop | Products |", "|---|---|"]
    lines += [f"| {s} | {n} |" for s, n in Counter(r["shop_name"] for r in rows).most_common()]
    lines += ["", "## Products per category", "", "| Category | Subcategory | Products |", "|---|---|---|"]
    lines += [
        f"| {c} | {s} | {n} |"
        for (c, s), n in sorted(Counter((r["category"], r["subcategory"]) for r in rows).items())
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--input", type=Path, default=DATA / "local_catalogue.csv")
    parser.add_argument("--output", type=Path, default=DATA / "local_catalogue_clean.csv")
    parser.add_argument("--no-url-check", action="store_true", help="skip the HTTP check of every URL")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    with args.input.open(encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    cleaned, report = clean(rows, args.input.parent, url_check=not args.no_url_check)
    with args.output.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(cleaned)
    write_report(report, cleaned, args.output.parent / "cleaning_report.md")
    for key, value in sorted(report.items()):
        log.info("%-32s %d", key, value)
    log.info("wrote %d products to %s", len(cleaned), args.output)


if __name__ == "__main__":
    main()
