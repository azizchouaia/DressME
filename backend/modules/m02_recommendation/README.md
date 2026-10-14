# M2 · Recommendation engine

**Owner:** BO1 / BO2 · **Used by:** BO1 BO2 BO3 BO5 BO6 BO7 BO8 BO9

**Includes:** Weather & context, slot-based outfit generation, compatibility model, ranking, Remix,
complete with AI (pin + fill slots), one-slot swap, outfit scoring.

Only **pretrained** models are used, nothing is trained in this project.

## Endpoints (prefix `/m02`)
Every call uses the team envelope `{user_id, payload}` → `{result, mocked}`; payloads are typed in `contract.py`.

| Endpoint | What it does | Main payload fields |
|---|---|---|
| `POST /m02/recommend` | Top-n outfits for the context (outfit of the day = `n: 1`) | `context`, `options` |
| `POST /m02/remix` | Alternative built from pieces not worn together, shares ≤ 1 piece with the base outfit | `base_item_ids` |
| `POST /m02/complete` | Complete with AI: keeps the pinned pieces, fills the empty slots | `pinned_item_ids` |
| `POST /m02/swap` | Best replacements for one slot, rest of the outfit unchanged | `item_ids`, `slot` |
| `POST /m02/score` | Scores given outfits (Smart Buy what-if, capsule, builder…) | `outfits: [[item_id…]]` |
| `GET /m02/weather?city=Tunis&date=` | Weather used for the context (Open-Meteo) | |
| `GET /m02/demo` | **Lab page** to try everything in a browser | |

Common payload: `context {occasion: work/casual/event, mood: comfy/bold/classy, city, date, weather?}`,
`options {n, rotation_window_days, forgotten_after_days, allow_outerwear, exclude_item_ids, style_vector}`,
`items` (inline wardrobe, optional), `wear_log [{date, item_ids}]` (from M3, optional).

Every outfit returned has `items`, `slots`, `score`, `score_breakdown` (compatibility, weather_fit, occasion_fit,
mood_fit, style_match, novelty, rotation_penalty, forgotten_bonus), `reasons` and `explanation`
(facts for M8 / the "why this outfit" screen), `forgotten_item_id`. `result.items` describes every piece used.

```bash
curl -X POST localhost:8000/m02/recommend -H "Content-Type: application/json" \
  -d '{"user_id":"demo_f","payload":{"context":{"occasion":"work","mood":"classy","city":"Tunis"}}}'
```

## Pipeline
```
context ─► Open-Meteo weather (temp, rain) for city + day
items   ─► FashionCLIP zero-shot attributes: warmth, formality, comfy / bold / classy
        ─► filters: laundry / excluded, too warm / too light, gym wear at work…
        ─► slot templates: top+bottom+shoes | dress+shoes, + outerwear if cold or rain
        ─► beam search: OutfitTransformer-CIR predicts the "ideal missing piece" for each empty slot,
           the 6 nearest pieces of the wardrobe are tried, partial outfits are pruned with OutfitTransformer-CP
        ─► score = 0.40 compatibility + 0.18 weather + 0.16 occasion + 0.08 mood + 0.10 taste (M5) + 0.08 novelty
                   − rotation penalty (worn in the last N days) + forgotten bonus (one piece unworn ≥ 60 days)
        ─► diversity (outfits share ≤ 1 piece) ─► reasons
```

## Models (all pretrained)
| Model | Role | Source |
|---|---|---|
| FashionCLIP `patrickjohncyh/fashion-clip` | item vector (image + text), zero-shot tags | Hugging Face |
| OutfitTransformer-CP | P(outfit compatible) | [FlorindoDev/OutfitTransformer-weights](https://huggingface.co/FlorindoDev/OutfitTransformer-weights) |
| OutfitTransformer-CIR | embedding of the ideal missing piece | same |

Check of the weights on Polyvore Outfits test (our run, `ml/scripts/m02/eval_pretrained.py --n 1000`):
compatibility AUC **0.950** (published val 0.952), fill-in-the-blank **70.4 %** with CIR (published val 68.3 %, chance 25 %).

**Item vector expected from M1:** 1024 floats = `[FashionCLIP image embedding (512) | FashionCLIP text embedding
of a short description such as "black striped t-shirt" (512)]`, each half L2-normalised. See `engine/encoder.py`.

## Run it
```bash
cd backend
pip install -r requirements.txt -r modules/m02_recommendation/requirements.txt
python ../ml/scripts/m02/download_models.py           # pretrained weights (+ --eval for the test data)
# demo wardrobe: unzip the Kaggle "clothing-dataset-full" images_compressed/ + images.csv into
# ml/data/clothing_dataset/, then:
python ../ml/scripts/m02/build_demo_wardrobe.py       # ~3 min on CPU
M02_USE_MOCK=false uvicorn api.main:app --reload       # Windows: set M02_USE_MOCK=false
# open http://localhost:8000/m02/demo
```
`M02_USE_MOCK` overrides the global `USE_MOCKS` for M2 only, so the others can keep their mocks.

## Until the other modules are live
* **M1** (items + vectors): demo wardrobes `demo_f` / `demo_m` (Kaggle photos) or `payload.items` inline.
* **M3** (wear log): demo users get a synthetic 120-day wear log; real callers pass `payload.wear_log`.
* **M5** (taste): `options.style_vector` (512 or 1024 floats); neutral 0.5 when absent.

## Rules
1. `mock.py` serves fixed data in the real shape while mocks are on, so nobody is blocked.
2. Keep the shapes of `contract.py`; another BO needs a feature here → ask the owner, never re-implement it.
