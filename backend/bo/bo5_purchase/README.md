# BO5 · Purchase decision support

**Business objective:** Revenue via affiliation · **Owner:** @azizchouaia

**Shared modules owned:** M6 Smart Buy / what-if engine, M13 Partner commerce links, M18 Size & fit advice

**Shared modules called:** M2, M5, M6, M8, M10, M13, M14, M16, M18 (mock them until they are ready)

## Own tasks
| Task | Calls |
|---|---|
    | Verdict screen + explanation | M6, M8 |
| Size & fit hint before buying | M18 |
| Wardrobe gap shopping list | M6 |
| Outfit preview with the candidate piece | M2 |
| Candidate in the outfit builder | M2 |
| Shares tagged with the boutique | M10 |
| Buy link after a positive verdict | M13 |
| Partner discount codes | M13 |
| Sales-assistant mode in store | M14 |
| Ask the assistant: does this fit? | M6, M8 |
| Cost-per-wear estimate | M16 |
| Price-sensitivity learning | M5 |

## Status (BO5)
Done: verdict + explanation (test UI), size & fit, buy links, promo codes, cost per wear (via M6 wear prediction).
Run: `uvicorn bo.bo5_purchase.demo.app:app --reload --port 8005` · `python -m bo.bo5_purchase.evaluate` ·
`python -m modules.m06_smartbuy.learn` · `python -m modules.m06_smartbuy.bandit`
