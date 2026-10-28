# Integrating M5 (style profile) · read this before wiring M2 to the app

**Owner:** BO4 · **For:** whoever integrates the modules (branch `feat/bo7-integration` and the mobile app)

## The one rule

> **M2 proposes outfits. M5 chooses which ones the user sees, and learns from every reaction.**
> **Never show M2's outfits to the user directly.**

Every outfit card shown to the user must come from **M5** (`POST /m05/choose` or
`GET /m05/onboarding/swipe-cards`), and every reaction to it must go back to **M5**
(`POST /m05/feedback` with the card's `log_id`).

Why:

- M2 uses pretrained models only (FashionCLIP, OutfitTransformer). It scores compatibility, weather and
  occasion, but **it never learns** what this user likes.
- M5 is the part that learns. It keeps the user's **taste vector** (Rocchio: liked − 0.3 × rejected), ranks
  M2's outfits by closeness to it, and adds 2 **discovery** cards per batch.
- If the app shows M2's list directly, or forgets to send the swipes to M5: the taste never moves,
  `/m05/profile` stays empty, the coach has nothing to explain, and M2's `style_match` stays neutral.

```
                 context (weather, occasion)
                          │
 app ── POST /m05/choose ─┼─► M5 ── asks ──► M2: ~20 outfits for this context (+ the taste vector)
                          │    │
                          │    └─ ranks them by cosine(outfit, taste): 8 closest + 2 discovery
 app ◄── 10 cards (log_id) ┘
 app ── swipe ──► POST /m05/feedback {log_id, reaction} ──► M5 updates the taste vector
                                                           (next M2 call gets the new taste)
```

## The scenario the app must follow

| Step | When | Call | Notes |
|---|---|---|---|
| 1. Onboarding | first open, `GET /m05/profile/{user_id}` is 404 or `onboarded: false` | `GET /m05/onboarding/swipe-cards?user_id=` → 10 cards | **No question, no form before it.** Reference looks (one per style family) + the user's outfits. |
| 2. Onboarding swipes | each swipe | `POST /m05/feedback` `{user_id, events: [{log_id, reaction: like \| reject, source: "onboarding"}]}` | Batch them (e.g. 5 at a time), send in the background. `onboarded` turns true once all 10 are answered. |
| 3. Daily outfits | outfit of the day / "more outfits" | `POST /m05/choose` `{user_id, context: {temp_c, rain, occasion, weekend}}` → 10 cards | Cards with `explore: true` are discovery cards (badge "Découverte"). |
| 4. Daily swipes | each swipe | `POST /m05/feedback` `{log_id, reaction: reject \| ignored \| accept \| heart, source: "swipe"}` | `worn` (source `worn`) when the user wears an outfit, even one never shown: send `item_ids` + `context`. |
| 5. Coach | user asks "why?" / "more classic" | `POST /m05/agent/chat`, `POST /m05/preferences` | Only after step 2. |
| 6. Other modules | need the user's taste | `GET /m05/profile/{user_id}` → `taste_vector` (512-d, FashionCLIP), `style_mix`, `top_styles` | Read it, never recompute it. |

Reaction → effect: `like`, `accept`, `heart`, `worn` = liked; `reject` = rejected; `ignored` = nothing.

The demo page `GET /m05/ui` runs exactly this scenario; use it as the reference client.

## Connecting M2: what to set and what to adapt

### 1. Turn M5's M2 bridge on

`backend/modules/m05_style_profile/config.yaml`:

```yaml
m02:
  source: module   # mock (default) -> module once modules.m02_recommendation is the real engine
```

With `module`, `POST /m05/choose` (without `candidates`) calls `modules.m02_recommendation` in-process
(`router._impl().recommend(...)`, the team envelope) and already sends:

- `context.occasion` (`uni` mapped to `casual`), `context.weather` (`temp_c`, rain / clear);
- `options.n` (10 max, M2's limit);
- `options.style_vector` = the user's taste vector from M5 (M2's `style_match` criterion).

If M2 fails or answers nothing usable, M5 falls back to its own mock of M2 and logs a warning; the
response's `candidates_source` says which one answered (`m02` or `m02_mock`).

The alternative is to call M2 yourself and give its outfits to M5:
`POST /m05/choose {user_id, context, candidates: [{outfit_id, item_ids}, ...]}`. M5 still ranks, logs and
learns. Use one of the two, never M2 alone.

### 2. M2 must recommend from the user's own wardrobe (M1) · **blocking**

M5 can only score outfits made of the user's **M1 items** (it needs their FashionCLIP vectors). Today M2,
without `payload.items`, uses its demo wardrobes (`demo_f`, `demo_m`) or M9's 3D wardrobe. Those item ids
are unknown to M5: M5 drops these outfits and falls back to its mock (warning
`none with <user>'s M1 items`).

To fix, in the integration:

- M2 reads the user's active items from M1 (`modules.m01_wardrobe`, `items`) **or** M5 passes them in
  `payload.items` (M5's `m02_client._from_module` is the place).
- M2 expects one **1024-d** vector per item: `[FashionCLIP image (512) | FashionCLIP text of a short
  description (512)]`. M1 stores the image half (512). The text half can be computed through M1
  `embed_texts` (e.g. "navy shirt" from colour + subcategory). Agree with M1's owner (BO4) where it lives.

Until this is done the scenario works, but on M5's mock outfits, not on M2's.

### 3. Keep the ids stable

- `outfit_id`: M2's id is kept; M5 derives one from the sorted item ids when it is missing.
- Item ids are M1's `item_id` everywhere (M2, M5, M3).

### 4. Other modules that need the taste

`GET /m05/profile/{user_id}` → `taste_vector`, or in-process `await service.profile(user_id)` (async).
Note: `m07_local_catalogue/clients.py::style_vector_from_m5` calls `impl.profile({...})` synchronously and
reads `style_vector`: that is the week-1 envelope; it gets no vector. Read `taste_vector` from
`GET /m05/profile/{user_id}` instead.

## Checklist for the integration branch

- [ ] Pull `garde-robe` (M1 + M5).
- [ ] `m02.source: module` in M5's `config.yaml` once the real M2 is merged.
- [ ] M2 recommends from the user's M1 items (point 2 above); check `candidates_source: "m02"` in
      `POST /m05/choose` responses.
- [ ] The app shows **only** M5's cards and sends **every** swipe to `POST /m05/feedback` with its `log_id`.
- [ ] First open = `GET /m05/onboarding/swipe-cards`, no screen before it.
- [ ] Other modules read the taste from `GET /m05/profile/{user_id}`.
- [ ] Tests: `cd backend && pytest -q modules/m05_style_profile`.

## Settings you may tune (`config.yaml`)

| Key | Default | Meaning |
|---|---|---|
| `bandit.onboarding_cards` | 10 | cards at first open |
| `bandit.batch_size` | 10 | cards per `/choose` |
| `rocchio.explore_cards` | 2 | discovery cards per batch |
| `rocchio.reject_weight` | 0.3 | weight of a "no" against a "yes" |
| `ranking` | `rocchio` | `bandit` reactivates the contextual bandit (kept for a context-dependent taste) |
| `storage` | `auto` | PostgreSQL when M1 is real, memory otherwise |

Questions: BO4 (M5 owner). Details: [`README.md`](README.md).
