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

# 3. Launch Docker Compose with the profile you want
# You can pass arguments to this script, like './run.sh --profile full'
docker compose "$@"
