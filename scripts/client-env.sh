#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/client-env.sh <client-or-env-file> [-- <command> [args...]]

Examples:
  scripts/client-env.sh acme
  scripts/client-env.sh .env.client-acme
  scripts/client-env.sh acme -- env | grep IDEAS_CACHE_PATH
EOF
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

client_or_file="$1"
shift

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

masked_key=""
if [[ -n "${BUFFER_API_KEY:-}" ]]; then
  key_len=${#BUFFER_API_KEY}
  if [[ $key_len -le 8 ]]; then
    masked_key="********"
  else
    masked_key="${BUFFER_API_KEY:0:4}****${BUFFER_API_KEY: -4}"
  fi
fi

echo "Loaded env: $env_file"
echo "BUFFER_API_KEY: ${masked_key:-<empty>}"
echo "IDEAS_CACHE_PATH: ${IDEAS_CACHE_PATH:-<unset>}"
echo "GENERATED_CONTENT_DIR: ${GENERATED_CONTENT_DIR:-<unset>}"
echo "DATABASE_ENABLED: ${DATABASE_ENABLED:-<unset>}"

if [[ $# -gt 0 ]]; then
  if [[ "$1" == "--" ]]; then
    shift
  fi
  if [[ $# -gt 0 ]]; then
    exec "$@"
  fi
fi