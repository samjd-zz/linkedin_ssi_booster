# Docker Operations and Troubleshooting

See the [Docker deployment guide](docker-deployment.md) for initial setup and GPU configuration.

## Voice Output (PulseAudio)

Voice synthesis requires PulseAudio passthrough from host to container.

### Automatic Setup (Recommended)

Use `run.sh` — it exports `USER_UID` and picks the host PulseAudio socket as
`PULSE_SOCKET`. On WSL2 with WSLg it uses `/mnt/wslg/PulseServer`, which
accepts anonymous clients; the `/run/user/<uid>/pulse/native` socket rejects
container cookies with `Access denied`. Elsewhere it uses
`$XDG_RUNTIME_DIR/pulse/native`. The socket is mounted at `/run/pulse/native`,
and the image routes ALSA's default device to PulseAudio (`/etc/asound.conf`)
so `sounddevice` can play Piper audio.

Piper is in the `full` profile. To use voice with a `core` console, start Piper
on its own first:

```bash
bash run.sh --profile full up -d --no-deps piper
bash run.sh --profile core run --rm app python main.py --console
```

### Manual Setup

Export `USER_UID` before running `docker compose`:

```bash
export USER_UID=$(id -u)
export PULSE_SOCKET=/mnt/wslg/PulseServer   # WSLg; else $XDG_RUNTIME_DIR/pulse/native
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

1. Piper is healthy: `docker ps --filter name=ssi_booster_piper`
2. PulseAudio accepts the container: `bash run.sh --profile core run --rm --no-deps --entrypoint pactl app info`
3. Socket is mounted: `docker compose config | grep pulse`

---

## Database Integration (PostgreSQL)

### Enable Database Mode

Add to `.env`:

```bash
DATABASE_ENABLED=true
POSTGRES_USER=ssi_booster
POSTGRES_PASSWORD=your_unique_alphanumeric_password_here
POSTGRES_DB=linkedin_ssi_booster
```

Docker Compose constructs the app's `DATABASE_URL` from the `POSTGRES_*` values.
Changing `POSTGRES_PASSWORD` after PostgreSQL first initializes does not change
the password stored in its existing volume.

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

### GPU Not Detected / "could not select device driver nvidia"

**Problem:** `nvidia-smi` fails inside container, or `docker compose` errors with
`could not select device driver "nvidia" with capabilities: [[gpu]]`.

**Solution:**

- Use `bash run.sh ...` instead of calling `docker compose` directly — it auto-detects GPU
  availability and only applies `docker-compose.gpu.yml` when a GPU actually works, falling back
  to CPU-only otherwise.
- **Linux:** Install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
- **Windows:** Enable WSL 2 in Docker Desktop settings
- Verify CUDA drivers: `nvidia-smi` on host should work
- `flux-init`/`flux_capacitor` (full profile) require NVIDIA; Ollama can use NVIDIA, Intel iGPU, or CPU, and `app` remains GPU-neutral.

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
2. Start Piper (`full` profile) and confirm it is healthy: `docker ps --filter name=ssi_booster_piper`
3. Check PulseAudio access: `bash run.sh --profile core run --rm --no-deps --entrypoint pactl app info` (`Access denied` on WSL means the wrong socket; set `PULSE_SOCKET=/mnt/wslg/PulseServer`)
4. Check socket mount: `docker compose config | grep pulse`
5. `Error querying device -1` means the app image predates `/etc/asound.conf`; rebuild it with `bash run.sh --profile core build app`

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
2. Verify the configured `POSTGRES_*` values match the existing database credentials; Compose constructs the app's `DATABASE_URL` from these values
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
