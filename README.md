# CLADE

**CLADE: Category-Level Answering from Deficient Evidence in Retrieval-Augmented Language Models**
Code, data, results and paper for the NeusymBridge-27 / NeSy-FM workshop paper (AAAI 2027).

Retrieval often hands a model a page that is true and relevant but names only
the answer's family ("hyperlipidemia" when the answer is "familial
hyperlipidemia"; "the pussytoes (*Antennaria*)" when the answer is one
*Antennaria* species). We call this *resolvable insufficiency*: the page cannot
settle the answer, but its family name indexes a short candidate list in an
ontology or taxonomy. Models meet it with **CLADE**, category-level answering
from deficient evidence: they treat such pages as permission to answer instead
of declining or looking further, in medicine (PrimeKG + MONDO) and in ecology
(GloBI + taxonomy) alike.

- Paper: [`paper/neusym.pdf`](paper/neusym.pdf), supplement: [`paper/neusym_supplement.pdf`](paper/neusym_supplement.pdf)
- Every number in the paper is in [`results/`](results/) (PrimeKG) and [`results/globi/`](results/globi/) (GloBI).
- Data sources, versions, counts and licenses: [`DATA.md`](DATA.md).

## Key results

Pooled over Qwen2.5 7B, OLMo 2 7B and Granite 3.1 8B; questions with all-sibling
distractors; effects in points with 95% bootstrap CIs.

| Finding | PrimeKG (diseases) | GloBI (species) | Files |
|---|---|---|---|
| Questions (5 options + "Not enough information") | 856 | 900 | `results/abstain_report_*.txt`, `results/globi/globi_questions.txt` |
| Decline effect of the page, family-only − silent | −13.8 [−20.3, −7.5], p = 3.6e-5 | −14.3 [−18.7, −9.6], p = 1.4e-9 | `abstain_report_pooled.txt` |
| Wrong-answer effect, family-only − silent | +7.7 [+1.2, +14.0] | +11.6 [+7.5, +15.4] | `abstain_report_pooled.txt` |
| Precision with a named page | 84–95% | 84–95% | `EXTRAS.md` §1 |
| Precision with a family-only page | 45–59% | 22–28% (chance 20%) | `EXTRAS.md` §1 |
| Counterfactual edit, declines, family − removed | −17.4 [−23.6, −11.5] | −27.7 [−32.2, −23.5] | `EXTRAS.md` §4 |
| Counterfactual edit, wrong, family − removed | +5.1 [+0.5, +10.3] | +6.7 [+3.4, +10.2] | `EXTRAS.md` §4 |
| AUROC of confidence, named vs. family-only page | 0.73–0.87 vs. 0.59–0.72 (5 models) | 0.82–0.86 vs. 0.52–0.68 | `EXTRAS.md` §1 |
| Instruction to decline: added declines (named / family / silent) | +9.1 / +15.2 / +14.0 | — | `results/EXTRAS.md` §3 |
| Ontology list holds the answer, family given / read off the page | 98.5% / 19.8% | — | `results/candidate_check_all.txt` |
| Choosing within the family: popularity prior vs. model | 46.8% vs. 35.9% | — | `results/candidate_check_all.txt` |

## Repository layout

| Path | Contents |
|---|---|
| `run_all.sh` | Entry point for the PrimeKG pipeline (download → analysis). |
| `globi.sh` | Entry point for the GloBI replication (download → report). |
| `config.sh`, `config_extend.sh`, `config_globi.sh` | All settings: SLURM account, models, data URLs, sample sizes, time limits. |
| `pipeline.sh` | The exact command behind each PrimeKG step. |
| `lib/common.sh` | Shared helpers: environment setup, downloads, SLURM submission. |
| `scripts/` | Analysis scripts (standard-library Python, except the model probes). |
| `tests/` | Synthetic fixtures and a tiny random model for the offline smoke tests. |
| `derived_data/primekg/` | PrimeKG relation splits, drug-matched samples, PubMed co-mention counts, candidate prefetch lists. |
| `derived_data/globi/` | GloBI species-to-species edges, the taxonomy table, and page tiers per edge. |
| `results/` | PrimeKG logs and tables; `results/csv/` holds per-question model answers. |
| `results/globi/` | GloBI logs and tables; `results/globi/csv/` holds per-question model answers. |
| `tools/check_results.sh` | Recomputes the tables from the shipped files and compares with `results/`. |
| `paper/` | LaTeX source (AAAI-27 kit, anonymous submission), figures, figure scripts and the PDFs. |

## Check the results (5 minutes, no network, no GPU)

```bash
bash tools/check_results.sh
```

This copies `derived_data/` and the per-question files into `check/`, reruns
the abstention reports, pooled tests, confidence, family-size, instruction and
counterfactual analyses for both domains, and compares each new log with the
shipped one. Expected output: `identical: 22 different: 0`. The three
ontology-recovery logs (`candidate_check_*`, `fanout`) read Wikipedia and
PubMed text, which is not redistributed; they are listed as "needs web caches".

## Reproduce from scratch

Requirements: Python 3.9+, network access for the download and text steps
(Harvard Dataverse, GitHub, Zenodo, Wikipedia, NCBI E-utilities, Hugging Face),
and SLURM for the model jobs (12 CPUs × 12 GB; models run in fp32 on CPU; each
job is resumable). On first use the scripts create a CPU environment at
`$ENV_DIR` (torch 2.5.1, transformers 4.48.3).

### PrimeKG

```bash
bash run_all.sh --smoke          # offline test on synthetic data (minutes)
export CONTACT="you@example.org" # e-mail for the Wikipedia User-Agent
export NCBI_API_KEY=...          # optional, faster PubMed (never commit it)
bash run_all.sh                  # login node, inside tmux; submits SLURM jobs
bash run_all.sh --status
```

| Step | Runs on | What it does | Main outputs |
|---|---|---|---|
| `download` | login node | PrimeKG `kg.csv`, MONDO | `data/`, `results/data_versions.txt` |
| `prepare` | any | Drug–disease relation splits, MONDO child→parent table | `work/pkg_*.csv`, `work/mondo_child_parent.csv` |
| `text` | login node | Wikipedia + PubMed text; each edge labeled named / family only / silent; candidate lists | `work/me_bal_union.csv`, caches |
| `extend` | login node | Downloads the extra models (14B, instruction and edit runs) | Hugging Face cache |
| `models` | SLURM | Closed-book probe; abstention questions with and without the page (5 models); instruction baseline; counterfactual edits; recovery | `work/abstain_<model>_<task>.csv`, `work/recover_*.csv` |
| `analysis` | any | All reports, pooled tests, recovery, extras, summary, figures | `results/` |

### GloBI

```bash
bash globi.sh --smoke all        # offline test (minutes)
bash globi.sh download           # Zenodo snapshot, DOI 10.5281/zenodo.4460654 (~0.8 GB)
bash globi.sh prepare            # species edges + taxonomy (15-40 min; submit with sbatch)
GLOBI_N=8000 bash globi.sh text  # Wikipedia articles, page tiers (1-2 h, login node)
bash globi.sh check              # question counts per group, examples (no model)
bash globi.sh models             # 3 models x 3 tasks on SLURM, then a report job
bash globi.sh status
```

The report is `results/globi/GLOBI.md` (written to `globi/results/` by a fresh
run). The paper used `GLOBI_N=8000` (edges measured per relation) and
`GLOBI_PER_BAND=75` (questions per group per relation).

Wikipedia and PubMed change over time, so a fresh run measures today's text.
The per-question files under `results/` record what the paper measured.

## Where each paper result comes from

| Paper item | Script | Output |
|---|---|---|
| How much graph text reaches the model; family name alone (closed book) | `four_boxes.py`, `tier_cliff.py` | `results/four_boxes_*.txt`, `results/tier_cliff_*.txt`, `results/SUMMARY.md` |
| Outcomes by page type, per model; pooled page effect | `abstain_probe.py`, `abstain_report.py` | `results/abstain_report_*.txt` |
| Confidence, family size, instruction baseline, counterfactual edit | `ns_extras.py` | `results/EXTRAS.md` |
| Ontology recovery (oracle and page-built lists, choosers) | `candidate_check.py`, `fanout.py`, `recover.py` | `results/candidate_check_*.txt`, `results/fanout.txt` |
| GloBI edges, taxonomy, tiers, questions | `globi_prep.py`, `gonogo_p1.py`, `abstain_probe.py` | `results/globi/globi_{prep,tiers,questions}.txt` |
| GloBI abstention, confidence, counterfactual | `abstain_report.py`, `ns_extras.py` | `results/globi/GLOBI.md`, `results/globi/EXTRAS_GLOBI.md` |
| Figures | `paper/build_figures.py`, `paper/drawio/` | `paper/fig_*.pdf` |

## Paper and figures

```bash
cd paper && latexmk -pdf neusym.tex && latexmk -pdf neusym_supplement.tex
python3 build_figures.py           # forest plot, recovery, three fixes (matplotlib)
```

Figures 1 and 3 are draw.io files (`paper/drawio/*.drawio`; open at
app.diagrams.net). `python3 drawio/build_ns.py` regenerates them;
`npm install mxgraph playwright && node drawio/render_pdf.js drawio/fig_edit.drawio`
exports a PDF. Icons are Microsoft Fluent Emoji 3D (MIT license) in `paper/icons/`.

## License

Code: MIT (`LICENSE`). Derived data follow their sources' licenses (`DATA.md`).
Wikipedia and PubMed text is not redistributed; the pipeline fetches it.

## Citation

See `CITATION.cff`.
