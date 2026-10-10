# Architecture

Mobile app (Flutter) → API gateway (FastAPI) → **Orchestrator agent** (LangGraph + LLM tool calling)
→ specialised agents (tools) → data stores.

| Agent | Input | Output |
|---|---|---|
| Vision | photo | cutout, tags, embedding |
| Stylist | occasion, weather, style vector | ranked outfits + reasons |
| Profile | events | style vector, analytics |
| Smart Buy | probe photo | score, duplicates, new outfits |
| Local shop | query / gap | Tunisian shop results |
| Try-on | body measurements, items | GLB render |

Stores: PostgreSQL (+pgvector), MinIO/S3 (images, renders), Redis (queue, cache).

Full diagrams and data examples: `docs/DressMe_MultiAgent_Pipeline.pdf`.

## Decision log
| Date | Decision | Why |
|---|---|---|
| 2026-10-10 | Monorepo, one folder per agent | avoid merge conflicts, clear ownership |
| 2026-10-10 | Flutter for mobile | one codebase, GLB viewer, camera |
| 2026-10-10 | SMPL-X + GLB for faceless avatar | real measurements, exportable |
