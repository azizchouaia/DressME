# M6 · Smart Buy / what-if engine (owner: BO5)

Partner links live in `modules/m13_partner_links`, size advice in `modules/m18_size_fit`, the test UI / CLI / evaluation in `bo/bo5_purchase`.

Owner: BO5. Shared modules owned: **M6 Smart Buy / what-if**, **M13 Partner links**, **M18 Size & fit**.

## What it does
User photographs a piece in a shop → the agent answers **Buy / Think / Skip** with reasons:
- Do I already own something similar? (duplicate check, M1 embeddings)
- How many new outfits does it unlock? (M2 recommender)
- Does it fill a gap in my wardrobe?
- Is the price worth it? (cost per new outfit)
- Which size should I take? (M18) · Where can I buy it locally, with a promo code? (M13 + M7)

## Pipeline
```
photo ─► M1 /classify ─► embedding + tags
              │
              ├─► M1 /similar ─────► redundancy (max similarity)
              ├─► M2 /recommend ───► new outfits unlocked
              ├─► gaps (profile) ──► gap fill
              └─► price ───────────► cost per new outfit
                         ▼
                 score 0–100 ─► verdict BUY / THINK / SKIP
                         ▼
         M8 explanation · M18 size advice · M13/M7 buy links
```
Diagram: `docs/bo5/smartbuy_pipeline.png`.

## Decision upgrades (in order)
| # | Idea | File | Switch |
|---|---|---|---|
| 3 | "Not sure" zone: close call or blurry photo -> ask ONE question (need it for an occasion?) | `pipeline/uncertainty.py` | `uncertain_band`, `min_ai_confidence` |
| 8 | What would change the answer (price, need, number owned) | `pipeline/whatif.py` | always on |
| 4 | Learned decision: logistic regression on labelled pieces (+ fair-price feature) | `learn.py`, `pipeline/decide.py` | `decision: learned` |
| 7 | XAI: what pushed the decision (+ toward BUY, - toward SKIP) | `pipeline/decide.py` | always on |
| 5 | Predicted wears per year + cost per wear, from similar owned pieces | `pipeline/wear.py` | needs `wear_count` in data |
| 9 | Personal strictness learned from feedback (Thompson-sampling bandit) | `bandit.py` | `personalize: true` |

```bash
python -m modules.m06_smartbuy.learn     # cross-validation rules vs learned, trains models/verdict_model.json
python -m modules.m06_smartbuy.bandit    # simulation: 3 shoppers, the bandit finds each one's strictness
```
Results on synthetic data: rules 71 % -> learned 86 % (5-fold CV). Bandit: finds the right
strictness for all 3 simulated shoppers (same advice as their hidden preference on 100 % of pieces).
When the real data arrives: `dataset: real`, then re-run `learn`.

## Test UI (browser)
```bash
pip install fastapi uvicorn
python -m modules.m06_smartbuy.synthetic                       # (re)generate synthetic data
uvicorn bo.bo5_purchase.demo.app:app --reload --port 8005 # open http://localhost:8005
```
Pick a wardrobe, then a generated piece (with the stylist label to compare) or build your own
(type + colour), set price / brand / body, and ask.

## Photos (real vision)
`vision.py` = FashionCLIP zero-shot (type + colour + 512-d embedding), local stand-in for M1 /classify.
```bash
pip install torch transformers pillow python-multipart   # first analysis downloads the model (~600 MB)
```
In the UI: **Upload a photo** of the piece (AI shows what it saw, you can fix it), and choose
**My closet** to build your real wardrobe from photos (saved in `ml/data/bo5/my_closet/`, not in git).
Note: closet items are compared through their tags (type + colour) so they match the synthetic data;
switch to the CLIP embedding once all wardrobes are real photos.

## Synthetic data
`synthetic.py` generates 5 wardrobes (162 items), 120 labelled candidates, 5 FICTIONAL shops and
size charts. Embeddings come from attributes (stand-in for FashionCLIP); labels come from
independent stylist rules + 8 % noise. Accuracy on it is a sanity check only; replace with real
photos + human labels for the final evaluation.

## Run it (terminal)
```bash
cd backend
python -m bo.bo5_purchase.cli --demo                      # 4 example candidates
python -m bo.bo5_purchase.cli --image cand_white_shirt --price 79 --chest 98
pytest modules/m06_smartbuy modules/m13_partner_links modules/m18_size_fit -q
```
All other modules are **mocked** (`clients/mocks.py`, data in `mocks/`). Set `use_mocks: false`
in `config.yaml` when M1/M2/M7/M8 are ready — nothing else changes.

## Where the data goes (`ml/data/bo5/`)
| Folder / file | What | Used by |
|---|---|---|
| `wardrobes/` | test wardrobes (images + `wardrobe.json`) | evaluation of M6 |
| `candidates/` | candidate pieces + `labels.csv` (buy/think/skip) | threshold tuning, accuracy |
| `partners.json` | 3–5 Tunisian shops, items, TND prices, links, promo codes | M13 |
| `size_charts.json` | brand size charts | M18 |

## Tuning
All thresholds and weights are in `config.yaml`. `python -m bo.bo5_purchase.evaluate` computes
accuracy against `labels.csv`.

## Smart Buy as an agent (identity + memory)

- **Identity** – `identity.py`: agent card (role, rules, when to use, skills, contract). `GET /m06/card`.
  The orchestrator tool description is built from it.
- **Memory** – `memory.py`, one file per user in `ml/data/bo5/memory/`:
  - short term (per `session_id`): last request + open question → the user can just answer (`answer`), no new photo;
  - long term: past verdicts, feedback (bought / liked), saved body / fit info for sizes.
- **Skills**: judge (photo) · answer (`answer` + same `session_id`) · feedback (`POST /m06/feedback`) ·
  history (`GET /m06/history/{user}`) · forget (`DELETE /m06/memory/{user}`).
- **Output for the orchestrator**: `decision_id`, `agent`, `memory_notes`, `next_actions`
  (ask_user → smartbuy, show_outfits → m02, find_cheaper → m07, open_shop → m13, feedback → smartbuy).
- **Real modules**: `config.yaml` → `real: [m1, m2, m7]`, each with the mock as fallback; output `sources` says who answered.
