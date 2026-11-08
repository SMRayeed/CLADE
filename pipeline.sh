# NeusymBridge pipeline: what each step runs. Sourced by run_all.sh.
#
# Paper: "CLADE: Category-Level Answering from Deficient Evidence in
# Retrieval-Augmented Language Models."

PKG_FILES=(pkg_ind_d2d.csv pkg_con_d2dis.csv pkg_off_d2dis.csv)
COLS=(--col-source x_name --col-target y_name --col-relation display_relation)

# --------------------------------------------------------------- download
step_download () {
    if [[ "$SMOKE" == "1" ]]; then
        log "smoke test: the fixture stands in for the downloads"
        return 0
    fi
    need_network download
    fetch_url "$PRIMEKG_URL" "$DATA/kg.csv"
    fetch_url "$MONDO_URL"   "$DATA/mondo.obo"
    {
        echo "# data files used by this run"
        echo "# downloaded $(date -u '+%Y-%m-%d %H:%M UTC')"
        for f in kg.csv mondo.obo; do
            printf '%s  %s\n' "$(sha256sum "$DATA/$f" | cut -c1-64)" "$f"
        done
        grep -m1 '^data-version' "$DATA/mondo.obo" | sed 's/^/mondo.obo /'
    } > "$RES/data_versions.txt"
    log "wrote $RES/data_versions.txt"
}

# --------------------------------------------------------------- prepare
step_prepare () {
    have "$DATA/kg.csv" "$DATA/mondo.obo" || die "data/ is missing kg.csv or mondo.obo; run: bash run_all.sh --from download"
    if ! have "$WORK/pkg_ind_d2d.csv" "$WORK/pkg_con_d2dis.csv" "$WORK/pkg_off_d2dis.csv" "$WORK/pkg_pc.csv"; then
        step_log prep_primekg py prep_primekg.py --kg "$DATA/kg.csv" --outdir "$WORK" || return 1
    fi
    if ! have "$WORK/mondo_child_parent.csv"; then
        step_log mondo_parents py mondo_parents.py --obo "$DATA/mondo.obo" \
            --primekg "$WORK/pkg_pc.csv" --out "$WORK/mondo_child_parent.csv" || return 1
    fi
}

# --------------------------------------------------------------- text
step_text () {
    need_network text
    reuse_caches
    check_pubmed_terms
    local web=(--contact "$CONTACT")
    local pmkey=()
    [[ -n "$NCBI_API_KEY" ]] && pmkey=(--api-key "$NCBI_API_KEY")

    # random sample, 600 edges per relation: the four-box table and the
    # family-only vs silent comparison
    if ! have "$WORK/p1_edges_d2.csv"; then
        step_log build_probe_sample py gonogo_p1.py build --edges "${PKG_FILES[@]}" "${COLS[@]}" \
            --names redirects --any-names --ancestors mondo_child_parent.csv \
            --ancestor-depth 2 --n "$PROBE_N" --seed "$SEED" "${web[@]}" \
            --out-edges p1_edges_d2.csv --out-prompts p1_prompts_d2.jsonl || return 1
    fi

    # drug-matched sample, measured in Wikipedia and PubMed: the question
    # set for the abstention and recovery tests
    if ! have "$WORK/matched_indication.csv" "$WORK/matched_contraindication.csv"; then
        step_log drug_matched_sample py drug_matched_sample.py \
            --edges pkg_ind_d2d.csv pkg_con_d2dis.csv --a indication --b contraindication \
            --min "$MATCH_MIN" --per-drug "$MATCH_PER_DRUG" --seed "$SEED" \
            --out-prefix matched || return 1
    fi
    if ! have "$WORK/matched_edges.csv"; then
        step_log build_matched py gonogo_p1.py build \
            --edges matched_indication.csv matched_contraindication.csv "${COLS[@]}" \
            --names redirects --any-names --ancestors mondo_child_parent.csv \
            --ancestor-depth 2 --n 2000 --seed "$SEED" "${web[@]}" \
            --out-edges matched_edges.csv --out-prompts matched_prompts.jsonl || return 1
    fi
    if ! have "$WORK/matched_edges_pm.csv"; then
        step_log second_corpus_single py second_corpus.py --scored matched_edges.csv \
            --corpus pubmed --names-cache gbif_cache --ancestors mondo_child_parent.csv \
            --ancestor-depth 2 --retmax 40 "${web[@]}" "${pmkey[@]}" \
            --out matched_edges_pm.csv || return 1
    fi
    if ! have "$WORK/matched_edges_pm_balanced.csv"; then
        step_log second_corpus_balanced py second_corpus.py --scored matched_edges.csv \
            --corpus pubmed --names-cache gbif_cache --ancestors mondo_child_parent.csv \
            --ancestor-depth 2 --retmax 40 --extra-terms "$PUBMED_TERMS" \
            "${web[@]}" "${pmkey[@]}" --out matched_edges_pm_balanced.csv || return 1
    fi
    if ! have "$WORK/me_bal_union.csv"; then
        ( cd "$WORK" && py retier.py --in matched_edges_pm_balanced.csv \
            --use tier_union --out me_bal_union.csv ) || return 1
    fi

    # evidence from the candidates' end: candidate disease articles and
    # PubMed pair and popularity counts, for both ways of building the list
    local mode netflags=(--fetch --pubmed)
    [[ "$SMOKE" == "1" ]] && netflags=()
    for mode in wiki all; do
        have "$WORK/done/candidate_fetch_$mode.ok" && continue
        step_log "candidate_fetch_$mode" py candidate_check.py --scored me_bal_union.csv \
            --edges "${PKG_FILES[@]}" "${COLS[@]}" --ancestors mondo_child_parent.csv \
            --wiki-cache wiki_cache --extra-text pubmed_cache --names-cache gbif_cache \
            --cand-cache candidate_wiki_cache --pubmed-cache pubmed_pairs.jsonl \
            --expand-depth "$EXPAND_DEPTH" --max-candidates "$MAX_CANDIDATES" \
            --max-set "$MAX_CANDIDATES" --page-text "$mode" --popularity \
            "${netflags[@]}" "${web[@]}" "${pmkey[@]}" \
            --out "candidate_prefetch_$mode.csv" || return 1
        touch "$WORK/done/candidate_fetch_$mode.ok"
    done

    if [[ "$SMOKE" != "1" ]]; then
        # shellcheck disable=SC2086
        fetch_models $(printf '%s\n' $PROBE_MODELS $ABSTAIN_MODELS $RECOVER_MODEL | sort -u)
    fi
}

# --------------------------------------------------------------- extend
# Login node. Downloads the models added for the 7-page version.
step_extend () {
    if [[ "$SMOKE" == "1" ]]; then
        log "smoke test: nothing to download"
        return 0
    fi
    need_network extend
    # shellcheck disable=SC2086
    fetch_models $(printf '%s\n' $EXTRA_ABSTAIN_MODELS $INSTRUCT_MODELS | awk 'NF && !seen[$0]++')
}

# --------------------------------------------------------------- models
is_gpu () { [[ " $GPU_MODELS " == *" $1 "* ]]; }
is_xl ()  { [[ "$1" == *14B* || "$1" == *32B* || "$1" == *70B* || "$1" == *72B* ]]; }
time_for () {
    if is_gpu "$1"; then echo "$TIME_GPU"
    elif is_small "$1"; then echo "$TIME_SMALL"
    elif is_xl "$1"; then echo "$TIME_XL"
    else echo "$TIME_LARGE"; fi
}

# submit to a GPU node, with the GPU environment and bfloat16 weights
submit_gpu () {
    local name="$1" time="$2"; shift 2
    sbatch --parsable --account="$ACCOUNT" --partition="$GPU_PARTITION" \
        --gpus-per-node=1 --cpus-per-task=8 --mem=64G --time="$time" \
        --job-name="$name" --output="$LOGS/%x_%j.out" --chdir="$ROOT" \
        --wrap="ENV_DIR=$GPU_ENV_DIR TORCH_INDEX=$GPU_TORCH_INDEX USE_GPU=1 $*"
}

all_abstain_models () { printf '%s\n' $ABSTAIN_MODELS $EXTRA_ABSTAIN_MODELS | awk 'NF && !seen[$0]++'; }

model_jobs () {
    local m
    for m in $PROBE_MODELS; do
        echo "probe $m $(time_for "$m")"
    done
    for m in $(all_abstain_models); do
        echo "abstain $m $(time_for "$m")"
    done
    for m in $INSTRUCT_MODELS; do
        echo "abstain_instruct $m $(time_for "$m")"
    done
    for m in $EDIT_MODELS; do
        echo "abstain_edit_family $m $(time_for "$m")"
        echo "abstain_edit_remove $m $(time_for "$m")"
    done
    echo "recover $RECOVER_MODEL $(time_for "$RECOVER_MODEL")"
}

run_model_task () {
    local task="$1" model="$2" tag
    tag="$(tag_of "$model")"
    local marker="$WORK/done/${task}_${tag}.ok"
    if [[ -f "$marker" ]]; then log "have $task $tag"; return 0; fi
    local th="${SLURM_CPUS_PER_TASK:-$CPUS}"
    local gflags=()
    [[ "${USE_GPU:-0}" == "1" ]] && gflags=(--gpu --dtype bfloat16)
    log "task $task  model $model  threads $th ${gflags[*]}"
    case "$task" in
        probe)
            ( cd "$WORK" && py run_probe_cpu.py --edges p1_edges_d2.csv \
                --out "p1_edges_d2_${tag}.csv" --model "$model" \
                --threads "$th" --batch-size 8 "${gflags[@]}" ) || return 1 ;;
        abstain)
            ( cd "$WORK" && py abstain_probe.py --scored me_bal_union.csv \
                --wiki-cache wiki_cache --extra-text pubmed_cache \
                --ancestors mondo_child_parent.csv --names-cache gbif_cache \
                --per-band "$PER_BAND" --options 5 --distractors sibling \
                --model "$model" --threads "$th" --batch-size 4 \
                --seed "$SEED" --out "abstain_${tag}_clean.csv" "${gflags[@]}" ) || return 1 ;;
        abstain_instruct)
            ( cd "$WORK" && py abstain_probe.py --scored me_bal_union.csv \
                --wiki-cache wiki_cache --extra-text pubmed_cache \
                --ancestors mondo_child_parent.csv --names-cache gbif_cache \
                --per-band "$PER_BAND" --options 5 --distractors sibling \
                --model "$model" --threads "$th" --batch-size 4 \
                --seed "$SEED" --instruct --conditions passage \
                --out "abstain_${tag}_instruct.csv" "${gflags[@]}" ) || return 1 ;;
        abstain_edit_family|abstain_edit_remove)
            local ed="to_family" suf="edit_family"
            [[ "$task" == "abstain_edit_remove" ]] && { ed="remove"; suf="edit_remove"; }
            ( cd "$WORK" && py abstain_probe.py --scored me_bal_union.csv \
                --wiki-cache wiki_cache --extra-text pubmed_cache \
                --ancestors mondo_child_parent.csv --names-cache gbif_cache \
                --per-band "$PER_BAND" --options 5 --distractors sibling \
                --model "$model" --threads "$th" --batch-size 4 \
                --seed "$SEED" --edit "$ed" --conditions passage \
                --out "abstain_${tag}_${suf}.csv" "${gflags[@]}" ) || return 1 ;;
        recover)
            ( cd "$WORK" && py recover.py --scored me_bal_union.csv \
                --wiki-cache wiki_cache --extra-text pubmed_cache \
                --ancestors mondo_child_parent.csv --names-cache gbif_cache \
                --expand-depth "$EXPAND_DEPTH" --max-candidates "$MAX_CANDIDATES" \
                --model "$model" --threads "$th" --batch-size 8 \
                --seed "$SEED" --out "recover_${tag}_clean.csv" ) || return 1 ;;
        *) die "unknown task $task" ;;
    esac
    touch "$marker"
}

step_models () {
    have "$WORK/p1_edges_d2.csv" "$WORK/me_bal_union.csv" \
        || die "the text step has not finished; run: bash run_all.sh --from text"
    local ids=() task model time tag
    while read -r task model time; do
        tag="$(tag_of "$model")"
        [[ -f "$WORK/done/${task}_${tag}.ok" ]] && { log "have $task $tag"; continue; }
        if [[ "$MODE" == "slurm" ]]; then
            local jid
            if is_gpu "$model"; then
                jid=$(submit_gpu "ns_${task}_${tag}" "$time" \
                      "bash $ROOT/run_all.sh --task $task $model") || die "sbatch failed"
            else
                jid=$(submit "ns_${task}_${tag}" "$time" "" \
                      "bash $ROOT/run_all.sh --task $task $model") || die "sbatch failed"
            fi
            log "submitted $task $tag  job $jid  ($time)"
            ids+=("$jid")
        else
            offline_models
            run_model_task "$task" "$model" || return 1
        fi
    done < <(model_jobs)

    if [[ "$MODE" == "slurm" && ${#ids[@]} -gt 0 ]]; then
        local dep jid
        dep="$(IFS=:; echo "${ids[*]}")"
        jid=$(submit "ns_analysis" "$TIME_ANALYSIS" "$dep" \
              "bash $ROOT/run_all.sh --local --only analysis") || die "sbatch failed"
        log "submitted analysis job $jid, starts after ${ids[*]}"
        SUBMITTED=1
    fi
}

# --------------------------------------------------------------- analysis
step_analysis () {
    local small large rec
    small="$(tag_of "$SMALL_MODEL")"; large="$(tag_of "$LARGE_MODEL")"
    rec="$(tag_of "$RECOVER_MODEL")"

    # Step one: how much of the graph text reaches (four boxes, 0.5B)
    local t
    for t in "$small" "$large"; do
        [[ -s "$WORK/p1_edges_d2_${t}.csv" ]] || { warn "no probe output for $t"; continue; }
        step_log "four_boxes_${t}" py four_boxes.py --scored "p1_edges_d2_${t}.csv" \
            --csv "$RES/four_boxes_${t}.csv"
        step_log "four_boxes_cut3_${t}" py four_boxes.py --scored "p1_edges_d2_${t}.csv" \
            --text-cut 3 --csv "$RES/four_boxes_cut3_${t}.csv"
        # family-only vs silent vs named, within relation
        step_log "tier_cliff_${t}" py tier_cliff.py --scored "p1_edges_d2_${t}.csv" \
            --csv "$RES/tier_cliff_${t}.csv"
    done

    # Step two: abstention, per model and pooled over the 7-8B models
    local csvs=() m f
    for m in $(all_abstain_models); do
        f="abstain_$(tag_of "$m")_clean.csv"
        if [[ -s "$WORK/$f" ]]; then
            step_log "abstain_report_$(tag_of "$m")" py abstain_report.py --csv "$f"
        fi
    done
    for m in $POOL_MODELS; do
        f="abstain_$(tag_of "$m")_clean.csv"
        [[ -s "$WORK/$f" ]] && csvs+=(--csv "$f")
    done
    if [[ ${#csvs[@]} -gt 0 ]]; then
        step_log abstain_report_pooled py abstain_report.py "${csvs[@]}" --pool
    fi

    # Step three: recovery through the ontology
    local recargs=()
    [[ -s "$WORK/recover_${rec}_clean.csv" ]] && recargs=(--recover-csv "recover_${rec}_clean.csv")
    for t in wiki all; do
        step_log "candidate_check_$t" py candidate_check.py --scored me_bal_union.csv \
            --edges "${PKG_FILES[@]}" "${COLS[@]}" --ancestors mondo_child_parent.csv \
            --wiki-cache wiki_cache --extra-text pubmed_cache --names-cache gbif_cache \
            --cand-cache candidate_wiki_cache --pubmed-cache pubmed_pairs.jsonl \
            --expand-depth "$EXPAND_DEPTH" --max-candidates "$MAX_CANDIDATES" \
            --max-set "$MAX_CANDIDATES" --page-text "$t" --popularity "${recargs[@]}" \
            --out "$RES/candidate_check_$t.csv"
    done
    step_log fanout py fanout.py --ancestors mondo_child_parent.csv \
        --scored me_bal_union.csv --wiki-cache wiki_cache --csv "$RES/fanout.csv"

    # confidence, family size, prompting baseline
    local base=() inst=() pool=()
    for m in $(all_abstain_models); do
        f="abstain_$(tag_of "$m")_clean.csv"; [[ -s "$WORK/$f" ]] && base+=("$f")
    done
    for m in $INSTRUCT_MODELS; do
        f="abstain_$(tag_of "$m")_instruct.csv"; [[ -s "$WORK/$f" ]] && inst+=("$f")
    done
    for m in $POOL_MODELS; do pool+=("$(tag_of "$m")"); done
    local efam=() erem=()
    for m in $EDIT_MODELS; do
        f="abstain_$(tag_of "$m")_edit_family.csv"; [[ -s "$WORK/$f" ]] && efam+=("$f")
        f="abstain_$(tag_of "$m")_edit_remove.csv"; [[ -s "$WORK/$f" ]] && erem+=("$f")
    done
    step_log ns_extras py ns_extras.py --abstain "${base[@]}" --instruct "${inst[@]}" \
        --edit-family "${efam[@]}" --edit-remove "${erem[@]}" \
        --pool "${pool[@]}" --recover "recover_${rec}_clean.csv" \
        --out "$RES/EXTRAS.md" --json "$RES/extras.json"

    step_log summary py ns_summary.py --work "$WORK" --small-tag "$small" \
        --large-tag "$large" --out "$RES/SUMMARY.md"

    mkdir -p "$RES/csv"
    for f in p1_edges_d2.csv "p1_edges_d2_${small}.csv" "p1_edges_d2_${large}.csv" \
             me_bal_union.csv mondo_child_parent.csv "recover_${rec}_clean.csv"; do
        [[ -s "$WORK/$f" ]] && cp "$WORK/$f" "$RES/csv/"
    done
    for f in "${base[@]}" "${inst[@]}" "${efam[@]}" "${erem[@]}"; do
        [[ -s "$WORK/$f" ]] && cp "$WORK/$f" "$RES/csv/"
    done

    ( cd "$ROOT/paper" && "$PY" build_figures.py ) > "$RES/figures.txt" 2>&1 \
        || warn "figures not rebuilt (matplotlib missing?); see $RES/figures.txt"
    return 0
}

# --------------------------------------------------------------- status
status_report () {
    local f
    echo "work dir: $WORK"
    for f in "$DATA/kg.csv" "$DATA/mondo.obo" "$WORK/pkg_ind_d2d.csv" \
             "$WORK/mondo_child_parent.csv" "$WORK/p1_edges_d2.csv" \
             "$WORK/matched_edges.csv" "$WORK/matched_edges_pm.csv" \
             "$WORK/matched_edges_pm_balanced.csv" "$WORK/me_bal_union.csv" \
             "$WORK/done/candidate_fetch_wiki.ok" "$WORK/done/candidate_fetch_all.ok" \
             "$RES/EXTRAS.md" "$RES/SUMMARY.md"; do
        if [[ -e "$f" ]]; then echo "  have     ${f#$BASE/}"; else echo "  missing  ${f#$BASE/}"; fi
    done
    echo "model tasks:"
    local task model time
    while read -r task model time; do
        if [[ -f "$WORK/done/${task}_$(tag_of "$model").ok" ]]; then
            echo "  done     $task $(tag_of "$model")"
        else
            echo "  pending  $task $(tag_of "$model")"
        fi
    done < <(model_jobs)
}

# --------------------------------------------------------------- smoke test
smoke_setup () {
    if ! have "$DATA/kg.csv"; then
        log "building the synthetic fixture"
        "$PY" "$ROOT/tests/make_fixture.py" --data "$DATA" --work "$WORK" \
            --terms "$PUBMED_TERMS" || die "fixture build failed"
    fi
    if [[ ! -d "$BASE/tiny_model_a" ]]; then
        log "building two tiny random models"
        "$PY" "$ROOT/tests/tiny_model.py" --text "$WORK/wiki_cache" --out "$BASE/tiny_model_a" --seed 1 \
            || die "tiny model build failed"
        "$PY" "$ROOT/tests/tiny_model.py" --text "$WORK/wiki_cache" --out "$BASE/tiny_model_b" --seed 2 \
            || die "tiny model build failed"
    fi
    SMALL_MODEL="$BASE/tiny_model_a"; LARGE_MODEL="$BASE/tiny_model_b"
    PROBE_MODELS="$SMALL_MODEL $LARGE_MODEL"
    ABSTAIN_MODELS="$SMALL_MODEL $LARGE_MODEL"
    POOL_MODELS="$LARGE_MODEL"
    RECOVER_MODEL="$LARGE_MODEL"
    PER_BAND=10; PROBE_N=60
    EXTRA_ABSTAIN_MODELS=""; INSTRUCT_MODELS="$LARGE_MODEL"; EDIT_MODELS="$LARGE_MODEL"; GPU_MODELS=""
    CPUS=2
}
