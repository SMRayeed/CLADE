# 📚 CLADE data

All our inputs are public. The pipelines download them for you.
We ship only the files the analysis reads, plus every per-question result.
We do not ship text from Wikipedia or PubMed.

## 🌐 Sources

| Source | Version | We use it for | License |
|---|---|---|---|
| 🗄️ PrimeKG `kg.csv` (Chandak et al. 2023), Harvard Dataverse file 6180620 | 2026-10-28, sha256 `0a5a010f…5c69` | drug → disease edges | see doi:10.7910/DVN/IXA7BM |
| 📁 MONDO disease ontology | 2026-10-06, sha256 `2631e8e1…ed60b` | disease families, candidate lists | CC BY 4.0 |
| 🦋 GloBI interaction dump (Poelen et al. 2014) | Zenodo doi:10.5281/zenodo.4460654 (`interactions.tsv.gz`, 783 MB) | species interactions and taxonomy | see the Zenodo record |
| 📖 English Wikipedia | MediaWiki API, 2026-10/11 | drug and species pages, common names | CC BY-SA 4.0 (not shipped) |
| 🔬 PubMed abstracts | NCBI E-utilities, 2026-10/11 | second text source, co-mention counts | publisher copyright (not shipped) |

Exact hashes: `results/data_versions.txt`.

## 🩺 Counts: PrimeKG

| Item | Count | Log |
|---|---:|---|
| 🗄️ PrimeKG rows | 8,100,498 | `results/prep_primekg.txt` |
| ✅ / ⛔ / 🔸 indication / contraindication / off-label edges | 9,388 / 30,675 / 2,568 | `results/prep_primekg.txt` |
| 📁 MONDO child → parent rows / diseases with a parent | 17,801 / 11,788 | `results/mondo_parents.txt` |
| 💊 Question pool | 574 drugs, 1,722 edges per relation | `results/drug_matched_sample.txt` |
| ❓ Questions | 856 (150 per page type per relation; 106 family-only contraindications) | `results/abstain_report_*.txt` |
| 👪 All-sibling questions, 7–8B models | 481 | `results/abstain_report_pooled.txt` |
| ✂️ Page-edit questions | 130 per model | `results/EXTRAS.md` §4 |
| 🔁 Recovery: family-only facts with a usable list | 410 | `results/candidate_check_all.txt` |

## 🦋 Counts: GloBI

| Item | Count | Log |
|---|---:|---|
| 🗄️ Records in the dump | 7,822,670 | `results/globi/globi_prep.txt` |
| 🔗 Records in our four relations | 3,210,597 | `results/globi/globi_prep.txt` |
| 🔗 Species-to-species edges | 457,386 | `results/globi/globi_prep.txt` |
| 🍃 eats: edges / consumers | 235,960 / 25,637 | `results/globi/globi_prep.txt` |
| 🪱 parasiteOf | 117,894 / 31,432 | |
| 🦈 preysOn | 87,678 / 5,138 | |
| 🐝 pollinates | 15,854 / 2,818 | |
| 🌳 Taxonomy rows; genera with ≥ 2 species | 77,852; 8,370 | `results/globi/globi_prep.txt` |
| 📖 Edges measured (page ≥ 3,000 characters) | 23,694 over 5,425 pages | `results/globi/globi_tiers.txt` |
| 🟢 / 🟡 / ⚪ page names it / only the family / nothing | 3.9% / 7.1% / 89.1% | `results/globi/globi_tiers.txt` |
| ❓ Questions | 900 (75 per page type per relation) | `results/globi/globi_questions.txt` |
| 👪 All-sibling questions | 833 | `results/globi/abstain_report_pooled.txt` |
| ✂️ Page-edit questions | 255 per model | `results/globi/EXTRAS_GLOBI.md` |

## 🗂️ Files in `derived_data/`

| File | Rows | What it holds |
|---|---:|---|
| `primekg/pkg_ind_d2d.csv`, `pkg_con_d2dis.csv`, `pkg_off_d2dis.csv` | 9,388 / 30,675 / 2,568 | PrimeKG drug → disease relations |
| `primekg/pkg_pc.csv` | 64,388 | PrimeKG disease → disease edges |
| `primekg/matched_*.csv` | | matched sample and its PubMed tiers |
| `primekg/candidate_prefetch_{wiki,all}.csv` | 576 / 429 | candidate lists built from the page |
| `primekg/pubmed_pairs.jsonl` | 13,593 | PubMed hit counts for drug–candidate pairs |
| `globi/globi_edges.csv` | 457,386 | `source, target, relation, n_records` |
| `globi/globi_child_parent.csv` | 77,852 | species → genus → family → order → class |
| `globi/globi_tiers.csv` | 23,694 | page tier per measured edge |

Per-question results live in `results/csv/` and `results/globi/csv/`.

**🔁 Recovery** (`recover_<model>_clean.csv`). One row per family-only fact. `k` is the list size, `has_gold` says if the list holds the answer, and `pick_*` / `hit_*` give each chooser's pick and hit (`ours`: evidence then model; `ours_ctx`: with the page; `random_k`; `rag_pool`).

## 🧾 File formats

**📖 Tier files** (`*_edges*.csv`, `me_*.csv`, `p1_edges_d2*.csv`, `globi_tiers.csv`). One row per graph edge. The `tier` column says how plainly the text names the target:

| Tier | Meaning | Counts as |
|:---:|---|---|
| 0 | exact name | 🟢 named |
| 1 | synonym | 🟢 named |
| 2 | common name (a Wikipedia redirect) | 🟢 named |
| 3 | only a parent, up to two levels up | 🟡 family only |
| 4 | not at all | ⚪ silent |

Other columns: `category_only` (tier 3), `art_len` (article length), `cooccurrence` (articles that mention both names), `out_degree` (the source's edges in the relation). Files with two texts add `tier_wiki`, `tier_second` and `tier_union`.

**❓ Closed-book probe** (`p1_edges_d2_<model>.csv`). The tier columns, plus `mc_correct` (1 if the model got the 5-option question right), `mc_gold_logprob`, `mc_best_logprob`, `mc_margin`, `mc_n_choices`.

**🤖 Abstention questions** (`abstain_<model>_<task>.csv`). One row per question and condition.

| Column | Meaning |
|---|---|
| `group` | named / category (family only) / silent |
| `condition` | `closed` (no page) or `passage` (with the page) |
| `n_options`, `n_sibling` | all options, and how many wrong options come from the answer's family |
| `pick`, `outcome` | the model's pick, and correct / wrong / abstain |
| `p_pick`, `p_decline`, `p_true` | option probabilities |

Tasks: `clean` (base prompt), `instruct` (told to decline on a broad category), `edit_family` / `edit_remove` (page edits).
