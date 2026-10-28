# BO7 · what BO7 needs from the other modules

BO7 (outfit sharing) calls the modules below through `bo7_sharing/integrations.py`. Until a team ships its
module, BO7 uses its own mock in the same shape, so the app works today. **When your `service.py` returns
the `result` below, BO7 uses your answer automatically** — nothing to change on the BO7 side. Every BO7 answer
says which one was used (`"source": "M6"` or `"mock"`).

BO7 calls your module's public function (the one your route serves) with `{"user_id": ..., "payload": {...}}`
and reads `result`. While `result` contains `"todo"` (week-1 placeholder) or your service raises
`NotImplementedError`, BO7 keeps its mock.

| Module (owner) | BO7 idea | Call | `result` BO7 reads |
|---|---|---|---|
| M1 wardrobe (BO3) | all ideas, give-away | items of a user; `duplicates` | already real (in-process) |
| M2 recommendation (BO1/BO2) | recreate a friend's look | `recommend` with `payload = {"mode": "match", "targets": [{"category", "color_hex", "label"}]}` | `{"items": [{"target", "item_id", "score"}]}` |
| M2 recommendation (BO1/BO2) | outfit board export | `recommend` with `payload = {"mode": "complete", "locked_items": [item_id]}` | `{"added": [item_id]}` |
| M3 wear log (BO1/BO2) | monthly recap, give-away | `stats` with `payload = {"month": "YYYY-MM"}` | `{"days_logged", "outfits", "wears": {item_id: n}}` |
| M5 style profile (BO4) | follow similar profiles | `profile` | `{"vector": {tag: weight}, "tags": [...]}` |
| M6 smart buy (BO5) | "Should I buy this?" poll | `verdict` with `payload = {"candidate": {"label", "category", "color_hex", "image", "price_tnd"}}` | `{"verdict": "buy"/"think"/"skip", "score": 0..1, "similar": [item_id], "new_outfits": n}` |
| M7 local catalogue (BO6) | shared looks tagged with local brands | `shops`, `search` | already real (in-process) |
| M11 trip planner (BO3) | share trip outfits | `plan` with `payload = {"destination", "days"}` | `{"days": [{"day", "item_ids"}], "packing": [item_id]}` |
| M12 style evolution (BO4) | share the style timeline | `timeline` with `payload = {"months": n}` | `{"months": [{"month": "YYYY-MM", "style", "main_colour"}]}` |
| M14 stylist mode (BO6) | stylist sharing looks | `clients` with `payload = {"list": "stylists"}` / `{"stylist_id"}` | `{"stylists": [{"stylist_id", "name", ...}]}` / `{"clients": [{"client_id", "name"}]}` |

The BO7 routes that use them are under `/bo7/social` (see `social.py`), and the Flutter screens are in
`mobile/lib/features/bo7_sharing/ui/feed_widgets.dart` and `social_screens.dart`.

Status of each module (real or mock): `GET /bo7/social/integrations`. Step-by-step guide in French for BO7: [GUIDE_MOCKS.md](GUIDE_MOCKS.md).
