# BO7 · Outfit sharing

**Business objective:** Organic acquisition & community · **Owner:** @bo7-owner

**Shared modules owned:** M10 Share / export cards, M15 Community challenges

**Shared modules called:** M1, M2, M3, M5, M6, M7, M10, M11, M12, M14, M15 (mock them until they are ready)

## Own tasks
| Task | Calls |
|---|---|
| Light outfit feed | M10 |
| Recreate a friend's look from a photo | M1, M2 |
| Monthly wardrobe recap card | M3, M10 |
| Should I buy this? poll for friends | M6 |
| Give-away posts for redundant pieces | M1 |
| Wardrobe pieces tagged on posts | M1 |
| 7 days, 7 outfits challenges | M15 |
| Stylist sharing looks with clients | M14 |
| Shared looks tagged with local brands | M7, M10 |
| Share the style evolution timeline | M12, M10 |
| Share trip outfits | M11, M10 |
| Follow similar style profiles | M5 |

## What is built so far
| Where | What |
|---|---|
| `backend/modules/m10_share_cards/` | M10 (owned by BO7): cards, referral links, channels, QR, KPIs, ambassadors |
| `backend/modules/m15_challenges/` | M15 (owned by BO7): challenges, rules, 2 trained ML models (completion, recommender), coach, posts, comments, nudges |
| `demo/` | browser demo of M10 + M15 at **http://localhost:8000/bo7/demo** (attached by `m10_share_cards/router.py`) |
| `m01_seed.py` | puts the 68 demo garments in the M1 wardrobe of the demo users (through M1's API) |
| `demo/cutout.py` | dev cutout used only while M1 is mocked (M1 mock does not remove backgrounds) |
| `demo_wardrobe/` | 56 real photos (Clothing dataset, A. Grigorev, free licence) + 12 Tunisian pieces (illustrations) |
| `mobile/lib/features/bo7_sharing/` | the BO7 Flutter app (Figma design, French): Défis, Communauté, Studio, Garde-robe, Sur mon avatar — see its README |
| `avatar.py` | "Share a 3D avatar look": BO9's viewer served on `/bo7/avatar/viewer/` (with a snapshot message), M9 asked for a render (`/bo7/avatar/status`); the picture goes to M10 as `avatar_image` of a `tryon` card |
| `app.py` | serves the Flutter web build on **http://localhost:8000/bo7/app/** (`flutter build web --base-href /bo7/app/`) |
| `ml/scripts/` | `train_challenge_completion.py`, `train_challenge_recommender.py`, `bo7_ml_export.py`, `bo7_viral_simulation.py`, `import_clothing_dataset.py` |

Own tasks already covered by the modules: light outfit feed (posts), monthly recap card, give-away posts,
7 days 7 outfits challenges, shared looks tagged with local brands, share a 3D avatar look (BO9 avatar, M9),
style timeline and trip cards (M10 kinds).

## Run
```bash
cd backend
pip install -r requirements.txt -r bo/bo7_sharing/requirements.txt
uvicorn api.main:app --reload        # then open http://localhost:8000/bo7/demo
pytest modules/m10_share_cards modules/m15_challenges bo/bo7_sharing
```
