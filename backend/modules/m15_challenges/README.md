# M15 · Community challenges

**Owner:** BO7 · **Used by:** BO4 BO6 BO7

**Includes:** 7 days, 7 outfits style challenges, participation and posts

## Files (team template + real implementation)
| File | Role |
|---|---|
| `contract.py` | `ChallengesInput` → `ChallengesOutput` and the REST models (+ generic `ChallengesRequest/Response`) |
| `mock.py` / `service.py` | week-1 mock / real implementation (same signature) |
| `router.py` | `/m15/...` endpoints, included automatically by `api/main.py` |
| `tool.py` | the orchestrator (BO8) picks it up automatically |
| `agent.py` + `pipeline/` | the logic, one file per step |
| `wardrobe.py` | reads garments from M1 (`POST /m01/items`), demo wardrobe until M1 is live |
| `requirements.txt` | extra packages (shared with M10) |

Style challenges such as **“7 days, 7 outfits”**: users join, log the outfit they wore each day, the rule engine
validates it, and valid entries become posts with a shareable card (M10).

Used by BO7 (B1 challenges), BO4 (style discovery challenges) and BO6 (local brand challenges).

## Contract
`contract.py`: one `ChallengesInput` with an `action` (`list`, `recommend`, `join`, `submit`, `progress`,
`leaderboard`, `feed`) → `ChallengesOutput`. Example: `tests/fixtures/input.json`.
Entries only send **item ids**; category, colours and local tag come from M1 (`wardrobe.py`, mock until M1 is live).

## Seed challenges (`config.yaml`)
| id | Challenge | Rules |
|---|---|---|
| `ch_7x7` | 7 days, 7 outfits | `no_repeat`, `min_items 2` |
| `ch_mono` | Monochrome week | `color_theme black/white/grey (all)` |
| `ch_jebba` | Traditional Friday | `category_required traditional` |
| `ch_10x10` | 10 × 10 capsule | `capsule_limit 10`, `min_items 3` |
| `ch_local` | Local brand week (BO6 sponsor) | `local_brand 1` |

A new challenge is just a new entry in the seed list; a new rule type is one function in `pipeline/rules.py`.

## Pipeline
| Step | File | Method |
|---|---|---|
| Rule engine | `pipeline/rules.py` | Pluggable validators, explicit violation messages |
| Feasibility | `pipeline/feasibility.py` | Count of disjoint outfits `min(min(tops, bottoms) + one-pieces, shoes)` after filtering by the item rules → score in [0, 1] + reason |
| Recommendation | `pipeline/recommend.py` | **ML ranker** P(join and finish) (`models/recommender.json`); fallback formula 0.60 feasibility + 0.25 log-popularity + 0.15 Jaccard |
| Next-day hint | `pipeline/suggest.py` | Greedy least-worn pieces that keep the challenge valid (M2 can replace it) |
| Progress | `pipeline/progress.py` | Streak, best streak, points, badges, next day |
| Leaderboard | `pipeline/leaderboard.py` | 10 × valid days + 5 × **Bayesian average of likes** (one viral post cannot beat a steady week) |

## Input → Code → Output (what the teacher asked for)
| Stage | Method | Step |
|---|---|---|
| Input | data | daily entry: challenge, day, item ids (+ garments from M1) |
| Code | **if/else** | rule engine, progress/streak/points, greedy next-day suggestion |
| Code | **ML** | completion model (best of 3, gradient boosting) → probability to finish + risk level (`pipeline/completion.py`) |
| Code | **ML** | recommender (learning to rank, best of 3) → challenges sorted by P(join and finish) (`pipeline/recommend.py`) |
| Code | **LLM · RAG** | TF-IDF retrieval of coaching tips from `knowledge/style_tips.yaml` |
| Code | **LLM · PE** | coach prompt (role, tone, retrieved tips, facts, ML probability) → coach message (`pipeline/coach.py`) |
| Code | M10 | share card for the valid day |
| Output | data | valid / violations, progress + P(finish), coach message, post + card, suggestion, **`pipeline` trace** |

### The ML models
Two tasks, three candidate models each (logistic regression, random forest, gradient boosting), trained on simulated
data (behaviour assumptions written in the scripts). The best one is exported to JSON and run in plain Python by
`pipeline/mlmodel.py` (no scikit-learn at runtime). Retrain on real data once the app has users; the format stays the same.

**1. Will the user finish the challenge?** `ml/scripts/train_challenge_completion.py` → `models/completion.json`
(6 000 participations, 5 features: feasibility, valid ratio, streak, progress, social; selection by 5-fold CV AUC).

| Model | CV AUC | Test AUC | Accuracy | Brier |
|---|---|---|---|---|
| logistic regression | 0.9 | 0.901 | 0.836 | 0.1096 |
| random forest | 0.923 | 0.925 | 0.861 | 0.0974 |
| gradient boosting **(kept)** | 0.934 | 0.933 | 0.868 | 0.0925 |

Baseline accuracy (always "no"): 0.726.

**2. Which challenges to recommend?** `ml/scripts/train_challenge_recommender.py` → `models/recommender.json`
(3000 users × 8 candidate challenges; label = joined **and** finished; 5 features: feasibility, popularity,
affinity, duration, user's past completion rate; split by user, selection by NDCG@3 on validation users).

| Ranker | NDCG@3 (test) | Precision@1 (test) |
|---|---|---|
| hand formula (old fixed weights) | 0.471 | 0.407 |
| logistic regression **(kept)** | 0.514 | 0.442 |
| random forest | 0.505 | 0.463 |
| gradient boosting | 0.504 | 0.444 |

Both files also store the full comparison and the feature importance.

## Memory of the agent (`memory.py`)
| Kind | What is kept | Where |
|---|---|---|
| Long-term, episodic | challenges, participations, daily entries, posts, likes, comments | SQLite `data/memory.sqlite` (`SqliteChallengeStore`, write-through, survives a restart) |
| User memory of the coach | tips already given, rules broken again and again, messages of each day | SQLite, tables `coach_tip`, `coach_issue`, `coach_message` (`CoachMemory`) |
| Short-term, working | the last 3 days of the challenge + today's facts | added to the coach prompt (`Memory (earlier days of this user)`) |
| Semantic | coaching tips | RAG knowledge base `knowledge/style_tips.yaml` |

Effects: the RAG skips tips already given to the user in this challenge, and when a rule breaks again the coach says
so ("That is 3 times for the colour theme"). The M10 share agent keeps its cards, opens and sign-ups the same way
(`modules/m10_share_cards/memory.py`). `BO7_MEMORY_PATH` / `BO7_SHARE_MEMORY_PATH` change the files; `:memory:`
keeps everything in RAM (tests).

## Real clothes in the demo (stand-in for M1)
On `/bo7/demo` → **My wardrobe 📷**, upload a photo of a garment (flat on a plain background) or give a photo to a demo item.
`cutout.py` removes the background (`rembg` U²-Net if installed, else border-colour flood fill), crops it and runs K-means for
the colours. Files go to `backend/bo/bo7_sharing/demo_wardrobe/` (`<item_id>.png` + `added.json`). Challenge cards and the share studio then
use the real cutouts.

**Public dataset:** `python ml/scripts/import_clothing_dataset.py --source clothing --per-class 6 --hide-mock` imports
~56 real photos from the free *Clothing dataset* (A. Grigorev, GitHub) with a description built from the class + K-means
colours. `--source products` uses *Fashion Product Images* (Hugging Face, with product names). `--clear` removes them.

When M1 is live, its `/wardrobe/items` replaces all of this.

## Created challenges and finisher card
- `POST /challenges` (or action `create`): a user, a stylist (M14) or a sponsoring brand (BO6) publishes a challenge.
  `rules.validate` rejects unknown colours, empty themes, out-of-range numbers and contradictions
  (`no_repeat` + `capsule_limit`). Everyone then sees its feasibility for their own wardrobe.
- When the last day is logged, M10 draws a **finisher card** (most-used pieces + valid days, best streak, points,
  likes) returned as `completion_card_url`: the moment users are most likely to share.

## Comments and nudges
- Comments on posts go through `pipeline/moderation.py` (if/else): empty or too long, links, capitals, repeated
  characters and hurtful words in English, French and derja are refused with the reason.
- `GET /m15/challenges/{id}/nudges`: the ML model ranks participants by P(finish), lowest first, and `suggest.py` prepares a
  valid outfit for their next day, ready to send as a reminder.

## API (prefix `/m15`, see `router.py`)
| Method | Path | What |
|---|---|---|
| POST | `/m15/challenges` | generic template endpoint: `{user_id, payload: ChallengesInput}` → `{result, mocked}` |
| GET | `/m15/challenges?user_id=&recommended=true` | list / ranked recommendations with feasibility |
| POST | `/m15/challenges/create` | create a challenge (validated rules) |
| GET | `/m15/challenges/{id}?user_id=` | one challenge |
| POST | `/m15/challenges/{id}/join` | join |
| POST | `/m15/challenges/{id}/entries` | log today's outfit → validation, post, card, next-day hint |
| GET | `/m15/challenges/{id}/progress?user_id=` | progress |
| GET | `/m15/challenges/{id}/leaderboard` | leaderboard |
| GET | `/m15/challenges/{id}/nudges?all=` | participants at risk (ML) + outfit to send |
| GET | `/m15/challenges/{id}/posts` | challenge feed |
| GET | `/m15/challenges/posts/all` | all challenge posts (light feed) |
| GET/POST | `/m15/challenges/posts/{post_id}/comments` | comments (moderated) |
| POST | `/m15/challenges/posts/{post_id}/like` | like / unlike |

## Run tests
```bash
cd backend && pip install -r modules/m15_challenges/requirements.txt && pytest modules/m15_challenges
```

## Status
- [x] baseline working end-to-end with mocks (demo wardrobe, memory store)
- [x] persistent memory (SQLite) and coach memory (tips given, recurring problems, last days)
- [x] rule engine, feasibility, recommendation, leaderboard, M10 cards on posts
- [ ] Postgres store, real M1 wardrobe (`wardrobe_source: http`), M5 style tags, `worn` events to M3
