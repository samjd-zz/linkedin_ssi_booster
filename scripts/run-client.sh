#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/run-client.sh <client-or-env-file> [--local] [--profile core|full] -- <main.py args>

Examples:
  scripts/run-client.sh acme -- --curate --dry-run
  scripts/run-client.sh .env.client-beta -- --schedule --week 1 --channel linkedin --type post
  scripts/run-client.sh acme --profile full -- --rei-generate --rei-theme "spec driven development"
  scripts/run-client.sh acme --local -- --generate --dry-run
EOF
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

client_or_file="$1"
shift

MODE="docker"
PROFILE="core"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --local)
      MODE="local"
      shift
      ;;
    --profile)
      if [[ $# -lt 2 ]]; then
        echo "Error: --profile requires a value (core|full)." >&2
        exit 1
      fi
      PROFILE="$2"
      shift 2
      ;;
    --)
      shift
      break
      ;;
    *)
      break
      ;;
  esac
done

if [[ "$PROFILE" != "core" && "$PROFILE" != "full" ]]; then
  echo "Error: --profile must be 'core' or 'full'." >&2
  exit 1
fi

if [[ $# -eq 0 ]]; then
  echo "Error: missing main.py args. Pass them after '--'." >&2
  usage
  exit 1
fi

MAIN_ARGS=("$@")

resolve_env_file() {
  local input="$1"
  if [[ -f "$input" ]]; then
    echo "$input"
    return 0
  fi

  local candidate=".env.client-${input}"
  if [[ -f "$candidate" ]]; then
    echo "$candidate"
    return 0
  fi

  echo ""
  return 1
}

env_file="$(resolve_env_file "$client_or_file" || true)"
if [[ -z "$env_file" ]]; then
  echo "Error: env file not found for input: $client_or_file" >&2
  echo "Checked: $client_or_file and .env.client-$client_or_file" >&2
  exit 1
fi

python_bin=""
if [[ -x ".venv/bin/python" ]]; then
  python_bin=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  python_bin="python3"
else
  echo "Error: no Python interpreter found to parse dotenv files." >&2
  exit 1
fi

if ! "$python_bin" -c "import dotenv" >/dev/null 2>&1; then
  echo "Error: python-dotenv is required to parse env files safely." >&2
  echo "Install it in your environment, then retry." >&2
  exit 1
fi

eval "$($python_bin - <<'PY' "$env_file"
from dotenv import dotenv_values
import shlex
import sys

path = sys.argv[1]
for key, value in dotenv_values(path).items():
    if value is None:
        continue
    print(f"export {key}={shlex.quote(value)}")
PY
)"

echo "Client env: $env_file"
echo "Mode: $MODE"
echo "Profile: $PROFILE"
echo "IDEAS_CACHE_PATH: ${IDEAS_CACHE_PATH:-<unset>}"
echo "GENERATED_CONTENT_DIR: ${GENERATED_CONTENT_DIR:-<unset>}"

if [[ "$MODE" == "local" ]]; then
  if [[ ! -x ".venv/bin/python" ]]; then
    echo "Error: .venv/bin/python not found or not executable." >&2
    exit 1
  fi
  exec .venv/bin/python main.py "${MAIN_ARGS[@]}"
fi

exec docker compose --profile "$PROFILE" run --rm app python main.py "${MAIN_ARGS[@]}"