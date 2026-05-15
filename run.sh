#!/bin/bash

# 1. Dynamically grab the current user's ID
export USER_UID=$(id -u)

# 2. Check if the PulseAudio socket exists (Astro3 check)
if [ ! -S "/run/user/$USER_UID/pulse/native" ]; then
    echo "⚠️ Warning: PulseAudio socket not found at /run/user/$USER_UID/pulse/native"
    echo "Audio might not work in the container."
fi

# 3. Launch Docker Compose with the profile you want
# You can pass arguments to this script, like './run.sh --profile full'
docker compose up "$@"