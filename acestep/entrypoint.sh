#!/usr/bin/env bash
set -e

log() { echo "[acestep] $1"; }

PORT="${PORT:-8001}"
MODEL="${ACESTEP_CONFIG_PATH:-acestep-v15-turbo}"

log "Starting ACE-Step 1.5 REST API server on port ${PORT}..."
log "Model: ${MODEL}"

cd /app/acestep

build_model_args() {
    local help_text="$1"
    local -a args=()

    if [[ "$help_text" == *"--config_path"* ]]; then
        args+=(--config_path "${MODEL}")
    elif [[ "$help_text" == *"--config-path"* ]]; then
        args+=(--config-path "${MODEL}")
    else
        log "No config-path flag detected in ACE-Step CLI; using default model selection."
    fi

    if [[ -n "${ACESTEP_LM_MODEL_PATH:-}" ]]; then
        if [[ "$help_text" == *"--lm-model-path"* ]]; then
            args+=(--lm-model-path "${ACESTEP_LM_MODEL_PATH}")
        elif [[ "$help_text" == *"--lm_model_path"* ]]; then
            args+=(--lm_model_path "${ACESTEP_LM_MODEL_PATH}")
        fi
    fi

    printf '%s\n' "${args[@]}"
}

# ACE-Step 1.5 provides a `acestep-api` entry point via pyproject.toml scripts
# Falls back to explicit Python invocation if the entry point is not available
if command -v acestep-api &>/dev/null; then
    mapfile -t MODEL_ARGS < <(build_model_args "$(acestep-api --help 2>&1)")
    exec acestep-api \
        --port "${PORT}" \
        --host "0.0.0.0" \
        "${MODEL_ARGS[@]}"
else
    mapfile -t MODEL_ARGS < <(build_model_args "$(python -m acestep.api --help 2>&1)")
    exec python -m acestep.api \
        --port "${PORT}" \
        --host "0.0.0.0" \
        "${MODEL_ARGS[@]}" 2>/dev/null \
    || exec uvicorn acestep.api:app \
        --port "${PORT}" \
        --host "0.0.0.0"
fi
