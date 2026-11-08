#!/bin/bash
# Recompute the tables from the per-question files shipped in this repository,
# without network access, model weights or web caches, and compare the new
# logs with results/ and results/globi/. Needs Python 3.9+ (standard library).
#
#   bash tools/check_results.sh
#
# The ontology-recovery logs (candidate_check_*, fanout) read the Wikipedia,
# PubMed and candidate caches, which are not redistributed; they are reported
# as "needs web caches" and the shipped logs stand.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/config.sh"; source "$ROOT/config_extend.sh"; source "$ROOT/config_globi.sh"
# shellcheck disable=SC1091
source "$ROOT/lib/common.sh"; source "$ROOT/pipeline.sh"
PY="${PY:-python3}"; SCR="$ROOT/scripts"
rm -rf "$ROOT/check"

# ---- PrimeKG
WORK="$ROOT/check/work"; RES="$ROOT/check/results"; mkdir -p "$WORK" "$RES"
cp "$ROOT"/derived_data/primekg/* "$ROOT"/results/csv/*.csv "$WORK/"
export WORK RES
step_analysis > "$ROOT/check/analysis.log" 2>&1

# ---- GloBI
GW="$ROOT/check/globi_work"; GR="$ROOT/check/results/globi"; mkdir -p "$GW" "$GR"
cp "$ROOT"/derived_data/globi/* "$ROOT"/results/globi/csv/*.csv "$GW/"
WORK="$GW"; RES="$GR"
base=(); efam=(); erem=(); pool=(); csvs=()
for m in $GLOBI_MODELS; do
    t="$(tag_of "$m")"; pool+=("$t")
    base+=("abstain_${t}_clean.csv"); csvs+=(--csv "abstain_${t}_clean.csv")
    efam+=("abstain_${t}_edit_family.csv"); erem+=("abstain_${t}_edit_remove.csv")
    step_log "abstain_report_${t}" py abstain_report.py --csv "abstain_${t}_clean.csv" >/dev/null
done
step_log abstain_report_pooled py abstain_report.py "${csvs[@]}" --pool >/dev/null
step_log globi_extras py ns_extras.py --abstain "${base[@]}" --edit-family "${efam[@]}" \
    --edit-remove "${erem[@]}" --pool "${pool[@]}" --out "$GR/EXTRAS_GLOBI.md" \
    --json "$GR/extras_globi.json" >/dev/null

# ---- compare
echo "recomputed logs in check/results/"
same=0; diffn=0
cmp_dir () {   # new_dir old_dir
    local f b
    for f in "$1"/*.txt "$1"/*.md; do
        b="$(basename "$f")"; [[ -f "$2/$b" ]] || continue
        case "$b" in figures.txt) continue ;; candidate_check_*|fanout*|candidate_fetch*) echo "  needs web caches: $b"; continue ;; esac
        if diff -q <(grep -v -E '^/|work/|<repo>|wrote |[0-9]{4}-[0-9]{2}-[0-9]{2}' "$f") \
                   <(grep -v -E '^/|work/|<repo>|wrote |[0-9]{4}-[0-9]{2}-[0-9]{2}' "$2/$b") >/dev/null; then
            same=$((same+1))
        else
            diffn=$((diffn+1)); echo "  differs: $b"
        fi
    done
}
cmp_dir "$ROOT/check/results" "$ROOT/results"
cmp_dir "$ROOT/check/results/globi" "$ROOT/results/globi"
echo "identical: $same   different: $diffn"
