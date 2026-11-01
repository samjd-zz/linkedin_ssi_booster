#!/usr/bin/env bash
# Download the Argos Translate English->Japanese model used as Rei's offline
# fallback for bilingual hook lines. Runs on the host; ./models is mounted into
# the app container. Only ctranslate2 + sentencepiece are needed at runtime.
set -euo pipefail

MODEL_URL="${ARGOS_EN_JA_URL:-https://argos-net.com/v1/translate-en_ja-1_1.argosmodel}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST_DIR="${REI_ARGOS_MODEL_DIR:-${SCRIPT_DIR}/../models/argos/translate-en_ja}"

if [[ -f "${DEST_DIR}/model/model.bin" ]]; then
  echo "Argos en->ja model already present at ${DEST_DIR}"
  exit 0
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

echo "Downloading ${MODEL_URL} ..."
curl -fL --retry 3 -o "${TMP_DIR}/en_ja.argosmodel" "${MODEL_URL}"

# .argosmodel is a zip with one top-level folder; use Python so unzip isn't required.
python3 - "${TMP_DIR}/en_ja.argosmodel" "${TMP_DIR}/unpacked" <<'EOF'
import sys
import zipfile

zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])
EOF

SRC_DIR="$(find "${TMP_DIR}/unpacked" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
if [[ ! -f "${SRC_DIR}/model/model.bin" || ! -f "${SRC_DIR}/sentencepiece.model" ]]; then
  echo "Unexpected archive layout; model/model.bin or sentencepiece.model missing." >&2
  exit 1
fi

mkdir -p "$(dirname "${DEST_DIR}")"
rm -rf "${DEST_DIR}"
mv "${SRC_DIR}" "${DEST_DIR}"
echo "Installed Argos en->ja model to ${DEST_DIR}"
