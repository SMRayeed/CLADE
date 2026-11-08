#!/bin/bash
# Second domain: the abstention test on GloBI species interactions, with the
# GloBI taxonomy (species -> genus -> family) in the role MONDO plays for
# diseases. A family-only page names the target's genus or family but not
# the species.
#
#   bash globi.sh download    login node: get the GloBI dump (skipped if GLOBI_TSV is set)
#   bash globi.sh prepare     species edges + taxonomy table            (any node)
#   bash globi.sh text        login node: Wikipedia articles, name tiers
#   bash globi.sh check       questions per group, and one example of each (no model)
#   bash globi.sh models      login node: download models, submit SLURM jobs + report job
#   bash globi.sh status      what is built, which jobs are done
#   bash globi.sh report      tables (the report job runs this by itself)
#
#   bash globi.sh all         download, prepare, text, check, models in one go
#   bash globi.sh --local models   run the model tasks in this shell instead of SLURM
#   bash globi.sh --smoke all      offline test on a synthetic fixture, tiny models
#
# Outputs go to globi/ (work/, results/, logs/). Every step skips what is
# already on disk, so rerunning a command resumes it.

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$ROOT/config.sh"
# shellcheck disable=SC1091
[[ -f "$ROOT/config_extend.sh" ]] && source "$ROOT/config_extend.sh"
# shellcheck disable=SC1091
source "$ROOT/config_globi.sh"
# shellcheck disable=SC1091
source "$ROOT/lib/common.sh"

MODE="slurm"; SMOKE=0; TASK=()
ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --local) MODE="local" ;;
        --smoke) SMOKE=1; MODE="local" ;;
        --task)  TASK=("$2" "$3"); shift 2 ;;
        -h|--help) sed -n '2,21p' "$0"; exit 0 ;;
        *) ARGS+=("$1") ;;
    esac
    shift
done
export SMOKE
CMD="${ARGS[0]:-}"
[[ -z "$CMD" && ${#TASK[@]} -eq 0 ]] && { sed -n '2,21p' "$0"; exit 0; }

if [[ "$SMOKE" == "1" ]]; then BASE="$ROOT/smoke_globi"; else BASE="$ROOT/globi"; fi
WORK="$BASE/work"; DATA="$BASE/data"; RES="$BASE/results"; LOGS="$BASE/logs"
SCR="$ROOT/scripts"
mkdir -p "$WORK/done" "$DATA" "$RES" "$LOGS"
export WORK DATA RES LOGS
export NT_ABBREV_BINOMIALS=1      # "Q. robur" names Quercus robur

setup_env

if [[ "$SMOKE" == "1" ]]; then
    if ! have "$DATA/interactions.tsv.gz"; then
        log "building the synthetic GloBI fixture"
        "$PY" "$ROOT/tests/make_globi_fixture.py" --data "$DATA" --work "$WORK" \
            || die "fixture build failed"
    fi
    if [[ ! -d "$BASE/tiny_model_a" ]]; then
        "$PY" "$ROOT/tests/tiny_model.py" --text "$WORK/wiki_cache" --out "$BASE/tiny_model_a" --seed 1 || die "tiny model"
        "$PY" "$ROOT/tests/tiny_model.py" --text "$WORK/wiki_cache" --out "$BASE/tiny_model_b" --seed 2 || die "tiny model"
    fi
    GLOBI_MODELS="$BASE/tiny_model_a $BASE/tiny_model_b"
    GLOBI_N=400; GLOBI_PER_BAND=8; GLOBI_MIN_CHARS=200; CPUS=2
fi

TSV="${GLOBI_TSV:-$DATA/interactions.tsv.gz}"

abs_args () {
    printf '%s\n' --scored globi_tiers.csv --wiki-cache wiki_cache \
        --ancestors globi_child_parent.csv --ancestor-cols child,parent \
        --names redirects --names-cache gbif_cache --depth 2 \
        --per-band "$GLOBI_PER_BAND" --options 5 --distractors sibling \
        --partners globi_edges.csv --seed "$SEED"
}

# ------------------------------------------------------------------ steps
step_download () {
    if [[ -n "$GLOBI_TSV" ]]; then
        have "$GLOBI_TSV" || die "GLOBI_TSV=$GLOBI_TSV does not exist"
        log "using $GLOBI_TSV"; return 0
    fi
    have "$TSV" && { log "have $(basename "$TSV")"; return 0; }
    need_network download
    log "download GloBI dump (about 1 GB; 5-30 min)"
    if ! curl -L --fail --retry 3 --retry-delay 10 -o "$TSV.part" "$GLOBI_URL"; then
        warn "primary URL failed; trying $GLOBI_URL_ALT"
        curl -L --fail --retry 3 --retry-delay 10 -o "$TSV.part" "$GLOBI_URL_ALT" \
            || { rm -f "$TSV.part"; die "GloBI download failed; set GLOBI_TSV to a local copy"; }
    fi
    gzip -t "$TSV.part" || { rm -f "$TSV.part"; die "the download is not a valid gzip file"; }
    mv "$TSV.part" "$TSV"
    log "have $(basename "$TSV") ($(du -h "$TSV" | cut -f1))"
}

step_prepare () {
    have "$WORK/globi_edges.csv" "$WORK/globi_child_parent.csv" && { log "have globi_edges.csv"; return 0; }
    have "$TSV" || die "no GloBI dump at $TSV; run: bash globi.sh download"
    step_log globi_prep py globi_prep.py --tsv "$TSV" --relations "$GLOBI_RELATIONS" \
        --edges-out "$WORK/globi_edges.csv" --taxonomy-out "$WORK/globi_child_parent.csv" \
        || die "globi_prep failed"
}

step_text () {
    have "$WORK/globi_tiers.csv" && { log "have globi_tiers.csv"; return 0; }
    have "$WORK/globi_edges.csv" || die "run: bash globi.sh prepare"
    need_network text
    step_log globi_tiers py gonogo_p1.py build --edges globi_edges.csv \
        --col-source source --col-target target --col-relation relation \
        --relations "$GLOBI_RELATIONS" --n "$GLOBI_N" --min-chars "$GLOBI_MIN_CHARS" \
        --names redirects --ancestors globi_child_parent.csv --ancestor-cols child,parent \
        --ancestor-depth 2 --contact "$CONTACT" --seed "$SEED" \
        --out-edges globi_tiers.csv --out-prompts globi_prompts.jsonl \
        || die "tier build failed"
}

step_check () {
    have "$WORK/globi_tiers.csv" || die "run: bash globi.sh text"
    mapfile -t A < <(abs_args)
    step_log globi_questions py abstain_probe.py "${A[@]}" --dry-run || die "dry run failed"
}

run_task () {      # run_task TASK MODEL
    local task="$1" model="$2" tag; tag="$(tag_of "$model")"
    local marker="$WORK/done/${task}_${tag}.ok"
    [[ -f "$marker" ]] && { log "have $task $tag"; return 0; }
    local th="${SLURM_CPUS_PER_TASK:-$CPUS}"
    mapfile -t A < <(abs_args)
    local extra=() out
    case "$task" in
        clean)        out="abstain_${tag}_clean.csv" ;;
        edit_family)  out="abstain_${tag}_edit_family.csv"; extra=(--edit to_family --conditions passage) ;;
        edit_remove)  out="abstain_${tag}_edit_remove.csv"; extra=(--edit remove --conditions passage) ;;
        *) die "unknown task $task" ;;
    esac
    log "task $task  model $model  threads $th"
    ( cd "$WORK" && py abstain_probe.py "${A[@]}" "${extra[@]}" --model "$model" \
        --threads "$th" --batch-size 4 --out "$out" ) > "$RES/${task}_${tag}.txt" 2>&1 \
        || { warn "$task $tag failed; see $RES/${task}_${tag}.txt"; return 1; }
    touch "$marker"
}

step_models () {
    have "$WORK/globi_tiers.csv" || die "run: bash globi.sh text"
    [[ "$SMOKE" == "1" ]] || { need_network models; fetch_models $GLOBI_MODELS; }
    if [[ "$MODE" == "local" ]]; then
        offline_models
        local m t
        for m in $GLOBI_MODELS; do for t in $GLOBI_TASKS; do run_task "$t" "$m"; done; done
        step_report
        return 0
    fi
    local ids=() m t tag id
    for m in $GLOBI_MODELS; do
        tag="$(tag_of "$m")"
        for t in $GLOBI_TASKS; do
            [[ -f "$WORK/done/${t}_${tag}.ok" ]] && { log "have $t $tag"; continue; }
            id=$(submit "globi_${t}_${tag}" "$TIME_GLOBI" "" "bash $ROOT/globi.sh --task $t $m") \
                || die "sbatch failed for $t $tag"
            log "submitted globi_${t}_${tag}: job $id"
            ids+=("$id")
        done
    done
    local dep; dep="$(IFS=:; echo "${ids[*]:-}")"
    id=$(submit "globi_report" "$TIME_ANALYSIS" "$dep" "bash $ROOT/globi.sh report") \
        || die "sbatch failed for the report job"
    log "submitted globi_report: job $id (runs after the model jobs)"
    log "watch with: squeue -u \$USER     results: $RES/GLOBI.md"
}

step_report () {
    local base=() efam=() erem=() pool=() csvs=() m tag f
    for m in $GLOBI_MODELS; do
        tag="$(tag_of "$m")"; pool+=("$tag")
        f="abstain_${tag}_clean.csv"
        if [[ -s "$WORK/$f" ]]; then
            base+=("$f"); csvs+=(--csv "$f")
            step_log "abstain_report_${tag}" py abstain_report.py --csv "$f"
        fi
        [[ -s "$WORK/abstain_${tag}_edit_family.csv" ]] && efam+=("abstain_${tag}_edit_family.csv")
        [[ -s "$WORK/abstain_${tag}_edit_remove.csv" ]] && erem+=("abstain_${tag}_edit_remove.csv")
    done
    [[ ${#base[@]} -eq 0 ]] && die "no model output yet in $WORK"
    [[ ${#csvs[@]} -ge 4 ]] && step_log abstain_report_pooled py abstain_report.py "${csvs[@]}" --pool
    step_log globi_extras py ns_extras.py --abstain "${base[@]}" \
        --edit-family "${efam[@]}" --edit-remove "${erem[@]}" --pool "${pool[@]}" \
        --out "$RES/EXTRAS_GLOBI.md" --json "$RES/extras_globi.json"
    {
        echo "# GloBI replication"
        echo
        echo "## Questions"
        sed -n '/questions (/,/all-sibling. is the share/p' "$RES/globi_questions.txt" 2>/dev/null | head -25
        echo
        echo "## Pooled abstention result (all-sibling questions)"
        echo '```'
        sed -n '/POOLED OVER/,$p' "$RES/abstain_report_pooled.txt" 2>/dev/null
        echo '```'
        echo
        cat "$RES/EXTRAS_GLOBI.md"
    } > "$RES/GLOBI.md"
    log "wrote $RES/GLOBI.md"
}

step_status () {
    local f
    for f in "$TSV" "$WORK/globi_edges.csv" "$WORK/globi_child_parent.csv" "$WORK/globi_tiers.csv"; do
        if have "$f"; then echo "  have     $(basename "$f")"; else echo "  missing  $(basename "$f")"; fi
    done
    local m t tag
    for m in $GLOBI_MODELS; do tag="$(tag_of "$m")"
        for t in $GLOBI_TASKS; do
            if [[ -f "$WORK/done/${t}_${tag}.ok" ]]; then echo "  done     $t $tag"; else echo "  pending  $t $tag"; fi
        done
    done
    have "$RES/GLOBI.md" && echo "  report   $RES/GLOBI.md"
}

if [[ ${#TASK[@]} -eq 2 ]]; then
    offline_models
    run_task "${TASK[0]}" "${TASK[1]}"
    exit $?
fi

case "$CMD" in
    download) step_download ;;
    prepare)  step_prepare ;;
    text)     step_text ;;
    check)    step_check ;;
    models)   step_models ;;
    report)   step_report ;;
    status)   step_status ;;
    all)      step_download && step_prepare && step_text && step_check && step_models ;;
    *) die "unknown command: $CMD (see bash globi.sh --help)" ;;
esac
