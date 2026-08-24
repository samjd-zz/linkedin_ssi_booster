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

## Rei Toei Diversity Controls

### `REI_TOEI_THEME_POOL_SIZE`

Number of extracted theme candidates considered before weighted selection.

Higher values increase variety; lower values keep selection focused on the strongest themes.

**Default:** `20`

```bash
REI_TOEI_THEME_POOL_SIZE=20
```

### `REI_TOEI_RECENT_TITLE_WINDOW`

How many recent Rei Suno artifacts are scanned to avoid repeating title patterns.

**Default:** `20`

```bash
REI_TOEI_RECENT_TITLE_WINDOW=20
```

### `REI_TOEI_THEME_REPEAT_PENALTY`

Penalty multiplier applied when a selected theme matches recent title history.

**Default:** `0.10`

**Range:** `0.01` (strong anti-repeat) to `1.0` (no penalty)

```bash
REI_TOEI_THEME_REPEAT_PENALTY=0.10
```

### `REI_TOEI_THEME_JITTER_RATIO`

Random jitter ratio applied to weighted theme scores before final selection.

Increases randomness among similarly scored themes.

**Default:** `0.10`

**Range:** `0.0` (deterministic weights) to `0.5` (high variance)

```bash
REI_TOEI_THEME_JITTER_RATIO=0.10
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

Path to FLUX local model assets inside the container.

- Supports either a model directory (recommended) or a direct `.gguf` file path.
- Runtime now loads in strict offline mode and will not download configs from Hugging Face.

**Default:** `/app/models/flux`

```bash
FLUX_MODEL_PATH=/app/models/flux
```

### `FLUX_DIFFUSERS_CONFIG_DIR`

Path to a local diffusers config directory used for offline FLUX loading.

Required files:

- `model_index.json`
- `transformer/config.json`

**Default:** `/app/models/flux/diffusers_config`

```bash
FLUX_DIFFUSERS_CONFIG_DIR=/app/models/flux/diffusers_config
```

### `GENERATED_CONTENT_DIR`

Root directory where generated local artifacts are saved.

This is a system-wide local-first storage root for generated content
(YouTube scripts, Rei Toei outputs, and FLUX art-avatar image/story artifacts).

**Default:** `yt-vid-data` (relative to project root)

```bash
GENERATED_CONTENT_DIR=yt-vid-data
```

### `YOUTUBE_SCRIPTS_SUBDIR`

Subdirectory under `GENERATED_CONTENT_DIR` used for generated YouTube scripts.

**Default:** `youtube_scripts`

```bash
YOUTUBE_SCRIPTS_SUBDIR=youtube_scripts
```

### `REI_TOEI_SUBDIR`

Subdirectory under `GENERATED_CONTENT_DIR` used for Rei Toei generated artifacts.

**Default:** `rei_toei`

```bash
REI_TOEI_SUBDIR=rei_toei
```

---

## FLUX Capacitor Art Avatar

The `services/flux_capacitor` package orchestrates FLUX image generation with strict Ollama-first GPU sequencing. All variables below are optional — the feature is **disabled by default** (`FLUX_CAPACITOR_ENABLED=false`) so the core profile is unaffected.

### `FLUX_CAPACITOR_ENABLED`

Master switch. Set to `true` to enable art-avatar generation in the schedule, curate, and console (`/art`) flows.

**Default:** `false`

```bash
FLUX_CAPACITOR_ENABLED=true
```

### `FLUX_CAPACITOR_MINIMAL_MODE`

Skip FLUX rendering entirely and always return the text-only path. Useful for testing the integration wiring without GPU load.

**Default:** `false`

```bash
FLUX_CAPACITOR_MINIMAL_MODE=true
```

### `FLUX_CAPACITOR_STYLE_PRESET`

Active style preset name. Controls visual tone and composition language injected into the FLUX prompt.

**Default:** `corporate_minimal`

**Available presets:**

- `corporate_minimal` — Muted palette, shallow geometry, polished corporate-safe composition
- `sacred_geometry_light` — Subtle sacred geometry with soft light accents, still restrained
- `tech_dark` — Dark background, cyan/purple accent tones, grid-inspired tech aesthetic

```bash
FLUX_CAPACITOR_STYLE_PRESET=corporate_minimal
```

### `FLUX_CAPACITOR_STYLE_SYSTEM_PROMPT`

Custom style system prompt that appends to (or replaces) the active preset's suffix. Override to inject your own visual identity.

**Default:** `"Minimalist corporate-art hybrid aesthetic. Muted palette, shallow sacred-geometry hints, restrained symmetry. Polished but corporate-safe composition. No excessive saturation, no disturbing imagery."`

```bash
FLUX_CAPACITOR_STYLE_SYSTEM_PROMPT="Clean isometric tech illustration, monochrome with single blue accent"
```

### `FLUX_CAPACITOR_REALISM_HINT`

Optional photographic/realism phrase appended at the end of every FLUX prompt.

Leave **unset** (default) to let the active style preset drive the image direction — this is the recommended default because photographic language can conflict with corporate-minimal and illustration presets.

Set this only when you explicitly want photographic quality, for example for headshots or product shots.

**Default:** `` (empty — realism is off)

**Range:** Any short comma-separated directive string, for example:

- `photorealistic, studio lighting, high detail` — strong photographic push
- `highly detailed, soft diffuse lighting` — quality boost without full realism

Can also be set per-request as `style_overrides["realism_hint"]` in code without affecting the global default.

```bash
# Off by default — preset-driven art direction is primary
# FLUX_CAPACITOR_REALISM_HINT=photorealistic, studio lighting, high detail
```

### Style Clamp Variables

Hard limits enforced at render time — cannot be overridden by individual caller requests.

| Variable                               | Default | Range     | Description                                     |
| -------------------------------------- | ------- | --------- | ----------------------------------------------- |
| `FLUX_CAPACITOR_SATURATION_CAP`        | `0.55`  | `0.0–1.0` | Maximum colour saturation allowed in the prompt |
| `FLUX_CAPACITOR_GEOMETRY_DENSITY_CAP`  | `0.40`  | `0.0–1.0` | Maximum geometric complexity in the scene       |
| `FLUX_CAPACITOR_SURREAL_INTENSITY_CAP` | `0.30`  | `0.0–1.0` | Maximum surrealism / abstract distortion        |

```bash
FLUX_CAPACITOR_SATURATION_CAP=0.55
FLUX_CAPACITOR_GEOMETRY_DENSITY_CAP=0.40
FLUX_CAPACITOR_SURREAL_INTENSITY_CAP=0.30
```

### GPU Policy Variables

Control single-GPU sequencing on RTX 3060.

| Variable                                    | Default | Description                                                       |
| ------------------------------------------- | ------- | ----------------------------------------------------------------- |
| `FLUX_CAPACITOR_OLLAMA_FIRST`               | `true`  | Ollama jobs always take priority over FLUX jobs                   |
| `FLUX_CAPACITOR_FLUX_AFTER_OLLAMA`          | `true`  | FLUX rendering only starts after Ollama work drains               |
| `FLUX_CAPACITOR_MAX_CONCURRENT_GPU_JOBS`    | `1`     | Hard cap on simultaneous GPU jobs (FLUX + Ollama combined)        |
| `FLUX_CAPACITOR_QUEUE_WAIT_TIMEOUT_SECONDS` | `120`   | Seconds to wait for a free GPU slot before deferring to text-only |

```bash
FLUX_CAPACITOR_OLLAMA_FIRST=true
FLUX_CAPACITOR_FLUX_AFTER_OLLAMA=true
FLUX_CAPACITOR_MAX_CONCURRENT_GPU_JOBS=1
FLUX_CAPACITOR_QUEUE_WAIT_TIMEOUT_SECONDS=120
```

### Render Dimension Variables

| Variable                       | Default | Description                                                                                                 |
| ------------------------------ | ------- | ----------------------------------------------------------------------------------------------------------- |
| `FLUX_CAPACITOR_RENDER_WIDTH`  | `768`   | Output image width in pixels                                                                                |
| `FLUX_CAPACITOR_RENDER_HEIGHT` | `768`   | Output image height in pixels                                                                               |
| `FLUX_CAPACITOR_RENDER_STEPS`  | `4`     | Diffusion steps (higher = slower but sharper; 4 is schnell-optimal)                                         |
| `FLUX_MAX_SEQUENCE_LENGTH`     | `192`   | Max token sequence length for FLUX text encoding (lower reduces memory usage)                               |
| `FLUX_KEEP_PIPELINE_LOADED`    | `true`  | Keep FLUX pipeline loaded between requests (recommended for service mode to avoid per-request memory creep) |
| `FLUX_LOG_MEMORY`              | `false` | Log CUDA allocated/reserved/peak memory before and after FLUX inference                                     |

```bash
FLUX_CAPACITOR_RENDER_WIDTH=768
FLUX_CAPACITOR_RENDER_HEIGHT=768
FLUX_CAPACITOR_RENDER_STEPS=4
FLUX_MAX_SEQUENCE_LENGTH=192
FLUX_KEEP_PIPELINE_LOADED=true
FLUX_LOG_MEMORY=false
```

### Artifact Storage Variables

| Variable                        | Default          | Description                                                                   |
| ------------------------------- | ---------------- | ----------------------------------------------------------------------------- |
| `FLUX_CAPACITOR_SUBDIR`         | `flux_capacitor` | Subdirectory under `GENERATED_CONTENT_DIR` for art-avatar images and metadata |
| `FLUX_CAPACITOR_STORIES_SUBDIR` | `stories`        | Subdirectory under `FLUX_CAPACITOR_SUBDIR` for story text artifacts           |

```bash
FLUX_CAPACITOR_SUBDIR=flux_capacitor
FLUX_CAPACITOR_STORIES_SUBDIR=stories
```

**Generated artifact layout:**

```
yt-vid-data/
  flux_capacitor/
    20260625_143000_linkedin_abc12345_req-id-fragment.png
    20260625_143000_linkedin_abc12345_req-id-fragment.json   ← image metadata
    stories/
      20260625_143000_linkedin_abc12345_req-id-fragment.txt  ← story text
      20260625_143000_linkedin_abc12345_req-id-fragment_meta.json
```

---

## Rei Toei Music Generation

### `REI_LYRIC_LANGUAGE`

Controls the language policy for Rei's generated lyrics.

**Default:** `bilingual`

**Options:**

- `bilingual` — Rei mixes English and Japanese within the same song.
- `japanese` — Always generate full Japanese lyrics; the probability setting is ignored.
- `english` — Always generate full English lyrics; the probability setting is ignored.

When bilingual mode is enabled, `REI_JAPANESE_LYRIC_PROBABILITY` is used as a target Japanese mix ratio during lyric composition.

```bash
REI_LYRIC_LANGUAGE=bilingual
```

### `REI_JAPANESE_LYRIC_PROBABILITY`

Target Japanese mix ratio when `REI_LYRIC_LANGUAGE=bilingual`.

**Default:** `0.25` (25% target Japanese mix)

**Range:** `0.0` to `1.0`

This setting is ignored when `REI_LYRIC_LANGUAGE=japanese` or `REI_LYRIC_LANGUAGE=english`.

```bash
REI_JAPANESE_LYRIC_PROBABILITY=0.25
```

### `SUNO_API_KEY` (required for Suno integration)

Suno API key from [sunoapi.org](https://sunoapi.org/api-key) — a third-party proxy for Suno AI with a stable v1 REST interface.

**Note:** Suno API integration enables full music generation with vocal synthesis. Without this key, Rei Toei will only generate prompts (no actual audio).

```bash
SUNO_API_KEY=your_suno_api_key_here
```

### `SUNO_API_BASE_URL` (optional)

Base URL for the sunoapi.org proxy. Do **not** change this to `api.suno.ai` — that is a different provider and your sunoapi.org key will be rejected with a 503.

**Default:** `https://api.sunoapi.org`

```bash
SUNO_API_BASE_URL=https://api.sunoapi.org
```

### `SUNO_MODEL` (optional)

Model version passed to sunoapi.org. Available options: `V4`, `V4_5`, `V4_5PLUS`, `V4_5ALL`, `V5`, `V5_5`.

**Default:** `V4_5`

```bash
SUNO_MODEL=V4_5
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

### `STRUDEL_MCP_COMMAND`

Command used by the Strudel agent to launch the MCP server over stdio.

**Default (Docker recommended):** `bash /app/scripts/strudel_mcp_patched.sh`

The wrapper preloads the MCP package and patches a known upstream runtime issue where media resources are blocked by Playwright routing, which can cause silent playback.

**Alternative (upstream direct):** `npx -y @williamzujkowski/live-coding-music-mcp`

```bash
# Docker recommended
STRUDEL_MCP_COMMAND="bash /app/scripts/strudel_mcp_patched.sh"

# Upstream direct command (without local patch)
# STRUDEL_MCP_COMMAND="npx -y @williamzujkowski/live-coding-music-mcp"
```

### `STRUDEL_PLAYBACK_HOLD_SECONDS`

How long the MCP subprocess stays alive after `playback` is triggered, so audio has time to become audible before teardown.

**Default:** `8`

```bash
STRUDEL_PLAYBACK_HOLD_SECONDS=8
```

### `STRUDEL_SAFE_FALLBACK_PATTERN`

Safe Strudel code used when known runtime-invalid constructs are detected (for example `.wrap(...)`).

The runtime is strict about workshop-style syntax:

- Use `sound(...)` and `.sound(...)`
- Do not use legacy aliases `s(...)` or `.s(...)`

**Default:** `sound('bd*2,hh*3').gain(1).fast(1)`

```bash
STRUDEL_SAFE_FALLBACK_PATTERN="sound('bd*2,hh*3').gain(1).fast(1)"
```

Known-good smoke test pattern:

```bash
sound("bd*2,hh*3")
```

### `STRUDEL_SHOW_BROWSER_WINDOW`

When `true`, the MCP flow calls `browser_window` with `action=show` after `init` and before writing/playing a pattern. This helps establish first-run audio context gesture in some Linux/Playwright environments.

**Default:** `true`

```bash
STRUDEL_SHOW_BROWSER_WINDOW=true
```

### `STRUDEL_WRITE_AUTO_PLAY`

Controls whether `edit_pattern` includes `auto_play=true` when writing code.

**Default:** `true`

```bash
STRUDEL_WRITE_AUTO_PLAY=true
```

### `STRUDEL_CALL_PLAYBACK_AFTER_WRITE`

Controls whether the agent sends an additional `playback(action=play)` call after writing a pattern. In some sessions this can interrupt/toggle playback when `auto_play` is already enabled.

**Default:** `false`

```bash
STRUDEL_CALL_PLAYBACK_AFTER_WRITE=false
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

## Curation dedup cache

### `IDEAS_CACHE_PATH`

Path to the published-ideas dedup cache file. Titles of articles already pushed to Buffer are stored here so the same article is never generated twice.

**Default:** `data/published_ideas_cache.json`

The default lives inside `data/`, which is bind-mounted into the Docker container (`./data:/app/data`). This means the cache persists correctly across `docker compose run --rm` invocations. If you change this path, make sure it resolves to a directory that is also mounted.

```bash
IDEAS_CACHE_PATH=data/published_ideas_cache.json
```

### `IDEAS_CACHE_TTL_DAYS`

Number of days before a cache entry is considered expired and pruned. Pruning happens automatically on each write so the cache never grows unboundedly and old articles can re-enter the pool after the TTL lapses.

**Default:** `30`

```bash
IDEAS_CACHE_TTL_DAYS=30
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

# Image Generation (FLUX.1-schnell + Art Avatar)
CIVITAI_API_KEY=your_civitai_key_here
FLUX_MODEL_PATH=/app/models/flux
FLUX_DIFFUSERS_CONFIG_DIR=/app/models/flux/diffusers_config
GENERATED_CONTENT_DIR=/app/yt-vid-data
YOUTUBE_SCRIPTS_SUBDIR=youtube_scripts
REI_TOEI_SUBDIR=rei_toei

# FLUX Capacitor Art Avatar (optional — disabled by default)
FLUX_CAPACITOR_ENABLED=false
FLUX_CAPACITOR_STYLE_PRESET=corporate_minimal
FLUX_CAPACITOR_SATURATION_CAP=0.55
FLUX_CAPACITOR_GEOMETRY_DENSITY_CAP=0.40
FLUX_CAPACITOR_SURREAL_INTENSITY_CAP=0.30
FLUX_CAPACITOR_OLLAMA_FIRST=true
FLUX_CAPACITOR_FLUX_AFTER_OLLAMA=true
FLUX_CAPACITOR_MAX_CONCURRENT_GPU_JOBS=1
FLUX_CAPACITOR_QUEUE_WAIT_TIMEOUT_SECONDS=120
FLUX_CAPACITOR_RENDER_WIDTH=768
FLUX_CAPACITOR_RENDER_HEIGHT=768
FLUX_CAPACITOR_RENDER_STEPS=4
FLUX_CAPACITOR_SUBDIR=flux_capacitor
FLUX_CAPACITOR_STORIES_SUBDIR=stories

# Strudel Music Generation (Docker)
OLLAMA_HOST=http://ollama:11434
STRUDEL_MCP_COMMAND="bash /app/scripts/strudel_mcp_patched.sh"

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

**Solution:** Ensure you're using service names from `docker-compose.yml` where applicable (e.g., `ollama`, `piper`) and that `STRUDEL_MCP_COMMAND` is valid in the runtime image.

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
