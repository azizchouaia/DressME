# Attributes report — 2026-10-24

## Gender per source

| Source | women | men | unisex | unknown |
|---|---|---|---|---|
| text | 1484 | 471 | 8 | 0 |
| photo | 2608 | 1055 | 0 | 0 |
| none | 0 | 0 | 0 | 749 |

## Photo vs written gender (1955 products where the shop writes women or men)

FashionCLIP zero-shot on the photo, compared with the gender written in the name / URL.

| Margin | Coverage | Accuracy | |
|---|---|---|---|
| 0 | 100.0% | 93.4% |  |
| 0.5 | 96.4% | 94.6% |  |
| 1 | 92.5% | 95.7% |  |
| 1.5 | 88.8% | 96.8% |  |
| 2 | 84.5% | 97.9% | ← used |
| 3 | 72.2% | 98.9% |  |

With the type rule (a photo guess against a type written ≥ 95% one gender is dropped; 52 dropped): margin 2, coverage 83.8%, accuracy **98.2%**.

## Season per source

| Source | summer | winter | none |
|---|---|---|---|
| text | 342 | 384 | 0 |
| photo | 1599 | 614 | 0 |
| none | 0 | 0 | 3436 |

## Photo vs the season in the name (577 products: lin, bretelles… / velours, laine…)

| Margin | Coverage | Accuracy | |
|---|---|---|---|
| 0 | 100.0% | 78.0% |  |
| 0.5 | 91.0% | 80.4% |  |
| 1 | 83.5% | 83.0% |  |
| 1.5 | 77.8% | 84.9% |  |
| 2 | 70.7% | 86.0% | ← used |
| 3 | 54.9% | 90.5% |  |
