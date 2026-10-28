# M5 · Adaptive style profile

**Owner:** BO4 · **Used by:** BO1 BO2 BO4 BO6 BO8 BO9

> **Integrating M5?** Read [INTEGRATION.md](INTEGRATION.md) first: M2 proposes outfits, M5 chooses what the user
> sees and learns from every swipe. Never show M2's outfits directly.

M5 learns each user's style and decides which outfit cards to show. M1 does the perception (FashionCLIP
vectors and attributes of every item). M5 does the decision:

- a **style mix** per item, over 12 archetypes;
- an **onboarding made of swipes only**: no form, no questions from the agent and no wardrobe analysis.
  A new user sees 10 varied cards right away, and the profile starts empty;
- a **taste vector** (512-d, in M1's FashionCLIP space) built by **Rocchio** from the liked and rejected
  cards; cards are ranked by their cosine to it, with 2 discovery cards per batch (`ranking: rocchio`, the
  default);
- a **per-user contextual bandit** (Linear Thompson Sampling), kept but not used by default
  (`ranking: bandit`), for a taste that depends on the situation;
- a **style coach agent**, available after the first swipes, that explains and adjusts the profile.

Everything runs server-side. The client only shows cards, preloads their images and sends swipes in the
background.

```
FIRST OPEN   no question ─► empty profile ─► 10 varied cards (one random reference look per family + one
             more card, random order) ─► swipes ─► taste = normalise(mean(liked) − 0.3·mean(rejected))
             ─► onboarded once the 10 cards are answered
DAILY        context ─► M2 (~20 outfits, filtered for the weather and the occasion) ─► cosine(outfit, taste)
             ─► 8 closest + 2 discovery cards (random places) ─► swipes ─► taste updated
ANY TIME     style coach: "I want more classic" ─► /preferences adds the classic style vector to the taste
```

## Demo

Open **`GET /m05/ui`**. It is a vanilla HTML/JS page like `/m01/ui` and calls only the M5 endpoints. It walks
through the whole scenario:

1. the 10 swipes, straight away: no consent screen, no form, no chat before them;
2. daily batches of 10 cards (8 close to the taste, 2 marked **Découverte**), with temperature, rain,
   occasion and weekend controls; the **✦ Coach de style** button then explains and adjusts the profile.

The side panel shows what M5 learnt as you swipe: style families, dominant styles, the strongest rules and
the wishes given to the coach.

- **Swipes:** arrow keys or drag. ← no, → yes, ↑ heart, ↓ skip.
- **"Pourquoi cette tenue ?"** shows the card's closeness to the taste and the styles it shares with it.
- **"Réinitialiser le profil"** deletes the user's M5 state. M1 items are not touched.

| Mode | How | What you get |
|---|---|---|
| mock (default) | `uvicorn api.main:app` | M1 mock (`usr_demo`, 13 pieces); M5 kept in memory. Style mixes are random, because the M1 mock has no FashionCLIP. |
| real | `.\backend\modules\m01_wardrobe\scripts\run_real_local.ps1` (or `run_real.ps1`) | M1 real (FashionCLIP + PostgreSQL). M5 stores into PostgreSQL automatically (`storage: auto`). The style mixes are meaningful. |

## Endpoints (prefix `/m05`)

| Method & path | Purpose |
|---|---|
| `GET /onboarding/swipe-cards?user_id=` | The first screen of a new user, with no question before it. 10 cards: one random reference look per style family + one more card (M2 outfit or look), in a random order. Creates the empty profile. Answer with `POST /feedback` (`source: onboarding`); the profile is `onboarded` once every card of the batch is answered. Calling it again gives a new batch. |
| `POST /choose` | `{context, candidates?, k?, explore?}` → `k` (10) cards, each logged in `bandit_log`. Rocchio: the closest to the taste, plus `rocchio.explore_cards` (2) discovery cards (`explore: true`) when `explore` is true. Without `candidates`, M5 asks M2 (or its mock). |
| `POST /feedback` | `{events: [{log_id \| outfit_id \| look_id \| item_ids, reaction, source, context?}]}`. One or many; send in the background. |
| `GET /profile/{user_id}` | Style mix, families, top styles, taste vector, wishes (`answers`), `n_feedback`: **this is what the other BOs read** |
| `DELETE /profile/{user_id}` | Deletes the M5 profile, bandit and logs (privacy, demo reset) |
| `GET /explain/{user_id}?log_id=&k=` | Readable rules. Rocchio: the styles of the taste (positive) and the styles rejected more than liked (negative); with `log_id`, the card's cosine to the taste and the styles it shares with it. Bandit: the strongest learned weights. |
| `GET /styles` | Style list, families, version, DIM |
| `POST /styles/recompute` | After editing `styles.json`: new style vectors and stale item mixes dropped. With `user_id`, that user's mixes are recomputed now. |
| `POST /preferences` | `{user_id, more: [style], less: [style]}` → profile. "More classic, less streetwear" after the first swipes: the latest wish wins; the wished style vectors are added to / removed from the taste (Rocchio, the swipes are kept). |
| `POST /agent/chat` | Style coach agent: `{user_id, message, thread_id?}` → `{reply, thread_id, steps, cards, profile_changed, model, elapsed_ms}`. **503** when the LLM is not reachable. See "Style coach agent". |
| `POST /profile`, `POST /gaps` | Week-1 envelope `{user_id, payload}` → `{result, mocked}` kept for the BO8 orchestrator tool. `/profile` returns the real profile. |

Error codes:

- **404**: unknown profile or log (for `/preferences`: the onboarding swipes are not finished).
- **422**: invalid input, such as an unknown style id, an unknown occasion or an unknown `log_id`.

**Reactions and rewards:**

| reaction | reward |
|---|---|
| `reject` | 0 |
| `ignored` | 0.2 |
| `accept` | 0.7 |
| `like` | 1 (swipe right during onboarding) |
| `heart` | 1 |
| `worn` | 1 |

**Sources and weights:**

| source | weight |
|---|---|
| `swipe` | 1 |
| `onboarding` | 1 |
| `worn` | 1 |
| `chat` | 0.5 |

The source is stored with every feedback. A card that already has a reward answers `duplicate`. A card
shown with an older style list answers `skipped`: it is logged but not learned.

## How it works

**Style mix (`styles.py`).** Every style in `styles.json` gets one FashionCLIP text vector, through M1's
`embed_texts`, normalised. The vectors are computed once per (style list version, M1 mode) and kept in
memory. For any embedding:

```
style_mix = softmax(factor * cosine(item, styles))
```

`factor` is 30 by default. An item's mix is computed the first time M5 needs it and stored in `item_style`
with the version. A style can also come from example photos (`vector_source: images`, `examples: [...]`).

**Taste vector: Rocchio (`rocchio.py`, `ranking: rocchio`, the default).** No context, no bandit: M2
already filters and scores the outfits for the weather and the occasion. M5 keeps, per user, the sums of
the FashionCLIP vectors of the liked cards and of the rejected cards (each weighted by its source), and:

```
taste = normalise( mean(liked) − 0.3 · mean(rejected) + 0.3 · (Σ "more" style vectors − Σ "less" ones) )
style_mix (profile) = style mix of the taste
```

- **like / accept / heart / worn** (reward ≥ 0.7) → liked; **reject** → rejected; **ignored** → nothing.
- A "no" weighs less than a "yes" (`reject_weight: 0.3`): a card can be rejected for its colour, not its style.
- Before the first liked card, `taste_vector` is `null` and `style_mix` is `{}`.
- Card embedding: the reference look's vector, or the normalised mean of the outfit's item vectors (M1).

**Onboarding (10 cards).** One random reference look per style family (9) + one more card, in a random
order: the goal is to explore the user's style, there is nothing to rank yet.

**Daily cards.** `score = cosine(outfit, taste)`. The `k − explore_cards` best are shown, plus
`explore_cards` (2) drawn from the lower half of the rest, at random places (`explore: true`, badge
**Découverte**): the user still sees other styles, and a liked discovery card widens the taste.
`explore: false` (the coach's `recommend_outfits`) ranks by cosine only.

**Contextual bandit (kept, `ranking: bandit`).** To reactivate when the taste must depend on the situation
("classic at work, bohemian at the weekend"): set `ranking: bandit` (env `M05_RANKING=bandit`). Every shown
card is logged with its bandit features in both modes, so its history is available.

- Features (`features.py`, as in `dressme_bandit.py`): context `[temp, rain, occ_work, occ_casual,
  occ_event, weekend]` (sport = baseline, `uni` → casual); outfit `[style mix (S), formality, warmth,
  novelty, taste_sim]`; `x = [1, outfit, outer(context, style mix), temp × warmth]`, `DIM = 1 + (S+4) + 6S + 1`
  = 90 with 12 styles. Formality from M1, warmth from `attributes.py`, novelty from M3 (mock 0.5).
- `LinearTS` (`bandit.py`): `A = prior_strength·I`, `b = A·prior_mean`; `choose` draws θ ~ N(A⁻¹b, v²A⁻¹)
  through a Cholesky factor (the reference `multivariate_normal` SVD fails with numpy 2.3); `rank` uses the
  mean; `update`: `A += w·xxᵀ`, `b += w·r·x`; stored as float64 bytea in `bandit_state`.
- Prior (`prior.py`): neutral (`taste_sim` +0.5), shifted by the wishes (more +0.2, less −0.3) with
  `shift_prior`, which keeps every update. A new style list restarts the model from this prior.
- Taste in this mode: `normalise((1 − lr)·taste + lr·card)`, `lr = max(taste_lr, 1/n_liked)`.

**Reference looks** (`reference_looks.json` → table `reference_look`): the looks of the onboarding swipe
cards, one per style (12).

- **Picture: an illustration** (`looks_svg.py`, `/m05/ui/looks/<id>.svg`). A flat fashion figure dressed with
  the look's real pieces and colours, described in its `art` field: hair, skin, top (tee, shirt, blouse,
  sweater, hoodie; fit, sleeves, ruffles, embroidery), bottom (straight, slim, flare, wide, midi or maxi
  skirt), dress (maxi, evening), outer layer (trench, blazer, track jacket), shoes, bag, and patterns (dots,
  floral, sequins, lace). Change a colour or a piece in the JSON, the card follows; no code change.
- **Vector: the FashionCLIP text vector of `description`.** FashionCLIP reads product photos; the vector of
  a drawing would be unreliable, so the drawings are only what the user sees. Keep `description` and `art`
  describing the same outfit.
- **A real photo instead** (later): `image_url` (http(s), or a file in `ui/looks/photos/` served as
  `/m05/ui/looks/photos/<id>.png`, sent to M1 as a data URL) + `vector_source: image`: the card shows the
  photo and the vector is the photo's. A missing local file falls back to the drawing and the description.
  AI prompts for a photo series: [`ui/looks/photos/PROMPTS.md`](ui/looks/photos/PROMPTS.md).
- Check: `python -m modules.m05_style_profile.scripts.check_look_photos` (real FashionCLIP) prints, for each
  look, its vector source and the style it lands on; every look should land on its own style.

## Style coach agent (`agent/`)

A conversational agent on top of the profile learnt from the swipes. It never asks onboarding questions:
before the first swipes, its tools answer that there is no profile yet.

"Pourquoi du streetwear ? Je veux plus classique": it explains what the bandit learnt, changes the profile
and shows new outfits, with the tools `get_style_profile`, `explain_my_recommendations`,
`update_style_preferences` and `recommend_outfits`. The LLM only decides and writes; every number comes from
M5's service.

```
user message ─► recall_profile ─► coach (LLM + tools) ──tool calls──► tools ─┐
                     ▲                    │                                      │
                     └────────────────────┼──────────────────────────────────────┘
                                          └─ no tool call ─► reply (+ cards)
```

| Element | Choice |
|---|---|
| **LLM** | `qwen3:4b-instruct` through Ollama (local, free, offline; tool calling; FR / AR / EN). `provider: shared` switches to `backend/shared/llm.py` (Claude, OpenAI...) without code changes. |
| **Short-term memory** | LangGraph checkpointer per `thread_id` (in memory, kept while the server runs); the LLM sees the last `history_messages` messages. |
| **Long-term memory** | The M5 profile itself (PostgreSQL in real mode): style mix, wishes, taste vector, bandit posterior. `recall_profile` reads it into the system prompt before every LLM call. |
| **Tools** | See above. They wrap M5's service (`/profile`, `/explain`, `/preferences`, `/choose` without discovery cards). The user id is bound in a closure: the LLM never chooses whose profile it touches. Invalid arguments come back to the LLM as text ("Not applied: ..."), so it can correct itself. |
| **Prompting** | Role + rules, the style catalogue (maps free words to style ids), the recalled profile, few-shot examples in FR / EN / Derja, "answer in the user's language". |
| **Techniques** | Tool calling (ReAct loop), contextual bandit. |

Run it: install [Ollama](https://ollama.com), `ollama pull qwen3:4b-instruct`, `pip install langchain-ollama`,
start the backend and open `/m05/ui`. Once the 10 swipes are done, the **✦ Coach de style** button opens the
coach. Each answer lists the tools it called; when the profile changes the side panel refreshes.

Pipeline picture for slides: `python -m modules.m05_style_profile.scripts.agent_graph` (writes
`agent/pipeline.mmd`, and `pipeline.png` when online).

## Configuration (`config.yaml`, everything in one place)

| Key | Default | Meaning |
|---|---|---|
| `style_mix_factor` | 30 | softmax temperature of the style mix |
| `ranking` | `rocchio` | `rocchio` (taste vector, default) or `bandit` (contextual bandit, kept) (env `M05_RANKING`) |
| `rocchio.reject_weight` | 0.3 | weight of the mean of the rejected cards in the taste |
| `rocchio.wish_weight` | 0.3 | weight of each "more" / "less" style vector (`/preferences`) |
| `rocchio.explore_cards` | 2 | discovery cards per `/choose` batch |
| `rocchio.negative_reward` | 0 | reward at or below which a card counts as rejected |
| `bandit.batch_size` / `onboarding_cards` | 10 / 10 | cards per batch (15 onboarding cards felt too long in tests) |
| `positive_reward` | 0.7 | reward from which a card counts as liked |
| `bandit.v`, `bandit.prior_strength`, `taste_lr`, `prior` | 0.3, 2, 0.1 | `ranking: bandit` only (see simulation below) |
| `rewards`, `source_weights` | see above | rewards per reaction, update weight per source |
| `context` | work/casual/event + sport baseline, `uni → casual` | occasions of the context vector |
| `warmth` | | warmth of an item (attribute rules) |
| `onboarding_contexts` | 5 situations | contexts used for the onboarding swipes |
| `m02.source` | `mock` | `mock` (built-in generator) or `module` (`modules.m02_recommendation`, falls back to the mock) |
| `m03.source` | `mock` | `mock` (novelty 0.5) or `item_fields` (from M1 `last_worn`) |
| `chat_mix_step` | 0.1 | `ranking: bandit`, `/preferences`: style-mix step for each more / less style |
| `agent.*` | Ollama, `qwen3:4b-instruct` | style coach LLM, context, history window, steps (env `M05_AGENT_PROVIDER`, `M05_AGENT_MODEL`, `M05_AGENT_BASE_URL`) |
| `storage` | `auto` | `auto` (PostgreSQL when M1 is real, otherwise memory), `memory` or `postgres` (env `M05_STORE`) |

**Changing the style list** (for example 40–60 clustered styles):

1. Edit `styles.json`. Each style needs `id`, `family` and `description`; each family needs a `label`.
2. Call `POST /m05/styles/recompute`.

No code changes. DIM, the bandits, the item mixes and the reference looks follow the new list.

## Data (PostgreSQL, created on first use like M1's `items`; the project has no Alembic yet)

| Table | Columns |
|---|---|
| `style_profile` | user_id PK, answers JSONB (wishes + internal `_onboarding_open`), style_mix JSONB, taste_vector VECTOR(512), liked_sum VECTOR(512), n_liked, rejected_sum VECTOR(512), n_rejected, onboarded, created_at, updated_at. The Rocchio columns are added to an existing table on first use (`ADD COLUMN IF NOT EXISTS`). |
| `item_style` | item_id PK (M1 `items.item_id`, no hard foreign key), style_mix JSONB, styles_version |
| `bandit_state` | user_id PK, dim, A BYTEA, b BYTEA, v, prior_mean BYTEA, prior_strength, n_updates, styles_version, updated_at |
| `bandit_log` | log_id PK, user_id, outfit_id, look_id, item_ids, context JSONB, features FLOAT[], shown_at, rank, score, reward, reaction, source, rewarded_at |
| `reference_look` | id PK, image_url, style_id, family, title, description, is_primary, formality, warmth, embedding VECTOR(512), version |

## Dependencies on other modules

- **M1:** reached in-process through `m01_client.py`, following M1's own mock/real switch. M5 uses
  `items`, `embeddings(user_id, item_ids)`, `embed_texts(texts)` and `classify(mode=inspiration_photo)` for
  photos. M5 never loads FashionCLIP and never reads the `items` table.
- **M2:** `m02_client.py`. The built-in mock builds about 20 outfits from the user's active items: top +
  bottom or a dress, plus shoes, plus outerwear below 18 °C. It drops warm pieces above 25 °C.
  `m02.source: module` calls the real M2 (`origin/feat/m02-m03-m04-m17`, envelope `{result: {outfits}}`)
  once it is merged. The real M2 already accepts M5's taste vector in `options.style_vector`.
- **M3:** `m03_client.py`. Mock: novelty 0.5, "worn" accepted.
- **Weather:** given by the client in `context` for now.

## Tests and validation

```bash
cd backend
pytest -q modules/m05_style_profile                       # M1 mocked, M5 in memory, agent with a scripted LLM
M05_TEST_DATABASE_URL=postgresql+asyncpg://... pytest -q modules/m05_style_profile/tests/test_store_pg.py
python -m modules.m05_style_profile.scripts.simulate      # bandit vs random, per 50 days
```

**Simulation** (`ranking: bandit`). A fake user likes classic at work and bohemian at the weekend, dislikes warm clothes when
it's hot and likes them when cold. One card per day for 300 days, averaged over 20 seeds, days 100–300:

| `bandit.v` | bandit liked | random liked |
|---|---|---|
| 0.3 (default) | ≈ 30 % | ≈ 21 % |
| 0.15 | ≈ 34 % | ≈ 21 % |
| 0.1 | ≈ 35 % | ≈ 21 % |

A single seed is noisy because there is only one reward per day. In the app each batch gives up to 10
rewards, so learning is faster.

**Performance:** `/choose` with 20 candidates takes about 5–8 ms server-side, well under the 50 ms target.
This excludes M2.

## Rules

1. `contract.py` is the API used by six BOs: change it only through a PR reviewed by BO4.
2. Another BO needs something here → ask the owner, never re-implement it. The BO8 taste agent should read
   `GET /m05/profile/{user_id}`.
