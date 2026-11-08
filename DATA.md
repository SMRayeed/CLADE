# Data

All inputs are public. The pipelines download them; this repository ships only
what the analysis reads after the download and text steps, plus every
per-question result. Text from Wikipedia and PubMed is not redistributed.

## Sources and versions

| Source | Version used | Use | License |
|---|---|---|---|
| PrimeKG `kg.csv` (Chandak et al. 2023), Harvard Dataverse file 6180620 | downloaded 2026-10-28; sha256 `0a5a010f…5c69` | drug–disease edges | see the dataset page (doi:10.7910/DVN/IXA7BM) |
| MONDO disease ontology | releases/2026-10-06; sha256 `2631e8e1…ed60b` | disease families, candidate lists | CC BY 4.0 |
| GloBI interaction dump (Poelen et al. 2014) | Zenodo snapshot, doi:10.5281/zenodo.4460654 (`interactions.tsv.gz`, 783 MB) | species interactions and taxonomy paths | see the Zenodo record; source datasets carry their own terms |
| English Wikipedia | fetched 2026-10/11 through the MediaWiki API | drug and species articles, redirect names | CC BY-SA 4.0 (not redistributed) |
| PubMed abstracts | fetched 2026-10/11 through NCBI E-utilities | second corpus, co-mention evidence | publisher copyright (not redistributed) |

Exact hashes: `results/data_versions.txt`.

## Counts: PrimeKG

| Item | Count | Log |
|---|---|---|
| PrimeKG rows | 8,100,498 | `results/prep_primekg.txt` |
| Indication / contraindication / off-label edges | 9,388 / 30,675 / 2,568 | `results/prep_primekg.txt` |
| MONDO child→parent rows / diseases with a parent | 17,801 / 11,788 | `results/mondo_parents.txt` |
| Drug-matched question pool | 574 drugs, 1,722 edges per relation | `results/drug_matched_sample.txt` |
| Abstention questions | 856: 150 per group (named / family only / silent) per relation, except 106 family-only contraindications | `results/abstain_report_*.txt` |
| Questions with all-sibling distractors, seen by the three 7–8B models | 481 | `results/abstain_report_pooled.txt` |
| Counterfactual edit (named questions whose answer has a MONDO parent) | 130 per model | `results/EXTRAS.md` §4 |
| Recovery: family-only facts with a usable oracle list | 410 | `results/candidate_check_all.txt` |

## Counts: GloBI

| Item | Count | Log |
|---|---|---|
| Interaction records in the dump | 7,822,670 | `results/globi/globi_prep.txt` |
| Records in eats / preysOn / parasiteOf / pollinates | 3,210,597 | `results/globi/globi_prep.txt` |
| Species-to-species edges (both sides binomial) | 457,386 | `results/globi/globi_prep.txt` |
| eats: edges / consumer species | 235,960 / 25,637 | `results/globi/globi_prep.txt` |
| parasiteOf | 117,894 / 31,432 | |
| preysOn | 87,678 / 5,138 | |
| pollinates | 15,854 / 2,818 | |
| Taxonomy child→parent rows; genera with ≥ 2 species | 77,852; 8,370 | `results/globi/globi_prep.txt` |
| Edges measured (consumer has a Wikipedia article of ≥ 3,000 characters) | 23,694 over 5,425 articles (eats 8,000, preysOn 8,000, pollinates 5,305, parasiteOf 2,389) | `results/globi/globi_tiers.txt` |
| Page names the partner species / only its genus or family / nothing | 3.9% / 7.1% / 89.1% | `results/globi/globi_tiers.txt` |
| Abstention questions | 900: 75 per group per relation | `results/globi/globi_questions.txt` |
| All-sibling questions seen by the three models | 833 | `results/globi/abstain_report_pooled.txt` |
| Counterfactual edit (named questions) | 255 per model | `results/globi/EXTRAS_GLOBI.md` |

## Files in `derived_data/`

| File | Rows | Contents |
|---|---|---|
| `primekg/pkg_ind_d2d.csv`, `pkg_con_d2dis.csv`, `pkg_off_d2dis.csv` | 9,388 / 30,675 / 2,568 | PrimeKG drug–disease relations (PrimeKG columns) |
| `primekg/pkg_pc.csv` | 64,388 | PrimeKG disease–disease edges |
| `primekg/matched_*.csv` | | drug-matched sample and its PubMed tiers |
| `primekg/candidate_prefetch_{wiki,all}.csv` | 576 / 429 | candidate lists built from the page (Wikipedia; Wikipedia + PubMed) |
| `primekg/pubmed_pairs.jsonl` | 13,593 | PubMed hit counts for drug–candidate co-mention queries |
| `globi/globi_edges.csv` | 457,386 | `source, target, relation, n_records` |
| `globi/globi_child_parent.csv` | 77,852 | species → genus → family → order → class |
| `globi/globi_tiers.csv` | 23,694 | page tier per measured edge (tier columns below) |

Per-question results are in `results/csv/` and `results/globi/csv/`.

**Recovery** (`recover_<model>_clean.csv`): one row per family-only fact; `k` candidate-list size, `has_gold`
whether the list holds the answer, `pick_*` / `hit_*` the pick and hit of each chooser (`ours`: evidence then
model; `ours_ctx`: with the page; `random_k`; `rag_pool`).

## File formats

**Tier files** (`*_edges*.csv`, `me_*.csv`, `p1_edges_d2*.csv`, `globi_tiers.csv`): one row per graph edge.
`tier` is how plainly the text names the target: 0 exact name, 1 synonym, 2 alternative or common name
(Wikipedia redirect), 3 only an ancestor (family: up to two ontology levels up), 4 not at all. Tiers 0-2 count
as "named". `category_only` marks tier 3, `art_len` the article length, `cooccurrence` how many articles mention
both names, `out_degree` the source's number of edges in the relation. Files with several texts add
`tier_wiki`, `tier_second` (PubMed or label) and `tier_union`.

**Closed-book probe** (`p1_edges_d2_<model>.csv`): the tier columns plus `mc_correct` (1 if the five-option
question was answered correctly), `mc_gold_logprob`, `mc_best_logprob`, `mc_margin`, `mc_n_choices`.

**Abstention questions** (`abstain_<model>_<task>.csv`): one row per question and condition. `group` is
named / category (family only) / silent; `condition` is `closed` (no page) or `passage` (with the page);
`n_options` counts all options including "Not enough information to tell", `n_sibling` how many distractors
come from the answer's own family; `pick` and `outcome` (correct / wrong / abstain) give the answer;
`p_pick`, `p_decline`, `p_true` are the normalized option probabilities. Tasks: `clean` (base prompt),
`instruct` (told to decline on a broad category), `edit_family` / `edit_remove` (counterfactual page edits).

