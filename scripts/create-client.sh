#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/create-client.sh <client-name> [--from <template-env-file>] [--force]

Description:
  Creates a client env file and isolated folders for multi-client operation.

Defaults:
  - Template: .env.example
  - Output env: .env.client-<client-name>
  - Data dir: data/client-<client-name>
  - Content dir: yt-vid-data/client-<client-name>

Examples:
  scripts/create-client.sh acme
  scripts/create-client.sh "Acme Corp"
  scripts/create-client.sh beta --from .env --force
EOF
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

if [[ "$1" == "-h" || "$1" == "--help" ]]; then
  usage
  exit 0
fi

client_name="$1"
shift

template_file=".env.example"
force=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from)
      [[ $# -ge 2 ]] || { echo "Error: --from requires a file path." >&2; exit 1; }
      template_file="$2"
      shift 2
      ;;
    --force)
      force=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Error: unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ ! -f "$template_file" ]]; then
  echo "Error: template env file not found: $template_file" >&2
  exit 1
fi

slug="$(printf '%s' "$client_name" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//')"
if [[ -z "$slug" ]]; then
  echo "Error: client name produced an empty slug." >&2
  exit 1
fi

env_file=".env.client-${slug}"
data_dir="data/client-${slug}"
content_dir="yt-vid-data/client-${slug}"

if [[ -f "$env_file" && "$force" != true ]]; then
  echo "Error: ${env_file} already exists. Use --force to overwrite." >&2
  exit 1
fi

mkdir -p "$data_dir" "$content_dir"
cp "$template_file" "$env_file"

append_or_replace() {
  local key="$1"
  local value="$2"

  if grep -Eq "^${key}=" "$env_file"; then
    sed -i -E "s|^${key}=.*$|${key}=${value}|" "$env_file"
  elif grep -Eq "^#\s*${key}=" "$env_file"; then
    sed -i -E "s|^#\s*${key}=.*$|${key}=${value}|" "$env_file"
  else
    printf '%s=%s\n' "$key" "$value" >> "$env_file"
  fi
}

append_or_replace "IDEAS_CACHE_PATH" "${data_dir}/published_ideas_cache.json"
append_or_replace "GENERATED_CONTENT_DIR" "${content_dir}"
append_or_replace "POSTGRES_DB" "linkedin_ssi_booster_${slug}"
append_or_replace "DATABASE_URL" "postgresql://ssi_booster:change_this_to_a_secure_password@postgres:5432/linkedin_ssi_booster_${slug}"

cat <<EOF
Created client scaffold:
- Env file: ${env_file}
- Data dir: ${data_dir}
- Generated content dir: ${content_dir}

Next steps:
1) Edit ${env_file} and set client-specific secrets (BUFFER_API_KEY, channel IDs, etc.)
2) Run a safe preview:
   scripts/run-client-curate.sh ${slug}
3) When ready to publish:
   scripts/run-client-curate.sh ${slug} --live --type post --reconcile
EOF
