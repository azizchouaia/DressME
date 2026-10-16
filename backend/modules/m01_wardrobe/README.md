# M1 · Wardrobe digitiser + item database

**Owner:** BO3 · **Used by:** BO1 BO2 BO3 BO4 BO5 BO6 BO7 BO8 BO9

Turns a photo into a structured wardrobe item and stores it. It covers background removal, type, colour,
season, pattern and formality classification, FashionCLIP embeddings, vector search, duplicate detection
and the Item table. Every other BO reads the wardrobe through M1 and never re-implements it.

## Endpoints (prefix `/m01`)

The models live in [`contract.py`](contract.py). `mock.py` and `service.py` expose exactly the same
async functions (`contract.API`), and a test checks that their signatures match.

| Endpoint | Request | Response |
|---|---|---|
| `POST /m01/classify` | `user_id`, `image` (base64, data URL or http(s) URL), `mode` = `add_to_wardrobe` \| `smartbuy_probe` \| `inspiration_photo`, `price_tnd?`, `on_duplicate` = `ask` (default) \| `add` | `garment: WardrobeItem`, `embedding: float[512]`, `needs_confirmation`, `duplicates: [{item_id, similarity}]`, `stored`, `pending` |
| `POST /m01/similar` | `user_id`, `item_id` **or** `image`, `k=5`, `threshold?` (default 0.75) | `neighbours: [{item_id, similarity}]` |
| `POST /m01/duplicates` | `user_id`, `threshold?` (default 0.85) | `groups: [[item_id, ...]]` |
| `POST /m01/items` | `user_id`, filters `category?`, `season?`, `color?`, `status?` (default: all but `pending`) | `items: WardrobeItem[]`, `total` |
| `GET /m01/items/{item_id}?user_id=` | | `WardrobeItem` (404 if unknown or another user's) |
| `PATCH /m01/items/{item_id}?user_id=` | `ItemUpdate`: only the fields sent change, `null` clears one (see "Item details") | `WardrobeItem` |
| `POST /m01/documents/extract` | `user_id`, `image`, `kind` = `auto` \| `receipt` \| `price_tag` \| `care_label`, `item_id?` | `kind`, `fields` (proposed values), `lines`, `selected_line`, `confidence`. **Nothing is saved.** 503 while M8 cannot extract |
| `POST /m01/items/{item_id}/confirm?user_id=` | | `WardrobeItem`, now `active`: accepts a pending duplicate (404 if not pending) |
| `DELETE /m01/items/{item_id}?user_id=` | | `{item_id, deleted}`. Also how a pending duplicate is cancelled |
| `GET /m01/ui` | | wardrobe demo page |
| `GET /m01/media/{path}` | | locally stored photos and cutouts |

Every response carries `mocked: bool`.

**Notes on the contract**
- Only `add_to_wardrobe` writes to the Item table. The two probe modes return the analysis without storing
  anything (`stored=false`, `embedding_id=null`).
- `WardrobeItem` is `shared.schemas.Garment` plus three fields:
  - `status` (`pending | active | archived | sold | donated`);
  - `price_tnd`;
  - a computed `shelf` (`accessories | clothes | shoes`).

  `status` and `price_tnd` will move into `Garment` (see "Outside M1").
- Search and duplicate detection only look at `active` items, and every query is filtered by `user_id`.
- **Adding a possible duplicate** (`add_to_wardrobe` with a similarity > 0.85 to an existing piece):
  1. With `on_duplicate=ask` (default), the piece is saved with `status=pending`, and the response has
     `pending=true`, `stored=false` and the `duplicates`.
  2. A pending piece is hidden from `/items`, `/similar` and `/duplicates`.
  3. The user decides:
     - **accept**: `POST /items/{id}/confirm` sets it to `active`;
     - **cancel**: `DELETE /items/{id}` removes it and its images.
  4. With `on_duplicate=add`, the piece is added directly. This is meant for bulk imports.

  The demo UI shows a "Doublon possible" dialog (new photo vs existing piece, "Annuler l'ajout" /
  "Ajouter quand même"). Esc cancels. When the wardrobe opens, it asks again about any piece left
  pending.
- Errors: `422` for an invalid image or request, `404` for an unknown item.

## Item details (form) and receipt / label scan

The user can add information that the photo cannot show, and correct what the AI guessed:

| Group | Fields (`ItemUpdate`) |
|---|---|
| Purchase | `price_tnd` (3 decimals, millimes), `purchase_date` or only `purchase_year` (old pieces), `store`, `store_id` (M7) |
| Identity | `brand`, `size` + `size_system` (`letter`, `eu`, `fr`, `us`, `uk`, `it`, `waist`, `shoe_eu`, `shoe_us`, `one_size`, `other`), `reference` |
| Material and care | `composition` (`[{material, percent}]`, total ≤ 100), `care` (list), `condition` (`new`, `good`, `worn`, `needs_repair`), `notes` |
| AI corrections | `category` (the piece changes shelf), `subcategory`, `season`, `colors`, `pattern`, `material`, `status` |
| Receipt | `receipt_image`: base64 to **keep** the receipt image (the user's choice), `null` to delete it. Without the option, the image is never stored |

How it works:
1. **The scan proposes, the user decides.** `POST /documents/extract` reads a receipt, a price tag or a
   care label and returns proposed values. Nothing is written. The UI fills the form and marks those
   fields "détecté". The user corrects them and saves with `PATCH /items/{id}`.
2. **Multi-article receipts.** All the lines are returned. With `item_id`, M1 picks the line of this piece
   from its type, using French and English keywords and abbreviations (`CHEM` → chemise, `CHINO`…). The
   user can choose another line.
3. **Extraction belongs to M8** (LLM layer, BO8). M1 never calls an LLM itself (module rule): the bridge
   is [`m08_client.py`](m08_client.py). M8 is still a skeleton, so in real mode `POST
   /documents/extract` answers **503** and the UI asks the user to fill the form by hand. The mock returns
   realistic extractions for the demo.
4. **The UI flow.** After a piece is added, the form opens as "Complétez les informations (facultatif)",
   with a "Plus tard" button. For existing or old pieces, use the "Informations → Modifier" button in the
   piece's sheet.

### Needed from M8 (PR for BO8)

M1 calls the M8 implementation (`parse`) in-process with:

```json
{"user_id": "...", "payload": {
  "task": "extract_garment_document",
  "kind": "auto | receipt | price_tag | care_label",
  "image": "data:image/jpeg;base64,...",
  "hint": {"languages": ["fr", "ar", "en"], "default_currency": "TND",
           "category": "bottom", "subcategory": "chinos", "colors": ["beige"], "brand": null},
  "result_schema": {"...": "see m08_client.RESULT_SCHEMA"}}}
```

M1 expects `{"result": {...}}` back, validated against `DocumentResponse`:

```json
{"kind": "receipt",
 "fields": {"price": null, "currency": "TND", "purchase_date": "2026-09-14", "store": "Zara · Tunisia Mall",
            "brand": "Zara", "size": null, "size_system": null, "reference": null, "composition": [], "care": []},
 "lines": [{"label": "CHINO COTON BEIGE 40", "price": 119.9, "quantity": 1}],
 "selected_line": 0,
 "confidence": {"purchase_date": 0.97}}
```

Requirements for M8:
- It needs a model that can read images (vision).
- It must handle French and Arabic, and TND amounts with 3 decimals.
- It must not keep the image (privacy).

Once M8 has a dedicated typed endpoint, only `m08_client.py` changes.

## Pipeline (`service.py` + `pipeline/`)

| Step | Model / technique | File |
|---|---|---|
| Decode | base64, data URL or http(s) (12 MB max, 10 s timeout, private hosts refused), EXIF rotation, resize to ≤ 1024 px | `pipeline/images.py` |
| Background removal | `rembg` `isnet-general-use`, falling back to `u2net`. Produces an RGBA cutout whose alpha channel is the mask, cropped to the garment | `pipeline/cutout.py` |
| Type, subtype, season, pattern, material, formality | **FashionCLIP** `patrickjohncyh/fashion-clip`, zero-shot with prompts `a photo of a {label}` and a softmax over the similarities | `pipeline/clip.py`, `pipeline/classifier.py` |
| Colours | K-means (k=3) in **CIE-LAB** on the mask pixels only, each colour named by its nearest palette entry (ΔE76), with its `share` | `pipeline/colors.py` |
| Embedding | FashionCLIP image embedding, 512-d, **L2-normalised** (computed on the cutout over white) | `pipeline/clip.py` |
| Vector search | PostgreSQL + **pgvector**, cosine distance, **HNSW** index (`vector_cosine_ops`) | `store.py` |
| Duplicates | pairs with similarity > threshold, grouped with **union-find** | `pipeline/dedup.py` |

**How the classifier decides**
- The category is the `GarmentCategory` with the highest **summed** probability over its subtypes.
- `confidence` is that summed probability.
- `subcategory` is the best subtype within the winning category.
- The season is multi-label: every season whose probability is ≥ 0.6 × the best season's is kept.
- `formality` is the expected value over 5 ordered levels (0 = very casual, 1 = formal).
- The Tunisian pieces (jebba, kachabia, sefsari, blouza) map to `traditional` and get a `local_tag`.

**Runtime**
- Models load lazily, once, on the first call (thread-safe), and run on CPU (`M01_DEVICE=cuda` to change).
- CPU-heavy steps run in a worker thread (`asyncio.to_thread`).

### Configuration: [`config.yaml`](config.yaml)

| Key | Value | Meaning |
|---|---|---|
| `thresholds.duplicate` | 0.85 | pairs above → same duplicate group, and the `duplicates` of `/classify` |
| `thresholds.similar` | 0.75 | default threshold of `/similar` |
| `thresholds.confidence` | 0.85 | below → `needs_confirmation=true` (calibrated on real photos, see below) |
| `thresholds.season_relative` | 0.6 | multi-label season rule |
| `logit_scales` | seasons 25, formality 50 | softer softmax for these heads (FashionCLIP's own scale is 100) |

The same file holds the zero-shot labels and prompts, and the colour palette (name → hex).

| Env variable | Default | |
|---|---|---|
| `USE_MOCKS` | `true` | global switch, for every module |
| `M01_USE_MOCKS` | *(unset)* | overrides `USE_MOCKS` for M1 only. Use `false` to run M1 for real while the other modules keep their mocks |
| `M01_STORAGE` | `local` | `local` (files in `data/`, served by `/m01/media`) or `s3` (`shared/storage.py`) |
| `M01_DATA_DIR` | `modules/m01_wardrobe/data` | local image store (git-ignored) |
| `M01_DEVICE` | `cpu` | torch device for FashionCLIP |

### Item table (`store.py`)

The detail columns (`brand`, `size`, `size_system`, `reference`, `purchase_date`, `purchase_year`, `store`,
`store_id`, `composition`, `care`, `condition`, `notes`, `receipt_image`) are added to an existing table
by `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` on the first call. This stays until there are Alembic
migrations.

The `items` table holds:
- the `Garment` columns (`colors` and `season` are JSONB);
- `embedding VECTOR(512)`;
- `status`;
- `price_tnd`.

On the first call, M1 runs `CREATE EXTENSION IF NOT EXISTS vector`, creates the table and builds the HNSW
index (`m=16, ef_construction=64`). This bootstrap is temporary, until migrations exist.

## Mock (`USE_MOCKS=true`, default)

The demo user `usr_demo` owns 13 pieces:
- navy linen shirt;
- **2nd navy shirt (near-duplicate)**;
- beige chinos, blue jeans;
- white sneakers, loafers;
- black leather jacket;
- brown leather bag, belt, sunglasses;
- red summer dress;
- white jebba (`traditional`);
- grey sweatshirt.

State lives in memory, so `classify` and `DELETE` really change the wardrobe until the server restarts.

**Embeddings** are deterministic. Pieces of the same "family" are about 0.78 similar, and the two navy
shirts are about 0.96, so `/duplicates` returns exactly one group.

**`classify` in the mock**
- The garment type is picked from the photo shape and hash: portrait → hanging clothes, landscape → shoes
  or accessory.
- The colours are really computed (LAB K-means).
- Photos are saved locally so the UI can show them.

The demo images are simple SVG silhouettes in `ui/assets/`.

## Wardrobe demo UI (`ui/`)

```bash
cd backend
pip install -r requirements.txt                        # API (the mock needs nothing more)
uvicorn api.main:app --reload
# → http://localhost:8000/m01/ui            (mock, user usr_demo)
# → http://localhost:8000/m01/ui?user=u42   (another user)
```

The page is vanilla HTML/CSS/JS with no build step, and it calls the M1 endpoints only. What it does:
- **Opening:** a closed wardrobe that opens with a 3D door animation (`prefers-reduced-motion` is
  respected).
- **Three sections:**
  - accessories on shelves (left);
  - clothes on a **double hanging rail** (centre): tops and jackets above; bottoms, dresses and
    traditional pieces below;
  - shoes on slanted shelves (right).
- **Detail panel:** colours, season, formality, confidence, similar pieces (`/similar`) and a "possible
  duplicate" badge.
- **"+" button:** sends a photo to `/classify`, and the new piece drops into the right section.
- **Filters and counters:** category and season filters, plus a piece count per section.
- **Removal:** a piece can be removed from the wardrobe (`DELETE`).

**Mobile:** one section at a time, with a switcher.

**Accessibility:** keyboard navigation, visible focus, `alt` text, a modal dialog with a focus trap, and
Esc to close.

### Real mode without Docker (temporary)

Until Docker Desktop is installed, `run_real_local.ps1` runs M1 for real on an **embedded PostgreSQL 16 +
pgvector** (`pgserver`). It needs no admin rights, only Python 3.10–3.12 available through `py`, which
hosts the database.

```powershell
.\backend\modules\m01_wardrobe\scripts\run_real_local.ps1                # http://localhost:8000/m01/ui
.\backend\modules\m01_wardrobe\scripts\run_real_local.ps1 -Test          # all tests, real DB + real models
.\backend\modules\m01_wardrobe\scripts\run_real_local.ps1 -Stop          # stop a database left running
.\backend\modules\m01_wardrobe\scripts\run_real_local.ps1 -Reset         # delete the local database
```

- **First run:** the script creates a venv in `.pgdev/` with `pgserver`.
- **Data:** the database lives in `data/pgdata/`. Both folders are git-ignored, and the data is kept
  between runs.
- **Ctrl+C:** stops the API and the database together.
- **Other modules:** only M1 goes real (`M01_USE_MOCKS=false`), so the other modules keep their mocks.

### Real mode (Docker Desktop)

One command, from the repo root (PowerShell):

```powershell
.\backend\modules\m01_wardrobe\scripts\run_real.ps1 -InstallDeps   # first time
.\backend\modules\m01_wardrobe\scripts\run_real.ps1                # then: http://localhost:8000/m01/ui
.\backend\modules\m01_wardrobe\scripts\run_real.ps1 -Test          # pgvector + real-model tests
```

What the script does:
1. Creates `infra/.env` from `.env.example` if it is missing. The file stays local and is git-ignored.
2. Starts only the `postgres` service of `infra/docker-compose.yml` (`pgvector/pgvector:pg16`) and waits
   for `pg_isready`.
3. Sets `M01_USE_MOCKS=false`.
4. Runs uvicorn.

The API reads `DATABASE_URL` from `infra/.env`, and the table, extension and index are created on the
first call.

Doing it by hand:

```powershell
docker compose -f infra/docker-compose.yml up -d postgres
cd backend; $env:M01_USE_MOCKS = "false"; uvicorn api.main:app --reload
```

The first `/classify` downloads FashionCLIP (~600 MB) and the rembg model (~180 MB) into the Hugging Face
and `~/.u2net` caches. In real mode the wardrobe starts empty: add pieces with "+". The Docker data lives
in the `pgdata` volume. `docker compose -f infra/docker-compose.yml down -v` wipes it.

### Measured on real photos (CPU)

These are 9 Wikimedia Commons photos: product shots plus people wearing the garment.
- **Speed:** the first call takes about 12 s (models load once). After that, about 1 s per photo.
- **Category:** correct on 7 of 9, including the jebba.
- **Errors caught:** the two errors are a leather texture close-up and a black-and-white photo of a person.
  Both have confidence ≤ 0.73, so they get `needs_confirmation`. Correct answers score ≥ 0.86. The
  threshold of 0.85 comes from this small sample and should be re-checked on a labelled set.
- **Duplicates:** uploading the same photo twice gives similarity 1.0, so it is reported as a duplicate.

**Known limits**
- **Photos of a person:** rembg keeps the whole person, so skin and hair end up in the colours. A
  clothes-segmentation model (for example SegFormer `mattmdjaga/segformer_b2_clothes`) would isolate the
  garment.
- **Pattern and material:** these zero-shot heads are unreliable (for example "polka dot silk" for a plain
  silk dress).
- **Shaded whites:** they are often named `light grey` or `silver`.

## Tests

```bash
cd backend
ruff check modules/m01_wardrobe
pytest modules/m01_wardrobe                    # mock, router, logic (models and DB mocked)
M01_RUN_SLOW=1 pytest modules/m01_wardrobe     # + real rembg / FashionCLIP pipeline
M01_TEST_DATABASE_URL=postgresql+asyncpg://dressme:change_me@localhost:5432/dressme   pytest modules/m01_wardrobe/tests/test_store_pg.py   # pgvector: schema, HNSW, filters, duplicates
```

The pgvector tests create their own users and delete their rows afterwards. Without Docker, an embedded
PostgreSQL + pgvector works for development: `pip install pgserver` (needs Python ≤ 3.12 on Windows).

## Rules
1. Keep the shapes of `contract.py`. Change them only through a PR reviewed by the owner (BO3).
2. `mock.py` and `service.py` keep the same functions and signatures (tested).
3. If another BO needs a feature here, it asks the owner and never re-implements it.
