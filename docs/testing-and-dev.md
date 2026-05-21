# Testing and Development

The project ships with a comprehensive pytest suite covering the Avatar Intelligence engine, grounding and evidence retrieval, confidence scoring, continual learning (NLP-extracted knowledge), curation, spaCy NLP, integration flags, persona graph retrieval, and selection learning.

## Running tests

```bash
pip install pytest
pytest tests/ -v
```

For tests that depend on environment variables such as `BUFFER_API_KEY`, the README recommends loading `.env` values with `python-dotenv`, including `python -m dotenv run -- python -m pytest tests/test_buffer_service.py -v`.

Latest full-suite run command (excluding Buffer service tests):

```bash
python -m pytest -q tests/ --ignore=tests/test_buffer_service.py
```

## Test coverage and results (latest)

### Summary

| Total tests | Passed | Failed |
| ----------- | ------ | ------ |
| 654         | 654    | 0      |

**Latest run:** May 20, 2026 (Python 3.12.3, pytest 9.0.3)

**Test breakdown:** 565 original + 89 Rei Toei (Phases 1A-1E: 27 foundation + 25 Suno + 20 Strudel + 9 console + 8 CLI flags)

All tests pass. The suite covers:

- Knowledge Graph subsystem (NetworkX)
- Hybrid BM25+graph retrieval and persona-aware reranking (now active in production via `ContentCurator`)
- GitHub repo context enrichment (`github_service.py` now wired into `main.py`, console mode, and curation)
- **Model2Vec text classification** — Fast static embedding-based classification using minishlab/potion-base-8M, with 10 default categories mapped to SSI components and custom category support. Includes graceful degradation tests, batch classification, category management, singleton pattern, cosine similarity utilities, and integration with RSS fetcher and selection learning ranking. **Phase 5 advanced features**: custom category CLI (`--add-category`, `--list-categories`, `--remove-category`), category-based persona retrieval (`retrieve_evidence(category_filter=...)`), category performance analytics (`_category_analytics.py`), category insights in `--avatar-learn-report`, and truth gate category alignment validation (`validate_category_alignment()` shown in `--dot-report --classify`).
- **Derivative of Truth framework** (truth gradient scoring, evidence/reasoning annotation, uncertainty logic)
- **Continual learning noise filtering pipeline** — comprehensive pre-storage sentence quality filters covering: first-person narration, adversative conjunction openers (`But`, `However`, `Yet`, `Nevertheless`), conditional tutorial fragments (`When/While/Whenever you are building…`), anthropomorphic background prose (`user never thinks about`), truncated RSS "Read more" fragments, newsletter/podcast preamble openers (including `This latest one looks at…`), newsletter promo banners (`Software Architects' Newsletter`, `things you need to know as an architect`), boilerplate article openers (including `This section covers/discusses…`), future-tense preamble teasers (`It will also cover/demonstrate/show…`), CTA/feedback boilerplate, passive advisory sentences, marketing superlative taglines, event marketing announcements, double-dash ToC blobs, section header blobs, dangling-pronoun openers and quantity references, pure URL sentences, ellipsis-truncated sentences, pipe-delimited navigation (single- and multi-pipe), HuggingFace/GitHub nav blobs, podcast preambles, scene-setters, "Here's what we" openers, "You'll learn" preambles, "We'll dive into" preambles, self-promotion sentences, camelCase mangled heading+body joins (product names like `SageMaker`/`GitHub` are exempt), table/architecture digit blobs, version-list blobs, generic fillers (no metric), bare product availability announcements, email consent-form fragments (`Enter your e-mail address … Select your country`), punctuation-start byline/changelog fragments, mid-word truncated sentences (scraper cut off page), long product-feature-list sidebar blobs (e.g. Elastic `Context engineering … Vector database … Threat protection …`), bullet-list run-ons (2+ `Be <Capital>` imperatives glued together), code-classname blobs (CamelCase identifier ≥25 chars, e.g. `JdbcChatMemoryRepositorySchemaInitializerPostgresqlTests`), and section-heading comparison questions (`Why X compared to Y?`). Filters run before spaCy extraction and deduplication.
- **Cross-URL statement deduplication** — in addition to per-source-URL SHA-256 id hashing, a normalised statement-text hash set is maintained so the same boilerplate paragraph fetched from multiple URLs (e.g. Elastic sidebar nav, InfoQ email consent form) is stored exactly once regardless of source.
- **`_is_spacy_available()` robustness fix** — `services/spacy_nlp.py` now catches `Exception` broadly (not just `ImportError`) so a missing torch `.so` in the anaconda environment no longer causes truth gate failures; `compute_similarity()` gracefully returns `0.0` and the `0.0 < sim < floor` guard ensures no sentences are incorrectly removed.
- **Console mode `/reload` command** — `_load_knowledge_state()` helper extracted from `run_console()`; `/reload` re-reads persona graph, domain packs, and `extracted_knowledge.json` mid-session without restarting. Duplicate routing block removed.
- **Truth Gate — DoT + spaCy integration upgrade** (overlap-enriched evidence paths, per-sentence DoT scoring, spaCy similarity floor, spaCy NER org-name check)
- **Truth Gate Part E — fact-pool spaCy similarity** (`fact_sim_scores` on `TruthGateMeta`; `TRUTH_GATE_FACT_SIM_FLOOR` default `0.05`; runs in all contexts including console mode; `low_fact_similarity` reason code; zero-sim exemption)
- **Truth Gate false-positive hardening** (filters concept/service ORG false positives like `S3`, `Java 21`, and `AI Q&A`; project names and aliases from `persona_graph.json` are now loaded at gate-time via `get_project_names_from_avatar_state()` — any ORG entity that is a substring of a known project name/alias is automatically skipped, e.g., `Regulatory Intelligence` → `Regulatory Intelligence Assistant`)
- **Multi-file domain knowledge loading** (`load_avatar_state()` now auto-merges `domain_knowledge_*.json` files such as Java/Python packs)
- **`content_curator` package refactor** (`services/content_curator.py` split into a proper Python package with seven focused submodules)
- **`avatar_intelligence` package refactor** (`services/avatar_intelligence.py` split into a proper Python package with ten focused submodules: `_paths`, `_models`, `_loaders`, `_normalizers`, `_retrieval`, `_grounding`, `_learning`, `_confidence`, `_narrative`, `_extraction`)
- **`console_grounding` package refactor** (`services/console_grounding.py` split into a proper Python package with focused submodules: `_config`, `_models`, `_profile_parser`, `_retrieval`, `_gate_helpers`, `_truth_gate`)
- **`selection_learning` package refactor** (`services/selection_learning.py` split into a proper Python package with focused submodules: `_constants`, `_models`, `_storage`, `_text`, `_logging`, `_published`, `_reconcile`, `_priors`, `_ranking`, `_feedback`)
- Avatar intelligence, curation, continual learning (NLP-extracted knowledge), learning, spaCy NLP, and all core automation features

**Derivative of Truth status:**

- All annotation logic, uncertainty calculation, and PLN-enhanced scoring tests pass (see `tests/test_derivative_of_truth.py`).
- Tests updated May 15, 2026 to reflect PLN-enhanced scoring (default mode since DoT+PLN integration).
- Implementation is aligned with [design.md](features/derivative-of-truth/design.md) and [plan.md](features/derivative-of-truth/plan.md).

**Truth Gate — DoT + spaCy upgrade status (April 30, 2026):**

- `EvidencePath.overlap` is now computed (Jaccard token overlap per sentence↔fact) — 4-term DoT formula is active.
- Per-sentence DoT scoring runs before the keep/remove decision; `weak_dot_gradient` is a first-class removal reason.
- spaCy `compute_similarity` floor check (`TRUTH_GATE_SPACY_SIM_FLOOR`, default `0.10`) flags numeric/org sentences with low semantic support.
- spaCy NER `ORG` extraction replaces `_ORG_NAME_RE` regex (regex fallback preserved when spaCy unavailable).
- ORG false-positive filters now skip known concept/service tokens (e.g., `S3`) and tech-version entities (e.g., `Java 21`).
- Compound tech phrases containing concept tokens (e.g., `AI Q&A`) are no longer treated as unsupported organizations.
- `TruthGateMeta` gains `dot_per_sentence_scores: list[float]` and `spacy_sim_scores: dict[str, float]`.
- Default spaCy model upgraded to `en_core_web_md` (word vectors loaded via `SPACY_MODEL` env var) — eliminates the W007 no-word-vectors warning.
- Avatar state loading now merges sibling `domain_knowledge_*.json` files (for example `domain_knowledge_java.json` and `domain_knowledge_python.json`) into one domain knowledge graph.
- **Multi-project sentence false-positive guard**: `_check_project_claim` no longer flags a keyword as falsely attributed to a project when another project co-mentioned in the same sentence already owns that keyword in its evidence (e.g., "Answer42's Spring Batch … while LinkedIn SSI Booster does X" — `spring` is not flagged against `LinkedIn SSI Booster`).
- See [idea.md](features/truth-gate-dot/idea.md) for full design rationale.

**Active production modules (as of April 30, 2026):**

| Module                                        | Status    | Integration point                                                                                                                                              |
| --------------------------------------------- | --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `services/github_service.py`                  | ✅ Active | `main.py` startup; context passed to `run_console()` and `ContentCurator` system prompt                                                                        |
| `services/model2vec_service.py`               | ✅ Active | `ContentCurator` initializes and `_rss_fetcher._attach_classifications()` applies classifications; used in `selection_learning/_ranking.py` for category boost |
| `services/hybrid_retriever.py`                | ✅ Active | `ContentCurator.__init__` bootstraps KG + `HybridRetriever`; used in `_grounding_facts_for_article()`                                                          |
| `services/ollama_service.py`                  | ✅ Active | `summarise_for_curation()` injects extracted grounding context (via `build_extracted_grounding_context`)                                                       |
| `services/content_curator/curator.py`         | ✅ Active | `ContentCurator` class — orchestrates article fetching, AI generation, confidence routing, Buffer push                                                         |
| `services/content_curator/_config.py`         | ✅ Active | RSS feeds, keywords, SSI weights/hints, env constants                                                                                                          |
| `services/content_curator/_rss_fetcher.py`    | ✅ Active | `fetch_relevant_articles()`, `fetch_article_text()`                                                                                                            |
| `services/content_curator/_ssi_picker.py`     | ✅ Active | `build_topic_signal()`, `pick_ssi_component()` — adaptive SSI component tilt from extracted facts                                                              |
| `services/content_curator/_evidence_paths.py` | ✅ Active | Converts persona/domain/extracted facts into `EvidencePath` objects for DoT scoring                                                                            |
| `services/content_curator/_text_utils.py`     | ✅ Active | `truncate_at_sentence()`, `extract_hashtags()`, `append_url_and_hashtags()`                                                                                    |
| `services/content_curator/_grounding.py`      | ✅ Active | `load_curation_grounding_keywords()`, `load_curation_grounding_tag_expansions()`                                                                               |
| `services/console_grounding/_truth_gate.py`   | ✅ Active | `truth_gate()` and `truth_gate_result()` with DoT + spaCy safety checks                                                                                        |
| `services/console_grounding/_retrieval.py`    | ✅ Active | Query constraints, deterministic fact ranking, and grounded reply construction                                                                                 |
| `services/selection_learning/__init__.py`     | ✅ Active | Public API shim for candidate logging, reconciliation, priors, ranking, and user feedback                                                                      |
| `services/selection_learning/_reconcile.py`   | ✅ Active | `reconcile_published()` match/label flow for Buffer SENT posts and acceptance-window rejection labeling                                                        |
| `services/selection_learning/_ranking.py`     | ✅ Active | `rank_articles()` using relevance + freshness + acceptance priors + boost factors                                                                              |

---

#### Test coverage by file

| Test file                                  | What it covers                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --- |
| `tests/test_avatar_state_loader.py`        | Persona graph and narrative memory loading, schema validation, malformed-input fallback, and automatic merge of `domain_knowledge_*.json` sources.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `tests/test_buffer_service.py`             | Buffer GraphQL API wrapper, queue fetching, and idea creation.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `tests/test_piper_service.py`              | Wyoming Piper TTS integration, audio synthesis protocol (byte-by-byte header reading + binary payload), sounddevice playback, speaker ID configuration.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |     |
| `tests/test_confidence_scoring.py`         | Signal extraction, score thresholds, and policy routing.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| `tests/test_content_curator.py`            | RSS curation pipeline, keyword filtering, article processing, topic signal, SSI component tilt, and `EvidencePath` construction — updated to reference new submodule paths.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| `tests/test_continual_learning.py`         | ExtractedFact/ExtractedKnowledgeGraph schema, loader, normalization, deduplication, integration, and **comprehensive noise filtering pipeline** — parametrized filter regression tests covering every guard in `_extraction.py`: adversative conjunctions, conditional tutorial fragments, anthropomorphism, first-person narration, RSS boilerplate, rhetorical questions, dangling-pronoun openers and quantity references, heading+pronoun concatenations, "rarely something" advisory, truncated fragments, URL sentences, pipe navigation (single- and multi-pipe), HuggingFace/GitHub blobs, podcast preambles, scene-setters, survey openers, educational preambles, self-promotion, camelCase mangled joins, table blobs, version-list blobs, generic fillers, bare availability announcements, email consent-form fragments, punctuation-start byline fragments, mid-word truncated sentences, and product-feature-list sidebar blobs. Includes edge-case exemption tests (availability + "enabling", filler + metric, camelCase in product name + year, unique version numbers) and `test_cross_url_dedup_same_statement_not_stored_twice` integration test. |
| `tests/test_derivative_of_truth.py`        | Truth gradient scoring, evidence/reasoning annotation, and uncertainty logic.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `tests/test_evidence_mapping.py`           | Evidence ID stability, normalization, retrieval scoring, fallback, and explain output.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| `tests/test_integration_flags.py`          | CLI flag registration and invalid-value handling.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `tests/test_knowledge_graph.py`            | KnowledgeGraphManager, node/link schema, graph proximity, claim support, serialization, and queries.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `tests/test_learning_report.py`            | JSONL moderation capture, heuristics, aggregation, and report formatting.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| `tests/test_persona_graph_retrieval.py`    | Real persona graph loading, retrieval spot checks, and fallback logic.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| `tests/test_selection_learning.py`         | Candidate logging, buffer-id update, published reconciliation, acceptance priors, and ranking behavior (including package-refactor compatibility).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `tests/test_model2vec_service.py`          | Model2Vec service: lazy model loading, graceful degradation when model2vec not installed, text classification (single + batch), category metadata management (add/remove/list), cosine similarity utilities, text hashing, default categories mapping to SSI components, custom categories, singleton pattern, `classify_article()` and `batch_classify_articles()` convenience wrappers, and integration with RSS fetcher (primary_category/primary_ssi_component keys) and selection learning ranking (category alignment boost).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |     |
| `tests/test_ollama_extracted_grounding.py` | Prompt injection of extracted knowledge context into curation generation.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| `tests/test_truth_gate_dot.py`             | Truth Gate — DoT + spaCy upgrade: overlap computation, per-sentence DoT scoring, spaCy similarity floor, spaCy NER org-name check, concept/service false-positive filters (`S3`, `Java 21`, `AI Q&A`), project-name substring false-positive guard (`Regulatory Intelligence Assistant`), formatting artifact detection (newline-split ORG phrases like `Scale\nIf`), community tag detection (slash-separated tags like `AI/GovTech/Ottawa`), `TruthGateMeta` field coverage, and **multi-project sentence false-positive guard** (keyword legitimately owned by one project is not falsely attributed to another co-mentioned project, e.g. `Answer42`'s Spring Batch not flagged when `LinkedIn SSI Booster` is also referenced).                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `tests/test_enhanced_console_routing.py`   | Enhanced console mode query routing: 5-mode routing logic (explicit generative, explicit artifact, learned knowledge, domain/project/tech context, general chat), `parse_query_constraints()` with new routing modes, `get_latest_extracted_knowledge()` filtering, `build_learned_knowledge_context()` formatting, `QueryConstraints` properties (`requires_grounding`, `requires_context`), and backward compatibility with existing flags.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `tests/test_rei_toei_service.py`           | Rei Toei music avatar service: persona/domain/pattern loading, theme extraction from knowledge, song concept generation, lyric composition, Suno prompt assembly, Suno API integration (generate/query), DoT validation for lyrics, Strudel pattern generation, syntax validation, concept-to-pattern mapping, MCP agent execution, pattern library management (72 tests across Phases 1A-1C).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `tests/test_rei_console_routing.py`        | Rei Toei console integration: `/rei-toei` and `/rei` command parsing, routing logic, whitespace handling, conversation context maintenance (9 tests, Phase 1D).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| `tests/test_rei_cli_flags.py`              | Rei Toei CLI flag parsing: --rei-generate, --rei-generate-strudel, --rei-theme, --rei-explain, --rei-preview, --rei-execute flags, combined flag parsing, helpful placeholder message display (8 tests, Phase 1E).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |

## Repository structure

Project file tree (top-level):

```
linkedin_ssi_booster/
├── main.py                        # CLI entrypoint — all flags, console loop, Rei Toei CLI handlers
├── scheduler.py                   # PostScheduler — Buffer queue slot assignment
├── content_calendar.py            # Weekly topic calendar (gitignored; see content_calendar.example.py)
├── requirements.txt               # Full dependency list
├── requirements-core.txt          # Minimal install (no GPU/image deps)
├── requirements-flux.txt          # FLUX image generation extras
├── run.sh                         # Docker helper (sets USER_UID, PulseAudio socket)
├── docker-compose.yml             # Service definitions (ollama, piper, strudel, flux, postgres, app)
├── Dockerfile
├── README.md
├── QUICKSTART.md
│
├── agents/
│   ├── buffer_mcp_agent.py        # Buffer MCP agent (GraphQL wrapper)
│   └── strudel_mcp_agent.py       # Strudel live-coding MCP agent (WebSocket, port 4321)
│
├── services/
│   ├── __init__.py
│   ├── buffer_service.py          # Buffer GraphQL API client
│   ├── ollama_service.py          # Ollama LLM client (chat_as_persona, generate_*)
│   ├── github_service.py          # GitHub profile context builder
│   ├── hybrid_retriever.py        # BM25 + graph proximity + claim-support retriever
│   ├── knowledge_graph.py         # KnowledgeGraphManager (NetworkX, bootstrap_from_avatar_state)
│   ├── model2vec_service.py       # Static embedding classifier (minishlab/potion-base-8M)
│   ├── piper_service.py           # Wyoming Piper TTS client (speak_text)
│   ├── pln_inference.py           # Probabilistic Logic Networks inference engine
│   ├── rei_toei_service.py        # Rei Toei music avatar — Suno + Strudel generation (2000+ lines)
│   ├── shared.py                  # Shared helpers (print_validation_reports, AVATAR_CONFIDENCE_POLICY)
│   ├── spacy_nlp.py               # spaCy NLP wrapper (NER, similarity, en_core_web_md)
│   ├── ssi_tracker.py             # SSI score persistence + Bluesky stats
│   ├── image_generation.py        # FLUX.1-schnell image generation (full profile only)
│   │
│   ├── content_curator/           # Refactored package (was content_curator.py)
│   │   ├── __init__.py            # Public API re-exports
│   │   ├── curator.py             # ContentCurator class — orchestrates fetch → generate → push
│   │   ├── _config.py             # RSS feeds, keywords, SSI weights/hints, env constants
│   │   ├── _rss_fetcher.py        # fetch_relevant_articles(), fetch_article_text()
│   │   ├── _text_utils.py         # truncate_at_sentence(), extract_hashtags(), append_url_and_hashtags()
│   │   ├── _evidence_paths.py     # EvidencePath builders for DoT scoring
│   │   ├── _ssi_picker.py         # build_topic_signal(), pick_ssi_component()
│   │   └── _grounding.py          # Grounding keyword/tag loaders
│   │
│   ├── avatar_intelligence/       # Refactored package (was avatar_intelligence.py)
│   │   ├── __init__.py            # Public API re-exports + load_avatar_state wrapper
│   │   ├── _paths.py              # Path constants (PERSONA_GRAPH_PATH, etc.)
│   │   ├── _models.py             # Dataclasses (AvatarState, EvidenceFact, DomainEvidenceFact, etc.)
│   │   ├── _loaders.py            # Schema validators + file loaders (merges domain_knowledge_*.json)
│   │   ├── _normalizers.py        # Evidence/domain/extracted fact normalization
│   │   ├── _retrieval.py          # BM25 + fallback evidence retrieval
│   │   ├── _grounding.py          # Grounding context builders
│   │   ├── _learning.py           # Moderation event capture + learning report
│   │   ├── _confidence.py         # Confidence scoring + publish-mode routing
│   │   ├── _narrative.py          # Narrative memory update + continuity context
│   │   └── _extraction.py         # spaCy fact extraction + noise filters + save helpers
│   │
│   ├── console_grounding/         # Refactored package (was console_grounding.py)
│   │   ├── __init__.py            # Public API re-exports
│   │   ├── _config.py             # Env/config knobs and keyword defaults
│   │   ├── _models.py             # ProjectFact, QueryConstraints, TruthGateMeta
│   │   ├── _profile_parser.py     # PROFILE_CONTEXT bullet parsing
│   │   ├── _retrieval.py          # Deterministic retrieval + grounded replies
│   │   ├── _gate_helpers.py       # Regex/BM25 helpers and evidence checks
│   │   ├── _truth_gate.py         # Truth gate orchestration + moderation hooks
│   │   └── _rei_console.py        # Rei Toei console handler (handle_rei_console, 350+ lines)
│   │
│   ├── selection_learning/        # Refactored package (was selection_learning.py)
│   │   ├── __init__.py            # Backward-compatible public API re-exports
│   │   ├── _constants.py          # Paths and scoring thresholds
│   │   ├── _models.py             # CandidateRecord / PublishedRecord / FeaturePrior
│   │   ├── _storage.py            # JSONL read/append/rewrite helpers
│   │   ├── _text.py               # Hashing, tokenization, Jaccard, matching
│   │   ├── _logging.py            # Candidate logging + NLP enrichment
│   │   ├── _published.py          # Published-cache upsert helpers
│   │   ├── _reconcile.py          # Buffer SENT reconciliation and labeling
│   │   ├── _priors.py             # Beta-smoothed acceptance priors + boosts
│   │   ├── _ranking.py            # Article ranking formula and freshness decay
│   │   ├── _feedback.py           # Explicit user feedback capture/application
│   │   └── _category_analytics.py # Category performance analytics for --avatar-learn-report
│   │
│   ├── derivative_of_truth/       # Derivative of Truth framework
│   │   ├── _constants.py          # Evidence/reasoning type constants
│   │   ├── _models.py             # EvidencePath, TruthGradientResult, DoTScore
│   │   ├── _scoring.py            # score_claim_with_truth_gradient(), report_truth_gradient()
│   │   └── _reporting.py          # format_truth_gradient_report(), format_dot_report_header()
│   │
│   └── database/                  # PostgreSQL integration (optional, DATABASE_ENABLED=true)
│       ├── __init__.py            # Public API re-exports
│       ├── models.py              # SQLAlchemy ORM models (17 tables)
│       ├── repositories.py        # Repository classes (read/query)
│       ├── writers.py             # Write helpers (upsert, bulk insert)
│       ├── session.py             # Engine + session factory
│       └── migrate_data.py        # JSON/JSONL → PostgreSQL migration script
│
├── data/
│   ├── avatar/                    # User-private runtime state (gitignored)
│   │   ├── persona_graph.json                  # Sam's persona graph
│   │   ├── domain_knowledge.json               # Primary domain knowledge
│   │   ├── domain_knowledge_java.json          # Java domain pack (auto-merged)
│   │   ├── domain_knowledge_python.json        # Python domain pack (auto-merged)
│   │   ├── narrative_memory.json               # Narrative continuity state
│   │   ├── extracted_knowledge.json            # NLP-extracted facts (--learn)
│   │   ├── rei_toei_persona_graph.json         # Rei Toei's persona graph
│   │   ├── rei_toei_domain_knowledge.json      # Rei Toei's music domain knowledge
│   │   └── rei_toei_strudel_patterns.json      # Strudel pattern template library
│   └── selection/                 # Selection learning state (gitignored)
│       ├── candidates.jsonl       # Generated post candidates
│       ├── published.jsonl        # Reconciled published posts
│       └── moderation.jsonl       # Moderation event log
│
├── docs/
│   ├── features/                  # Feature design docs (idea.md + plan.md per feature)
│   │   ├── rei-toei/              # Rei Toei music avatar (Phases 1A-1E complete)
│   │   ├── database/              # PostgreSQL integration
│   │   ├── derivative-of-truth/   # DoT framework
│   │   └── ...
│   └── *.md                       # Architecture, CLI reference, environment variables, etc.
│
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   ├── test_avatar_state_loader.py
│   ├── test_buffer_service.py
│   ├── test_confidence_scoring.py
│   ├── test_content_curator.py
│   ├── test_continual_learning.py
│   ├── test_database_repos.py
│   ├── test_derivative_of_truth.py
│   ├── test_enhanced_console_routing.py
│   ├── test_evidence_mapping.py
│   ├── test_integration_flags.py
│   ├── test_knowledge_graph.py
│   ├── test_learned_knowledge_search.py
│   ├── test_learning_report.py
│   ├── test_model2vec_service.py
│   ├── test_ollama_extracted_grounding.py
│   ├── test_persona_graph_retrieval.py
│   ├── test_piper_service.py
│   ├── test_rei_cli_flags.py       # Rei Toei CLI flags (Phase 1E, 8 tests)
│   ├── test_rei_console_routing.py # Rei Toei console routing (Phase 1D, 9 tests)
│   ├── test_rei_toei_service.py    # Rei Toei service (Phases 1A-1C, 72 tests)
│   ├── test_selection_learning.py
│   ├── test_spacy_nlp.py
│   └── test_truth_gate_dot.py
│
├── media/                         # Documentation images and favicons
├── scripts/
│   ├── init-db.sql                # PostgreSQL schema initialisation
│   ├── add_url_links_columns.sql  # Migration: url_links columns
│   └── download-flux1-schnell-Q4_K_S.sh
└── yt-vid-data/                   # Generated YouTube scripts + Rei Toei Suno JSON outputs
```

User-private runtime state is under `data/avatar/` and `data/selection/` (local, gitignored).
