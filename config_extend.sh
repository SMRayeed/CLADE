# Settings for the experiments added in November 2026. Sourced by
# run_all.sh right after config.sh, so config.sh stays as you edited it.
# Every value can also be set in the environment; set a model list to ""
# to skip it (e.g. INSTRUCT_MODELS="" bash run_all.sh --only models).

# ---------------------------------------------------------------- extensions
# Added for the 7-page version. `bash run_all.sh --only extend` downloads the
# new models; `--only models` then submits only the jobs not yet done.

# A larger model on the abstention questions (reported per model, not pooled).
EXTRA_ABSTAIN_MODELS="${EXTRA_ABSTAIN_MODELS-Qwen/Qwen2.5-14B-Instruct}"
# Prompting baseline: the pooled 7-8B models with one added instruction.
INSTRUCT_MODELS="${INSTRUCT_MODELS-$POOL_MODELS}"
# Counterfactual page edit on the named questions (family name vs removed).
EDIT_MODELS="${EDIT_MODELS-$POOL_MODELS}"
TIME_XL="${TIME_XL:-12:00:00}"           # 14B-class jobs on CPU; resubmit to resume

# Optional GPU. Models listed here run on a GPU node in bfloat16 instead of
# on CPU in float32, e.g. GPU_MODELS="Qwen/Qwen2.5-14B-Instruct".
GPU_MODELS="${GPU_MODELS:-}"
GPU_PARTITION="${GPU_PARTITION:-gpu}"
GPU_ENV_DIR="${GPU_ENV_DIR:-$HOME/gpu_probe_env}"
GPU_TORCH_INDEX="${GPU_TORCH_INDEX:-https://download.pytorch.org/whl/cu121}"
TIME_GPU="${TIME_GPU:-08:00:00}"
