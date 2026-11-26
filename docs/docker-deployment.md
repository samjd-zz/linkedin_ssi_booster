# Docker & Deployment Guide

This document covers Docker Compose setup, profiles, GPU passthrough, and deployment best practices for the LinkedIn SSI Booster.

> **Use `bash run.sh` as the main launcher.** It exports the runtime variables
> needed by the stack, detects NVIDIA, AMD, or Intel GPU support, selects the correct
> Compose override, and falls back to CPU. Use bare `docker compose` only for
> low-level maintenance or when you are intentionally reproducing those settings.

---

## Overview

The system uses **Docker Compose with profiles** to manage hardware resources efficiently:

- **`core` profile:** Lightweight daily operations (Ollama LLM + app)
- **`full` profile:** Adds Wyoming Piper TTS, FLUX.1-schnell image generation (requires RTX 3060 12GB or better), and MCP agents

`ollama` runs **CPU-only by default** (no GPU required for `core`), while `app` is always GPU-neutral. `run.sh`
selects an NVIDIA, AMD Vulkan, or Intel override when detected; on GPU-less hosts it falls back to CPU.
Detection does not guarantee GPU offloading. See [GPU Passthrough](#gpu-passthrough).

---

## Prerequisites

### Required

- **Docker Engine** (Linux) or **Docker Desktop** (Windows/Mac)
  - Windows: Enable **WSL 2** in Docker Desktop settings for GPU access
- **PulseAudio** running on the host — required only for voice output (`CONSOLE_USE_VOICE=true`)

For NVIDIA acceleration or the full FLUX profile, also install the NVIDIA Container Toolkit on Linux and CUDA 12.4.1+ host drivers. Intel iGPU acceleration uses the Intel IPEX-LLM image and does not require CUDA.

### Hardware Recommendations

- **Core:** CPU or supported NVIDIA, AMD, or Intel GPU; model size and context determine memory needs.
- **Full:** NVIDIA RTX 3060 12GB or better for FLUX image generation.
- **RAM:** 16GB+ system memory
- **Storage:** 20GB+ free disk space (models + data)

---

## Services Overview

| Service             | Profile        | Description                                                                                                                                  |
| ------------------- | -------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `ollama`            | `core`, `full` | Ollama LLM server — CPU-only by default, GPU-accelerated when `run.sh` detects a usable NVIDIA GPU; persisted via named `ollama_data` volume |
| `ollama-init`       | `core`, `full` | One-shot init container — reuses cached `OLLAMA_MODEL` + `OLLAMA_MODEL_FALLBACK`, pulling only unavailable models |
| `argos-init`        | `core`, `full` | Required one-shot initializer — reuses or downloads Rei's offline English-to-Japanese model |
| `piper`             | `full`         | Wyoming Piper TTS server on port `10200` — downloads voice model on first start                                                              |
| `strudel-mcp-agent` | `full`         | Strudel music generation agent — uses Gemma 4 to generate Strudel.js patterns and sends to MCP server                                        |
| `buffer-mcp-agent`  | `full`         | Buffer MCP agent — uses Gemma 4 to generate Buffer API requests and sends to official Buffer MCP server                                      |
| `postgres`          | `core`, `full` | PostgreSQL 16 Alpine database — always started as an app dependency; application dual-write is optional |
| `flux-init`         | `full`         | One-shot Alpine container — downloads FLUX.1-schnell GGUF weights via Civitai; `flux_capacitor` depends on it                                |
| `flux_capacitor`    | `full`         | FLUX.1-schnell inference service — compiles GPU-accelerated `llama-cpp-python`; waits for `flux-init` to complete                            |
| `app`               | `core`, `full` | GPU-neutral SSI Booster application — Python 3.11 + spaCy `en_core_web_md` and `ja_core_news_md`; calls accelerated services over HTTP       |

The application source is copied into the `app` image rather than bind-mounted. `run.sh` reuses local images by default; after source changes, explicitly use `run --build`, `up --build`, or `build app`. See [cache-first/offline commands](features/docker-cache-first.md) for prerequisites, GPU probe caching, and no-pull startup.

At startup, the app image identifies itself as GPU-neutral and reports the supported backend acceleration choices: NVIDIA CUDA, Intel iGPU, or CPU. Hardware-specific runtime banners belong to the Ollama and FLUX service containers, not the application container.

### spaCy language models in the image

The Ubuntu-based, GPU-neutral `core_base` stage installs `requirements-core.txt` (which declares `spacy[ja]`, pulling the SudachiPy tokenizer Japanese requires) and downloads both `en_core_web_md` and `ja_core_news_md`. CUDA and Intel iGPU runtimes remain isolated to the Ollama and FLUX services that use them directly. The language models are baked into the app image, not the mounted volumes, so changing `SPACY_MODELS` in `.env` to a model that was never downloaded will not work at runtime — the loader warns and falls back to the English pipeline.

Model downloads sit in a cached Docker layer. After changing the spaCy install line in the `Dockerfile`, rebuild without cache or the old layer is reused:

```bash
bash run.sh --profile core build --no-cache app
```

Verify the Japanese pipeline is actually live in the container:

```bash
bash run.sh --profile core run --rm app \
  python -c "import spacy; nlp=spacy.load('ja_core_news_md'); \
d=nlp('新宿LOFTでライブを観た'); print([(t.text, t.pos_) for t in d]); print(d.ents)"
```

Correct output splits the string into separate tokens (`新宿`, `LOFT`, `ライブ`, …). A single unsegmented token means SudachiPy is missing and the English tokenizer is handling the text.

---

## First-Time Setup

### 1. Configure Environment Variables

Copy `.env.example` to `.env` without overwriting an existing configuration:

```bash
cp -n .env.example .env
```

**Required variables:**

- `POSTGRES_PASSWORD` — Set a unique, strong alphanumeric password before the
  first start, even if `DATABASE_ENABLED=false`; the app always depends on PostgreSQL.
- `BUFFER_API_KEY` — Required for live Buffer operations, not console chat or dry runs.
- `CIVITAI_API_KEY` — Required for the full profile's FLUX model download.
- `PERSONA_SYSTEM_PROMPT` and `SSI_FOCUS_*` — Optional persona and pillar customization.

**Docker-specific notes:**

- `OLLAMA_BASE_URL` is automatically overridden to `http://ollama:11434` in `docker-compose.yml` — **do not change it in `.env`**
- `OLLAMA_HOST` is automatically overridden to `http://ollama:11434` for Strudel agent
- `STRUDEL_MCP_COMMAND` is set to `npx -y @williamzujkowski/live-coding-music-mcp`
- `WYOMING_PIPER_HOST` should be set to `piper` (not `localhost`)

See [Environment Variables Reference](environment-variables.md) for complete documentation.

### 2. Copy Avatar Data Files

```bash
# Preserve existing files; edit these examples for your own use.
cp -n data/avatar/persona_graph.example.json data/avatar/persona_graph.json
cp -n data/avatar/domain_knowledge.example.json data/avatar/domain_knowledge.json
cp -n data/avatar/narrative_memory.example.json data/avatar/narrative_memory.json
cp -n content_calendar.example.py content_calendar.py
```

Shipped `domain_knowledge_*.json` packs are auto-merged; no copies are needed.

### 3. Edit Persona Files

Customize `persona_graph.json` with your real career facts, projects, and skills. This is the foundation of grounded content generation.

See [Persona and Avatar Intelligence](persona-and-avatar.md) for persona design best practices.

---

## Launching the Stack

### Using `run.sh` (Recommended)

`run.sh` automatically exports `USER_UID=$(id -u)` for PulseAudio passthrough, enabling voice output in console mode.

```bash
# Standard mode — Ollama + app + PostgreSQL (daily use)
bash run.sh --profile core up -d

# Full mode — adds FLUX image generation
bash run.sh --profile full up -d
```

### First Start Sequence

1. **`ollama`** starts the LLM server and **`postgres`** starts on port `5432`.
2. **`ollama-init`** checks both configured models and pulls missing models.
   The app does not wait for this service, so wait for successful completion
   before generating; see the [first-run walkthrough](amd-linux-quickstart.md#3-build-and-initialize).
3. **`argos-init`** reuses or downloads the offline translation model.
   The app waits for this initializer to succeed.
4. **`app`** starts its configured command and exits when that command finishes.
5. The `full` profile additionally starts Piper, FLUX and the MCP agents.

The initializers are one-shot containers; a successful exit is expected.

---

## Running Commands

All commands run inside the `app` container:

```bash
# Interactive persona console (TTY required)
bash run.sh --profile core run --rm -it app python main.py --console

# Console with DoT verification enabled
bash run.sh --profile core run --rm -it app python main.py --console --verify

# Dry-run schedule (no Buffer calls)
bash run.sh --profile core run --rm app python main.py --schedule --week 1 --dry-run

# Curate AI news → Buffer Ideas
bash run.sh --profile core run --rm app python main.py --curate

# Curate with classification and learning
bash run.sh --profile core run --rm app python main.py --curate --classify --learn

# Record today's SSI scores
bash run.sh --profile core run --rm app python main.py --save-ssi 10.49 9.69 11.0 12.15

# Database migration (file → PostgreSQL)
bash run.sh --profile core run --rm app python -m services.database.migrate_data
```

---

## Agent Services

### Strudel Music Agent (Full Profile)

Monitor agent logs:

```bash
docker compose logs -f strudel-mcp-agent
```

Run agent with custom prompt (one-off):

```bash
docker compose --profile full run --rm strudel-mcp-agent python agents/strudel_mcp_agent.py
```

Edit agent code:

```bash
# Agent code is bind-mounted from ./agents/ — edit and restart
nano agents/strudel_mcp_agent.py
docker compose restart strudel-mcp-agent
```

### Buffer MCP Agent (Full Profile)

Monitor agent logs:

```bash
docker compose logs -f buffer-mcp-agent
```

Run agent with custom prompt (one-off):

```bash
docker compose --profile full run --rm buffer-mcp-agent python agents/buffer_mcp_agent.py
```

---

## GPU Passthrough

### Auto-detection (recommended: `run.sh`)

`run.sh` probes for GPU availability in tiered order before every command:

1. **NVIDIA GPUs (Linux / WSL 2):** Checks for `nvidia-smi` + working container GPU passthrough. When detected, it merges `docker-compose.gpu.yml` for Ollama compute (`ollama`, `ollama-init`). The full profile separately assigns NVIDIA acceleration to FLUX.
2. **AMD Radeon (native Linux):** Checks DRM vendor `0x1002` and `/dev/dri`, then merges `docker-compose.amd.yml` for Ollama Vulkan acceleration.
3. **Intel GPUs / iGPUs (Iris Xe / Arc / Core Ultra):** Checks DRM vendor `0x8086` on native Linux or `/dev/dxg` on Windows WSL 2. It merges `docker-compose.intel.yml` or `docker-compose.intel-wsl.yml` for IPEX-LLM/SYCL. A generic `/dev/dri` directory alone no longer implies Intel hardware.
4. **CPU-only Fallback:** When no supported GPU is detected, runs standard CPU-only. GPU detection selects a runtime; inspect Ollama logs to confirm actual offloading.

```bash
bash run.sh --profile core up -d      # NVIDIA, AMD or Intel runtime selected when detected
```

`flux-init` and `flux_capacitor` (full profile only) always require an NVIDIA GPU and are not affected by
this toggle — they keep a hardcoded `nvidia` reservation in `docker-compose.yml`.

### Linux (AMD Radeon Vulkan)

Follow the [AMD Linux quickstart](amd-linux-quickstart.md) for a complete fresh
install, model initialization, GPU verification, and troubleshooting.
It targets native Ubuntu and uses Ollama's Vulkan backend rather than ROCm;
the override exposes `/dev/dri` only to Ollama. Support varies by hardware and
driver, so verify actual offloading. Use `core` on AMD-only hosts: FLUX in the
`full` profile still requires NVIDIA CUDA.

### Linux (NVIDIA)

Requires [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).

Verify GPU access (after `run.sh` has enabled the GPU override):

```bash
bash run.sh --profile core run --rm app nvidia-smi
```

### Windows (WSL 2)

Docker Desktop handles GPU passthrough automatically via WSL 2.

- For NVIDIA cards, WSL 2 exposes GPU capabilities directly through the NVIDIA driver.
- For Intel Iris Xe / Arc graphics, WSL 2 maps GPU acceleration through `/dev/dxg`, which `run.sh` auto-detects and layers in `docker-compose.intel-wsl.yml`. This override runs the container `privileged` and mounts `/usr/lib/wsl` in addition to `/dev/dri`, which the WSL 2 GPU bridge requires.

Verify:

```bash
bash run.sh --profile core config
```

### Service GPU Configuration

`ollama` and `ollama-init` have no GPU reservation in `docker-compose.yml` (CPU-only baseline). `app` remains GPU-neutral in every override because it calls Ollama and FLUX over HTTP.

- `docker-compose.gpu.yml` adds NVIDIA reservations (`capabilities: [gpu]`).
- `docker-compose.intel.yml` (native Linux) and `docker-compose.intel-wsl.yml` (Windows WSL 2) switch the `ollama`/`ollama-init` image to `intelanalytics/ipex-llm-inference-cpp-xpu:latest`, mount `/dev/dri`, and run `ipex-llm-init --gpu --device iGPU` before `init-ollama` to start the SYCL/Level-Zero accelerated server. Do not add `group_add: [video, render]` to these overrides — this image's `/etc/group` has no such entries and Docker will refuse to start the container; device passthrough alone is sufficient.

If you call `docker compose` directly instead of `run.sh` on a GPU-less host, you get CPU-only
behavior automatically — no `nvidia` driver error. To force a specific GPU profile manually without `run.sh`:

- NVIDIA: `docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile core up -d`
- Intel (Linux): `docker compose -f docker-compose.yml -f docker-compose.intel.yml --profile core up -d`
- Intel (WSL 2): `docker compose -f docker-compose.yml -f docker-compose.intel-wsl.yml --profile core up -d`

---

## Storage and Persistence

### Named Volumes

| Volume        | Purpose                                        | Persists On Restart |
| ------------- | ---------------------------------------------- | ------------------- |
| `ollama_data` | Ollama model cache (models pulled from Ollama) | ✅ Yes              |

### Bind Mounts

| Host Path               | Container Path          | Purpose                                           |
| ----------------------- | ----------------------- | ------------------------------------------------- |
| `./data/`               | `/app/data/`            | Persona, domain, learning data                    |
| `./yt-vid-data/`        | `/app/yt-vid-data/`     | Generated-content root (images/scripts/artifacts) |
| `./agents/`             | `/app/agents/`          | Agent source code (read-only)                     |
| `./models/flux/`        | `/app/models/flux/`     | FLUX GGUF weights (read-only)                     |
| `$PULSE_SOCKET`         | `/run/pulse/native`     | PulseAudio socket (chosen by `run.sh`)            |
| `./strudel-mcp-server/` | `/app/strudel/`         | Strudel MCP server repo (auto-cloned)             |
| `./postgres-data/`      | `/var/lib/postgresql/`  | PostgreSQL database files (if enabled)            |

**Key Points:**

- **Runtime data** (`data/`, `yt-vid-data/`) is bind-mounted — changes are visible immediately on host
- **Ollama models** persist in the named `ollama_data` volume — survives `docker compose down`
- **Agent code** is bind-mounted read-only — edit `./agents/` and restart service to apply changes
- **FLUX weights** are bind-mounted read-only — downloaded once by `flux-init`, shared across containers
- Generated-content subdirectories are controlled via env vars:
  - `GENERATED_CONTENT_DIR=/app/yt-vid-data`
  - `YOUTUBE_SCRIPTS_SUBDIR=youtube_scripts`
  - `REI_TOEI_SUBDIR=rei_toei`

---

## Further operations

See [Docker operations](docker-operations.md) for voice, database, service management, FLUX, troubleshooting, and deployment.
