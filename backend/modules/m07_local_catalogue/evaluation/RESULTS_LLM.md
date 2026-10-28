# BO6 LLM in M7 — requests the rules do not understand

16 hand-written requests (`queries_llm.yaml`, FR / EN / darija / Arabic) where `parse.py` finds no piece, colour or photo. Rules alone vs rules + LLM (`pipeline/understand.py`, with its checks). CPU only (Intel i7-1165G7, no GPU).

| | type understood and right | budget / city right | pieces found | LLM latency (median) |
|---|---|---|---|---|
| rules | 0/16 | 15/16 | 0/16 | - |
| qwen2.5:7b | 11/16 | 16/16 | 14/16 | 14.8 s |
| qwen2.5:3b | 12/16 | 16/16 | 16/16 | 7.6 s |

## Per request (French rewrite by the LLM)

| id | request | qwen2.5:7b | qwen2.5:3b |
|---|---|---|---|
| h01 | nlawej 3la haja l 3ers mouch ghalia | ✅ robe de soirée → dress | ✅ robe de mariée → dress |
| h02 | haja nlabesha l b7ar fi sif | ❌ chemise → shirt | ✅ robe de soirée → dress |
| h03 | 7ajti b haja n7otha 3la sa9aya f chta | ❌ chemise → shirt | ❌ robe de mariage → dress |
| h04 | nheb haja nlabesha l khedma | ❌ robe de soirée → dress | ✅ robe de soirée → suit |
| h05 | chnowa nlabes l soutenance mte3i a9al men 200 | ✅ robe de soutenance → dress | ✅ robe de soirée → dress |
| h06 | 7aja tdafini f chta | ❌ robe de soirée → dress | ❌ robe de soirée → dress |
| h07 | something nice for my sister's engagement under 150 dinars | ✅ robe de soirée → dress | ✅ robe de mariage → dress |
| h08 | what can I wear to the gym | ✅ tennis shoes → sneakers | ✅ vêtement de sport → sneakers |
| h09 | an outfit for a job interview | ✅ costume d'affaires → suit | ✅ robe de travail → suit |
| h10 | I need something to keep me warm this winter | ✅ manteau chaud → coat | ✅ manteau chaud → coat |
| h11 | une tenue pour le hammam | ❌ tenue de hammam → - | ❌ tenue hammam → jacket |
| h12 | quelque chose pour la plage cet été | ✅ shorts de bain → swimwear | ✅ robe de plage → swimwear |
| h13 | un cadeau pour ma mère moins de 80 dt | ✅ sac de femme → bag | ❌ robe de fête → dress |
| h14 | de quoi protéger mes yeux du soleil | ✅ sunglasses → sunglasses | ✅ sunglasses → sunglasses |
| h15 | عندي عرس في سوسة نحب حاجة باهية | ✅ robe de soirée → dress | ✅ robe de mariage élégante → dress |
| h16 | حاجة للبحر في الصيف | ✅ shorts de bain → swimwear | ✅ robe de plage → swimwear |

Caveat: the requests and their intent were written by the same team as the system; a set written by someone else would give a fairer figure.
