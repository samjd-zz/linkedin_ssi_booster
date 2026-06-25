# GitHub Copilot Instructions — LinkedIn SSI Booster

## Project Purpose

Python automation tool that generates and schedules LinkedIn posts via the Buffer API to improve Shawn's LinkedIn Social Selling Index (SSI) across all four components. Uses a locally-run Ollama LLM, a truth gate, a Derivative of Truth scoring framework, and a continual learning pipeline to produce grounded, persona-consistent content.

## Tech Stack

- **Language**: Python 3.12+ (3.12.2 in production)
- **LLM**: Ollama (local) via `services/ollama_service.py` — primary model `gemma4:e4b`, fallback `qwen3.5:9b`
- **Database**: PostgreSQL 16 Alpine (optional dual-write mode) — SQLAlchemy 2.0+ ORM, 17 tables
- **NLP**: spaCy `en_core_web_md` — NER, semantic similarity, fact extraction (`services/spacy_nlp.py`)
- **Classification**: Model2Vec (`minishlab/potion-base-8M`) — static embedding-based text classification
- **Logic/Inference**: PLN (Probabilistic Logic Networks) — `services/pln_inference.py`
- **Voice/TTS**: Wyoming Piper — local neural TTS on port 10200 (Docker service)
- **Image Gen**: FLUX.1-schnell (GGUF quantized) — local GPU image generation (full profile only)
- **Music Gen**: Strudel MCP server — live-coding music via stdio JSON-RPC (`STRUDEL_MCP_COMMAND`)
- **Social Scheduling**: Buffer GraphQL API — all calls go through `services/buffer_service.py`
- **RSS Parsing**: `feedparser` + `trafilatura` — used in `services/content_curator/_rss_fetcher.py`
- **Graph / Retrieval**: NetworkX (`services/knowledge_graph.py`), BM25 + hybrid retrieval (`services/hybrid_retriever.py`)
- **Scheduling**: `APScheduler` + `pytz` (America/Toronto timezone)
- **Config**: `python-dotenv` — secrets from `.env` only

## Package Structure

```
linkedin_ssi_booster/
├── main.py                        # CLI entrypoint (argparse)
├── scheduler.py                   # Optimal posting-time logic
├── content_calendar.py            # 4-week topic list
├── services/
│   ├── buffer_service.py          # Buffer GraphQL wrapper
│   ├── ollama_service.py          # Ollama LLM wrapper (summarise, generate)
│   ├── hybrid_retriever.py        # BM25 + KG hybrid retrieval + persona reranking
│   ├── knowledge_graph.py         # NetworkX graph manager
│   ├── github_service.py          # GitHub repo context enrichment (cached 24h)
│   ├── spacy_nlp.py               # spaCy: themes, similarity, sentiment
│   ├── ssi_tracker.py             # SSI score tracking + report
│   ├── shared.py                  # Shared env flags (AVATAR_LEARNING_ENABLED, etc.)
│   ├── console_grounding/         # Truth gate + deterministic grounding
│   │   ├── _config.py             # env/config knobs and keyword defaults
│   │   ├── _models.py             # ProjectFact, QueryConstraints, TruthGateMeta
│   │   ├── _profile_parser.py     # PROFILE_CONTEXT bullet parsing
│   │   ├── _retrieval.py          # deterministic retrieval + grounded replies
│   │   ├── _gate_helpers.py       # BM25/regex helpers, false-positive filters
│   │   └── _truth_gate.py         # 4-layer truth gate: BM25 → DoT → spaCy sim → NER
│   ├── content_curator/           # RSS curation pipeline
│   │   ├── curator.py             # ContentCurator class — orchestrates full pipeline
│   │   ├── _config.py             # RSS feeds, keywords, SSI weights
│   │   ├── _rss_fetcher.py        # fetch_relevant_articles(), fetch_article_text()
│   │   ├── _text_utils.py         # truncate_at_sentence(), hashtag helpers
│   │   ├── _evidence_paths.py     # EvidencePath builders for DoT scoring
│   │   ├── _ssi_picker.py         # topic signal + adaptive SSI component selection
│   │   └── _grounding.py          # grounding keyword/tag loaders
│   ├── avatar_intelligence/       # Persona graph, confidence, learning, memory
│   │   ├── _paths.py              # PERSONA_GRAPH_PATH and sibling constants
│   │   ├── _models.py             # AvatarState, EvidenceFact, ConfidenceResult, etc.
│   │   ├── _loaders.py            # schema validators + file loaders
│   │   ├── _normalizers.py        # evidence/domain/extracted fact normalization
│   │   ├── _retrieval.py          # BM25 + fallback evidence retrieval
│   │   ├── _grounding.py          # grounding context builders
│   │   ├── _learning.py           # moderation event capture + learning report
│   │   ├── _confidence.py         # confidence scoring + publish-mode routing
│   │   ├── _narrative.py          # narrative memory update + continuity context
│   │   └── _extraction.py         # spaCy fact extraction + save helpers
│   ├── derivative_of_truth/       # Truth gradient scoring framework
│   │   ├── _models.py             # EvidencePath, TruthGradientResult
│   │   ├── _scoring.py            # 4-term gradient formula
│   │   └── _reporting.py          # CLI report formatters (format_truth_gradient_report)
│   └── selection_learning/        # Article ranking + feedback loop
│       ├── _constants.py          # paths and scoring thresholds
│       ├── _models.py             # CandidateRecord, PublishedRecord, FeaturePrior
│       ├── _storage.py            # JSONL read/append/rewrite helpers
│       ├── _text.py               # hashing, tokenization, Jaccard, matching
│       ├── _logging.py            # candidate logging + NLP enrichment
│       ├── _published.py          # published-cache upsert helpers
│       ├── _reconcile.py          # Buffer SENT reconciliation + labeling
│       ├── _priors.py             # Beta-smoothed acceptance priors + boosts
│       ├── _ranking.py            # article ranking: relevance + freshness + priors
│       └── _feedback.py           # explicit user feedback capture/application
├── data/
│   ├── avatar/
│   │   ├── persona_graph.json     # persona facts, projects, companies, claims
│   │   ├── domain_knowledge_*.json # domain knowledge packs (auto-merged at load)
│   │   └── narrative_memory.json  # rolling narrative memory (max 200 items)
│   └── selection/                 # JSONL candidate + published logs
├── agents/
│   ├── buffer_mcp_agent.py        # Buffer MCP agent — natural language Buffer API
│   └── strudel_mcp_agent.py       # Strudel music generation agent
├── scripts/
│   ├── download-flux1-schnell-Q4_K_S.sh # FLUX model download script
│   └── init-db.sql                # PostgreSQL schema DDL
├── tests/                         # pytest suite (565 tests, all passing)
└── docs/                          # architecture, features, usage docs
```

## Import Conventions

- Always use absolute imports from the project root: `from services.X import Y`
- Scripts are run from the project root: `python main.py --curate`
- Never add `sys.path` manipulation inside source files

## Key Architecture Concepts

**Truth Gate** (`services/console_grounding/_truth_gate.py`): 4-layer filter applied to every generated sentence:

1. BM25 evidence scoring vs article + persona facts (`TRUTH_GATE_BM25_THRESHOLD`, default 0.75)
2. Per-sentence Derivative of Truth gradient (Jaccard overlap-enriched 4-term formula)
3. spaCy semantic similarity floor for numeric/org/year sentences (`TRUTH_GATE_SPACY_SIM_FLOOR`, default 0.10)
4. spaCy NER ORG-name validation with false-positive filters (concept abbrevs, project substrings, event keywords)

**Derivative of Truth** (`services/derivative_of_truth/`): Scores the whole post against all evidence paths. `gradient = base_cred × (1 − uncertainty_penalty)`. High cred + low token overlap → credible but off-topic → penalty applied.

**Confidence Scoring** (`services/avatar_intelligence/_confidence.py`): Publish-safety score (0.0–1.0), starts at 1.0 with deductions for truth-gate removals, unsupported claims, channel length pressure, and narrative repetition. Routes posts via `AVATAR_CONFIDENCE_POLICY` (balanced/strict/draft-first).

**Continual Learning**: `--learn` flag triggers `extract_and_append_knowledge()` per article, writing `ExtractedFact` objects to `data/avatar/`. When `--learn` is active, the `max_ideas` cap is bypassed so all relevant articles are processed.

**Persona Graph** (`data/avatar/persona_graph.json`): Source of truth for all personal claims, projects, companies, and years. Domain knowledge packs (`domain_knowledge_*.json`) are auto-merged at load time.

## Code Conventions

- Type-annotate all function parameters and return types
- Use `logging.getLogger(__name__)` — never `print()` for diagnostics
- Catch specific exceptions (never bare `except:`)
- Constants → `UPPER_SNAKE_CASE` at module top
- `--dry-run` flag to preview without hitting external APIs
- All LLM calls go through `services/ollama_service.py` — do not scatter model calls across the codebase
- All Buffer API calls go through `services/buffer_service.py`

## File Size & Modularization (CRITICAL)

**Maximum file size: 300-500 lines per `.py` file**

- Any service module exceeding 500 lines MUST be refactored into a package structure
- Use package-based architecture with private modules (underscore prefix) + public API via `__init__.py`
- **Pattern to follow**: `avatar_intelligence/`, `console_grounding/`, `content_curator/`, `selection_learning/`, `derivative_of_truth/`, `rei_toei/`
- **Standard package layout**:
  - `_config.py` — configuration, constants, enums
  - `_models.py` — dataclasses, type definitions
  - `_loaders.py` — file I/O, data loading functions
  - `_<domain>.py` — domain-specific logic (e.g., `_retrieval.py`, `_scoring.py`, `_pipeline.py`)
  - `service.py` or main orchestration module — high-level API
  - `__init__.py` — re-export public API for backward compatibility
- Each module should have a single, focused responsibility
- If a module approaches 500 lines, break it down further by extracting helpers, utilities, or sub-pipelines
- **No monolithic files** — maintainability and testability are top priorities
- When refactoring, maintain backward compatibility via re-exports in `__init__.py`

## Secret Management

- All secrets via `os.getenv()` after `load_dotenv()`
- Required: `BUFFER_API_KEY`, `OLLAMA_BASE_URL`
- Optional (database): `DATABASE_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `DATABASE_ENABLED`
- Optional (image gen): `CIVITAI_API_KEY`, `FLUX_MODEL_PATH`
- Optional (voice): `CONSOLE_USE_VOICE`, `WYOMING_PIPER_HOST`, `WYOMING_PIPER_PORT`
- Optional (music): `STRUDEL_MCP_COMMAND`
- Optional (classification): `MODEL2VEC_ENABLED`, `CURATE_CLASSIFY`
- Never suggest hardcoding keys or committing `.env`

## SSI Components (context for prompt suggestions)

| Key                    | Description                                               |
| ---------------------- | --------------------------------------------------------- |
| `establish_brand`      | Share builds, lessons, technical depth                    |
| `find_right_people`    | Tools, communities, questions that attract right audience |
| `engage_with_insights` | Summarise/react to AI news with a bold take               |
| `build_relationships`  | Behind-the-scenes stories, honest lessons                 |

## Preferences

- Concise, idiomatic Python — avoid unnecessary abstraction
- Prefer `pathlib.Path` over `os.path` for file operations
- Raise `ValueError` for invalid config at init time (fail fast)
- Keep Buffer and Ollama calls in their respective service classes — do not scatter API calls across the codebase

## After Every Code Change

- Always run `source .venv/bin/activate && python -m py_compile <changed_files>` immediately after editing any `.py` file
- Fix all syntax errors before considering a task complete
- Example: `source .venv/bin/activate && python -m py_compile services/content_curator/curator.py services/console_grounding/_gate_helpers.py`
- **Always run tests with the project venv activated and `python -m pytest`** — never use a bare `pytest` binary or `.venv/bin/pytest` directly:
  ```bash
  source .venv/bin/activate && python -m pytest -q tests/test_<module>.py
  source .venv/bin/activate && python -m pytest -q   # full suite
  ```
- **Write unit tests** for every new module or significant new function — place them in `tests/test_<module_name>.py` following the patterns in `tests/test_learning_report.py` and `tests/test_confidence_scoring.py`. Tests must pass before a task is considered complete.
- **Update `docs/testing-and-dev.md`** whenever the test count changes (current: 766 passed, 2 skipped) or new behaviour is covered — keep the test table and count in sync.
- **Update README.md** whenever you change how the tool is configured, how a feature works, or what env vars are required — keep the docs in sync with the code.
- **Update relevant feature docs** in `docs/features/` when implementing new subsystems.

## Version & Test Status

- **Version**: alpha-v0.0.3.3
- **Test Count**: 768 collected; 766 passed, 2 skipped, 0 failed
- **Test Isolation**: Database tests use in-memory SQLite for speed and isolation

## Docker & Deployment

- **Profiles**: Use `--profile core` for standard operations (Ollama + Piper TTS + app), `--profile full` to include FLUX image generation (requires RTX 3060 12GB+)
- **Run script**: Use `bash run.sh --profile core up -d` to automatically handle PulseAudio passthrough (exports `USER_UID`)
- **Database**: PostgreSQL integration is optional — set `DATABASE_ENABLED=true` in `.env` to enable dual-write mode
- **Voice output**: Requires PulseAudio passthrough — `run.sh` handles socket mounting automatically
- **GPU passthrough**: All GPU services use `deploy.resources.reservations.devices` — requires NVIDIA Container Toolkit on Linux
- **OLLAMA_BASE_URL**: Automatically overridden to `http://ollama:11434` in `docker-compose.yml` — do not change in `.env` for Docker use

## Key CLI Flags & Features

**Classification & Learning:**

- `--classify` — Auto-classify articles via Model2Vec during curation
- `--list-categories` — Show all available classification categories (10 default + custom)
- `--add-category NAME DESC SSI_COMPONENT` — Add custom category
- `--remove-category NAME [NAME...]` — Remove custom categories
- `--learn` — Extract and persist knowledge from curated articles to `extracted_knowledge.json`

**Explainability & Reports:**

- `--dot-report` — Show Derivative of Truth report (truth gradient, evidence, uncertainty) for every post
- `--avatar-explain` — Show evidence IDs and grounding summary after each generation
- `--avatar-learn-report` — Print learning report from captured moderation events
- `--verify` — Enable DoT + similarity verification in console mode (off by default)

**Console Mode:**

- `--console` — Interactive persona chat with deterministic grounding
- `--console --verify` — Enable inline truth scoring (DoT + fact-pool similarity) after AI replies
- `/verify`, `/avatar-explain`, `/dot-report` — Toggle diagnostic modes during console session
- `/reload` — Re-read all avatar files (persona graph, domain knowledge, extracted knowledge) without restarting

**Database:**

- PostgreSQL integration (Phase 4 complete) — 17 tables, dual-write mode, SQLAlchemy 2.0+
- `python -m services.database.migrate_data` — Migrate existing JSON/JSONL data to database
- Set `DATABASE_ENABLED=false` in `.env` to revert to file-based storage (non-breaking rollback)
