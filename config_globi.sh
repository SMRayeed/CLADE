# Settings for globi.sh, the second-domain replication on GloBI species
# interactions. Sourced after config.sh and config_extend.sh, so SLURM,
# Python and model settings come from there. Every value can be overridden
# in the environment, e.g.  GLOBI_PER_BAND=80 bash globi.sh check

# The GloBI interaction dump (tab-separated, gzipped). The default is the
# archived Zenodo snapshot (DOI 10.5281/zenodo.4460654, about 820 MB), which is
# citable and fixed; the live snapshot is tried if it fails.
GLOBI_URL="${GLOBI_URL:-https://zenodo.org/records/4460654/files/interactions.tsv.gz?download=1}"
GLOBI_URL_ALT="${GLOBI_URL_ALT:-https://depot.globalbioticinteractions.org/snapshot/target/data/tsv/interactions.tsv.gz}"
# If you already have the dump on disk, point to it and nothing is downloaded.
GLOBI_TSV="${GLOBI_TSV:-}"

# Relations asked about. Each has a question template in abstain_probe.py.
GLOBI_RELATIONS="${GLOBI_RELATIONS:-eats,preysOn,parasiteOf,pollinates}"
# Edges measured per relation (articles fetched for their sources). Family-only
# pages are the scarce group, so this is set well above 3 x GLOBI_PER_BAND.
GLOBI_N="${GLOBI_N:-2500}"
GLOBI_MIN_CHARS="${GLOBI_MIN_CHARS:-3000}"   # skip stub articles
# Questions per group (named / family-only / silent) per relation.
GLOBI_PER_BAND="${GLOBI_PER_BAND:-75}"   # 4 x 3 x 75 = 900 questions, the PrimeKG scale

# The three 7-8B models of the paper's pooled result.
GLOBI_MODELS="${GLOBI_MODELS-$POOL_MODELS}"
# Tasks per model: clean = with page and closed book; edit_* = counterfactual.
GLOBI_TASKS="${GLOBI_TASKS:-clean edit_family edit_remove}"
TIME_GLOBI="${TIME_GLOBI:-12:00:00}"
