# NeusymBridge additional analyses

## 1. Confidence of answers with the page

| Model | Page | Answered | Precision | Conf. right | Conf. wrong | AUROC |
|---|---|---|---|---|---|---|
| Qwen2.5-0.5B-Instruct | named | 97/106 | 84.5 | 0.83 | 0.49 | 0.85 |
| Qwen2.5-0.5B-Instruct | family only | 194/215 | 38.1 | 0.71 | 0.60 | 0.64 |
| Qwen2.5-0.5B-Instruct | silent | 127/160 | 36.2 | 0.60 | 0.45 | 0.70 |
| Qwen2.5-7B-Instruct | named | 80/106 | 95.0 | 0.98 | 1.00 | 0.73 |
| Qwen2.5-7B-Instruct | family only | 96/215 | 59.4 | 0.98 | 0.90 | 0.72 |
| Qwen2.5-7B-Instruct | silent | 26/160 | 84.6 | 0.98 | 0.88 | 0.77 |
| OLMo-2-1124-7B-Instruct | named | 98/106 | 83.7 | 0.97 | 0.75 | 0.86 |
| OLMo-2-1124-7B-Instruct | family only | 176/215 | 45.5 | 0.89 | 0.77 | 0.71 |
| OLMo-2-1124-7B-Instruct | silent | 88/160 | 55.7 | 0.82 | 0.73 | 0.65 |
| granite-3.1-8b-instruct | named | 85/106 | 90.6 | 0.95 | 0.71 | 0.87 |
| granite-3.1-8b-instruct | family only | 122/215 | 53.3 | 0.90 | 0.82 | 0.66 |
| granite-3.1-8b-instruct | silent | 40/160 | 60.0 | 0.89 | 0.76 | 0.76 |
| Qwen2.5-14B-Instruct | named | 75/106 | 96.0 | 0.99 | 0.92 | 0.77 |
| Qwen2.5-14B-Instruct | family only | 89/215 | 58.4 | 0.98 | 0.99 | 0.59 |
| Qwen2.5-14B-Instruct | silent | 23/160 | 82.6 | 0.97 | 0.99 | 0.68 |

## 2. Decline effect by family size

Pooled over OLMo-2-1124-7B-Instruct, Qwen2.5-7B-Instruct, granite-3.1-8b-instruct. Family list size from the recovery run (thirds: up to 10, 11 to 20, above 20 members). Effect = (page effect on declines, family-only) minus (same, silent); points, 95% CI.

| Family size | n | Members (median) | Decline effect vs silent | Wrong with page |
|---|---|---|---|---|
| small | 71 | 7 | -17.3 [-26.2, -8.2], p=0.001 | 40.4% |
| medium | 69 | 16 | -18.4 [-26.6, -10.3], p=0.000 | 22.7% |
| large | 68 | 44 | -6.5 [-15.7, +3.0], p=0.174 | 26.0% |

## 3. Prompting baseline: tell the model to decline on a broad category

With the page, base prompt vs. prompt with the instruction (%). Change in points, 95% bootstrap CI over questions.

| Model | Page | n | Declines base → instr. | Correct base → instr. | Wrong base → instr. | Precision base → instr. |
|---|---|---|---|---|---|---|
| Qwen2.5-7B-Instruct | named | 106 | 24.5 → 29.2 | 71.7 → 67.0 | 3.8 → 3.8 | 95.0 → 94.7 |
| Qwen2.5-7B-Instruct | family only | 215 | 55.4 → 64.2 | 26.5 → 23.3 | 18.1 → 12.6 | 59.4 → 64.9 |
| Qwen2.5-7B-Instruct | silent | 160 | 83.8 → 88.1 | 13.8 → 10.6 | 2.5 → 1.2 | 84.6 → 89.5 |
| OLMo-2-1124-7B-Instruct | named | 106 | 7.5 → 27.4 | 77.4 → 65.1 | 15.1 → 7.5 | 83.7 → 89.6 |
| OLMo-2-1124-7B-Instruct | family only | 215 | 18.1 → 56.3 | 37.2 → 20.9 | 44.6 → 22.8 | 45.5 → 47.9 |
| OLMo-2-1124-7B-Instruct | silent | 160 | 45.0 → 85.6 | 30.6 → 8.8 | 24.4 → 5.6 | 55.7 → 60.9 |
| granite-3.1-8b-instruct | named | 106 | 19.8 → 22.6 | 72.6 → 70.8 | 7.5 → 6.6 | 90.6 → 91.5 |
| granite-3.1-8b-instruct | family only | 215 | 43.3 → 41.9 | 30.2 → 31.2 | 26.5 → 27.0 | 53.3 → 53.6 |
| granite-3.1-8b-instruct | silent | 160 | 75.0 → 71.9 | 15.0 → 15.6 | 10.0 → 12.5 | 60.0 → 55.6 |

Pooled over models (each question averaged over the models that ran it):

| Page | Declines change | Correct change | Wrong change |
|---|---|---|---|
| named | +9.1 [+6.0, +12.6] | -6.3 [-9.4, -3.5] | -2.8 [-5.0, -0.9] |
| family only | +15.2 [+12.4, +18.1] | -6.2 [-8.2, -4.2] | -9.0 [-11.8, -6.2] |
| silent | +14.0 [+10.6, +17.1] | -8.1 [-10.8, -5.6] | -5.8 [-8.3, -3.5] |

## 4. Counterfactual page edit (same named questions)

Original page names the answer; *family* replaces every mention with its MONDO parent; *removed* deletes the sentences that mention it. Rates with the page (%).

| Model | n | Version | Declines | Correct | Wrong | Precision |
|---|---|---|---|---|---|---|
| OLMo-2-1124-7B-Instruct | 130 | original | 6.2 | 74.6 | 19.2 | 79.5 |
| OLMo-2-1124-7B-Instruct | 130 | family | 7.7 | 58.5 | 33.8 | 63.3 |
| OLMo-2-1124-7B-Instruct | 130 | removed | 18.5 | 52.3 | 29.2 | 64.2 |
| Qwen2.5-7B-Instruct | 130 | original | 27.7 | 66.9 | 5.4 | 92.6 |
| Qwen2.5-7B-Instruct | 130 | family | 43.8 | 46.2 | 10.0 | 82.2 |
| Qwen2.5-7B-Instruct | 130 | removed | 70.0 | 26.9 | 3.1 | 89.7 |
| granite-3.1-8b-instruct | 130 | original | 23.8 | 69.2 | 6.9 | 90.9 |
| granite-3.1-8b-instruct | 130 | family | 40.8 | 43.1 | 16.2 | 72.7 |
| granite-3.1-8b-instruct | 130 | removed | 56.2 | 31.5 | 12.3 | 71.9 |

Pooled over OLMo-2-1124-7B-Instruct, Qwen2.5-7B-Instruct, granite-3.1-8b-instruct: change in points (each question averaged over models), 95% bootstrap CI.

| Outcome | Family minus removed | Family minus original |
|---|---|---|
| Declines | -17.4 [-23.6, -11.5] | +11.5 [+7.4, +15.9] |
| Wrong | +5.1 [+0.5, +10.3] | +9.5 [+5.9, +13.6] |
| Correct | +12.3 [+6.9, +17.9] | -21.0 [-26.9, -15.6] |

