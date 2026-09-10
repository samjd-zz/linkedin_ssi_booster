#!/bin/bash

# 1. Dynamically grab the current user's ID
export USER_UID=$(id -u)
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$USER_UID}
export PULSE_RUNTIME_DIR=${PULSE_RUNTIME_DIR:-$XDG_RUNTIME_DIR/pulse}
export DISPLAY=${DISPLAY:-:0}
export XAUTHORITY=${XAUTHORITY:-$HOME/.Xauthority}

# 2. Check if the PulseAudio socket exists (Astro3 check)
if [ ! -S "$PULSE_RUNTIME_DIR/native" ]; then
    echo "⚠️ Warning: PulseAudio socket not found at $PULSE_RUNTIME_DIR/native"
    echo "Audio might not work in the container."
fi

# 3. Auto-detect a usable NVIDIA GPU + container runtime and layer in GPU reservations
COMPOSE_FILES=(-f docker-compose.yml)
if command -v nvidia-smi >/dev/null 2>&1 && docker info 2>/dev/null | grep -qi nvidia; then
    if docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi >/dev/null 2>&1; then
        echo "🎮 NVIDIA GPU detected — enabling GPU passthrough."
        COMPOSE_FILES+=(-f docker-compose.gpu.yml)
    else
        echo "⚠️  nvidia-smi/runtime found but GPU passthrough test failed — falling back to CPU-only."
    fi
else
    echo "ℹ️  No NVIDIA GPU/runtime detected — running CPU-only."
fi

# 4. Launch Docker Compose with the profile you want
# You can pass arguments to this script, like './run.sh --profile full'
docker compose "${COMPOSE_FILES[@]}" "$@"
