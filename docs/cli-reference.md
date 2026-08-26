# CLI Flags Reference

This document provides a comprehensive reference for all command-line flags supported by the LinkedIn SSI Booster.

---

## Overview

The CLI centers on three main workflows:

1. **Schedule mode** (`--schedule`) — Generate posts from your private content calendar, with optional FLUX art-avatar rendering
2. **Curate mode** (`--curate`) — Fetch and comment on live RSS articles, with optional FLUX art-avatar rendering
3. **Console mode** (`--console`) — Interactive persona chat with deterministic grounding and on-demand art generation (`/art`)

All modes support `--dry-run` to preview outputs without making Buffer API calls.

---

## Global Flags

### `--dry-run`

Preview outputs without making Buffer API calls. Works with `--schedule` and `--curate`.

**Example:**

```bash
python main.py --schedule --week 1 --dry-run
python main.py --curate --dry-run
```

### `--channel <channel>`

Target a specific social media channel. Options: `linkedin`, `x`, `bluesky`, `threads`, `facebook`, `youtube`, `all`

**Default:** `linkedin`

**Example:**

```bash
python main.py --schedule --week 1 --channel x
python main.py --curate --channel all
```

**Channel behavior:**

| Channel    | Output Format                                                                                     |
| ---------- | ------------------------------------------------------------------------------------------------- |
| `linkedin` | Default; source URL and hashtags appended programmatically for curation                           |
| `x`        | 280-character limit, single paragraph, no hashtag append                                          |
| `bluesky`  | 300-character limit, X-like post behavior                                                         |
| `threads`  | 500-character limit, conversational short post, no hashtag append                                 |
| `facebook` | Similar to LinkedIn; source URL and hashtags appended for curation                                |
| `youtube`  | Generates spoken script, prints it, saves to `<GENERATED_CONTENT_DIR>/<YOUTUBE_SCRIPTS_SUBDIR>/`; not pushed to Buffer |
| `all`      | Runs LinkedIn, X, Bluesky, Threads, Facebook, and YouTube together (YouTube as local script only) |

---

## Schedule Mode Flags

### `--schedule --week <N>`

Generate posts from week N of your content calendar (`content_calendar.py`).

**Required:** `--week` must be specified

**Example:**

```bash
# Generate posts for week 1
python main.py --schedule --week 1

# Generate for week 2, X channel
python main.py --schedule --week 2 --channel x

# Dry-run for week 3
python main.py --schedule --week 3 --dry-run
```

**How it works:**

- Loads content topics from `content_calendar.py` for the specified week
- Generates posts using persona grounding and domain knowledge
- Applies truth gate validation and confidence scoring
- Routes to Buffer queue or Ideas board based on confidence policy
- Uses configured posting slots from `.env` (`SSI_FOCUS_*` weights)

When `FLUX_CAPACITOR_ENABLED=true`, a FLUX image is rendered for each non-YouTube post after Ollama text generation completes. Art metadata (`art_avatar_status`, `art_avatar_image_path`, `art_avatar_story_path`, etc.) is attached to each post entry.

With the default `balanced` policy, low-confidence curation output is routed to Buffer Ideas for review, while medium and high confidence output is posted directly. `strict` makes Ideas more likely and can block low-confidence output; `draft-first` sends everything to Ideas.

---

## Curate Mode Flags

### `--curate`

Fetch RSS articles, filter by keywords, rank by relevance and acceptance priors, generate commentary, and route to Buffer Ideas or scheduled posts. When `FLUX_CAPACITOR_ENABLED=true`, a FLUX art avatar is rendered for each non-YouTube, non-all-channel idea after generation.

**Example:**

```bash
# Curate articles → Buffer Ideas (default)
python main.py --curate

# Curate articles → scheduled posts
python main.py --curate --type post

# Curate with classification
python main.py --curate --classify

# Curate with learning (fast mode, no generation)
python main.py --curate --learn

# Curate with everything (classify, learn, generate)
python main.py --curate --classify --learn --type post
```

### `--type <type>`

Control where curated content is routed. Options: `idea` (default), `post`

**Default:** `idea` (sends to Buffer Ideas for manual review)

**Important:** The confidence policy still applies. Under the default `balanced` policy, low-confidence content is routed to Ideas even if `--type post` is requested. Medium and high confidence content can be posted directly.

**Example:**

```bash
# Route to Buffer Ideas (default)
python main.py --curate

# Route directly to Buffer queue
python main.py --curate --type post
```

### `--classify`

Auto-classify articles via Model2Vec during curation. Attaches primary category and SSI component mapping to each article.

**Requires:** `pip install model2vec`

**Example:**

```bash
python main.py --curate --classify
```

**What it does:**

- Classifies each article into one of 10 default categories + custom categories
- Maps category to SSI component (`establish_brand`, `find_right_people`, etc.)
- Uses category for article ranking and SSI component alignment
- Shows category alignment score in `--dot-report` output

**Note:** Set `CURATE_CLASSIFY=true` in `.env` to auto-classify on every `--curate` run (equivalent to always passing `--classify`).

### `--learn`

Extract and persist knowledge from curated articles into `extracted_knowledge.json`.

**Example:**

```bash
# Fast learn-only (no generation)
python main.py --curate --learn

# Preview + learn (dry-run)
python main.py --curate --learn --dry-run

# Live + learn (generate and push to Buffer)
python main.py --curate --learn --type post
```

**Three modes:**

1. **Fast learn-only** (`--curate --learn`, no `--dry-run`) — Fetches all RSS articles and runs knowledge extraction on each one, skipping generation, confidence scoring, and Buffer entirely. No sleep delays between articles. Use this to bulk-load the knowledge base as fast as possible.

2. **Preview + learn** (`--curate --learn --dry-run`) — Extracts knowledge AND generates posts in dry-run mode (nothing pushed to Buffer). Shows what would be generated.

3. **Live + learn** (`--curate --learn` without `--dry-run`) — Generates and pushes posts to Buffer while also extracting knowledge from each article.

**Note:** When `--learn` is active, the normal 5-post cap is bypassed — every relevant article found across all feeds is processed (e.g., 60+ articles in one pass).

### `--confidence-policy <policy>`

Override the default confidence routing policy. Options: `balanced`, `strict`, `draft-first`

**Default:** Uses `AVATAR_CONFIDENCE_POLICY` from `.env` (default: `balanced`)

**Example:**

```bash
# Use strict policy (more content goes to Ideas)
python main.py --curate --confidence-policy strict
```

**Policy descriptions:**

- `balanced` — Normal threshold for Ideas vs direct posting
- `strict` — Higher bar, more content goes to Ideas for review
- `draft-first` — Everything goes to Ideas, nothing auto-scheduled

---

## Console Mode Flags

### `--console`

Open an interactive persona chat with deterministic grounding for factual project, career, and domain knowledge queries.

**Example:**

```bash
# Basic console mode
python main.py --console

# Console with DoT verification
python main.py --console --verify

# Console with avatar explanations
python main.py --console --avatar-explain

# Console with DoT reports
python main.py --console --dot-report

# Console with all diagnostic modes
python main.py --console --verify --avatar-explain --dot-report
```

**Console commands:**

| Command            | Description                                                                                      |
| ------------------ | ------------------------------------------------------------------------------------------------ |
| `/help`            | Display all available commands                                                                   |
| `/reset`           | Clear conversation history                                                                       |
| `/reload`          | Re-read persona graph, domain packs, and extracted_knowledge.json                                |
| `/exit` or `/quit` | Exit console mode                                                                                |
| `/verify`          | Toggle DoT + similarity verification on/off                                                      |
| `/avatar-explain`  | Toggle avatar-explain report (evidence IDs and grounding summary) on/off                         |
| `/dot-report`      | Toggle Derivative of Truth report (truth gradient and uncertainty) on/off                        |
| `/graph-stats`     | Show knowledge graph statistics plus domain-knowledge profiles for both Sam and Rei               |
| `/katzilla <query>`| Show deterministic external evidence citations for a query                                       |
| `/rei` or `/rei-toei` | Switch to Rei Toei music avatar mode                                                          |
| `/art [topic]`     | Render FLUX art avatar from the most recent AI reply in this session. Optional topic hint narrows the visual prompt. |

`/art` always uses the previous assistant message in the current console session as source text. If you have not generated an AI reply yet, ask a question or produce a response first, then run `/art` with an optional topic hint.

The image prompt is then influenced by the active FLUX style preset, the `FLUX_CAPACITOR_STYLE_SYSTEM_PROMPT`, and any optional realism hint or knowledge context. There is no separate art persona graph.

`/graph-stats` now prints three sections in one report:

1. Core graph metrics (node + edge counts)
2. Node-type distribution
3. Domain knowledge profiles for both personas.
Sam profile: merged totals across `domain_knowledge.json` and any `domain_knowledge_*.json` packs (domains, facts, relationships).
Rei profile: structural summary of `rei_toei_domain_knowledge.json` (sections, dict key volume, list item volume, and top sections).

**Query routing:**

Console mode intelligently routes queries to the appropriate subsystem:

1. **Explicit file name requests** → Deterministic citation (raw facts from data/avatar directory)
   - Triggers: `persona_graph`, `extracted_knowledge`, `domain_knowledge`, `narrative_memory`

2. **"From your learned knowledge"** → Use latest 5 extracted knowledge as context (or search)
   - Triggers: "from your learned knowledge", "based on what you learned"
   - **Search mode**: "search your learned knowledge" performs keyword-based search

3. **Everything else** → LLM with graph-enhanced retrieval (default)
   - Uses hybrid fact ranking: 70% BM25 + 20% graph proximity + 10% claim support
   - Natural AI responses grounded in your knowledge base

See [Usage Guide](usage-schedule-curate-console.md) for detailed console mode documentation.

### `--verify`

Enable inline truth score after every AI-generated reply in console mode. Shows DoT gradient and fact-pool similarity.

**Default:** OFF (DoT scanning and similarity checks disabled in console mode)

**Example:**

```bash
python main.py --console --verify
```

**Output:**

```
Sam> [reply text]
  ● DoT 0.82  fact sim 0.71
```

Symbol color reflects DoT score:

- `●` green (≥ 0.75 — well-grounded)
- `◑` yellow (≥ 0.45 — moderate)
- `○` red (< 0.45 — weakly supported)

---

## Reporting and Diagnostic Flags

### `--avatar-explain`

Show evidence IDs and grounding summary after each generation. Works with `--schedule`, `--curate`, and `--console`.

**Example:**

```bash
python main.py --schedule --week 1 --avatar-explain
python main.py --curate --avatar-explain
python main.py --console --avatar-explain
```

**Output:**

Shows which persona facts, domain facts, and extracted knowledge grounded each post.

### `--dot-report`

Show Derivative of Truth (truth gradient, evidence, uncertainty) report for every generated post or curated idea.

**Example:**

```bash
python main.py --schedule --week 1 --dot-report
python main.py --curate --dot-report
python main.py --console --dot-report
```

**Output:**

- Truth gradient score (0-1)
- Evidence type breakdown (persona, domain, extracted)
- Reasoning quality score
- Source credibility score
- Token overlap score
- Uncertainty estimate

When combined with `--classify`, also shows category alignment validation score.

### `--avatar-learn-report`

Print learning report from captured moderation events and exit. Shows which sources and topics are most effective.

**Example:**

```bash
python main.py --avatar-learn-report
```

**Output:**

- Acceptance priors per source
- Acceptance priors per topic
- Acceptance priors per SSI component
- Truth gate removal statistics
- Confidence routing statistics

---

## Classification and Category Management

### `--list-categories`

List all available Model2Vec categories (10 default + any custom) with descriptions and SSI component mapping.

**Example:**

```bash
python main.py --list-categories
```

**Output:**

- Category name
- Description
- SSI component mapping
- Whether it's a default or custom category

### `--add-category <name> <description> <ssi_component>`

Add a custom classification category. Category is immediately available for `--classify` runs.

**Arguments:**

- `name` — Category name (e.g., "Government Tech")
- `description` — Category description (e.g., "Public sector AI, digital government, and civic technology")
- `ssi_component` — One of: `establish_brand`, `find_right_people`, `engage_with_insights`, `build_relationships`

**Example:**

```bash
python main.py --add-category 'Government Tech' 'Public sector AI, digital government, and civic technology' engage_with_insights
```

### `--remove-category <name> [<name>...]`

Remove one or more custom categories. Default categories cannot be removed.

**Example:**

```bash
# Remove single category
python main.py --remove-category 'Government Tech'

# Remove multiple categories
python main.py --remove-category 'Government Tech' 'Open Source'
```

---

## SSI Tracking and Reporting

### `--save-ssi <brand> <find> <engage> <build>`

Record today's LinkedIn SSI scores for tracking over time.

**Arguments:**

- `brand` — "Establish your professional brand" score (0-25)
- `find` — "Find the right people" score (0-25)
- `engage` — "Engage with insights" score (0-25)
- `build` — "Build relationships" score (0-25)

**Example:**

```bash
python main.py --save-ssi 10.49 9.69 11.0 12.15
```

**Storage:**

Scores are saved to `data/ssi_tracker.jsonl` with timestamp.

### `--report`

Generate SSI tracking report showing score trends over time.

**Example:**

```bash
python main.py --report
```

**Output:**

- Current scores per pillar
- Score changes over time
- Recommendations for which pillar to focus on

---

## Reconcile Mode

### `--reconcile`

Compare Buffer-published posts against `data/selection/generated_candidates.jsonl` using exact Buffer post ID, article URL, or Jaccard token similarity.

**Example:**

```bash
python main.py --reconcile
```

**How it works:**

- Matches candidates become `selected=True`
- Older unmatched candidates become `selected=False`
- These labels feed Beta-smoothed acceptance priors for future curation ranking

**Note:** Run this periodically (e.g., weekly) to keep selection learning up-to-date.

---

## Database Migration

### Database Migration (Python Module)

Migrate existing JSON/JSONL data to PostgreSQL database.

**Example:**

```bash
# Migrate all data (requires DATABASE_ENABLED=true in .env)
python -m services.database.migrate_data

# Dry-run mode (preview only)
python -m services.database.migrate_data --dry-run
```

**What it migrates:**

- Persona graph (projects, companies, skills, claims)
- Domain knowledge (facts, relationships)
- Extracted knowledge
- Narrative memory
- Candidate records
- Published records
- Moderation events
- Confidence decisions
- Truth trajectories

See [Database Integration](features/database/idea.md) for schema details.

---

## Docker Commands

When running via Docker Compose, prefix commands with `docker compose --profile core run --rm app`:

```bash
# Interactive console (TTY required)
docker compose --profile core run --rm -it app python main.py --console

# Console with verification
docker compose --profile core run --rm -it app python main.py --console --verify

# Dry-run schedule
docker compose --profile core run --rm app python main.py --schedule --week 1 --dry-run

# Curate AI news → Buffer Ideas
docker compose --profile core run --rm app python main.py --curate

# Curate with classification and learning
docker compose --profile core run --rm app python main.py --curate --classify --learn

# Record SSI scores
docker compose --profile core run --rm app python main.py --save-ssi 10.49 9.69 11.0 12.15

# Database migration
docker compose --profile core run --rm app python -m services.database.migrate_data
```

See [Docker & Deployment Guide](docker-deployment.md) for full Docker documentation.

---

## Common Workflows

### Daily Content Generation

```bash
# Generate week 1 posts, dry-run first
python main.py --schedule --week 1 --dry-run

# If satisfied, remove --dry-run to publish
python main.py --schedule --week 1
```

### Content Curation Pipeline

```bash
# Curate articles with classification → Buffer Ideas
python main.py --curate --classify

# If you want to auto-publish high-confidence posts
python main.py --curate --classify --type post --confidence-policy balanced
```

### Knowledge Base Building

```bash
# Fast bulk learning (no generation)
python main.py --curate --learn

# Or learn while generating (slower)
python main.py --curate --learn --type post
```

### Interactive Exploration

```bash
# Console mode with all diagnostic modes
python main.py --console --verify --avatar-explain --dot-report

# Or toggle modes during session with /verify, /avatar-explain, /dot-report
python main.py --console
```

### Weekly Maintenance

```bash
# Reconcile Buffer posts with candidates (update selection learning)
python main.py --reconcile

# View learning report
python main.py --avatar-learn-report

# Record SSI scores
python main.py --save-ssi 10.49 9.69 11.0 12.15

# View SSI trend report
python main.py --report
```

---

## Troubleshooting

### Command Not Found

**Problem:** `python: command not found`

**Solution:** Use `python3` on some systems:

```bash
python3 main.py --console
```

### ModuleNotFoundError

**Problem:** `ModuleNotFoundError: No module named 'services'`

**Solution:** Ensure you're running from the project root and have installed dependencies:

```bash
cd /path/to/linkedin_ssi_booster
pip install -r requirements.txt
python main.py --console
```

### Buffer API Key Missing

**Problem:** `KeyError: 'BUFFER_API_KEY'`

**Solution:** Ensure `.env` file exists and contains `BUFFER_API_KEY`:

```bash
cp .env.example .env
# Edit .env and add your Buffer API key
```

### Model2Vec Classification Failed

**Problem:** `--classify` flag causes error

**Solution:** Install Model2Vec dependency:

```bash
pip install model2vec
```

Or disable classification in `.env`:

```bash
MODEL2VEC_ENABLED=false
CURATE_CLASSIFY=false
```

### Console Mode Not Interactive

**Problem:** Console mode doesn't accept input in Docker

**Solution:** Add `-it` flags for TTY:

```bash
docker compose --profile core run --rm -it app python main.py --console
```

---

## Rei Toei Music Generation

**Status:** Phase 1E Partial — CLI flags added, full implementation in progress

Rei Toei is the AI music avatar that transforms curated technical knowledge into original music compositions via Suno (vocal songs) and Strudel (algorithmic patterns).

### `--rei-generate`

Generate a Suno song prompt from recent extracted knowledge.

**Status:** ✅ Implemented (generates, can save, can submit to Suno when `SUNO_API_KEY` is set)

**Example:**

```bash
python main.py --rei-generate
python main.py --rei-generate --rei-theme "microservices architecture"
python main.py --rei-generate --rei-explain
```

**Current behavior:**

- Uses `--rei-theme` if provided, otherwise derives themes from extracted knowledge
- `--rei-preview` skips save/submit
- Without `--rei-preview`, saves artifact to `yt-vid-data/rei-toei/` and submits to Suno when configured

### `--rei-generate-strudel`

Generate a Strudel/Tidal Cycles algorithmic pattern instead of a Suno song.

**Status:** ✅ Implemented (generation path active)

**Example:**

```bash
python main.py --rei-generate-strudel
python main.py --rei-generate-strudel --rei-theme "async programming"
python main.py --rei-generate-strudel --rei-execute
```

**Current behavior:**

- Generates pattern from selected/matched template
- `--rei-preview` skips save/execute
- Without `--rei-preview`, persists generated pattern to `data/avatar/rei_toei_generated_patterns.jsonl`

### `--rei-theme <theme>`

Specify a custom theme for music generation (works with both `--rei-generate` and `--rei-generate-strudel`).

**Example:**

```bash
python main.py --rei-generate --rei-theme "vector databases"
python main.py --rei-generate-strudel --rei-theme "distributed systems"
```

### `--rei-explain`

Show reasoning for generation choices including evidence IDs and grounding facts.

**Example:**

```bash
python main.py --rei-generate --rei-explain
python main.py --rei-generate-strudel --rei-theme "kubernetes" --rei-explain
```

### `--rei-preview`

Preview generated music without saving to library or executing patterns.

**Example:**

```bash
python main.py --rei-generate --rei-preview
python main.py --rei-generate-strudel --rei-preview
```

### `--rei-execute`

Execute generated Strudel pattern via MCP agent (requires `--rei-generate-strudel`).

**Example:**

```bash
python main.py --rei-generate-strudel --rei-execute
python main.py --rei-generate-strudel --rei-theme "neural networks" --rei-execute
```

**Note:** Execution uses WebSocket first (`STRUDEL_WS_URL`, default `ws://localhost:4321`) and falls back to stdio MCP execution when WebSocket is unavailable.

Strudel syntax note: use workshop-style `sound(...)` / `.sound(...)` forms. Legacy aliases `s(...)` and `.s(...)` are rejected by runtime guardrails.

For deeper implementation notes, see the troubleshooting section in `docs/rei-toei-customization.md`.

### Console Mode Alternative

For full Rei Toei functionality, use console mode:

```bash
python main.py --console
# Then type: /rei-toei or /rei
```

**Console commands:**

- `/rei-toei` or `/rei` — Switch to Rei Toei music avatar mode
- General conversation with Rei about music, technical concepts, or knowledge
- Request Strudel pattern generation: "generate a strudel pattern about microservices"
- Request Suno song generation: "write a song about async programming"

---

## See Also

- [Usage Guide](usage-schedule-curate-console.md) — Detailed workflow documentation
- [Environment Variables Reference](environment-variables.md) — All configuration options
- [Docker & Deployment Guide](docker-deployment.md) — Docker-specific commands
- [Persona and Avatar Intelligence](persona-and-avatar.md) — Grounding and learning concepts
- [Rei Toei Feature Plan](features/rei-toei/plan.md) — Complete implementation roadmap
