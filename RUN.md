# How to run DressMe (full integration)

This guide runs the **whole app**: the backend with every module (M1–M20), the orchestrator, the 9 BOs, and
the Flutter app with sign-in. Branch: **`integration`**. Tested on Windows 11 (PowerShell); macOS / Linux
commands are the same, with `/` paths and `source .venv/bin/activate`.

---

## 1. What you need (once)

| Tool | Version | Used for |
|---|---|---|
| Git | any | the code |
| Python | 3.11 – 3.13 | backend |
| Docker Desktop | any | PostgreSQL 16 + pgvector |
| Flutter | 3.24+ (Dart 3.5+) | mobile / web app |
| Google Chrome | any | running the app on the web, voice input |
| Ollama *(only for the offline LLM)* | any | local LLM |
| Blender 4.2 *(optional)* | 4.2 | M9 "Try it on" renders (BO9 old screen) |

Disk: about 6 GB for the Python packages and the AI models (FashionCLIP, OutfitTransformer).

---

## 2. Get the code

```powershell
git clone https://github.com/azizchouaia/dressme.git
cd dressme
git checkout integration
```

---

## 3. Configure (once)

```powershell
copy infra\.env.example infra\.env
```

Open `infra\.env` and choose the **LLM** of the assistant (orchestrator + agents):

**A) Groq — recommended** (free key, fast, picks the right agent). Create a key at https://console.groq.com → *API Keys*.

```
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile
LLM_API_KEY=gsk_your_key_here
LLM_BASE_URL=https://api.groq.com/openai/v1
```

**B) Ollama — offline.** `qwen2.5:14b` chooses agents much better than `llama3.1:8b` (needs ~10 GB RAM).

```
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:14b
LLM_API_KEY=ollama
LLM_BASE_URL=http://localhost:11434/v1
```

Never commit `infra\.env` (it holds your key). The rest of the file is already set: every module runs for
real (`USE_MOCKS=false`), M5 ranks the real M2 outfits (`M05_M02_SOURCE=module`), BO6 uses the real modules
(`M07_REAL`, `M14_REAL`). Optional: `M09_BLENDER=C:/Program Files/Blender Foundation/Blender 4.2/blender.exe`.

---

## 4. Install (once)

### 4.1 Database

Start **Docker Desktop**, then:

```powershell
cd infra
docker compose up -d postgres
cd ..
```

Only PostgreSQL is needed (Redis and MinIO in the compose file are not used).

### 4.2 Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-all.txt
python -m scripts.init_db
python ml/scripts/m02/download_models.py
```

- `init_db` creates the tables (users, M1 items with pgvector, M3, M4) and the demo account
  **demo@dressme.tn / demo1234**. M5 and M14 create their own tables / files on first use.
- `download_models.py` fetches the OutfitTransformer weights of M2 into `ml/models/m02/`.
- If PowerShell blocks the activation: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

### 4.3 Local LLM (only with option B)

```powershell
ollama pull qwen2.5:14b
```

### 4.4 App

```powershell
cd mobile
flutter pub get
flutter analyze
```

`flutter analyze` must say **No issues found**.

### 4.5 Demo data for the pro space (optional, BO6)

```powershell
cd backend
python -m modules.m14_stylist_mode.simulate.pros
```

Creates fictional demo stylists and boutiques (all marked "(demo)") for Shop → Boutique → Pro space.

---

## 5. Run (every time) — 3 terminals

**Terminal 1 — database**

```powershell
cd infra
docker compose up -d postgres
```

**Terminal 2 — backend** (wait for `Application startup complete`)

```powershell
cd backend
.venv\Scripts\Activate.ps1
python -m uvicorn api.main:app --port 8000
```

Check: http://localhost:8000/docs (API) and http://localhost:8000/viewer/index.html (3D avatar).

**Terminal 3 — app**

```powershell
cd mobile
flutter run -d chrome
```

With option B, Ollama must be running too (`ollama serve`, or the Ollama app). "Address already in use" means
it is already running.

The **first** outfit / Smart Buy / photo call loads the AI models: about 1 minute, then it is fast.

---

## 6. Try the app (5-minute demo)

1. **Sign in** with `demo@dressme.tn` / `demo1234` (or create an account). The tour shows the 4 main ideas.
2. **Wardrobe (BO4)** → *Open the wardrobe* → *Add a piece* (photo). It is cut out, classified, hung on the right
   rail. Duplicates are refused. Tap a piece: details, *Send to the laundry*, *Give it away*.
3. **My style (BO4 · M5)** → swipe the 10 looks. *What M5 learnt* fills in; then *Your 10 outfits* from your pieces.
4. **Home** → **Today**: outfit of the day (BO2 → M4 → M2 on your wardrobe, M5 taste). *I wear it* logs the wear (M3).
5. **See it on me** (any outfit) → **My 3D avatar (BO9)**: your pieces painted on the SMPL-X body. *Share this look* (BO7 · M10).
6. **Shop → Smart Buy (BO5)**: photo or type + colour + price → BUY / THINK / SKIP. *Find it cheaper in local
   shops* (BO6) · *Try it on with my wardrobe* (BO9).
7. **Assistant (BO8)**: write, speak 🎤 or send a photo 📷. "Should I buy a navy blazer at 120 TND?",
   "What should I wear tomorrow for work?", "Find a white shirt in a shop in Tunis". Each answer is drawn like
   its agent's screen.
8. **More** → BO3 (forgotten pieces, duplicates), BO6 Boutique, BO7 challenges, *For the team · test every BO* on Home.

---

## 7. What is where (integration map)

| BO | Owner | Screen in the app | Modules |
|---|---|---|---|
| BO1 / BO2 | Racem | Outfits (Racem's agents + "who calls whom") | M2, M3, M4, M17, stylist |
| BO3 | Amine | More → Wear what you own | M1, M3 |
| BO4 | Amine | Wardrobe (doors, rails), My style (swipe) | M1, M5 |
| BO5 | Aziz | Shop → Smart Buy, wishlist, check-in | M6, M13, M18 |
| BO6 | Kenza | Shop → Local shops, Boutique / pro space | M7, M14 |
| BO7 | Amenallah | More → Share & challenges, *Share this look* everywhere | M10, M15 |
| BO8 | Nadhir | Assistant (orchestrator, photo, voice) | orchestrator, M8, M19, M20 |
| BO9 | Nadhir | My 3D avatar (SMPL-X studio), Try it on | M9, avatar_studio |

Cross-BO links: Today / outfits → avatar and sharing · Smart Buy ↔ local shops · BO3 → outfit / give away ·
assistant actions open the right screen. Not built yet (answer "not available yet", never fake data):
M11, M12, M16 and `/m05/gaps`.

---

## 8. Tests

```powershell
cd backend
python -m pytest -q
```

About 700 tests pass (some are skipped when a model or service is not installed).

---

## 9. Problems and fixes

| You see | Do |
|---|---|
| `ModuleNotFoundError` (psycopg2, multipart…) | `pip install -r requirements-all.txt` in the venv |
| `Connect call failed ('127.0.0.1', 5432)` | Docker Desktop off: start it, `docker compose up -d postgres` |
| Assistant: `503 assistant unavailable` | LLM not reachable: check the key (Groq) or that Ollama runs |
| Assistant writes a "function call" or picks the wrong agent | use Groq or `qwen2.5:14b` (section 3) |
| BO1: "wardrobe empty … add at least 2 pieces" | add pieces in Wardrobe (top, bottom, shoes) |
| `prompts.npz` / M2 weights missing | `python ml/scripts/m02/download_models.py` |
| `Blender not found` (Try it on) | install Blender 4.2 and set `M09_BLENDER`, or use *My 3D avatar* |
| 3D avatar page "Not Found" | restart the backend (it serves `/viewer`) |
| Avatar stays bare after a change | Ctrl+Shift+R in Chrome (cache) |
| App shows "server is not answering" | backend not started on port 8000 |
| Voice does nothing | use Chrome and allow the microphone |
| Port 8000 already in use | close the other backend, or `--port 8001` and `flutter run --dart-define=API_URL=http://localhost:8001` |
| Real phone | `flutter run --dart-define=API_URL=http://<PC IP>:8000` and start uvicorn with `--host 0.0.0.0` |

---

## 10. Rules for the team

- Work on your branch, merge into **`integration`**; `main` only takes reviewed releases.
- Never commit `infra/.env`, model weights, SMPL-X files or generated GLBs.
- Before pushing: `pytest -q` (backend) and `flutter analyze` (app) clean.
