# Docker & Deployment Guide

This document covers Docker Compose setup, profiles, GPU passthrough, and deployment best practices for the LinkedIn SSI Booster.

---

## Overview

The system uses **Docker Compose with profiles** to manage hardware resources efficiently:

- **`core` profile:** Lightweight daily operations (Ollama LLM + Wyoming Piper TTS + app)
- **`full` profile:** Includes FLUX.1-schnell image generation (requires RTX 3060 12GB or better)

---

## Prerequisites

### Required

- **Docker Engine** (Linux) or **Docker Desktop** (Windows/Mac)
  - Windows: Enable **WSL 2** in Docker Desktop settings for GPU access
- **NVIDIA Container Toolkit** (Linux only) — Docker Desktop handles GPU passthrough automatically on Windows/WSL 2
- **CUDA 12.4.1+** drivers on the host
- **PulseAudio** running on the host — required for voice output (`CONSOLE_USE_VOICE=true`)

### Hardware Recommendations

- **Minimum:** RTX 3060 8GB (core profile only)
- **Recommended:** RTX 3060 12GB or better (full profile with FLUX image generation)
- **RAM:** 16GB+ system memory
- **Storage:** 20GB+ free disk space (models + data)

---

## Services Overview

| Service                | Profile        | Description                                                                                                       |
| ---------------------- | -------------- | ----------------------------------------------------------------------------------------------------------------- |
| `ollama`               | `core`, `full` | Ollama LLM server — GPU-accelerated, persisted via named `ollama_data` volume                                     |
| `ollama-init`          | `core`, `full` | One-shot init container — pulls `OLLAMA_MODEL` + `OLLAMA_MODEL_FALLBACK` then exits                               |
| `piper`                | `core`, `full` | Wyoming Piper TTS server on port `10200` — downloads voice model on first start                                   |
| `strudel-mcp-agent`    | `core`, `full` | Strudel music generation agent — uses Gemma 4 to generate Strudel.js patterns and sends to MCP server             |
| `buffer-mcp-agent`     | `core`, `full` | Buffer MCP agent — uses Gemma 4 to generate Buffer API requests and sends to official Buffer MCP server           |
| `postgres`             | `core`, `full` | PostgreSQL 16 Alpine database — optional dual-write mode (set `DATABASE_ENABLED=true` in `.env`)                  |
| `flux-init`            | `full`         | One-shot Alpine container — downloads FLUX.1-schnell GGUF weights via Civitai; `flux_capacitor` depends on it           |
| `flux_capacitor`       | `full`         | FLUX.1-schnell inference service — compiles GPU-accelerated `llama-cpp-python`; waits for `flux-init` to complete |
| `app`                  | `core`, `full` | SSI Booster application — Python 3.11 + spaCy `en_core_web_md` and `ja_core_news_md` (`core_base` Dockerfile stage) |

### spaCy language models in the image

The `core_base` stage installs `requirements-core.txt` (which declares `spacy[ja]`, pulling the SudachiPy tokenizer Japanese requires) and downloads both `en_core_web_md` and `ja_core_news_md`. These are baked into the image, not the mounted volumes, so changing `SPACY_MODELS` in `.env` to a model that was never downloaded will not work at runtime — the loader warns and falls back to the English pipeline.

Model downloads sit in a cached Docker layer. After changing the spaCy install line in the `Dockerfile`, rebuild without cache or the old layer is reused:

```bash
docker compose --profile core build --no-cache app
```

Verify the Japanese pipeline is actually live in the container:

```bash
docker compose --profile core run --rm app \
  python -c "import spacy; nlp=spacy.load('ja_core_news_md'); \
d=nlp('新宿LOFTでライブを観た'); print([(t.text, t.pos_) for t in d]); print(d.ents)"
```

Correct output splits the string into separate tokens (`新宿`, `LOFT`, `ライブ`, …). A single unsegmented token means SudachiPy is missing and the English tokenizer is handling the text.

---

## First-Time Setup

### 1. Configure Environment Variables

Copy `.env.example` to `.env` and fill in required values:

```bash
cp .env.example .env
```

**Required variables:**

- `BUFFER_API_KEY` — Your Buffer API access token
- `CIVITAI_API_KEY` — Required for full profile (FLUX model download)
- `PERSONA_SYSTEM_PROMPT` — Your persona description
- `SSI_FOCUS_*` — SSI pillar weights (should sum to 100)

**Docker-specific notes:**

- `OLLAMA_BASE_URL` is automatically overridden to `http://ollama:11434` in `docker-compose.yml` — **do not change it in `.env`**
- `OLLAMA_HOST` is automatically overridden to `http://ollama:11434` for Strudel agent
- `STRUDEL_MCP_COMMAND` is set to `npx -y @williamzujkowski/live-coding-music-mcp`
- `WYOMING_PIPER_HOST` should be set to `piper` (not `localhost`)

See [Environment Variables Reference](environment-variables.md) for complete documentation.

### 2. Copy Avatar Data Files

```bash
# Required files (bind-mounted into container)
cp data/avatar/persona_graph.example.json   data/avatar/persona_graph.json
cp data/avatar/domain_knowledge.example.json data/avatar/domain_knowledge.json
cp data/avatar/narrative_memory.example.json data/avatar/narrative_memory.json
cp content_calendar.example.py               content_calendar.py

# Optional domain knowledge packs (auto-merged at load time)
cp data/avatar/domain_knowledge_java.json   data/avatar/domain_knowledge_java.json
cp data/avatar/domain_knowledge_python.json data/avatar/domain_knowledge_python.json
```

### 3. Edit Persona Files

Customize `persona_graph.json` with your real career facts, projects, and skills. This is the foundation of grounded content generation.

See [Persona and Avatar Intelligence](persona-and-avatar.md) for persona design best practices.

---

## Launching the Stack

### Using `run.sh` (Recommended)

`run.sh` automatically exports `USER_UID=$(id -u)` for PulseAudio passthrough, enabling voice output in console mode.

```bash
# Standard mode — LLM + TTS + app (daily use)
bash run.sh --profile core up -d

# Full mode — adds FLUX image generation
bash run.sh --profile full up -d
```

### Using `docker compose` Directly

Works but audio output will be silent unless `USER_UID` is already exported:

```bash
# Core profile
docker compose --profile core up -d

# Full profile
docker compose --profile full up -d
```

### First Start Sequence

1. **`ollama-init`** pulls `OLLAMA_MODEL` and `OLLAMA_MODEL_FALLBACK` from Ollama registry
2. **`ollama`** starts LLM server on port `11434`
3. **`piper`** downloads voice model (if not cached) and starts TTS server on port `10200`
4. **`flux-init`** (full profile only) downloads FLUX GGUF weights from Civitai
5. **`flux_capacitor`** (full profile only) compiles `llama-cpp-python` with GPU support and starts inference service
6. **`strudel-mcp-agent`** and **`buffer-mcp-agent`** start autonomous agent services
7. **`postgres`** (if `DATABASE_ENABLED=true`) starts PostgreSQL database on port `5432`
8. **`app`** starts SSI Booster application

> **Note:** `ollama-init` and `flux-init` are one-shot containers that exit after completing their tasks. This is expected behavior.

---

## Running Commands

All commands run inside the `app` container:

```bash
# Interactive persona console (TTY required)
docker compose --profile core run --rm -it app python main.py --console

# Console with DoT verification enabled
docker compose --profile core run --rm -it app python main.py --console --verify

# Dry-run schedule (no Buffer calls)
docker compose --profile core run --rm app python main.py --schedule --week 1 --dry-run

# Curate AI news → Buffer Ideas
docker compose --profile core run --rm app python main.py --curate

# Curate with classification and learning
docker compose --profile core run --rm app python main.py --curate --classify --learn

# Record today's SSI scores
docker compose --profile core run --rm app python main.py --save-ssi 10.49 9.69 11.0 12.15

# Database migration (file → PostgreSQL)
docker compose --profile core run --rm app python -m services.database.migrate_data
```

---

## Agent Services

### Strudel Music Agent

Monitor agent logs:

```bash
docker compose logs -f strudel-mcp-agent
```

Run agent with custom prompt (one-off):

```bash
docker compose --profile core run --rm strudel-mcp-agent python agents/strudel_mcp_agent.py
```

Edit agent code:

```bash
# Agent code is bind-mounted from ./agents/ — edit and restart
nano agents/strudel_mcp_agent.py
docker compose restart strudel-mcp-agent
```

### Buffer MCP Agent

Monitor agent logs:

```bash
docker compose logs -f buffer-mcp-agent
```

Run agent with custom prompt (one-off):

```bash
docker compose --profile core run --rm buffer-mcp-agent python agents/buffer_mcp_agent.py
```

---

## GPU Passthrough

### Linux

Requires [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).

Verify GPU access:

```bash
docker compose --profile core run --rm app nvidia-smi
```

### Windows (WSL 2)

Docker Desktop handles GPU passthrough automatically via WSL 2. No manual toolkit installation required.

Verify:

```bash
docker compose --profile core run --rm app nvidia-smi
```

### Service GPU Configuration

All GPU services use `deploy.resources.reservations.devices` in `docker-compose.yml`:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

---

## Storage and Persistence

### Named Volumes

| Volume        | Purpose                                        | Persists On Restart |
| ------------- | ---------------------------------------------- | ------------------- |
| `ollama_data` | Ollama model cache (models pulled from Ollama) | ✅ Yes              |

### Bind Mounts

| Host Path               | Container Path          | Purpose                                |
| ----------------------- | ----------------------- | -------------------------------------- |
| `./data/`               | `/app/data/`            | Persona, domain, learning data         |
| `./yt-vid-data/`        | `/app/yt-vid-data/`     | Generated-content root (images/scripts/artifacts) |
| `./agents/`             | `/app/agents/`          | Agent source code (read-only)          |
| `./models/flux/`        | `/app/models/flux/`     | FLUX GGUF weights (read-only)          |
| `~/.pulse/`             | `/home/appuser/.pulse/` | PulseAudio socket (via `run.sh`)       |
| `./strudel-mcp-server/` | `/app/strudel/`         | Strudel MCP server repo (auto-cloned)  |
| `./postgres-data/`      | `/var/lib/postgresql/`  | PostgreSQL database files (if enabled) |

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

## Voice Output (PulseAudio)

Voice synthesis requires PulseAudio passthrough from host to container.

### Automatic Setup (Recommended)

Use `run.sh` — it exports `USER_UID` and mounts the PulseAudio socket automatically:

```bash
bash run.sh --profile core up -d
```

### Manual Setup

Export `USER_UID` before running `docker compose`:

```bash
export USER_UID=$(id -u)
docker compose --profile core up -d
```

### Verify Voice Output

```bash
# Enable voice in .env
CONSOLE_USE_VOICE=true
WYOMING_PIPER_HOST=piper
WYOMING_PIPER_PORT=10200

# Test in console mode
docker compose --profile core run --rm -it app python main.py --console
```

Type a query and listen for TTS output. If silent, check:

1. PulseAudio is running on host: `pulseaudio --check && echo "OK"`
2. `USER_UID` is exported: `echo $USER_UID`
3. Socket is mounted: `docker compose config | grep pulse`

---

## Database Integration (PostgreSQL)

### Enable Database Mode

Add to `.env`:

```bash
DATABASE_ENABLED=true
POSTGRES_USER=ssi_booster
POSTGRES_PASSWORD=your_secure_password_here
POSTGRES_DB=linkedin_ssi_booster
DATABASE_URL=postgresql://ssi_booster:your_password@postgres:5432/linkedin_ssi_booster
```

Start PostgreSQL container:

```bash
docker compose --profile core up -d postgres
```

### Verify Database

```bash
# Check tables created
docker exec -it ssi_booster_postgres psql -U ssi_booster -d linkedin_ssi_booster -c "\dt"

# Connect to database
docker exec -it ssi_booster_postgres psql -U ssi_booster -d linkedin_ssi_booster
```

### Migrate Existing Data

```bash
# Migrate all JSON/JSONL data to database
docker compose --profile core run --rm app python -m services.database.migrate_data

# Dry-run mode (preview only)
docker compose --profile core run --rm app python -m services.database.migrate_data --dry-run
```

### Rollback to File-Based Storage

Set `DATABASE_ENABLED=false` in `.env`. All JSON/JSONL files remain untouched during dual-write mode.

See [Database Integration](features/database/idea.md) for schema details and performance benchmarks.

---

## Managing Services

### Start Services

```bash
# Core profile (daily use)
bash run.sh --profile core up -d

# Full profile (image generation)
bash run.sh --profile full up -d
```

### Stop Services

```bash
# Stop all services
docker compose --profile core down

# Stop and remove volumes (destructive)
docker compose --profile core down -v
```

### Restart a Single Service

```bash
docker compose restart app
docker compose restart ollama
docker compose restart strudel-mcp-agent
```

### View Logs

```bash
# Follow all logs
docker compose logs -f

# Follow single service
docker compose logs -f app
docker compose logs -f ollama
docker compose logs -f strudel-mcp-agent

# View last 100 lines
docker compose logs --tail=100 app
```

### Rebuild After Code Changes

```bash
# Rebuild app container
docker compose build app

# Rebuild and restart
docker compose up -d --build app

# Rebuild agent (if agent code changed)
docker compose build strudel-mcp-agent
docker compose restart strudel-mcp-agent
```

---

## FLUX Image Generation (Full Profile)

### Prerequisites

- **RTX 3060 12GB or better** — 8GB cards may struggle
- **Civitai API key** — required for `flux-init` to download weights
- **20GB+ free disk space** — GGUF model is ~4GB, with additional space for output images

### Enable Full Profile

```bash
# Add to .env
CIVITAI_API_KEY=your_civitai_key_here
FLUX_MODEL_PATH=/app/models/flux
FLUX_DIFFUSERS_CONFIG_DIR=/app/models/flux/diffusers_config
GENERATED_CONTENT_DIR=/app/yt-vid-data
YOUTUBE_SCRIPTS_SUBDIR=youtube_scripts
REI_TOEI_SUBDIR=rei_toei

# Launch full stack
bash run.sh --profile full up -d
```

### First Start Sequence

1. `flux-init` downloads model files to `./models/flux/`
2. Verify local diffusers config exists at `./models/flux/diffusers_config/`
3. `flux_capacitor` waits for `flux-init` to complete
4. `flux_capacitor` compiles `llama-cpp-python` with CUDA support (takes 5-10 minutes)
5. `flux_capacitor` starts inference service
6. `app` starts and can now generate images

### Pre-Download Weights (Optional)

Download weights without starting the full stack:

```bash
docker compose --profile full run --rm flux-init
```

### Verify Image Generation

Generated artifacts are saved under `./yt-vid-data/` on the host.
Examples:
- YouTube scripts: `./yt-vid-data/youtube_scripts/`
- Rei Toei outputs: `./yt-vid-data/rei_toei/`
- FLUX art-avatar images: `./yt-vid-data/flux_capacitor/`
- FLUX art-avatar stories: `./yt-vid-data/flux_capacitor/stories/`

> **Note:** Art-avatar rendering is controlled by `FLUX_CAPACITOR_ENABLED=true` in `.env`.
> When disabled (the default), the text pipeline runs normally and no GPU work is submitted to the FLUX service.
> When enabled, the GPU orchestrator enforces Ollama-first sequencing: FLUX jobs start only after all active Ollama work drains.
> If the queue wait exceeds `FLUX_CAPACITOR_QUEUE_WAIT_TIMEOUT_SECONDS`, the pipeline degrades gracefully to text-only output.

---

## Troubleshooting

### Services Won't Start

**Problem:** Containers exit immediately or fail health checks.

**Solution:**

1. Check logs: `docker compose logs <service_name>`
2. Verify environment variables in `.env`
3. Ensure required files exist: `persona_graph.json`, `domain_knowledge.json`, `narrative_memory.json`

### GPU Not Detected

**Problem:** `nvidia-smi` fails inside container.

**Solution:**

- **Linux:** Install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
- **Windows:** Enable WSL 2 in Docker Desktop settings
- Verify CUDA drivers: `nvidia-smi` on host should work

### Ollama Models Not Loading

**Problem:** LLM generation fails with "model not found."

**Solution:**

1. Check `ollama-init` logs: `docker compose logs ollama-init`
2. Verify model names in `.env`: `OLLAMA_MODEL=gemma4:e4b`
3. Manually pull models:
   ```bash
   docker compose exec ollama ollama pull gemma4:e4b
   docker compose exec ollama ollama pull qwen3.5:9b
   ```

### Voice Output Silent

**Problem:** `CONSOLE_USE_VOICE=true` but no audio.

**Solution:**

1. Use `bash run.sh` instead of `docker compose` directly
2. Verify PulseAudio on host: `pulseaudio --check && echo "OK"`
3. Check socket mount: `docker compose config | grep pulse`
4. Verify `USER_UID` is exported: `echo $USER_UID`

### Port Conflicts

**Problem:** Services fail to start with "port already in use."

**Solution:**

1. Check what's using the port: `sudo lsof -i :11434` (Ollama), `sudo lsof -i :10200` (Piper)
2. Stop conflicting service or change port in `docker-compose.yml`

### Out of Memory (OOM)

**Problem:** Services crash with OOM errors.

**Solution:**

1. Use `core` profile for daily operations (skip FLUX)
2. Reduce `OLLAMA_NUM_CTX` in `.env` (e.g., from `32768` to `16384`)
3. Close other GPU-heavy applications

### Database Connection Failed

**Problem:** `DATABASE_ENABLED=true` but connection fails.

**Solution:**

1. Verify PostgreSQL is running: `docker ps | grep postgres`
2. Check `DATABASE_URL` in `.env` matches credentials
3. Test connection:
   ```bash
   docker exec -it ssi_booster_postgres psql -U ssi_booster -d linkedin_ssi_booster -c '\dt'
   ```

### FLUX Init Fails

**Problem:** `flux-init` exits with download error.

**Solution:**

1. Verify `CIVITAI_API_KEY` in `.env`
2. Check network connectivity to Civitai
3. Manually download and place in `./models/flux/`:
   ```bash
   # Use the download script
   bash scripts/download-flux1-schnell-Q4_K_S.sh
   ```

---

## Production Deployment

### Security Best Practices

- **Strong passwords:** Use long, random passwords for `POSTGRES_PASSWORD`
- **Secrets management:** Never commit `.env` — use secrets managers in production
- **Network isolation:** Use Docker networks to isolate services
- **Read-only mounts:** Bind-mount sensitive files as read-only where possible

### Resource Limits

Add resource limits to `docker-compose.yml`:

```yaml
services:
  app:
    deploy:
      resources:
        limits:
          cpus: "4"
          memory: 8G
        reservations:
          cpus: "2"
          memory: 4G
```

### Monitoring

Use Docker health checks and monitoring tools:

```bash
# Check service health
docker compose ps

# Export logs to file
docker compose logs > logs.txt

# Use external monitoring (Prometheus, Grafana, etc.)
```

### Backups

```bash
# Backup persona data
tar -czf backup-$(date +%Y%m%d).tar.gz data/

# Backup Ollama models
docker run --rm -v ollama_data:/data -v $(pwd):/backup alpine tar -czf /backup/ollama-backup.tar.gz /data

# Backup PostgreSQL database
docker exec ssi_booster_postgres pg_dump -U ssi_booster linkedin_ssi_booster > backup.sql
```

---

## See Also

- [Environment Variables Reference](environment-variables.md) — Complete env var documentation
- [Setup Guide](setup.md) — Initial setup walkthrough
- [Usage Guide](usage-schedule-curate-console.md) — CLI commands and workflows
- [Architecture Guide](architecture.md) — System design and data flow
