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

# 3. Auto-detect a usable GPU (NVIDIA or Intel) and layer in the appropriate Compose override
COMPOSE_FILES=(-f docker-compose.yml)
if command -v nvidia-smi >/dev/null 2>&1 && docker info 2>/dev/null | grep -qi nvidia; then
    if docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi >/dev/null 2>&1; then
        echo "🎮 NVIDIA GPU detected — enabling NVIDIA GPU passthrough."
        COMPOSE_FILES+=(-f docker-compose.gpu.yml)
    else
        echo "⚠️  nvidia-smi/runtime found but GPU passthrough test failed — falling back to CPU-only."
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

# 4. Rebuild one-off app runs so they never execute stale source copied into an old image.
COMPOSE_ARGS=("$@")
for ((i = 0; i < ${#COMPOSE_ARGS[@]}; i++)); do
    if [[ "${COMPOSE_ARGS[$i]}" != "run" ]]; then
        continue
    fi

    has_build=false
    service=""
    for ((j = i + 1; j < ${#COMPOSE_ARGS[@]}; j++)); do
        case "${COMPOSE_ARGS[$j]}" in
            --build)
                has_build=true
                ;;
            --*)
                ;;
            *)
                service="${COMPOSE_ARGS[$j]}"
                break
                ;;
        esac
    done

    if [[ "$service" == "app" && "$has_build" == "false" ]]; then
        COMPOSE_ARGS=(
            "${COMPOSE_ARGS[@]:0:$((i + 1))}"
            --build
            "${COMPOSE_ARGS[@]:$((i + 1))}"
        )
    fi
    break
done

# 5. Launch Docker Compose with the selected profile and GPU override.
docker compose "${COMPOSE_FILES[@]}" "${COMPOSE_ARGS[@]}"
