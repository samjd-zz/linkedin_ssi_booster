#!/bin/bash

# 1. Dynamically grab the current user's ID
export USER_UID=$(id -u)
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$USER_UID}
export PULSE_RUNTIME_DIR=${PULSE_RUNTIME_DIR:-$XDG_RUNTIME_DIR/pulse}
export DISPLAY=${DISPLAY:-:0}
export XAUTHORITY=${XAUTHORITY:-$HOME/.Xauthority}

# 2. Pick the host PulseAudio socket. WSLg's /mnt/wslg/PulseServer accepts
# anonymous clients; its runtime-dir socket rejects container cookies.
if [ -z "${PULSE_SOCKET:-}" ]; then
    if [ -S /mnt/wslg/PulseServer ]; then
        PULSE_SOCKET=/mnt/wslg/PulseServer
    else
        PULSE_SOCKET=$PULSE_RUNTIME_DIR/native
    fi
fi
export PULSE_SOCKET
if [ ! -S "$PULSE_SOCKET" ]; then
    echo "⚠️ Warning: PulseAudio socket not found at $PULSE_SOCKET"
    echo "Audio might not work in the container."
fi

# 3. Auto-detect a usable GPU (NVIDIA or Intel) and layer in the appropriate Compose override
COMPOSE_FILES=(-f docker-compose.yml)
if command -v nvidia-smi >/dev/null 2>&1 && docker info 2>/dev/null | grep -qi nvidia; then
    if docker run --pull=never --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi >/dev/null 2>&1; then
        echo "🎮 NVIDIA GPU detected — enabling NVIDIA GPU passthrough."
        COMPOSE_FILES+=(-f docker-compose.gpu.yml)
    else
        echo "⚠️  GPU probe image missing or passthrough test failed — falling back to CPU-only. Cache nvidia/cuda:12.4.1-base-ubuntu22.04 to enable the offline probe."
    fi
elif [ -d "/dev/dri" ] || [ -e "/dev/dxg" ] || [ "${INTEL_GPU:-false}" = "true" ]; then
    # Intel Iris Xe / Arc / Core Ultra iGPU on native Linux or Windows WSL 2.
    if [ -d "/dev/dri" ]; then
        echo "⚡ Intel GPU detected (/dev/dri) — enabling Intel GPU acceleration for Ollama."
        COMPOSE_FILES+=(-f docker-compose.intel.yml)
    elif [ -e "/dev/dxg" ]; then
        echo "⚡ Windows WSL 2 GPU detected (/dev/dxg) — enabling Intel GPU acceleration for Ollama."
        COMPOSE_FILES+=(-f docker-compose.intel-wsl.yml)
    fi
else
    echo "ℹ️  No NVIDIA or Intel GPU detected — running CPU-only."
fi

# 4. Reuse local images by default; pass Compose's run/up --build to rebuild.
docker compose "${COMPOSE_FILES[@]}" "$@"
