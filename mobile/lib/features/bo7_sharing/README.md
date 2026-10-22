# BO7 · Outfit sharing (Flutter)

The BO7 part of the DressMe app, in the design of the Figma prototype (`core/design/dressme_design.dart`), in French.
Same features as the browser demo (`/bo7/demo`), on the same API.

| Tab | What it does | Modules called |
|---|---|---|
| **Défis** | Challenges sorted by the ML recommender, wardrobe fit, create a challenge; a challenge: join, log the day's outfit, coach message (RAG + LLM), card of the day, ML chance to finish, leaderboard, nudges, posts, "Voir le pipeline" | M15, M1, M10 |
| **Communauté** | Feed of every counted day: card, caption, likes, comments | M15 |
| **Studio** | Pick my pieces, card type (Tenue du jour, Mon look, Je donne, **Sur mon avatar**), caption language, QR, tag a Tunisian shop, share on a channel, "shop this look in Tunisia", KPIs (opens, sign-ups, K-factor, channels, ambassadors) | M10, M1, M7 |
| **Sur mon avatar** | The BO9 avatar (M9) on a card: picture of BO9's 3D viewer (web), M9's render when M9 is real, or an imported image; the outfit pieces next to it | M9 (BO9), M10, M1 |
| **Garde-robe** | The M1 wardrobe as a closet (rails, hangers, shelf, shoe rack, walnut doors); add a piece from a photo, remove a piece | M1, M7 |

```
data/   bo7_api.dart (API address), bo7_models.dart (JSON → Dart), bo7_repository.dart (every call)
logic/  bo7_providers.dart (Riverpod)
ui/     bo7_sharing_screen.dart (4 tabs + bottom bar), challenges_tab, challenge_detail_screen, community_tab,
        studio_tab, share_result, avatar_share_screen, avatar/ (BO9 viewer: web iframe / mobile message), wardrobe_tab
```

## Run it (web, simplest)

The API serves the web build of the app on its own address, so there is no CORS setting to change and the BO9
viewer can be photographed from the app.

```bash
cd mobile
flutter pub get
flutter build web --base-href /bo7/app/
# then start the API (backend/: uvicorn api.main:app --reload) and open
#   http://localhost:8000/bo7/app/#/bo7_sharing
```

On a phone or emulator: `flutter run --dart-define=API_URL=http://<PC IP>:8000` (the 3D viewer is web-only;
on the phone the avatar picture is imported).

## The avatar (BO9)

BO9 (`feat/bo9-avatar-3d`) ships a Three.js viewer of an SMPL-X body (`avatar_studio/web/viewer`). The body files
are not in Git (SMPL-X licence): BO9 generates them with `ai/smplx_export.py` into `avatar_studio/web/presets/`.
Without them the viewer shows no body, and the card shows a faceless silhouette until a picture is imported.
BO9's avatar is not dressed yet, so the card shows the avatar and the pieces side by side.

Tests: `flutter test test/bo7_sharing`.
