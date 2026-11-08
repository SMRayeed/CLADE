# NeusymBridge results summary

Recomputed from the per-edge CSV files in `work/`. Detailed logs are in `results/`.

## How much of the graph text reaches (Qwen2.5-0.5B-Instruct, 1,800 edges)

| | Model knows it | Model does not |
|---|---|---|
| Text names it | 5.2% | 6.2% |
| Text does not | 22.2% | 66.4% |

Accuracy on facts the text does not name: 25.1% (chance 20%).

## Does a family name alone help? (Qwen2.5-7B-Instruct, closed book)

| Relation | named | family only | silent |
|---|---|---|---|
| contraindication | 32.50% (n=40) | 18.75% (n=16) | 23.35% (n=544) |
| indication | 84.16% (n=101) | 44.68% (n=94) | 43.95% (n=405) |
| off-label use | 57.14% (n=63) | 37.50% (n=72) | 31.61% (n=465) |

Stratified odds ratios: `results/tier_cliff_*.txt`.

## Question pool (drug-matched sample, Wikipedia + PubMed)

| Group | edges |
|---|---|
| named | 774 |
| family only | 458 |
| silent | 2,212 |

## Where the other numbers are

| Paper item | File |
|---|---|
| Four-box table, both cuts | `results/four_boxes_*.txt` |
| Family-only vs silent vs named, stratified by relation | `results/tier_cliff_*.txt` |
| Abstention, per model | `results/abstain_report_<model>.txt` |
| Abstention, pooled over the 7-8B models (difference in differences) | `results/abstain_report_pooled.txt` |
| Recovery: list coverage, page-built lists, choosing a member, end to end | `results/candidate_check_wiki.txt` |
| Page-built lists from Wikipedia + PubMed | `results/candidate_check_all.txt` |
| Fan-out of MONDO families | `results/fanout.txt` |
| MONDO table size | `results/mondo_parents.txt` |

