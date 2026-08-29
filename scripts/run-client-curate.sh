#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/run-client-curate.sh <client-or-env-file> [options] [-- <extra main.py args>]

Defaults:
  - Runs: --curate --dry-run --type idea
  - Mode: Docker profile core

Options:
  --channel <list>        Comma-separated channels (default: linkedin,x,bluesky)
  --live                  Remove --dry-run and schedule/push according to --type
  --type <idea|post>      Output routing type (default: idea)
  --reconcile             Add --reconcile
  --learn                 Add --learn
  --classify              Add --classify
  --local                 Run with local .venv instead of Docker
  --profile <core|full>   Docker profile (default: core)

Examples:
  scripts/run-client-curate.sh acme
  scripts/run-client-curate.sh acme --live --type post --reconcile
  scripts/run-client-curate.sh .env.client-beta --channel linkedin,youtube --classify
  scripts/run-client-curate.sh acme --local -- --dot-report --avatar-explain
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

client_or_file="$1"
shift

channel="linkedin,x,bluesky"
type="idea"
dry_run=true
reconcile=false
learn=false
classify=false
local_mode=false
profile="core"
extra_args=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --channel)
      [[ $# -ge 2 ]] || { echo "Error: --channel requires a value." >&2; exit 1; }
      channel="$2"
      shift 2
      ;;
    --live)
      dry_run=false
      shift
      ;;
    --type)
      [[ $# -ge 2 ]] || { echo "Error: --type requires idea|post." >&2; exit 1; }
      type="$2"
      shift 2
      ;;
    --reconcile)
      reconcile=true
      shift
      ;;
    --learn)
      learn=true
      shift
      ;;
    --classify)
      classify=true
      shift
      ;;
    --local)
      local_mode=true
      shift
      ;;
    --profile)
      [[ $# -ge 2 ]] || { echo "Error: --profile requires core|full." >&2; exit 1; }
      profile="$2"
      shift 2
      ;;
    --)
      shift
      extra_args=("$@")
      break
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

if [[ "$type" != "idea" && "$type" != "post" ]]; then
  echo "Error: --type must be idea or post." >&2
  exit 1
fi

if [[ "$profile" != "core" && "$profile" != "full" ]]; then
  echo "Error: --profile must be core or full." >&2
  exit 1
fi

main_args=(--curate --channel "$channel" --type "$type")

if [[ "$dry_run" == true ]]; then
  main_args+=(--dry-run)
fi
if [[ "$reconcile" == true ]]; then
  main_args+=(--reconcile)
fi
if [[ "$learn" == true ]]; then
  main_args+=(--learn)
fi
if [[ "$classify" == true ]]; then
  main_args+=(--classify)
fi

if [[ ${#extra_args[@]} -gt 0 ]]; then
  main_args+=("${extra_args[@]}")
fi

runner=(scripts/run-client.sh "$client_or_file")
if [[ "$local_mode" == true ]]; then
  runner+=(--local)
else
  runner+=(--profile "$profile")
fi
runner+=(--)
runner+=("${main_args[@]}")

printf 'Executing:'
printf ' %q' "${runner[@]}"
printf '\n'

exec "${runner[@]}"
