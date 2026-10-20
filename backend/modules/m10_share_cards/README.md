# M10 · Share / export cards

**Owner:** BO7 · **Used by:** BO4 BO5 BO6 BO7 BO9

**Includes:** Outfit card image, board export, share link

## Files (team template + real implementation)
| File | Role |
|---|---|
| `contract.py` | `ShareCardInput` → `ShareCardOutput` (+ the template's generic `CardRequest` / `CardResponse`) |
| `mock.py` | week-1 fixed data in the agreed shape (still served if the extra packages are missing) |
| `service.py` | real implementation, same signature as the mock (calls `agent.py`) |
| `router.py` | `/m10/...` endpoints, included automatically by `api/main.py` |
| `tool.py` | the orchestrator (BO8) picks it up automatically |
| `agent.py` + `pipeline/` | the logic, one file per step |
| `requirements.txt` | extra packages: `pip install -r modules/m10_share_cards/requirements.txt` |

## Rules
1. Keep the shapes of `contract.py`; change them only through a PR reviewed by BO7.
2. Another BO needs a feature here → ask BO7, never re-implement it.

Turns any DressMe result into an image card ready for Instagram / WhatsApp, with a referral link that lets us measure
organic acquisition (BO7 business objective).

Used by BO4 (shareable style card), BO5 (shares tagged with the boutique), BO6 (local brands), BO7 (all sharing ideas),
BO9 (try-on look). **Do not rebuild cards in another module: call this one.**

## Contract
`contract.py`: `ShareCardInput` → `ShareCardOutput`. Example: `tests/fixtures/input.json`.

| `kind` | Used for |
|---|---|
| `outfit` | outfit of the day / recommendation (S2) |
| `board` | builder board export (S3) |
| `tryon` | 3D avatar look (S4, BO9) |
| `recap` | monthly wardrobe recap (S8), stats only |
| `giveaway` | give-away post (S10) |
| `challenge` | community challenge entry (M15) |
| `style_timeline` | style evolution (B4, BO4) |
| `trip` | trip lookbook (B5) |
| `poll` | "should I buy this?" poll (S7) |

## Pipeline
| Step | File | Method |
|---|---|---|
| Layout | `pipeline/layout.py` | Flat-lay: rows by body zone (upper / lower / feet), weighted heights, no overlap |
| Palette | `pipeline/palette.py` | Background from garment colours: mean luminance → dark or light card, hue of the most saturated piece, text colour by WCAG contrast ≥ 4.5 |
| Render | `pipeline/render.py` | Pillow; M1 cutouts (data URI, http, s3, path) with soft shadow; silhouette placeholder if no cutout |
| Link | `pipeline/links.py` | 7-char base62 referral code (SHA-256), `https://dressme.tn/s/<code>` |
| Caption | `pipeline/caption.py` | Template caption + accessible alt text (M8 can replace the caption later) |
| KPIs | `pipeline/metrics.py` | CTR, conversion, invites per sharer, **K-factor**, growth projection |

K-factor = invites per sharer × CTR × conversion. K > 1 means each user brings more than one new user.

## Input → Code → Output (what the teacher asked for)
| Stage | Method | Step |
|---|---|---|
| Input | data | card request: kind, items (id, category, cutout, colour, brand), stats, format, language |
| Code | **ML** | K-means clustering of cutout pixels → dominant colour (`pipeline/colors_ml.py`) |
| Code | **if/else** | flat-lay layout, palette rules (WCAG contrast), referral code (`layout.py`, `palette.py`, `links.py`) |
| Code | **LLM · RAG** | TF-IDF retrieval of caption guidelines from `knowledge/captions.yaml` (`pipeline/rag.py`) |
| Code | **LLM · PE** | role + constraints + retrieved context + few-shot + facts → caption (`pipeline/caption_llm.py`) |
| Output | data | PNG card, caption, referral link, alt text, **`pipeline` trace**, retrieved docs, prompt |

Every response contains `pipeline` (the steps above), `retrieved` and `prompt`, shown on `/bo7/demo`.

### Turn the real LLM on
Without configuration the caption uses the template (if/else fallback). To use an LLM, fill `infra/.env`
(`LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`) and install the provider package, e.g. `pip install langchain-anthropic`,
or for a free local model: install Ollama, `ollama pull llama3.2`, `pip install langchain-ollama`,
`LLM_PROVIDER=ollama`, `LLM_MODEL=llama3.2`.

## Channel attribution (which channel brings users)
Every card returns `channel_links` (WhatsApp, Instagram, Facebook, X, copy), each tagged with `?ch=`. Opens and
sign-ups keep their channel (sign-up = last-touch: channel of the latest open). `/m10/metrics` adds `channels`
(opens, sign-ups, conversion per channel) and `best_channel` (highest conversion with ≥ 3 opens): the app can put that
share button first. `GET /m10/s/{code}/page` is the public page a friend sees, with Open Graph tags so the card
shows as a preview in chat apps, and a "Join DressMe" button that attributes the sign-up.

## Languages, QR code, ambassadors
- `language`: template captions in `en`, `fr` and `tn` (Tunisian derja in Latin letters); the LLM prompt asks for the same.
- `qr: true` draws a QR code of the referral link (`?ch=qr`) with "Scan to see this look on DressMe": printed flyers,
  a boutique screen, a story shown on another phone. Needs the optional `qrcode` package; cards render without it.
- `GET /m10/ambassadors`: users ranked by the sign-ups their cards brought, 50 points per sign-up, titles at 1, 5 and
  20 sign-ups (Ambassador, Style influencer, DressMe star).

## API (prefix `/m10`, see `router.py`)
| Method | Path | What |
|---|---|---|
| POST | `/m10/card` | generic template endpoint: `{user_id, payload: ShareCardInput}` → `{result, mocked}` |
| POST | `/m10/cards` | create a card (body = `ShareCardInput`) |
| GET | `/m10/cards/{card_id}` | card metadata |
| GET | `/m10/cards/{card_id}/image` | PNG |
| GET | `/m10/s/{code}?ch=` | open a shared link (counts an open + channel) |
| GET | `/m10/s/{code}/page?ch=` | public landing page (Open Graph preview, join button) |
| POST | `/m10/s/{code}/signup` | attribute a new user to the link |
| GET | `/m10/metrics?user_id=` | BO7 KPIs |
| GET | `/m10/ambassadors` | referral leaderboard (tiers, points) |

## Run tests
```bash
cd backend && pip install -r modules/m10_share_cards/requirements.txt && pytest modules/m10_share_cards
```

## Status
- [x] baseline working end-to-end with mocks (memory store, silhouettes when no cutout)
- [x] real rendering (Pillow) + referral tracking + KPIs
- [ ] Postgres + S3 store (`storage: s3` in `config.yaml` already uploads PNGs through `shared.storage`)
- [ ] LLM caption through M8
