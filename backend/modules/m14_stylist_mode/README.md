# M14 · Stylist / boutique mode — ProAgent

**Owner:** BO6 · **Used by:** BO4 BO5 BO6 BO7 BO8 · **Build week:** 4 (needs M1–M10)

> **Status: design only.** This README is the plan, kept until the modules M14 depends on are ready.
> The router still serves `mock.py`. Nothing below is implemented yet.

The professional side of DressMe: human stylists and Tunisian boutiques (persona *Amel*, boutique owner).
Example: Amel opens her dashboard and reads *"132 searches for gold sandals under 60 TND in Sousse this
month, 0 in your catalogue"*. A user stuck with the assistant before a wedding is handed to a stylist in
Tunis who already has a 5-line summary, the user's wardrobe and budget.

Not to be confused with the **Stylist agent** of `docs/architecture.md`, which is M2 (outfit generation).
M14 is about **human professionals**. It calls M2, M6 and M8 and never re-implements them.

## What M14 includes (task split)
| Block | Meaning |
|---|---|
| Professional account | `stylist` or `boutique` role. A boutique account is linked to a shop of the M7 catalogue. |
| Client profiles | A pro sees their clients' wardrobe (M1), style profile (M5) and outfits, **with the client's consent**. |
| Boutique demand dashboard | What users search, at what budget, in which city, and what they cannot find. |
| Hand-off | From the AI assistant (M8) to a human stylist, with the context already summarised. |

## Who calls it
| BO | Own task | What it needs from M14 | Feature |
|---|---|---|---|
| BO4 | Stylist validation of the profile | Stylist reads and corrects the style profile; corrections go back to M5 | F3 |
| BO5 | Sales-assistant mode in store | A seller advises a client in the shop with M6 on the client's wardrobe | F5 |
| BO6 | Boutique-owner dashboard | Aggregated demand for one shop | F6 |
| BO7 | Stylist sharing looks with clients | Stylist ↔ client link, send a look (card from M10) | F4 |
| BO8 | Hand-off to a human stylist | Queue, stylist choice, conversation summary | F7 |

## How it fits together
```
                      ┌──────────── events (M7 searches, M13 clicks, M6 verdicts, M9 try-ons, M8 chats)
                      ▼
 users ──► app ──► M14 ─┬─ F1 accounts ─────────── pro ↔ shop (M7)
                        ├─ F2 client brief ─────── M1 + M3 + M5 + M8 summary
                        ├─ F3 profile review ───── corrections → M5 (human labels)
                        ├─ F4 looks to clients ─── M2 score + M10 card
                        ├─ F5 in-store session ─── M1 embedding + M6 verdict
                        ├─ F6 demand dashboard ─── themes · unmet demand · prices · trends · forecast
                        ├─ F7 hand-off ─────────── escalate? → match stylist → summary → queue
                        └─ F8 client segments ──── clusters of a pro's clientele
```

## Features: input → model → output

### F1 · Professional account (no model)
```
input                              logic                                   output
{type: stylist|boutique,      ──►  validate · link shop_id to M7       ──► {pro_id, type, shop_id,
 name, city, shop_id?,             catalogue (GET /m07/shops)              verified: false}
 specialities, languages}          one boutique account per shop
```

### F2 · Client link + client brief
```
input                              model                                   output
{pro_id, client_id}           ──►  consent check (client accepted)     ──► {wardrobe_summary: counts per
                                   M1 items · M3 wear stats ·               category, colours, most/least
                                   M5 style vector + archetype ·            worn, budget range,
                                   M8 summarises into 5 lines               summary_fr, archetype}
```

### F3 · Profile review by a stylist (BO4) — human in the loop
```
input                              model                                   output
{pro_id, client_id,           ──►  diff with the current M5 profile    ──► {accepted_changes,
 corrections: {archetype,          each correction = a human label          sent_to_m5: true}
 likes[], dislikes[],              → M5 feedback API (accept/reject)
 colours[]}, note}                 stored to measure M5 vs. stylist
```
The stylist's corrections are **labels** for M5: we can report how often the profile agrees with a
professional (agreement rate, before / after).

### F4 · Stylist sends a look to a client (BO7)
```
input                              model                                   output
{pro_id, client_id,           ──►  M2 compatibility score of the look  ──► {look_id, score,
 item_ids (client wardrobe         + M7 local pieces when an item is        card_url (M10),
 and/or M7 product_ids),           a shop product                           message}
 message}                          M10 renders the card
```

### F5 · In-store sales-assistant session (BO5)
```
input                              model                                   output
{pro_id (boutique),           ──►  M1 FashionCLIP embedding of the     ──► {verdict: buy|think|skip,
 client_id (QR consent),           piece · M6 verdict on the CLIENT's        new_outfits, similar_owned,
 photo or product_id}              wardrobe · M8 explanation                 explanation_fr}
```

### F6 · Boutique demand dashboard (BO6) — the core of M14
Built from events, aggregated for one `shop_id` over a period. Five sub-models:

```
F6.a demand themes
input: search queries of the period ──► FashionCLIP text encoder (same as M7, 512-d)
                                        → UMAP (optional) → HDBSCAN (or KMeans)
                                        → M8 names each cluster
──► output: [{theme: "robes blanches mariage", n_queries, share, median_budget_tnd, top_cities}]

F6.b unmet demand (gap between demand and the shop's catalogue)
input: theme centroids + searches with 0 results or low best match
       + embeddings of the shop's products (M7 index)
──► coverage(theme) = max cosine(theme centroid, shop products)
    unmet = many queries × low coverage (in the shop AND in the whole catalogue)
──► output: [{theme, n_queries, coverage, best_shop_product?, hint_fr: "132 recherches, 0 chez vous"}]

F6.c price positioning
input: budgets asked (parsed.max_price_tnd) per category + shop prices
──► quantiles (p25/p50/p75) and share of demand the shop's prices can serve
──► output: {category: {demand_p50, shop_p50, served_share}}

F6.d emerging trends
input: weekly counts per theme / term
──► z-score vs. the previous 8 weeks (or Poisson test), min count threshold
──► output: [{theme, growth, z}]

F6.e demand forecast (if time allows)
input: weekly counts per category + Tunisian calendar features
       (Ramadan, Aïd el-Fitr / el-Adha, summer weddings, back-to-school, sales periods, temperature)
──► LightGBM regressor (baseline: seasonal naive; alternatives: Prophet, SARIMA)
    validated first on the H&M Kaggle transactions, then on our event logs
──► output: [{category, week, forecast, low, high}]
```

### F7 · Hand-off from the assistant to a human stylist (BO8)
```
F7.a should we escalate?
input: chat messages (FR / EN / darija), M8 confidence, turn count
──► stage 1: zero-shot through M8 (labels: complex_occasion, low_confidence, frustration, asks_human)
    stage 2: fine-tuned classifier (XLM-R / mBERT, TunBERT for darija) on labelled synthetic chats
    + rules: user asks for a human → always escalate
──► output: {escalate: bool, reason, score}

F7.b which stylist?
input: client style vector (M5), city, language, budget + stylists (portfolio centroid, city,
       languages, availability, load)
──► score = w1·cos(client, portfolio) + w2·same_city + w3·language + w4·availability − w5·load
    (weights in config.yaml; later learning-to-rank from accepted / declined hand-offs)
──► output: ranked [{pro_id, score, reasons}]

F7.c context summary
input: conversation + client brief (F2)
──► M8 explanation writer
──► output: {summary_fr (≤ 5 lines), occasion, budget_tnd, items_discussed}

Final output of POST /m14/handoff: {handoff_id, pro_id, status: queued, summary, reason}
```

### F8 · Client segments of a pro (optional)
```
input: the pro's clients: M5 style vectors + budget + city + wear stats (M3)
──► KMeans (k by silhouette) → M8 names each segment
──► output: [{segment: "minimaliste urbain, budget 80–150 TND", n_clients, top_items}]
```

## Contract (planned, replaces the placeholder `POST /m14/clients`)
Write `contract.py` + `mock.py` with these shapes **first**, so BO4/5/7/8 can code against them.
```
POST  /m14/pro                       F1  create a pro account
GET   /m14/pro/{pro_id}              F1
POST  /m14/clients                   F2  link a client to a pro (invitation + consent)
GET   /m14/clients/{id}/brief        F2  client brief
POST  /m14/clients/{id}/review       F3  stylist corrections → M5          (BO4)
POST  /m14/looks                     F4  send a look to a client           (BO7)
POST  /m14/instore/session           F5  in-store verdict for a client     (BO5)
GET   /m14/dashboard/{shop_id}       F6  ?period=30d → themes, unmet, prices, trends, forecast  (BO6)
POST  /m14/handoff                   F7  create a hand-off                 (BO8)
GET   /m14/handoff/queue             F7  ?pro_id= → queued hand-offs
PATCH /m14/handoff/{id}              F7  accept / decline / close
GET   /m14/pro/{pro_id}/segments     F8
```
`tool.py` exposes `handoff` and `dashboard` to the orchestrator (BO8).

## Planned layout (same pattern as M7)
```
m14_stylist_mode/
  contract.py  mock.py  router.py  service.py  tool.py
  clients.py          # HTTP calls to M1 M2 M3 M5 M6 M7 M8 M10 (mocked until they exist)
  config.yaml         # weights F7.b, thresholds F6.b/F6.d, HDBSCAN params
  accounts/           # F1 pro accounts, F2 consent + links
  crm/                # F2 brief, F3 review, F4 looks, F8 segments
  instore/            # F5
  dashboard/          # F6: events.py themes.py coverage.py prices.py trends.py forecast.py
  handoff/            # F7: escalate.py match.py summary.py
  simulate/           # synthetic users, queries, stylists, chats (see Data)
  tests/
ml/notebooks/boutique/  # evaluation notebooks (ml/notebooks/stylist/ is M2's)
```

## Data needed
| Data | Used by | Source | Status |
|---|---|---|---|
| Tunisian shops + products + FashionCLIP index | F1, F6.b, F6.c | M7, `ml/data/shops/` (DVC) | ✅ ready |
| Search + click logs (query, parsed filters, results shown, views, shop clicks, ts) | F6 | M7 `events.py` → `ml/data/logs/m07_events.jsonl`; `python -m modules.m07_local_catalogue.events` gives the summary | ✅ ready (M7 README, "Search and click log") |
| Other events: M13 clicks, M6 verdicts, M9 try-ons, M8 chats | F6, F7 | shared `Event` schema | ❌ new `EventType`s needed (PR reviewed by M6) |
| Wardrobes, wear stats, style vectors | F2, F5, F7.b, F8 | M1, M3, M5 | ⏳ mock until ready |
| Stylist profiles + portfolios | F7.b | synthetic (`simulate/`), looks from Polyvore | ❌ |
| Labelled chats (escalate or not) | F7.a | synthetic (LLM) + public dialogue datasets | ❌ |
| Tunisian calendar (holidays, Ramadan, sales, weddings) | F6.e | public calendars, Ministry of Commerce sales dates | ❌ |

New event types to propose in `shared/schemas/event.py`: `local_search`, `product_view`, `shop_click`
(already written by M7 in that shape), `handoff_request`, `handoff_closed`, `look_shared`, `profile_review`.

**No real users before the demo**, so the dashboard runs on **simulated traffic**, said clearly in the
report: `simulate/` creates N users (city, budget in TND, archetype) from Tunisian distributions, an LLM
writes their queries in FR / EN / darija, and the queries go through the **real** M7 search so the logs
are realistic. Methods are first validated on public data (H&M) where possible.

### Where to find examples
| Need | Dataset | Link |
|---|---|---|
| Transactions, customers, articles (forecast, segments, trends) | H&M Personalized Fashion Recommendations | https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations |
| Real shopping search queries (shape of queries, query → product) | Amazon Shopping Queries (ESCI) | https://github.com/amazon-science/esci-data |
| Stylist looks / outfits (portfolios, F4) | Polyvore Outfits | https://github.com/mvasil/fashion-compatibility |
| Fashion shopping conversations (hand-off context) | MMD — Multimodal Dialogs | https://amritasaha1812.github.io/MMD/ |
| Customer-support intents (escalation labels) | Bitext customer support | https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset |
| Darija sentiment (frustration detection) | TSAC | https://github.com/fbougares/TSAC |
| Darija language model | TunBERT | https://github.com/instadeepai/tunbert |
| Seasonality of fashion searches in Tunisia | Google Trends (geo = TN) | https://trends.google.com/trends/explore?geo=TN |

## Evaluation (`ml/notebooks/boutique/`)
- F6.a: silhouette / DBCV, plus a human check of 20 theme names.
- F6.b: inject known gaps in the simulated traffic (e.g. demand for a piece no shop sells) → recall of
  injected gaps.
- F6.e: MAPE / sMAPE vs. seasonal naive, on H&M then on the logs.
- F7.a: precision / recall / F1 on a held-out labelled set; missing a "wants a human" case costs more
  than a false alarm.
- F7.b: top-1 / top-3 accuracy against stylists chosen by hand on 30 cases.
- F3: agreement rate between the M5 profile and stylist corrections.

## Dependencies (mock until ready)
M1 items + embeddings · M2 compatibility score · M3 wear stats · M5 style vector + feedback API ·
M6 verdict · M7 catalogue + search logs · M8 summary, naming, zero-shot · M10 cards.

## Privacy
A pro reading a client's wardrobe touches personal data: explicit, revocable consent per pro, clients
see who has access, the dashboard only shows **aggregates** (no user id, minimum group size, e.g. 10).
Mention it in the specifications (Tunisian law 2004-63 on personal data protection).

## Open questions
- "Hand-off" for BO8 = assistant → human stylist; for BO5 = seller in the shop. Confirm with BO5 and
  BO8 before freezing the contract.
- Who verifies pro accounts (manual flag for the demo?).
- Are stylists paid / is there booking? (Out of scope unless BO5 / M13 need it.)

## Rules
1. Week 1: ship `mock.py` (fixed data in the agreed shape) so nobody is blocked.
2. Keep the shapes of `contract.py`; the real `service.py` replaces the mock without changing the API.
3. Another BO needs a feature here -> they ask the owner, never re-implement it.

## Run tests
```bash
cd backend && pytest modules/m14_stylist_mode
```

## Status
- [ ] contract + mock with the shapes above (unblocks BO4 / BO5 / BO7 / BO8)
- [x] search and click logging in M7 (`events.py`)
- [ ] new event types in the shared schema (PR reviewed by M6)
- [ ] simulated traffic (`simulate/`)
- [ ] F6 dashboard: themes, unmet demand, prices, trends
- [ ] F7 hand-off: escalate, match, summary
- [ ] F2 / F3 / F4 / F5 once M1, M2, M5, M6 are real
- [ ] F6.e forecast, F8 segments
- [ ] evaluated (`ml/notebooks/boutique/`)
