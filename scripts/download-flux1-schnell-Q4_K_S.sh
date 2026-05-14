#!/bin/bash

# this script will download the FLUX.1-schnell GGUF model from CivitAI and the 
# associated VAE and text encoders, saving them to ~/models/flux/
# direct link (requires login): 
# https://civitai.com/models/648580/flux1-schnell-gguf-q2k-q3ks-q4q41q4ks-q5q51-q5ks-q6k-q8?modelVersionId=746301

# Load variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
else
    echo "❌ Error: .env file not found. Please create one based on .env.example"
    exit 1
fi

if [ -z "$CIVITAI_API_KEY" ]; then
    echo "⚠️ Warning: CIVITAI_API_KEY is not set. Image generation will fail."
    echo "Please add your key to .env and restart to enable FLUX."
    exit 0 # Exit 0 so service_started doesn't hang the rest of the stack
fi

# Define path
MODEL_DIR="/app/models/flux"
mkdir -p "$MODEL_DIR"

echo "-------------------------------------------------------"
echo "🚀 SSI Booster: Initializing FLUX Intelligence Stack"
echo "📂 Models will be saved to: $MODEL_DIR"
echo "-------------------------------------------------------"

download_file() {
    local url=$1
    local output=$2
    local label=$3

    if [ -f "$output" ]; then
        echo "✅ $label already exists. Skipping."
    else
        echo "📥 Downloading $label..."
        # -f fails on 401/404, -L follows redirects, -C - resumes
        curl -f -C - -L -H "Authorization: Bearer $CIVITAI_API_KEY" "$url" -o "$output"
        if [ $? -ne 0 ]; then
            echo "❌ Failed to download $label. Check your API key and connection."
        fi
    fi
}

# 1. The Brain (Transformer)
download_file "https://civitai.com/api/download/models/746301" \
              "$MODEL_DIR/flux1-schnell-Q4_K_S.gguf" "Flux Brain (GGUF)"

# 2. VAE
download_file "https://huggingface.co/second-state/FLUX.1-dev-GGUF/resolve/main/ae.safetensors" \
              "$MODEL_DIR/ae.safetensors" "VAE"

# 3. CLIP Encoder
download_file "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors" \
              "$MODEL_DIR/clip_l.safetensors" "CLIP Encoder"

# 4. T5 Encoder
download_file "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_q4_k_m.gguf" \
              "$MODEL_DIR/t5xxl_q4_k_m.gguf" "T5 Encoder"

echo "-------------------------------------------------------"
echo "✅ Setup Complete. Your RTX 3060 is ready for FLUX."
echo "-------------------------------------------------------"