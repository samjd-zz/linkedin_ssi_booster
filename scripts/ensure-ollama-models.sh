#!/bin/sh
set -eu

for model in "${OLLAMA_MODEL:-llama3.2}" "${OLLAMA_MODEL_FALLBACK:-}"; do
    [ -n "$model" ] || continue
    if ollama show "$model" >/dev/null 2>&1; then
        echo "[ollama-init] Using cached model: $model"
    else
        echo "[ollama-init] Model unavailable locally; pulling: $model"
        ollama pull "$model"
    fi
done
echo "[ollama-init] Done."
