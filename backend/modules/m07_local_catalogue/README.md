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

Agent fields (all optional, added for the orchestrator): input `session_id`, `language` (`fr` / `en` / `ar`),
`answer` (`{question_key, value}`: answer to the last question) and `next_page`; output `agent`,
`session_id`, `decision_id`, `question` + `question_key`, `memory_notes`, `next_actions`.

## Agent (DressMe Agent Guide)
One agent per BO: **`localshop`** is the BO6 agent; M7 (search) and M14 (boutique mode) are its skills.
| Guide file | Here |
|---|---|
| `contract.py` | `LocalShopInput` / `LocalShopOutput` + `Answer`, `NextAction`, `AgentInfo`, `Feedback` |
| `identity.py` | `CARD` (role, rules, when to use / not, skills); served at `GET /m07/card`; the tool description is built from it (`shared.agent_card.describe` when the BO8 branch is merged) |
| `agent.py` | `run()` = memory in (answer / next page / remembered gender) → search → memory out → question + `next_actions` |
| `memory.py` | one JSON per user in `ml/data/bo6/memory/` (never git); anonymous callers stay in RAM |
| `tool.py` | found by `orchestrator/registry.py` |

**Question** (one, only when the answer changes the results; asked on the first page only):
- `gender` — results for both women and men and the user said neither → *"Pour femme ou pour homme ?"*
- `max_price_tnd` — nothing under the budget → *"Rien à moins de 15 TND (le moins cher : 49 TND)…"*
- `query` — no piece, colour or photo understood and nothing found → *"Quel type de pièce cherches-tu ?"*

The orchestrator asks it, then calls `localshop` again with `answer` and the same `session_id`; the request
is not repeated. Answers are read in FR / EN / darija / Arabic ("femme", "rajel", "للنساء", "les deux").

**Memory.** Short term: the last request + open question of each session (answer, `next_page`). Long term:
history of searches, feedback (useful / bought) and the gender answered, reused in later chats (said in
`memory_notes`) unless the text says otherwise ("pour mon mari") or the type is not worn by that gender
here (`memory_gender_min_share`: no men's filter on dresses). `DELETE /m07/memory/{user_id}` forgets all.

**`next_actions`**: `ask_user` (the question) · `open_shop` (product page, app logs the click) · `judge` →
`smartbuy` (photo + price + shop of the top result) · `show_outfits` → `stylist` · `more_results` →
`localshop` with `next_page` · `feedback` → `POST /m07/feedback`. Labels follow `language`.

## Occasions, seasons and the usual budget (BO6 ideas 8 and 9)

**Occasions and seasons** (`pipeline/context.py`, read by `parse.py`). One lexicon in FR / EN / darija /
Arabic, shared with M14's hand-off summary:

| Occasion code | Said as (examples) | Pieces searched when no piece is named |
|---|---|---|
| `mariage` | mariage, wedding, 3ers, عرس | dresses, sets, suits, jumpsuits, traditional outfits, heels |
| `fiançailles` | fiançailles, engagement, khotba, خطوبة | same as a wedding |
| `henna` | henna, henné, outia, حنة | traditional outfits, dresses, sets |
| `aïd` | aïd, eid, 3id, عيد | traditional outfits, dresses, sets, suits, shirts |
| `ramadan` | ramadan, sahria, رمضان, سهرية | traditional outfits, dresses, sets, jumpsuits, hijabs |
| `entretien` / `soutenance` / `travail` | interview, graduation, bureau, work | suits, shirts, trousers, jackets, shoes… |
| `soirée` | soirée, gala, party, fête | dresses, jumpsuits, sets, suits, heels |
| `plage` | plage, beach, b7ar, البحر (= summer) | swimwear, shorts, sandals, t-shirts, sunglasses, hats |

- *"tenue pour un mariage"*: no piece named, so the search keeps the wedding pieces, and `note` says it
  ("Pour un mariage : robes, ensembles, costumes…"). *"robe pour un mariage"*: the piece decides; the
  occasion only adds words to the FashionCLIP prompt ("elegant wedding guest").
- **Season** (été / summer / sif / صيف, hiver / winter / chta / شتاء, or the beach): the `season` part of
  the score (config `weights.season`) puts first the pieces whose name and type say that season (lin,
  bretelles, crochet, sandals… / velours, laine, polaire, boots, coats…). It never hides a piece.
- Callers can pass `occasion` (any word of the lexicon) and `season` (`summer` / `winter`) as fields.

**Usual budget** (`memory.budget_samples` + `agent._usual_budget`). From the budgets the user gave (and the
prices of what they bought, through `/m07/feedback`), the agent keeps the median of the latest ones per type
(subcategory, else category), from `budget_memory.min_samples` of them. When a request has no budget:
`parsed.usual_budget_tnd`, the `budget` part of the score puts the pieces within it first, a memory note
says it, and the reason "Dans ton budget habituel (≤ 90 TND)" is added. A budget said always wins; nothing
is hidden; `DELETE /m07/memory/{user}` forgets it.

Tests: `tests/test_context_budget.py` (15).

## With the user's wardrobe: M1 + M2 (BO6 ideas 3 and 10)

`clients.py` calls M1 (`POST /m01/items`, the user's wardrobe) and M2 (`POST /m02/score`, `POST /m02/complete`,
OutfitTransformer). Until their branches are merged, `config.yaml -> real: []` and a **simulation** answers
(a fixed 8-piece wardrobe, complementary slots and a colour rule); every answer says which one in `sources`
(`{"m1": "mock", "m2": "mock"}`). A real call that fails also falls back to the simulation.

- **Idea 10 · why this local piece**: in a search with a `user_id`, the top `wardrobe.match_top` results get
  `wardrobe_matches` (pieces of the wardrobe with M2 compatibility >= `wardrobe.min_score`) and the reason
  "Va avec ta garde-robe : jean (bleu), baskets (blanc)…".
- **Idea 3 · local piece -> complete outfit**: `POST /m07/outfits {user_id, product_id, occasion?, n, language}`
  -> `outfits` (the shop piece + wardrobe pieces, M2 score), `goes_with`, `why` (local origin, shop, city,
  price, compatibility), `sources`. The piece is sent to M2 pinned and inline, with its item vector
  [FashionCLIP image | text], since it is not in the wardrobe. Occasions map to M2's work / casual / event.
- **Selected 4 · Tunisian brands in the outfit of the day**: `POST /m07/local-pieces {user_id, item_ids, occasion?,
  season?, city?, max_price_tnd?, gender?, n}`. For the outfit (wardrobe ids, e.g. BO1's outfit of the day),
  each missing slot (a bottom for a top, shoes, a bag, a jacket), then each piece to replace, gets the best
  local piece of the normal search, scored by M2 with the whole outfit (`/m02/score`). BO1 shows them.
- Smart Buy (BO5) is an agent: localshop does not call it; the `judge` next action lets the orchestrator
  chain it (one agent never calls another directly).

**Integration**: put `real: [m1, m2]` in `config.yaml` once `garde-robe` and `feat/m02-m03-m04-m17` are merged;
nothing else changes. Tests: `tests/test_wardrobe.py` (6, the real path is faked).

## LLM of the BO6 agent (`llm.py`) — Qwen 2.5 7B, local with Ollama
One LLM for the whole BO6 agent (M7 and its M14 skill), run locally by Ollama (free, no API key,
French + Arabic). **It reads and writes; it never chooses a product, a price, a score or a stylist.**

| Where | What the LLM does | What the code checks |
|---|---|---|
| M7 `pipeline/understand.py` | A request the rules do not understand at all ("haja nlabesha l b7ar fi sif") → JSON: piece type, colour, gender, budget, city + a short French rewrite; then the **normal search** runs on it | JSON schema with the catalogue's codes (Ollama structured outputs); a budget must be written in the request, a city said in it, a gender said in it; the search only keeps the result if it finds pieces |
| M14 hand-off summary | One clear French sentence for the stylist | ≤ 260 characters, no number the client did not write; the facts lines stay from the code |
| M14 escalation | On a longer chat the rules do not escalate: asks for a human / frustrated / important occasion | The LLM must quote the client's words; a quote not in the chat is ignored; it can add a signal, never remove one |
| M14 boutique tips | 2-3 tips from the dashboard figures (`GET /m14/dashboard/insights`) | Every number of a tip must be in the figures, else the tip is dropped; rule-based tips when the LLM is off |

Setup: install Ollama, then `ollama pull qwen2.5:7b`. Settings in `config.yaml → llm` (`enabled`, `model`,
`timeout_s`, one switch per use). **LLM off, not installed or too slow → the rules answer**, exactly as
before (the same fallback idea as real modules vs mocks). The agent card (`identity.py`) declares it.
Tests never call Ollama (a fake LLM in `tests/test_llm.py`). Measured gain: `evaluation/RESULTS_LLM.md`
(`python -m modules.m07_local_catalogue.evaluation.llm_eval qwen2.5:7b`).

## Endpoints (prefix `/m07`, `router.py`, included automatically by `api/main.py`)
- `POST /m07/search` — body = `LocalShopInput`, answer = `LocalShopOutput` (with a `search_id`)
- `GET /m07/card` (and `/m07/identity`) — agent card
- `POST /m07/feedback` — `{user_id, decision_id, useful, bought_product_id}` → long-term memory
- `GET /m07/history/{user_id}` — past searches · `DELETE /m07/memory/{user_id}` — forget the user
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
- [x] agent shape of the DressMe Agent Guide: card, memory (session + long term + forget), question /
  answer, next page, `next_actions`, FR / EN / AR labels (`tests/test_agent_memory.py`)
- [ ] human grades (`judgments.csv`) and a second, unseen set of requests
