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
- `pipeline/parse.py` — FR/EN/Tunisian text → subcategory, colour, budget, city, English prompt for FashionCLIP.
- `pipeline/retrieve.py` — hybrid: FashionCLIP text→image (or photo→photo) cosine + BM25.
- `pipeline/filter.py` — price (TND), city or its governorate (La Marsa counts for "Tunis"), category, stock.
- `pipeline/rerank.py` — weighted score (weights in `config.yaml`), style vector, MMR, French reasons built
  only from the data (no LLM, nothing invented: an unknown colour is said to be unknown).
- `pipeline/encoder.py` — FashionCLIP (`patrickjohncyh/fashion-clip`) run locally on CPU or GPU.
- `pipeline/ingest.py` — offline: one embedding per product photo → `ml/data/shops/index/`.

Same FashionCLIP space as the Vision agent (M1) and the Profile style vector (M5), so
`image_embedding` (Smart Buy "alternatives in TND") and `style_vector` plug in directly.

**Choice vs. the architecture doc.** The doc suggests multilingual text embeddings (e5 / bge-m3) + BM25.
We use FashionCLIP (image + text in one space, requested for M7 and shared with M1/M5) + BM25; the
multilingual part (FR/EN/Tunisian/Arabic) is handled by `parse.py` and BM25, since FashionCLIP reads English.

## Contract
`contract.py`. Input: `query` and/or `gap`, `category`/`subcategory`, `image_embedding`, plus optional
`city`, `max_price_tnd`, `min_price_tnd`, `color`, `user_id`, `style_vector` (an M5 id such as `"vec_u042"`
as in the architecture doc, resolved through M5 by `clients.py`, or the 512 values), `include_unavailable`, `k`. Explicit
fields win over what is read in the text. Output: `results` (`shop`, `area`, `item`, `price_tnd`, `match`
as in the architecture doc, plus ids, links, photo, size, `reasons`), `parsed` (filters applied),
`total_matches`, `note` (e.g. city filter relaxed because nothing matched there).

## Endpoints (prefix `/m07`, `router.py`, included automatically by `api/main.py`)
- `POST /m07/search` — body = `LocalShopInput`, answer = `LocalShopOutput`
- `GET /m07/shops` — shops in the catalogue (city, product count, website)
- `GET /m07/products/{product_id}` — one product
- `GET /m07/images/{name}` — local copy of a product photo (`image_path` of a result), so apps do not
  depend on the shops' websites

The router serves the real `service.py`. When the knowledge base is not on the machine (fresh clone
without `dvc pull`), the service answers with `mock.py`'s fixed data instead of failing. `tool.py`
exposes the same service to the orchestrator (picked up automatically).

Front end: BO6 screen `mobile/lib/features/bo6_local_market/` (search, filters, results, detail sheet).

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

## Status
- [x] catalogue scraped, cleaned, URL-checked
- [x] FashionCLIP index + hybrid search + filters + style rerank, API and orchestrator tool
- [x] BO6 Flutter screen on top of the API
- [ ] evaluated (metrics in `ml/notebooks/localcatalogue/`)
