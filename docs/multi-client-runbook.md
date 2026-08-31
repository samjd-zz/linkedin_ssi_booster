# Multi-Client Runbook (Simple .env-per-client workflow)

This runbook is the lowest-complexity way to run multiple client accounts in one codebase.

Use one env file per client, load it explicitly per command, and isolate any file/DB outputs so client data never mixes.

## 1) Create one env file per client

Recommended naming:

- `.env.client-acme`
- `.env.client-beta`

Start each from `.env.example`.

Fast scaffold command (recommended):

```bash
scripts/create-client.sh acme
scripts/create-client.sh beta
```

This creates:

- `.env.client-acme` (or matching slug)
- `data/client-acme/`
- `data/client-acme/avatar/` (persona_graph.json, domain_knowledge.json, narrative_memory.json, extracted_knowledge.json — seeded from the `*.example.json` templates)
- `yt-vid-data/client-acme/`

**Important:** edit `data/client-acme/avatar/persona_graph.json` with the client's real name, projects, and facts before generating content — the seeded file is a blank template, not Shawn's persona.

## 2) Required isolation settings per client

For each client env file, set unique values for:

- `BUFFER_API_KEY`
- `IDEAS_CACHE_PATH`
- `GENERATED_CONTENT_DIR`
- `AVATAR_DATA_DIR` (persona graph, domain knowledge, narrative memory, extracted knowledge — see below)
- Any selection/learning file paths if you override defaults
- `DATABASE_URL` or `POSTGRES_DB` (only when `DATABASE_ENABLED=true`)
- Channel IDs and per-channel footers

Example path pattern:

- Client A: `IDEAS_CACHE_PATH=data/client-acme/published_ideas_cache.json`
- Client B: `IDEAS_CACHE_PATH=data/client-beta/published_ideas_cache.json`

`AVATAR_DATA_DIR` controls where the persona/avatar files live (default: `data/avatar`). Without a unique value per client, every client shares the same `persona_graph.json` and narrative memory — set it to `data/client-<name>/avatar` for each client. `scripts/create-client.sh` sets this automatically.

## 2.1) Required content settings per client (curation + learning)

`--curate` and `--learn` are also driven entirely by env vars, so each client needs their own niche configured or they'll curate/learn from Shawn's defaults:

- `CURATOR_RSS_FEEDS` — JSON array of the client's own RSS sources (leave unset to inherit built-in defaults, which are Shawn's feeds)
- `CURATOR_KEYWORDS` — comma-separated niche keywords used to filter articles and score grounding facts
- `CONSOLE_GROUNDING_TECH_KEYWORDS` — technical keyword set used for fact retrieval scoring
- `PERSONA_SYSTEM_PROMPT` and `SSI_ESTABLISH_BRAND` / `SSI_FIND_RIGHT_PEOPLE` / `SSI_ENGAGE_WITH_INSIGHTS` / `SSI_BUILD_RELATIONSHIPS` — the client's voice and brand pillars

`--learn` writes extracted facts to `${AVATAR_DATA_DIR}/extracted_knowledge.json`, so once `AVATAR_DATA_DIR` and `CURATOR_RSS_FEEDS`/`CURATOR_KEYWORDS` are set per client, learning is automatically scoped to that client — no extra wiring needed.

## 3) Keep shared, safe defaults the same

Usually keep these common unless a client needs special behavior:

- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL`
- Truth gate thresholds
- spaCy/model2vec toggles

## 4) Add per-client directories once

Create per-client data/output folders before first run:

```bash
mkdir -p data/client-acme data/client-beta
mkdir -p yt-vid-data/client-acme yt-vid-data/client-beta
```

## 5) Run commands with the correct env file

Always load the client env in the same command line as the run.

Core profile examples:

```bash
set -a; source .env.client-acme; set +a; docker compose --profile core run --rm app python main.py --curate --channel linkedin,x,bluesky --type post --reconcile
```

```bash
set -a; source .env.client-beta; set +a; docker compose --profile core run --rm app python main.py --schedule --week 1 --channel linkedin --type post
```

Local venv examples:

```bash
set -a; source .env.client-acme; set +a; source .venv/bin/activate && python main.py --curate --dry-run
```

```bash
set -a; source .env.client-beta; set +a; source .venv/bin/activate && python main.py --generate --dry-run
```

## 5.1) Preferred helper scripts (recommended)

Two helper scripts are now included:

- `scripts/create-client.sh`
- `scripts/client-env.sh`
- `scripts/run-client.sh`
- `scripts/run-client-curate.sh`

Quick examples:

```bash
scripts/client-env.sh acme
scripts/client-env.sh .env.client-beta
```

```bash
scripts/run-client.sh acme -- --curate --dry-run
scripts/run-client.sh beta -- --schedule --week 1 --channel linkedin --type post
scripts/run-client.sh acme --profile full -- --rei-generate --rei-theme "spec driven development"
scripts/run-client.sh acme --local -- --generate --dry-run
```

Preset wrapper for curation workflow:

```bash
scripts/run-client-curate.sh acme
scripts/run-client-curate.sh acme --live --type post --reconcile
scripts/run-client-curate.sh beta --channel linkedin,youtube --classify
scripts/run-client-curate.sh acme --local -- --dot-report --avatar-explain
```

Behavior:

- Client name `acme` resolves to `.env.client-acme`
- You can also pass a direct env file path
- `run-client.sh` defaults to Docker mode with `--profile core`
- Add `--local` to run with `.venv/bin/python` instead of Docker
- `run-client-curate.sh` defaults to `--curate --dry-run --type idea` for safer day-to-day use

## 6) Quick safety checks before each run

Run these checks after loading a client env:

```bash
echo "$BUFFER_API_KEY" | sed 's/./*/g' | cut -c1-8
echo "$IDEAS_CACHE_PATH"
echo "$GENERATED_CONTENT_DIR"
echo "$AVATAR_DATA_DIR"
echo "$DATABASE_ENABLED"
```

If database mode is enabled, also check:

```bash
echo "$DATABASE_URL"
```

## 7) Optional helper aliases (safe alternative)

Because footers and prompts are often multiline, avoid `source .env...` in custom aliases.

If you want shortcuts, wrap the safe scripts instead:

```bash
alias run_acme_curate='scripts/run-client-curate.sh acme'
alias run_beta_curate='scripts/run-client-curate.sh beta'
```

Then run:

```bash
run_acme_curate
run_beta_curate --live --type post --reconcile
```

## 8) Client onboarding checklist

For each new client:

1. Copy `.env.example` to a new `.env.client-<name>` file.
2. Set client-specific keys and channel IDs.
3. Set unique `IDEAS_CACHE_PATH`, `GENERATED_CONTENT_DIR`, and `AVATAR_DATA_DIR`.
4. Fill in `data/client-<name>/avatar/persona_graph.json` with the client's real name, projects, and facts.
5. Set `CURATOR_RSS_FEEDS`, `CURATOR_KEYWORDS`, and `PERSONA_SYSTEM_PROMPT`/`SSI_*` prompts for the client's niche and voice.
6. If DB is enabled, set unique DB name/URL.
7. Create folders with `mkdir -p` (or use `scripts/create-client.sh`, which does all of the above).
8. Run one `--dry-run` command and verify output path and behavior.

## 9) Common failure modes

- Wrong client env loaded: posts go to wrong Buffer account.
- Shared cache path: duplicate detection leaks across clients.
- Shared output dir: generated assets mixed across clients.
- Shared `AVATAR_DATA_DIR`: persona graph, narrative memory, and learned facts leak across clients.
- Shared DB in multi-client mode: history/learning contamination.

## 10) Minimal standard to stay safe

If you only remember one rule: never run without explicitly loading the client env first, and never reuse cache/output/database paths across clients.
