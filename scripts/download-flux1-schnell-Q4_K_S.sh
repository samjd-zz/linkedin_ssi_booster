#!/bin/bash

set -euo pipefail

# Define path mapping
MODEL_DIR="/app/models/flux"
mkdir -p "$MODEL_DIR"

echo "-------------------------------------------------------"
echo "🚀 Initializing Unified FLUX GGUF Engine Stack"
echo "📂 Target Directory: $MODEL_DIR"
echo "-------------------------------------------------------"

download_file() {
    local url=$1
    local output=$2
    local label=$3

    if [ -f "$output" ]; then
        echo "✅ $label already exists. Skipping."
    else
        echo "📥 Downloading $label..."
        mkdir -p "$(dirname "$output")"
        # Pure LFS / direct endpoint download
        curl -f -L "$url" -o "$output"
        if [ $? -ne 0 ]; then
            echo "❌ Failed to download $label."
            return 1
        fi
    fi
    return 0
}

# 1. The Quantized Brain (Already working!)
download_file "https://huggingface.co/city96/FLUX.1-schnell-gguf/resolve/main/flux1-schnell-Q4_K_S.gguf" \
              "$MODEL_DIR/flux1-schnell-Q4_K_S.gguf" "Flux Transformer (Q4_K_S GGUF)"

# 2. VAE (Pulled from second-state's un-gated public mirror)
download_file "https://huggingface.co/second-state/FLUX.1-schnell-GGUF/resolve/main/ae.safetensors" \
              "$MODEL_DIR/ae.safetensors" "VAE"

# 3. CLIP Encoder (Pulled from comfyanonymous's wide-open text encoder hub)
download_file "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors" \
              "$MODEL_DIR/clip_l.safetensors" "CLIP Text Encoder"

# 4. T5 Encoder (Matches your python filename expectation exactly)
download_file "https://huggingface.co/city96/t5-v1_1-xxl-encoder-gguf/resolve/main/t5-v1_1-xxl-encoder-Q4_K_M.gguf" \
              "$MODEL_DIR/t5-v1_1-xxl-encoder-Q4_K_M.gguf" "T5 Text Encoder"

echo "-------------------------------------------------------"
echo "✅ Initialization Completed Successfully."
echo "-------------------------------------------------------"