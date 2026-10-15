# M7 · Local catalogue — LocalShopAgent

**Owner:** BO6 · **Used by:** BO1 BO2 BO3 BO5 BO6 BO7 BO8 BO9

Find pieces sold by Tunisian shops and brands that fit a request, a budget in TND, a city and the
user's style. Example: *"baskets blanches à Tunis pour 80 TND"* → Manuella · Tunis · Basket à plateforme
femme · 69.3 TND · match 0.87.

M7 is a shared module (task split): BO6 builds it, BO1/2/3/5/7/8/9 call it through the API or the
orchestrator tool `localshop`. It searches a curated knowledge base, never the shops live.

## How a search works
```
request ──► parse ──► retrieve ──────────────────► filter ──► rerank ──► results
"baskets    sneakers   FashionCLIP: "a photo of     price ≤ 80   match = visual + text   shop, area, item,
 blanches   white      white sneakers" vs every     Tunis gov.   + attributes + style    price_tnd, match,
 Tunis      Tunis      product photo (512-d)        sneakers     MMR diversity           reasons
 80 TND"    ≤ 80 TND   + BM25 on name/colour/shop   in stock
```
- `pipeline/parse.py` — FR/EN/Tunisian text → subcategory, colour, gender, budget, city, English prompt for
  FashionCLIP. Darija ("sabbat ahmar", "sbadri kahla a9al men 150 alf", "سروال رجالي") is first turned into
  French by `darija.py` (`parsed.translated` shows how it was read); "pour mon mari" counts as men.
- `pipeline/retrieve.py` — hybrid: FashionCLIP text→image (or photo→photo) cosine + BM25.
- `pipeline/filter.py` — price (TND), city or its governorate (La Marsa counts for "Tunis"), category, stock,
  gender (a men's request drops pieces known to be for women; unisex and unknown pieces stay, ranked lower),
  colour (strict: "robe noire" shows black dresses only, not the ones whose colour the shop does not give).
  When nothing matches, the agent relaxes one filter at a time and says so in `note`: city first (black
  dresses elsewhere before other colours in Sfax), then sold-out pieces, then the colour.
- `pipeline/rerank.py` — weighted score (weights in `config.yaml`), style vector, MMR, French reasons built
  only from the data (no LLM, nothing invented: an unknown colour is said to be unknown).
- `pipeline/encoder.py` — FashionCLIP (`patrickjohncyh/fashion-clip`) run locally on CPU or GPU.
- `pipeline/ingest.py` — offline: one embedding per product photo → `ml/data/shops/index/`.
- `pipeline/attributes.py` — offline: gender of the pieces whose name does not say it, from the photo
  (FashionCLIP zero-shot), kept only above a confidence margin. Evaluated on the products whose name says it:
  96.7 % right on 88.5 % of them at the margin used (`ml/data/shops/attributes_report.md`).

Same FashionCLIP space as the Vision agent (M1) and the Profile style vector (M5), so
`image_embedding` (Smart Buy "alternatives in TND") and `style_vector` plug in directly.

**Choice vs. the architecture doc.** The doc suggests multilingual text embeddings (e5 / bge-m3) + BM25.
We use FashionCLIP (image + text in one space, requested for M7 and shared with M1/M5) + BM25; the
multilingual part (FR/EN/Tunisian/Arabic) is handled by `parse.py` and BM25, since FashionCLIP reads English.

## Contract
`contract.py`. Input: `query` and/or `gap`, `category`/`subcategory`, `image_embedding`, plus optional
`city`, `max_price_tnd`, `min_price_tnd`, `color`, `gender` (`women` / `men`), `user_id`, `style_vector` (an M5 id such as `"vec_u042"`
as in the architecture doc, resolved through M5 by `clients.py`, or the 512 values), `include_unavailable`, `k` (≤ 100) and `offset` (next page = same request with
`offset` += `k`; pages never repeat a result). Explicit
fields win over what is read in the text. Output: `results` (`shop`, `area`, `item`, `price_tnd`, `match`
as in the architecture doc, plus ids, links, photo, size, `gender`, `reasons`), `parsed` (filters applied,
`translated` darija request),
`total_matches`, `note` (e.g. city filter relaxed because nothing matched there).

## Endpoints (prefix `/m07`, `router.py`, included automatically by `api/main.py`)
- `POST /m07/search` — body = `LocalShopInput`, answer = `LocalShopOutput` (with a `search_id`)
- `POST /m07/events` — body = `ClickEvent`: `product_view` (a result was opened) or `shop_click` (the
  user went to the shop's website), with the `search_id` and the rank; answers 204
- `GET /m07/shops` — shops in the catalogue (city, product count, website)
- `GET /m07/products/{product_id}` — one product
- `GET /m07/images/{name}` — local copy of a product photo (`image_path` of a result), so apps do not
  depend on the shops' websites

The router serves the real `service.py`. When the knowledge base is not on the machine (fresh clone
without `dvc pull`), the service answers with `mock.py`'s fixed data instead of failing. `tool.py`
exposes the same service to the orchestrator (picked up automatically).

Front end: BO6 screen `mobile/lib/features/bo6_local_market/` (search, filters, results, detail sheet).
It sends `product_view` when a result is opened and `shop_click` when "Voir sur le site" is tapped.

## Search and click log (`events.py`)
Every real search (API or orchestrator, not the mock) and every click is appended to
`ml/data/logs/m07_events.jsonl` (never git; `log_events: false` in `config.yaml` turns it off). One JSON
line per event with the fields of the shared `Event` schema (`event_id`, `user_id`, `type`, `target_id`,
`value`, `channel`, `ts`) plus `data`:
- `local_search`: the request, explicit filters, how it was understood (`parsed`, incl. `translated`),
  `total_matches`, the results shown (product, shop, match, price), the note, the latency;
- `product_view` / `shop_click`: product, shop, `search_id`, rank.

No IP or device data; `user_id` only when the caller sends it. This is the data of M14's boutique
dashboard (unmet demand = searches with no result, impressions / views / clicks per shop):
```bash
cd backend && python -m modules.m07_local_catalogue.events --days 30   # summary as JSON
```
The types `local_search`, `product_view`, `shop_click` are not in `shared/schemas/event.py` yet: to add
through a PR reviewed by M6 when the shared event store exists.

## Rules
1. Keep the shapes of `contract.py`; change them only through a PR reviewed by the owner (BO6).
2. Another BO needs a feature here -> they ask the owner, never re-implement it.

## Data (`ml/data/shops/`, tracked with DVC, never git)
Paths are set in `config.yaml` / `paths.py`.
```bash
cd backend
python -m modules.m07_local_catalogue.scraper.run      # 1. scrape shops       -> local_catalogue.csv + images/
python -m modules.m07_local_catalogue.scraper.clean    # 2. clean + check URLs -> local_catalogue_clean.csv
python -m modules.m07_local_catalogue.pipeline.ingest  # 3. FashionCLIP index  -> index/ (incremental)
python -m modules.m07_local_catalogue.pipeline.attributes  # 4. gender from photo -> clean CSV + attributes_report.md
python -m modules.m07_local_catalogue.scraper.run --shops strass joliesse --merge   # add/refresh some shops only
cd .. && dvc add ml/data/shops && git add ml/data/shops.dvc   # share it with the team
```
Extra dependencies: `requirements.txt` of this folder (torch, transformers for FashionCLIP). Weights:
the Hugging Face model is downloaded on first use (~600 MB), or put a copy in `ml/models/fashion-clip/`
(DVC) and it is used instead.

**Scraper** (`scraper/run.py`): one adapter per platform in `scraper/sources.py` (Shopify `/products.json`,
WooCommerce Store API, PrestaShop JSON listings, schema.org JSON-LD, HA's JSON API, LYOUM's HTML cards).
Shops and skipped shops with the reason are listed in `scraper/shops.py`. It honours robots.txt, waits
between requests, keeps local pieces only (no foreign labels, no children's items, no non-fashion items)
and saves one photo per product.

**Cleaning** (`scraper/clean.py`, counts in `ml/data/shops/cleaning_report.md`):
- duplicates: same photo (perceptual hash) + same name + same price, in one shop or across shops;
- categories: contract `GarmentCategory` + `subcategory` + French label (`taxonomy.py`), so
  "sneakers / baskets" are always `shoes / sneakers / Baskets`;
- gender: from the name / URL ("Basket femme", `/collections/homme`); both or none named = unknown here,
  the photo fills it later (step 4);
- colours: code (`white`) + French name + hex; sizes: one notation, sorted (`S, M, XXL`), with `size_type`;
  cities: canonical name + governorate;
- prices: numbers in TND (every adapter keeps TND prices only), outliers flagged, never changed;
- URLs: every product page and photo URL requested; dead product pages dropped, other failures flagged;
- missing values stay empty and are listed in `missing_fields` (nothing is guessed).

| Column | Example | Notes |
|---|---|---|
| `product_id` | prd_3f9c1a0b2e | Stable: hash of the product URL |
| `shop_name`, `shop_url` | Manuella, https://manuella.com.tn | |
| `product_name` | Basket à plateforme femme | As on the shop |
| `category`, `subcategory`, `label_fr` | shoes, sneakers, Baskets | Shared contract + finer type |
| `color`, `color_fr`, `color_hex` | white, Blanc, #FFFFFF | Main colour; empty when the shop does not give it |
| `gender`, `gender_source` | men · photo | `women` / `men` / `unisex` / empty; `text` (name or URL) or `photo` (estimated, step 4) |
| `size`, `size_type` | 36, 37, 38 · numeric | Sizes in stock when the shop exposes stock per size |
| `price_tnd`, `currency` | 69.3 · TND | Lowest current price (sale price included) |
| `city`, `governorate` | Tunis · Tunis | Where the shop is; `; `-separated for chains; empty if unknown |
| `available` | true | In stock at `last_checked` |
| `origin_type` | local_brand | `local_brand` or `local_retailer` (Tunisian shop reselling other labels) |
| `image_url`, `image_path` | …, images/1a9b….jpg | Shop photo URL + local copy (relative to `ml/data/shops/`) |
| `product_url` | | Product page on the shop's website |
| `last_checked` | 2026-10-14 | Scrape date |
| `product_url_status`, `image_url_status` | ok | Result of the URL check |
| `missing_fields` | color; city | Fields left empty because the shop does not give them |
| `quality_flags` | price_very_low | To review by hand |

## Run tests
```bash
cd backend && pytest modules/m07_local_catalogue
```
Tests use a tiny catalogue and a fake encoder: no torch, network or model download needed.

## Evaluation (`evaluation/`)
```bash
cd backend && python -m modules.m07_local_catalogue.evaluation.run   # -> evaluation/RESULTS.md
```
- `queries.yaml`: 72 requests as users write them (28 FR, 12 EN, 18 darija in Latin letters, 14 in Arabic
  script) with their intent written by hand (type, colour, gender, budget, city, material).
- **Understanding** (gold): `parse.py`'s reading vs the written intent, per field and per language.
- **Ranking** (silver): each product graded 0 / 1 / 2 from the intent and its attributes; nDCG@10, P@5,
  MRR, wrong results in the top 5, no-result rate, latency.
- **Ablation**: BM25 alone and FashionCLIP alone on the raw request, the pipeline without FashionCLIP,
  with the visual score only, without the darija lexicon, without gender, and the full pipeline.
- **Human grades**: `ml/data/shops/eval/judgments_todo.csv` lists the products shown (top 10 of the
  pipeline and of both baselines). Fill `human_rel` (0 / 1 / 2) for some requests, save as
  `judgments.csv`, run again: RESULTS.md then adds human nDCG@10 / P@5 and the agreement with silver grades
  (Cohen's kappa).

Results and their limits: [evaluation/RESULTS.md](evaluation/RESULTS.md). The first run found 4 requests
read wrong (feminine Arabic adjectives, "argentée", "handbag"); the rules were fixed, so the 100 %
understanding is measured on the set that found them. New requests written by someone else would give an
unbiased figure.

## Status
- [x] catalogue scraped, cleaned, URL-checked
- [x] FashionCLIP index + hybrid search + filters + style rerank, API and orchestrator tool
- [x] BO6 Flutter screen on top of the API
- [x] darija requests (Latin letters and Arabic script) + gender (text, then photo zero-shot, evaluated)
- [x] evaluated on 72 hand-written requests, with ablation (`evaluation/RESULTS.md`)
- [x] search and click log for M14 (`events.py`, `POST /m07/events`)
- [ ] human grades (`judgments.csv`) and a second, unseen set of requests
