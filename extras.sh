#!/bin/bash
# Two follow-up tests on the finished PrimeKG run. Both reuse work/ as
# run_all.sh left it, so run_all.sh must have finished first.
#
#   1. Step 2 of the hand-off: of the families a drug's page names, which one
#      holds the answer? Qwen2.5-7B reads the page and picks one; three rules
#      that read no meaning (first mentioned, smallest, random) sit beside it.
#      The chosen family is then expanded and scored end to end.
#   2. Free text: the abstention test with no options. Each model writes an
#      answer, which is scored by matching names: correct, decline, a wrong
#      sibling, the family name itself, or something else.
#
#   bash extras.sh submit    login node: submit the model jobs to SLURM
#   bash extras.sh status    which jobs have finished
#   bash extras.sh score     login node (needs network): PubMed counts for the
#                            new lists, then the step-2 tables
#   bash extras.sh report    print both summaries
#
#   bash extras.sh --local submit   run the model jobs in this shell instead
#   bash extras.sh --smoke ...      the same on the smoke fixture
#
# Settings: FREETEXT_N questions per page type (default 40, so 120 questions,
# each asked closed book and with the page), FREETEXT_MODELS (default the
# three 7-8B models), PICK_MODEL (default the recovery model, Qwen2.5-7B).

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$ROOT/config.sh"
# shellcheck disable=SC1091
[[ -f "$ROOT/config_extend.sh" ]] && source "$ROOT/config_extend.sh"
# shellcheck disable=SC1091
source "$ROOT/lib/common.sh"

MODE="slurm"; SMOKE=0; ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --local) MODE="local" ;;
        --smoke) SMOKE=1; MODE="local" ;;
        -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
        *) ARGS+=("$1") ;;
    esac
    shift
done
export SMOKE
CMD="${ARGS[0]:-}"
[[ -z "$CMD" ]] && { sed -n '2,25p' "$0"; exit 0; }

if [[ "$SMOKE" == "1" ]]; then BASE="$ROOT/smoke"; else BASE="$ROOT"; fi
WORK="$BASE/work"; RES="$BASE/results"; LOGS="$BASE/logs"; SCR="$ROOT/scripts"
mkdir -p "$WORK/done" "$RES" "$LOGS"
export WORK RES LOGS

FREETEXT_N="${FREETEXT_N:-40}"
FREETEXT_MODELS="${FREETEXT_MODELS-$POOL_MODELS}"
PICK_MODEL="${PICK_MODEL:-$RECOVER_MODEL}"
TIME_EXTRA="${TIME_EXTRA:-06:00:00}"
if [[ "$SMOKE" == "1" ]]; then
    FREETEXT_N=5
    PICK_MODEL="$BASE/tiny_model_b"
    FREETEXT_MODELS="$BASE/tiny_model_b"
fi
PKG=(pkg_ind_d2d.csv pkg_con_d2dis.csv pkg_off_d2dis.csv)
COLS=(--col-source x_name --col-target y_name --col-relation display_relation)
CC=(--scored me_bal_union.csv --edges "${PKG[@]}" "${COLS[@]}"
    --ancestors mondo_child_parent.csv --wiki-cache wiki_cache
    --extra-text pubmed_cache --names-cache gbif_cache
    --cand-cache candidate_wiki_cache --pubmed-cache pubmed_pairs.jsonl
    --expand-depth "$EXPAND_DEPTH" --max-candidates "$MAX_CANDIDATES"
    --max-set "$MAX_CANDIDATES" --page-text wiki --popularity)

setup_env
have "$WORK/me_bal_union.csv" || die "run_all.sh has not finished: $WORK/me_bal_union.csv is missing"

run_task () {      # run_task pick|freetext MODEL
    local task="$1" model="$2" tag th="${SLURM_CPUS_PER_TASK:-$CPUS}"
    tag="$(tag_of "$model")"
    local marker="$WORK/done/extra_${task}_${tag}.ok"
    [[ -f "$marker" ]] && { log "have $task $tag"; return 0; }
    case "$task" in
        pick)
            ( cd "$WORK" && py candidate_check.py "${CC[@]}" \
                --pick-model "$model" --threads "$th" --batch-size 4 \
                --picks-out "family_picks_${tag}.csv" ) \
                > "$RES/family_pick_${tag}.txt" 2>&1 || return 1 ;;
        freetext)
            ( cd "$WORK" && py abstain_probe.py --scored me_bal_union.csv \
                --wiki-cache wiki_cache --extra-text pubmed_cache \
                --ancestors mondo_child_parent.csv --names-cache gbif_cache \
                --per-band "$PER_BAND" --options 5 --distractors sibling \
                --model "$model" --threads "$th" --batch-size 4 --seed "$SEED" \
                --freetext "$FREETEXT_N" --out "freetext_${tag}.csv" ) \
                > "$RES/freetext_${tag}.txt" 2>&1 || return 1
            cp "$WORK/freetext_${tag}.csv" "$RES/" ;;
        *) die "unknown task $task" ;;
    esac
    touch "$marker"
    log "done $task $tag -> $RES"
}

jobs_list () {
    echo "pick $PICK_MODEL"
    local m
    for m in $FREETEXT_MODELS; do echo "freetext $m"; done
}

case "$CMD" in
    _task) run_task "${ARGS[1]}" "${ARGS[2]}" ;;
    submit)
        while read -r task model; do
            if [[ "$MODE" == "slurm" ]]; then
                jid=$(submit "ex_${task}_$(tag_of "$model")" "$TIME_EXTRA" "" \
                      "bash $ROOT/extras.sh _task $task $model") || die "sbatch failed"
                log "submitted $task $(tag_of "$model")  job $jid"
            else
                run_task "$task" "$model" || die "$task $model failed"
            fi
        done < <(jobs_list) ;;
    status)
        while read -r task model; do
            t="$(tag_of "$model")"
            if [[ -f "$WORK/done/extra_${task}_${t}.ok" ]]; then echo "done     $task $t"
            else echo "pending  $task $t"; fi
        done < <(jobs_list) ;;
    score)
        t="$(tag_of "$PICK_MODEL")"
        have "$WORK/family_picks_${t}.csv" || die "no family picks yet; run: bash extras.sh submit"
        net=(--fetch --pubmed --contact "$CONTACT")
        [[ -n "${NCBI_API_KEY:-}" ]] && net+=(--api-key "$NCBI_API_KEY")
        [[ "$SMOKE" == "1" ]] && net=()
        ( cd "$WORK" && py candidate_check.py "${CC[@]}" \
            --family-picks "family_picks_${t}.csv" "${net[@]}" \
            --out "$RES/candidate_check_llm.csv" ) \
            > "$RES/candidate_check_llm.txt" 2>&1 || die "scoring failed; see $RES/candidate_check_llm.txt"
        log "wrote $RES/candidate_check_llm.txt" ;;
    report)
        t="$(tag_of "$PICK_MODEL")"
        for f in "$RES/candidate_check_llm.txt" "$RES/family_pick_${t}.txt"; do
            [[ -s "$f" ]] || continue
            echo "=== $(basename "$f")"
            sed -n '/STEP 2: WHICH FAMILY/,/^  llm /p;/END TO END, NO ORACLE/,/^$/p' "$f"
            break
        done
        for m in $FREETEXT_MODELS; do
            f="$RES/freetext_$(tag_of "$m").txt"
            [[ -s "$f" ]] || { echo "=== no free-text output yet for $(tag_of "$m")"; continue; }
            echo "=== free text, $(tag_of "$m")"
            sed -n '/condition group/,/decline effect/p' "$f"
        done ;;
    *) die "unknown command $CMD (see bash extras.sh --help)" ;;
esac
