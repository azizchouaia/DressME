# M17 · Capsule engine

**Owner:** BO1 / BO2 · **Used by:** BO1 (capsule mode) · BO3 (capsule wardrobe) · BO4 (capsule from the style archetype)

**Includes:** pick the N pieces that combine the most (compatibility graph + integer linear programming), list
every outfit of the capsule, plan a month of outfits with rotation.

M17 scores nothing itself: every pair and outfit is scored by **M2** (`/m02/score`: pretrained OutfitTransformer
compatibility, calibrated per outfit shape, season weather fit, occasion fit). Day occasions come from the **M4**
calendar when M4 runs. No model is trained.

## Algorithm (BO1 prototype 10)
1. **Season filter**: pieces too warm / too light for the season are dropped (warmth read by M2).
2. **Compatibility graph**: every pair of pieces from different slots (top–bottom, top–shoes, dress–shoes,
   top–outerwear…) scored by M2. Versatility of a piece = mean of its 5 best pairs → candidate pool = the most
   versatile pieces per slot (12 tops, 8 bottoms, 6 dresses, 6 shoes, 4 outerwear).
3. **Candidate outfits** from the pool (top+bottom+shoes, dress+shoes, + the 2 best-matching jackets when the
   season allows / requires them), scored by M2 for each occasion. **Valid** = compatibility ≥ 0.55 (better than
   55 % of random outfits of the same shape), weather fit ≥ 0.5, occasion fit ≥ 0.5 for at least one occasion.
   Value = 0.5 compatibility + 0.25 weather + 0.25 best occasion fit.
4. **Integer linear program** (`scipy.optimize.milp`, HiGHS):
   maximise Σ value·y_o  s.t.  y_o ≤ x_i for each piece i of outfit o, Σ x = N, category minimums,
   must-include pieces, at least `size / (2 × occasions)` outfits per occasion (dropped if impossible);
   x binary, 0 ≤ y ≤ 1. A greedy heuristic runs for comparison (`method: "both"`).
5. **Plan**: each day gets an outfit fitting its occasion (M4 calendar), high value, not worn in the last 7
   days, few pieces from yesterday.

On the demo wardrobes (12 pieces): autumn womenswear **89 outfits with ILP vs 47 greedy** (16 for work);
winter menswear **67 vs 7**. ~15–25 s on a laptop CPU (mostly M2 scoring ~2,000 outfits per occasion).

## Endpoints (prefix `/m17`)
| Endpoint | Payload | Result |
|---|---|---|
| `POST /m17/capsule` | `size` (12), `season` (auto/spring/summer/autumn/winter), `occasions` (["casual","work"]), `minimums?`, `must_include`, `exclude_item_ids`, `method` (ilp/greedy/both), `plan_days` (30), `start?`, `items?` (inline M1 wardrobe), `min_compatibility` | `pieces` (+ outfits each), `outfits` (items, value, occasions, fits), `n_outfits`, `by_occasion`, `unused_pieces`, `graph_edges`, `comparison` (ilp vs greedy, optimal flag), `plan` (date, occasion, reason, outfit), `plan_stats`, `items` (name, category, image) |
| `POST /m17/plan` | `item_ids` of an existing capsule + season / occasions / plan_days | same, for that capsule |
| `GET /m17/demo` | | **lab page** (mobile-friendly; `?run` creates a capsule on load) |

The capsule is returned, not stored: the BO screen saves the chosen `item_ids` (and can re-plan with `/m17/plan`).

## Run it
```bash
cd backend
pip install -r modules/m17_capsule/requirements.txt          # scipy
M02_USE_MOCK=false M17_USE_MOCK=false uvicorn api.main:app     # M17 needs the real M2
# http://localhost:8000/m17/demo
pytest -q modules/m17_capsule    # fake M2 scorer: no models; includes a brute-force optimality check
```
