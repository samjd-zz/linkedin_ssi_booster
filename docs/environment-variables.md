# Environment Variables Reference

This document provides a comprehensive reference for all environment variables used by the LinkedIn SSI Booster system.

## Quick Setup

Copy `.env.example` to `.env` and fill in the required values:

```bash
cp .env.example .env
```

---

## Buffer API

### `BUFFER_API_KEY` (required)

Your Buffer API access token. Get this from your [Buffer Developer Dashboard](https://buffer.com/developers/api).

```bash
BUFFER_API_KEY=your_buffer_api_key_here
```

---

## Ollama LLM Configuration

### `OLLAMA_MODEL` (required)

Primary LLM model for all generation calls.

**Default:** `gemma4:e4b`

**Recommended models:**

- `gemma4:e4b` — Fast, accurate, excellent instruction following
- `qwen3.5:9b` — Good fallback with strong reasoning

```bash
OLLAMA_MODEL=gemma4:e4b
```

### `OLLAMA_MODEL_FALLBACK`

Auto-retried once on empty output or error response from primary model.

**Default:** `qwen3.5:9b`

```bash
OLLAMA_MODEL_FALLBACK=qwen3.5:9b
```

### `OLLAMA_BASE_URL`

Ollama server URL. **Automatically overridden to `http://ollama:11434` in Docker** — do not change for Docker deployments.

**Default:** `http://localhost:11434` (local development)

**Docker:** `http://ollama:11434` (automatic override in `docker-compose.yml`)

```bash
# Local development
OLLAMA_BASE_URL=http://localhost:11434

# Docker (override handled automatically)
OLLAMA_BASE_URL=http://ollama:11434
```

### `OLLAMA_NUM_CTX`

Context window size in tokens. Larger values allow more grounding facts and longer articles but increase memory usage.

**Default:** `16384`

**Recommended:** `32768` for grounded prompts with extensive persona facts

```bash
OLLAMA_NUM_CTX=32768
```

---

## Truth Gate Thresholds

### `TRUTH_GATE_BM25_THRESHOLD`

Minimum BM25 score for a sentence to be considered supported by evidence. Lower values are more permissive, higher values are stricter.

**Default:** `1.0`

**Range:** `0.5` (very permissive) to `2.0` (very strict)

```bash
TRUTH_GATE_BM25_THRESHOLD=1.0
```

### `TRUTH_GATE_SPACY_SIM_FLOOR`

Minimum spaCy cosine similarity between a sentence and the source article for numeric/org/year claims. Only applies in curation mode where source articles are available.

**Default:** `0.10`

**Range:** `0.05` (permissive) to `0.20` (strict)

```bash
TRUTH_GATE_SPACY_SIM_FLOOR=0.10
```

### `TRUTH_GATE_FACT_SIM_FLOOR`

Minimum spaCy cosine similarity between a sentence and the best-matching persona/domain fact. Runs in all modes including console.

**Default:** `0.05`

**Range:** `0.03` (permissive) to `0.15` (strict)

```bash
TRUTH_GATE_FACT_SIM_FLOOR=0.05
```

### `TRUTH_GRADIENT_FLAG_THRESHOLD`

Minimum Derivative of Truth composite score for a sentence to pass validation. Sentences below this threshold are flagged as `weak_dot_gradient` and removed.

**Default:** `0.35`

**Range:** `0.25` (permissive) to `0.50` (strict)

```bash
TRUTH_GRADIENT_FLAG_THRESHOLD=0.35
```

---

## Continual Learning

### `EXTRACTED_CONTEXT_LIMIT`

Maximum number of extracted facts injected into curation prompts as additional context.

**Default:** `10`

```bash
EXTRACTED_CONTEXT_LIMIT=10
```

### `EXTRACTED_EVIDENCE_COUNT`

Maximum number of extracted facts used as evidence per article during grounding and DoT scoring.

**Default:** `2`

```bash
EXTRACTED_EVIDENCE_COUNT=2
```

### `TOPIC_SIGNAL_WINDOW`

Number of most-recent extracted facts used to build adaptive topic signal for curation ranking.

**Default:** `50`

```bash
TOPIC_SIGNAL_WINDOW=50
```

---

## Avatar Intelligence

### `AVATAR_CONFIDENCE_POLICY`

Publication safety routing policy. Controls how generated content is routed based on confidence scores.

**Options:**

- `balanced` (default) — Normal threshold for Ideas vs direct posting
- `strict` — Higher bar, more content goes to Ideas for review
- `draft-first` — Everything goes to Ideas, nothing auto-scheduled

```bash
AVATAR_CONFIDENCE_POLICY=balanced
```

### `AVATAR_LEARNING_ENABLED`

Enable narrative memory and moderation event logging for continual learning.

**Default:** `true`

```bash
AVATAR_LEARNING_ENABLED=true
```

### `AVATAR_MAX_MEMORY_ITEMS`

Maximum items retained in narrative memory before FIFO (First In, First Out) trim.

**Default:** `200`

```bash
AVATAR_MAX_MEMORY_ITEMS=200
```

---

## Katzilla Integration (Phases 1-6)

### `KATZILLA_ENABLED`

Enable Katzilla-backed external evidence retrieval.

Default: `false`

When enabled, `KATZILLA_API_KEY` must also be set.

```bash
KATZILLA_ENABLED=false
```

### `KATZILLA_API_KEY`

API key used for Katzilla requests (sent as `X-API-Key`).

Required only when `KATZILLA_ENABLED=true`.

```bash
KATZILLA_API_KEY=your_katzilla_key_here
```

### `KATZILLA_BASE_URL`

Base URL for Katzilla API calls.

Default: `https://katzilla.dev`

```bash
KATZILLA_BASE_URL=https://katzilla.dev
```

### `KATZILLA_TIMEOUT_SECONDS`

Per-request timeout for Katzilla calls.

Default: `6.0`

```bash
KATZILLA_TIMEOUT_SECONDS=6.0
```

### `KATZILLA_DEFAULT_FORMAT`

Default Katzilla response format requested by the client.

Default: `compact`

```bash
KATZILLA_DEFAULT_FORMAT=compact
```

### `KATZILLA_MAX_EXTERNAL_RESULTS`

Maximum number of external evidence items appended per retrieval query.

Default: `2`

```bash
KATZILLA_MAX_EXTERNAL_RESULTS=2
```

### `KATZILLA_FIELD_ALLOWLIST`

Comma-separated field list requested from Katzilla for token/cost optimization.

Default: `title,summary,source_url,published_at,tags`

```bash
KATZILLA_FIELD_ALLOWLIST=title,summary,source_url,published_at,tags
```

### `KATZILLA_TELEMETRY_ENABLED`

Enable JSONL telemetry capture for Katzilla calls.

Default: `true`

```bash
KATZILLA_TELEMETRY_ENABLED=true
```

### `KATZILLA_MAX_CALLS_PER_DAY`

Daily call budget for Katzilla external evidence retrieval.

Default: `50`

```bash
KATZILLA_MAX_CALLS_PER_DAY=50
```

### `KATZILLA_MAX_UNCERTAINTY_PER_DAY`

Daily uncertainty budget for Katzilla retrieval (sum of per-call average uncertainty).

Default: `20.0`

```bash
KATZILLA_MAX_UNCERTAINTY_PER_DAY=20.0
```

---

## Model2Vec Classification

### `MODEL2VEC_ENABLED`

Enable static embedding-based text classification for articles and posts.

**Default:** `true`

**Note:** Requires `pip install model2vec`

```bash
MODEL2VEC_ENABLED=true
```

### `CURATE_CLASSIFY`

Auto-classify articles on every `--curate` run, equivalent to always passing `--classify` flag.

**Default:** `false`

```bash
CURATE_CLASSIFY=false
```

---

## SSI Focus Weights

Control the distribution of content across LinkedIn's four SSI pillars. **Values should sum to 100.**

### `SSI_FOCUS_ESTABLISH_BRAND`

Weight for "Establish your professional brand" pillar (completeness of profile, consistency of posting, saves/shares).

**Default:** `25`

```bash
SSI_FOCUS_ESTABLISH_BRAND=25
```

### `SSI_FOCUS_FIND_RIGHT_PEOPLE`

Weight for "Find the right people" pillar (profile searches, connection acceptance rate, right-audience reach).

**Default:** `25`

```bash
SSI_FOCUS_FIND_RIGHT_PEOPLE=25
```

### `SSI_FOCUS_ENGAGE_WITH_INSIGHTS`

Weight for "Engage with insights" pillar (shares, comments, reactions on industry content, thought leadership).

**Default:** `25`

```bash
SSI_FOCUS_ENGAGE_WITH_INSIGHTS=25
```

### `SSI_FOCUS_BUILD_RELATIONSHIPS`

Weight for "Build relationships" pillar (connection growth, message response rate, relationship depth).

**Default:** `25`

```bash
SSI_FOCUS_BUILD_RELATIONSHIPS=25
```

**Example: Boost a lagging pillar**

If your "Engage with insights" score is low, increase its weight:

```bash
SSI_FOCUS_ESTABLISH_BRAND=20
SSI_FOCUS_FIND_RIGHT_PEOPLE=20
SSI_FOCUS_ENGAGE_WITH_INSIGHTS=40  # Boosted
SSI_FOCUS_BUILD_RELATIONSHIPS=20
```

---

## Voice / Text-to-Speech (Wyoming Piper)

### `CONSOLE_USE_VOICE`

Enable Wyoming Piper TTS voice output in console mode. Voice output is **in addition to** text output, not replacing it.

**Default:** `false`

**Note:** Requires PulseAudio passthrough in Docker. Use `bash run.sh` to automatically configure audio.

```bash
CONSOLE_USE_VOICE=true
```

### `WYOMING_PIPER_HOST`

Wyoming Piper TTS server hostname.

**Default (Docker):** `piper`

**Default (local dev):** `localhost`

```bash
# Docker
WYOMING_PIPER_HOST=piper

# Local development
WYOMING_PIPER_HOST=localhost
```

### `WYOMING_PIPER_PORT`

Wyoming Piper TTS server port.

**Default:** `10200`

```bash
WYOMING_PIPER_PORT=10200
```

### `CONSOLE_VOICE_SPEAKER`

Speaker ID for multi-speaker voice models. Required for voices like `en_US-libritts_r-medium`.

**Example:** `896` for `en_US-libritts_r-medium`

```bash
CONSOLE_VOICE_SPEAKER=896
```

### `HOST_UID` and `PULSE_RUNTIME_DIR`

Set automatically by `run.sh` for PulseAudio passthrough. Do not set manually.

```bash
# Set automatically by run.sh
HOST_UID=1000
PULSE_RUNTIME_DIR=/run/user/1000/pulse
```

---

## Image Generation (FLUX.1-schnell)

### `CIVITAI_API_KEY` (required for full profile)

Civitai API key for downloading FLUX GGUF model weights. Get your key from [Civitai](https://civitai.com/).

```bash
CIVITAI_API_KEY=your_civitai_key_here
```

### `FLUX_MODEL_PATH`

Path to the FLUX GGUF model file inside the container.

**Default:** `/app/models/flux/flux1-schnell-Q4_K_S.gguf`

```bash
FLUX_MODEL_PATH=/app/models/flux/flux1-schnell-Q4_K_S.gguf
```

### `IMAGE_OUTPUT_DIR`

Directory where generated images are saved inside the container.

**Default:** `/app/yt-vid-data`

```bash
IMAGE_OUTPUT_DIR=/app/yt-vid-data
```

---

## Rei Toei Music Generation

### `SUNO_API_KEY` (required for Suno integration)

Suno AI music generation API key. Get your API key from https://api.sunoapi.org/ or similar Suno API provider.

**Note:** Suno API integration enables full music generation with vocal synthesis. Without this key, Rei Toei will only generate prompts (no actual audio).

```bash
SUNO_API_KEY=your_suno_api_key_here
```

### `REI_TOEI_USE_SAM_PERSONA`

Enable Rei Toei to access Sam's persona graph for project knowledge inspiration.

**Default:** `true`

When enabled, Rei can organically reference Sam's GitHub projects, skills, and company experience in song concepts and lyrics. This is **additive** to Rei's own persona graph, domain knowledge, and pattern library — she always uses her own knowledge files.

**When true:** The LLM receives Sam's project context as optional inspiration during song concept and lyric generation. Rei may naturally weave project references into metaphors if thematically relevant.

**When false:** Rei only uses her own knowledge sources (rei_toei_persona_graph.json, rei_toei_domain_knowledge.json, rei_toei_strudel_patterns.json).

```bash
# Enable Sam's persona graph for richer context
REI_TOEI_USE_SAM_PERSONA=true

# Disable to use only Rei's baseline knowledge
REI_TOEI_USE_SAM_PERSONA=false
```

## Strudel Music Generation

### `OLLAMA_HOST`

Ollama server URL for Strudel agent. Automatically overridden to `http://ollama:11434` in Docker.

**Default (local):** `http://localhost:11434`

**Docker:** `http://ollama:11434` (automatic override)

```bash
# Docker (override handled automatically)
OLLAMA_HOST=http://ollama:11434
```

### `STRUDEL_WS_URL`

WebSocket URL for Strudel MCP server.

**Default (local):** `ws://localhost:4321`

**Docker:** `ws://strudel-music-server:4321`

```bash
# Docker
STRUDEL_WS_URL=ws://strudel-music-server:4321

# Local development
STRUDEL_WS_URL=ws://localhost:4321
```

### `STRUDEL_MCP_URL`

HTTP URL for Strudel MCP server.

**Default (local):** `http://localhost:3000`

**Docker:** `http://strudel-music-server:3000`

```bash
# Docker
STRUDEL_MCP_URL=http://strudel-music-server:3000

# Local development
STRUDEL_MCP_URL=http://localhost:3000
```

---

## Database Integration (PostgreSQL)

### `DATABASE_ENABLED`

Enable PostgreSQL dual-write mode. When `false`, system uses file-based storage (JSON/JSONL).

**Default:** `false`

```bash
DATABASE_ENABLED=true
```

### `POSTGRES_USER`

PostgreSQL database username.

**Default:** `ssi_booster`

```bash
POSTGRES_USER=ssi_booster
```

### `POSTGRES_PASSWORD` (required when DATABASE_ENABLED=true)

PostgreSQL database password. Use a strong password for production.

```bash
POSTGRES_PASSWORD=your_secure_password_here
```

### `POSTGRES_DB`

PostgreSQL database name.

**Default:** `linkedin_ssi_booster`

```bash
POSTGRES_DB=linkedin_ssi_booster
```

### `DATABASE_URL` (required when DATABASE_ENABLED=true)

Full PostgreSQL connection string. Must match the user/password/db settings above.

**Format:** `postgresql://user:password@host:port/database`

**Docker:** Use `postgres` as hostname

**Local:** Use `localhost` as hostname

```bash
# Docker
DATABASE_URL=postgresql://ssi_booster:your_password@postgres:5432/linkedin_ssi_booster

# Local development
DATABASE_URL=postgresql://ssi_booster:your_password@localhost:5432/linkedin_ssi_booster
```

---

## Persona Configuration

### `PERSONA_SYSTEM_PROMPT` (required)

Your persona system prompt. This is the foundation of your avatar's voice and grounding behavior.

**Example:**

```bash
PERSONA_SYSTEM_PROMPT="You are Sam, a senior software engineer specializing in AI/ML automation and backend systems. You have 10+ years of experience building production-grade applications in Java, Python, and cloud infrastructure."
```

See [docs/persona-and-avatar.md](persona-and-avatar.md) for persona design best practices.

---

## Console Grounding Keywords

### `CONSOLE_GROUNDING_TECH_KEYWORDS`

Comma-separated list of technical terms that trigger tech-tag grounding in console mode. Extend this list to include your project stack and domain vocabulary.

**Default:** Built-in keywords include `java`, `spring`, `python`, `fastapi`, `rag`, `llm`, `bm25`, `vector search`, `microservices`, etc.

```bash
CONSOLE_GROUNDING_TECH_KEYWORDS=spring ai,sentence transformers,pubsub+,fastmcp
```

### `CONSOLE_GROUNDING_TAG_EXPANSIONS`

Umbrella term expansions for broad queries. Format: `term:related1|related2|related3`

**Example:**

```bash
CONSOLE_GROUNDING_TAG_EXPANSIONS=java:spring|jms|oracle|weblogic,python:fastapi|scikit-learn
```

---

## Curator Keywords

### `CURATOR_KEYWORDS`

Comma-separated list of keywords for RSS article filtering during curation. Articles must match at least one keyword to be considered.

**Example:**

```bash
CURATOR_KEYWORDS=artificial intelligence,machine learning,llm,retrieval,rag,vector search,semantic search,prompt engineering,ai agent
```

---

## Complete Example `.env` File

```bash
# Buffer API
BUFFER_API_KEY=your_buffer_api_key_here

# Ollama LLM
OLLAMA_MODEL=gemma4:e4b
OLLAMA_MODEL_FALLBACK=qwen3.5:9b
OLLAMA_BASE_URL=http://localhost:11434  # Override to http://ollama:11434 in Docker
OLLAMA_NUM_CTX=32768

# Truth Gate Thresholds
TRUTH_GATE_BM25_THRESHOLD=1.0
TRUTH_GATE_SPACY_SIM_FLOOR=0.10
TRUTH_GATE_FACT_SIM_FLOOR=0.05
TRUTH_GRADIENT_FLAG_THRESHOLD=0.35

# Continual Learning
EXTRACTED_CONTEXT_LIMIT=10
EXTRACTED_EVIDENCE_COUNT=2
TOPIC_SIGNAL_WINDOW=50

# Avatar Intelligence
AVATAR_CONFIDENCE_POLICY=balanced
AVATAR_LEARNING_ENABLED=true
AVATAR_MAX_MEMORY_ITEMS=200

# Model2Vec Classification
MODEL2VEC_ENABLED=true
CURATE_CLASSIFY=false

# SSI Focus Weights (sum to 100)
SSI_FOCUS_ESTABLISH_BRAND=25
SSI_FOCUS_FIND_RIGHT_PEOPLE=25
SSI_FOCUS_ENGAGE_WITH_INSIGHTS=25
SSI_FOCUS_BUILD_RELATIONSHIPS=25

# Voice / TTS (Docker only)
CONSOLE_USE_VOICE=true
WYOMING_PIPER_HOST=piper
WYOMING_PIPER_PORT=10200
CONSOLE_VOICE_SPEAKER=896

# Image Generation (full profile only)
CIVITAI_API_KEY=your_civitai_key_here
FLUX_MODEL_PATH=/app/models/flux/flux1-schnell-Q4_K_S.gguf
IMAGE_OUTPUT_DIR=/app/yt-vid-data

# Strudel Music Generation (Docker)
OLLAMA_HOST=http://ollama:11434
STRUDEL_WS_URL=ws://strudel-music-server:4321
STRUDEL_MCP_URL=http://strudel-music-server:3000

# Database Integration (optional)
DATABASE_ENABLED=false
POSTGRES_USER=ssi_booster
POSTGRES_PASSWORD=your_secure_password_here
POSTGRES_DB=linkedin_ssi_booster
DATABASE_URL=postgresql://ssi_booster:your_password@postgres:5432/linkedin_ssi_booster

# Persona
PERSONA_SYSTEM_PROMPT="You are Sam, a senior software engineer..."
```

---

## Troubleshooting

### Docker URL Overrides Not Working

**Problem:** Services can't connect to Ollama or other services in Docker.

**Solution:** Ensure you're using service names from `docker-compose.yml` (e.g., `ollama`, `piper`, `strudel-music-server`) not `localhost`. The system automatically overrides these in Docker.

### Voice Output Silent

**Problem:** `CONSOLE_USE_VOICE=true` but no audio in Docker.

**Solution:** Use `bash run.sh --profile core up -d` instead of `docker compose` directly. `run.sh` exports `USER_UID` and mounts the PulseAudio socket.

### Truth Gate Too Strict/Permissive

**Problem:** Too many sentences removed OR weak claims passing through.

**Solution:** Adjust threshold env vars incrementally:

- Lower `TRUTH_GATE_BM25_THRESHOLD` to be more permissive
- Raise `TRUTH_GRADIENT_FLAG_THRESHOLD` to be stricter
- Lower `TRUTH_GATE_SPACY_SIM_FLOOR` to allow more paraphrasing

### Database Connection Failed

**Problem:** `DATABASE_ENABLED=true` but connection fails.

**Solution:**

1. Verify PostgreSQL container is running: `docker ps | grep postgres`
2. Check `DATABASE_URL` matches your credentials
3. Test connection: `docker exec -it ssi_booster_postgres psql -U ssi_booster -d linkedin_ssi_booster -c '\dt'`

---

## See Also

- [Setup Guide](setup.md) — Full environment setup walkthrough
- [Docker & Deployment](docker-deployment.md) — Docker Compose configuration and profiles
- [Usage Guide](usage-schedule-curate-console.md) — CLI commands and workflows
