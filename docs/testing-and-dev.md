# Testing and Development

The project ships with a comprehensive `pytest` suite covering the Avatar Intelligence engine, grounding and evidence retrieval, confidence scoring, continual learning (NLP-extracted knowledge), curation, spaCy NLP, integration flags, persona graph retrieval, and selection learning.

---

## Running Tests

To set up your environment and execute tests, use the following standard commands:

```bash
# Install test dependencies
pip install pytest

# Run full test suite with verbose output
pytest tests/ -v

```

### Environment-Dependent Tests

For tests that depend on environment variables (such as `BUFFER_API_KEY`), load your `.env` configuration using `python-dotenv`:

```bash
python -m dotenv run -- python -m pytest tests/test_buffer_service.py -v

```

### Fast Execution Pass

To execute a rapid full-suite run while intentionally bypassing the external Buffer service suites, use the following isolation command:

```bash
python -m pytest -q tests/ --ignore=tests/test_buffer_service.py

```

---

## Test Coverage and Results (Latest)

### Summary Metrics

| Total Tests | Passed  | Skipped | Failed | Status        |
| ----------- | ------- | ------- | ------ | ------------- |
| **776**     | **774** | **2**   | **0**  | ✅ **All pass** |

- **Latest Run Date:** July 1, 2026
- **Latest Run Scope:** Full suite — confirmed 0 failed after session-management bug fixes and FLUX config env-isolation fix
- **Environment Specs:** Python 3.12.3, pytest 9.0.3
- **Notes:** 2 skipped = `test_get_scheduled_posts` / `test_get_published_posts` — Buffer API key present but lacks `channels` permission in this environment; tests skip cleanly via fixture guard.

### Test Suite Breakdown

- **565** Original core logic assertions
- **91** Rei Toei validation tests (Phases 1A–1E)
- _27 Foundation | 25 Suno | 20 Strudel | 9 Console Mode | 8 CLI Integration Flags_

- **6** Continuous knowledge extraction quality assertions
- **5** Selection Learning database integration tests (Phase 5)
- _3 CandidateRecordRepository | 2 PublishedRecordRepository_
- **16** Katzilla integration tests (Phases 1-6)
- _6 Service client | 2 Envelope adapter | 4 Retrieval integration/fallback_
- _+4 Phase 4-6 coverage: citation UX, external DoT paths, telemetry budgets_
- **45** FLUX Capacitor art-avatar subsystem tests (Phase 1: package foundation)
- _34 Pipeline | 11 GPU Orchestration Policy_
- **18** FLUX Capacitor main.py integration tests (Steps 5–7)
- _3 Schedule flow | 7 Curate flow | 7 Console flow (plus 1 SourceMode assertion)_
  - `tests/test_flux_capacitor_schedule_integration.py`
  - `tests/test_flux_capacitor_curate_console_integration.py`

- **17** MCP agent unit tests (new)
- _9 Buffer MCP agent tests + 8 Strudel MCP agent tests_
- **4** Singleton concurrency tests (new)
- _3 Database engine/session singleton lifecycle + 1 Flux service singleton under concurrent access_

---

## Recent Bug Fixes Covered by Tests

### `next(get_session())` anti-pattern — `_confidence.py` and `_learning.py`

Two DB write helpers in `services/avatar_intelligence/` were calling `next(get_session())` instead of using the context manager. This abandoned the generator before its `finally: session.close()` and `except: session.rollback()` branches could execute, leaking connections and silently skipping rollbacks on error. Fixed to `with get_session() as session:` in both files. Test mocks in `test_confidence_scoring.py` and `test_learning_report.py` updated from `lambda: iter([DummySession()])` to proper `@contextmanager` functions.

### `test_defaults_valid` env leakage — `test_flux_capacitor_pipeline.py`

`TestFluxCapacitorConfig.test_defaults_valid` was constructing `FluxCapacitorConfig()` without clearing `FLUX_CAPACITOR_ENABLED`, so it picked up the live `.env` value (`true`) instead of testing the code default (`false`). Fixed with `patch.dict("os.environ", {"FLUX_CAPACITOR_ENABLED": "false"})` scoped to that test.

---

## Core Technical Coverage Highlights

### 🧠 Architectural Foundations

- **Knowledge Graph Subsystem:** Verifies `KnowledgeGraphManager`, strict node/link schemas, graph proximity weights, claim support calculation, and serialization via NetworkX.
- **Hybrid Retrieval Mechanics:** Validates dual BM25 + graph retrieval routines along with persona-aware reranking layers actively running in production through `ContentCurator`.
- **Context Enrichment Engine:** Guarantees `github_service.py` is correctly wired into `main.py`, interactive console modes, and automated curation flows.
- **Console Runtime Stability:** Tests the interactive `/reload` console command to ensure `_load_knowledge_state()` hot-reloads persona graphs, domain packs, and `extracted_knowledge.json` mid-session without triggering duplicate routing blocks.
- **Graceful Degradation Safeguards:** Verifies `_is_spacy_available()` broad exception handling so that environment-level anomalies (e.g., missing compiled torch libraries in Anaconda) fallback cleanly to basic regex parsing without breaking core Truth Gate evaluations.

---

### 🚀 Advanced Feature Implementations

### 1. Model2Vec Text Classification

Driven by ultra-fast static embedding classification models (`minishlab/potion-base-8M`), mapped explicitly to 10 default SSI architecture categories with on-the-fly custom category allocations.

- **Tested Implementations:** Lazy-loading performance, thread-safe Singleton design patterns, batch classification optimization, array text-hashing, and cosine similarity calculators.
- **Integration Points:** Evaluates RSS fetcher automation tagging alongside category-alignment scoring boosts during selection learning rank passes.
- **Phase 5 CLI Features Covered:**
- Metadata manipulation parameters: `--add-category`, `--list-categories`, `--remove-category`
- Filtered evidence retrieval passes: `retrieve_evidence(category_filter=...)`
- Behavioral analysis and truth verification engines: `_category_analytics.py`, `--avatar-learn-report`, and `validate_category_alignment()` execution checks via `--dot-report --classify`.

### 2. Derivative of Truth (DoT) Engine

- **Scoring Integrity:** Fully asserts truth gradient scoring loops, granular text evidence/reasoning annotations, and mathematical uncertainty logic frameworks (`tests/test_derivative_of_truth.py`).
- **Algorithmic Alignment:** Confirms correct execution behavior of Probabilistic Logic Networks (PLN) enhanced scoring engines in strict accordance with project core design blueprints.

### 3. Continual Learning Noise Filters

Validates a comprehensive, heavily parametrized pre-storage ingestion filter pipeline inside `_extraction.py`. The suite tests that noisy scraper text is systematically stripped out _before_ running spaCy parsing or duplicate content detection.

Validated noise reduction boundaries include:

- **Structural Fragments:** Rhetorical questions, first-person narrative prose, standalone URL sentences, and double-dash Table of Contents blocks.
- **Scraper & Layout Garbage:** Ellipsis-truncated sentences, mid-word scraper cutoffs, pipe-delimited navigation strings (single and multi-pipe), and heavy developer ecosystem navigation headers (e.g., HuggingFace/GitHub sidebar blocks).
- **Grammatical Openers:** Sentences beginning with adversative conjunctions (`But`, `However`, `Yet`), or conditional tutorial introductions (`When/While/Whenever you are building...`).
- **Boilerplate & Marketing:** Newsletter/podcast preambles (`This latest one looks at...`), promotional marketing banners, call-to-action (CTA) feedback boxes, passive advisory guidelines, event announcements, and email consent footers.
- **Technical Layout Artifacts:** Densely crowded table/architecture digit grids, multi-row software version matrices, bare-minimum product availability notifications, and massive structural lists (e.g., Elastic sidebar product feature blocks).
- **Strict Exemption Guards:** Assures that verified product names with structural camelCase patterns (e.g., `SageMaker`, `GitHub`) or specific metric statements are preserved without false filtering.

### 4. Cross-URL Statement Deduplication

- **Storage Optimization:** Asserts that beyond unique URL SHA-256 identifier checks, a normalized global text hash map is processed.
- **Behavior:** Identical legal footprints, boilerplate marketing terms, or technical sidebars fetched from completely distinct domains are localized and recorded exactly once.

### 5. Truth Gate Safety Upgrades

- **Jaccard Overlap Processing:** Measures token-level overlap patterns across active facts to successfully fuel the 4-term DoT equation.
- **Vector Model Validation:** Enforces minimum semantic constraints via `TRUTH_GATE_SPACY_SIM_FLOOR` (default `0.10`). Standardizes the runtime pipeline on the `en_core_web_md` medium vector model, systematically erasing legacy W007 missing-word-vector warnings.
- **Entity False-Positive Hardening:** Employs advanced spaCy Named Entity Recognition (`NER`) to handle organizational filtering. Queries project schemas directly at gate runtime via `get_project_names_from_avatar_state()`, stopping baseline developer components (`S3`, `Java 21`, `AI Q&A`) from being flagged as ungrounded external organizations.
- **Multi-Project Collisions:** Uses contextual boundary rules inside `_check_project_claim` to ensure shared context sentences co-mentioning separate internal platforms do not cause cross-contamination false failures.

---

## Production Module & Package Decoupling Status

The architecture is fully modularized into dedicated Python packages containing clean submodule splits:

| System Package / Module         | In Production | Core Integration Point                                                                                                                                           |
| ------------------------------- | ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `services/github_service.py`    | ✅ Active     | Appended at `main.py` startup; feeds downstream curation pipelines.                                                                                              |
| `services/model2vec_service.py` | ✅ Active     | Managed by `ContentCurator` and used inside `selection_learning/_ranking.py` for scoring boosts.                                                                 |
| `services/hybrid_retriever.py`  | ✅ Active     | Bootstrapped at curator initializing stages to query graph networks.                                                                                             |
| `services/ollama_service.py`    | ✅ Active     | Injects grounded context arrays using `build_extracted_grounding_context` tools.                                                                                 |
| `services/content_curator/`     | ✅ Active     | **7 Focused Submodules:** `curator`, `_config`, `_rss_fetcher`, `_ssi_picker`, `_evidence_paths`, `_text_utils`, `_grounding`.                                   |
| `services/avatar_intelligence/` | ✅ Active     | **10 Focused Submodules:** `_paths`, `_models`, `_loaders`, `_normalizers`, `_retrieval`, `_grounding`, `_learning`, `_confidence`, `_narrative`, `_extraction`. |
| `services/console_grounding/`   | ✅ Active     | **6 Focused Submodules:** `_config`, `_models`, `_profile_parser`, `_retrieval`, `_gate_helpers`, `_truth_gate`.                                                 |
| `services/selection_learning/`  | ✅ Active     | **10 Focused Submodules:** `_constants`, `_models`, `_storage`, `_text`, `_logging`, `_published`, `_reconcile`, `_priors`, `_ranking`, `_feedback`.             |
| `services/rei_toei/`            | ✅ Active     | **7 Focused Submodules:** `_config`, `_models`, `_loaders`, `_suno_client`, `_suno_pipeline`, `_strudel_pipeline`, `service`.                                    |
| `services/flux_capacitor/`      | ✅ Active     | **6 Focused Submodules:** `_config`, `_models`, `_prompting`, `_pipeline`, `_storage`, `__init__` — GPUOrchestrator, FluxCapacitorService, style presets.        |

---

## Comprehensive Test File Mapping

| Targeted Test File Vector               | Detailed Functional Coverage Matrix                                                                                                                                        |
| --------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tests/test_avatar_state_loader.py`     | Confirms graph structural configurations, narrative memory loading, malformed input recovery routines, and multi-file asset joining (`domain_knowledge_*.json`).           |
| `tests/test_buffer_service.py`          | Exercises the GraphQL API wrapper connectivity layers, buffer item queues, and content idea generation.                                                                    |
| `tests/test_piper_service.py`           | Verifies Wyoming Piper TTS protocol behaviors, header parsing, byte payload streaming, and sound device mapping.                                                           |
| `tests/test_confidence_scoring.py`      | Tests extracted heuristic signals, routing rules, and execution scoring boundaries.                                                                                        |
| `tests/test_content_curator.py`         | Drives RSS fetch pipelines, keyword screening constraints, SSI adaptive category shifts, and module routing layouts.                                                       |
| `tests/test_continual_learning.py`      | Orchestrates comprehensive noise filtering regression, multi-source ingestion constraints, structural text normalization, and multi-URL exact statement uniqueness checks. |
| `tests/test_derivative_of_truth.py`     | Evaluates gradient equations, factual annotation workflows, programmatic uncertainty logic, and core PLN evaluations.                                                      |
| `tests/test_evidence_mapping.py`        | Targets factual ID tracking consistency, retrieval prioritization fallback loops, and conversational reasoning reporting.                                                  |
| `tests/test_integration_flags.py`       | Asserts CLI parameter parsing, flag registrations, environment bindings, and error routines on invalid parameter types.                                                    |
| `tests/test_knowledge_graph.py`         | Asserts NetworkX data states, link metadata schemas, localized node weights, serialization consistency, and network queries.                                               |
| `tests/test_learning_report.py`         | Tracks JSONL moderation entry monitoring, analytics ingestion aggregators, and markdown formatting templates.                                                              |
| `tests/test_persona_graph_retrieval.py` | Assesses live profile data loading passes, keyword spot-check maps, and fallback routines.                                                                                 |
| `tests/test_selection_learning.py`      | Audits candidate data logging loops, buffer assignment routines, published state reconciliation tasks, and ranking adjustments.                                            |
| `tests/test_model2vec_service.py`       | Evaluates lazy model loads, graceful degradation on missing runtimes, metadata analytics, and item prioritization scoring within selection learning.                       |
| `tests/test_buffer_mcp_agent.py`        | Verifies Buffer MCP agent health checks, Ollama request generation/parsing, MCP initialize handshake, tool-call payload wrapping, and JSON-RPC passthrough behavior.      |
| `tests/test_strudel_mcp_agent.py`       | Verifies Strudel MCP agent JSON-RPC stdio flow, health-check tool discovery, tool-envelope parsing, and success/error handling for init/edit/playback tool calls.         |
| `tests/test_flux_capacitor_pipeline.py` | Config validation, model contracts, style preset clamping, prompt assembly, GPU orchestrator state machine, pipeline disabled/deferred/FAILED paths, DNS-unreachable FLUX service TEXT_ONLY fallback, story artifact persistence, service singleton. |
| `tests/test_gpu_orchestration_policy.py`| Ollama-first queue ordering, TEXT_ONLY timeout fallback, slot acquire/release lifecycle, exception-safe context manager, concurrency safety with multiple FLUX requests.   |
| `tests/test_flux_capacitor_schedule_integration.py` | Schedule-flow wiring: skips YouTube channel, records rendered metadata, catches and wraps exceptions as failed result. |
| `tests/test_flux_capacitor_curate_console_integration.py` | Curate-flow wiring: skips youtube/all channels, rendered/deferred/failed paths, SourceMode.CURATE propagation. Console-flow wiring: empty-text guard, rendered/deferred/failed paths, SourceMode.CONSOLE propagation, None topic hint. |
| `tests/test_database_session_singleton.py` | Thread-safe DB singleton initialization for `get_engine`/`get_session_factory`, and listener-scoping validation to prevent duplicate Pool-level callback registration. |
| `tests/test_flux_service_singleton.py` | Concurrent `get_flux_service` access validation to ensure a single shared `FluxCapacitorService` instance is constructed process-wide. |
