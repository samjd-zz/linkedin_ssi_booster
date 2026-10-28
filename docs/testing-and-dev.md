# Testing and Development

The project ships with a comprehensive `pytest` suite covering the Avatar Intelligence engine, grounding and evidence retrieval, confidence scoring, continual learning (NLP-extracted knowledge), curation, spaCy NLP, integration flags, persona graph retrieval, and selection learning.

---

## Running Tests

To set up your environment and execute tests, use the following standard commands:

```bash
# Install test dependencies
source .venv/bin/activate && pip install pytest pytest-cov

# Run full test suite with verbose output
source .venv/bin/activate && python -m pytest tests/ -v

# Run full test suite with source coverage
source .venv/bin/activate && python -m pytest --cov=services --cov=agents --cov=main --cov=scheduler --cov=content_calendar --cov-report=term-missing:skip-covered -q

```

### Environment-Dependent Tests

For tests that depend on environment variables (such as `BUFFER_API_KEY`), load your `.env` configuration using `python-dotenv`:

```bash
source .venv/bin/activate && python -m dotenv run -- python -m pytest tests/test_buffer_service.py -v

```

### Fast Execution Pass

To execute a rapid full-suite run while intentionally bypassing the external Buffer service suites, use the following isolation command:

```bash
source .venv/bin/activate && python -m pytest -q tests/ --ignore=tests/test_buffer_service.py

```

---

## Test Coverage and Results (Latest)

### Summary Metrics

| Collected | Passed | Skipped | Failed | Deselected | Source Coverage | Status |
| --------- | ------ | ------- | ------ | ---------- | --------------- | ------ |
| **1028** | **1026** | **0** | **0** | **2** | **70%** | All executed tests passed |

- **Latest Run Date:** October 27, 2026
- **Latest Changes:** 30 schedule/cleanup regressions covering shared preparation, per-topic grounding reuse, SSI-equivalent early caps and skewed-allocation queue order, full previews/YouTube, generated-content report reuse/fallback, phase timings, and actual-use FLUX cleanup. Previous work added 22 console, 31 curation, and 7 Rei CLI preview regressions. Source coverage was remeasured October 27, 2026.
- **Latest Run Scope:** Entire suite except the two live Buffer API tests, explicitly deselected to avoid account/network access: **1,026 passed, 0 failed, 2 deselected** in 50.86 seconds with coverage enabled. One existing non-terminal `term_image` warning remains. The focused persona-retrieval module passed **12 tests**; the preceding schedule/cleanup/FLUX/Rei-preview/timing run passed **101 tests**.
- **Environment Specs:** Python 3.12.3, pytest 9.0.3, pytest-cov 7.1.0, coverage 7.17.0
- **Coverage Scope:** `services`, `agents`, `main`, and `scheduler` measured with pytest-cov. `content_calendar` was also requested but never imported, producing a coverage warning; it is not included in the reported denominator.
- **Persona retrieval regression fix:** `test_persona_graph_retrieval.py` no longer hard-codes a private persona's project count. It compares loaded project IDs/order with the configured source JSON and verifies one evidence fact per project, including IDs, names, details, years, and skills. Fixture path overrides are restored even if loading fails. All 12 tests in that module pass; no persona data or production normalization behavior was changed.

### What These Results Measure

The latest run executed **1,026 of 1,028 collected tests**, all passing with
zero failures. The two live Buffer tests were explicitly deselected, not skipped
or counted as passing; live API behavior was not verified by this run.

The **70% source-coverage figure was measured October 27, 2026**: 12,802
executable statements, 3,881 missed, and 8,921 executed (69.68%, rounded to 70%
by the report). This replaces the historical September 14 figure of 66%.
It measures statement coverage, not branch coverage or live API correctness.
`content_calendar` was not imported by the suite and is absent from the total;
18 fully covered files were omitted from the terminal listing but included in
the total. Entry-point coverage was 55% for `main.py` and 68% for `scheduler.py`.

The recent performance work added **90 regression tests**:

| Area | Added tests | Behaviors covered |
| ---- | ----------- | ----------------- |
| [Curation](#curation-performance-regressions) | 31 | FLUX gating, bounded NLP corpora, truth-gate metadata reuse, timing telemetry |
| [Rei CLI preview](#rei-cli-preview-preparation-and-timing) | 7 | Preparation gating, shared client/history, preview isolation, explicit-theme syntax |
| [Sam/Rei console](#console-performance-regressions) | 22 | Batched retrieval, large embeddings, reload consistency, lazy knowledge, voice/history/timings |
| [Scheduling and cleanup](#schedule-performance-regressions) | 30 | Grounding reuse, SSI cap/order preservation, report scope/fallback, actual-use resource cleanup |

These regressions verify operation counts, outputs, and error/lifecycle
contracts using mocks. They do not measure real GPU latency or live publishing.

To remeasure source coverage while excluding the two live Buffer tests:

```bash
source .venv/bin/activate && python -m pytest -q tests/ \
  --deselect=tests/test_buffer_service.py::test_get_scheduled_posts \
  --deselect=tests/test_buffer_service.py::test_get_published_posts \
  --cov=services --cov=agents --cov=main --cov=scheduler --cov=content_calendar \
  --cov-report=term-missing:skip-covered
```

Inspect both the test summary and coverage report before updating the badges.
The persona integration checks require the maintainer's local graph; when that
private graph is not configured, those checks retain their existing skip behavior.

### Test Suite Breakdown

- **565** Original core logic assertions
- **115** Rei Toei validation tests (Phases 1A–1E + console LLM behavior + Romaji music hooks)
- _27 Foundation | 26 Suno | 20 Strudel | 18 Console Mode | 8 CLI Integration Flags + 2 fallback paths_

- **6** Continuous knowledge extraction quality assertions
- **5** Selection Learning database integration tests (Phase 5)
- _3 CandidateRecordRepository | 2 PublishedRecordRepository_
- **16** Katzilla integration tests (Phases 1-6)
- _6 Service client | 2 Envelope adapter | 4 Retrieval integration/fallback_
- _+4 Phase 4-6 coverage: citation UX, external DoT paths, telemetry budgets_
- **47** FLUX Capacitor art-avatar subsystem tests (Phase 1: package foundation)
- **21** spaCy search tokenizer, batch similarity, and reusable BM25 index tests
- _36 Pipeline | 11 GPU Orchestration Policy_
- **20** FLUX Capacitor main.py integration tests (Steps 5–7)
- _3 Schedule flow | 7 Curate flow | 9 Console flow (includes auto-render trigger for Japanese character/art requests)_
  - `tests/test_flux_capacitor_schedule_integration.py`
  - `tests/test_flux_capacitor_curate_console_integration.py`

- **17** MCP agent unit tests (new)
- _9 Buffer MCP agent tests + 8 Strudel MCP agent tests_
- **6** Strudel WebSocket bridge tests (new)
- **6** Database writer dual-write tests (new)
- **4** Suno submission orchestration tests (new)
- **3** spaCy pipeline thread-safety tests (new)
- **4** Singleton concurrency tests (new)
- _3 Database engine/session singleton lifecycle + 1 Flux service singleton under concurrent access_
- **31** Curation performance regression tests (new)
- _10 FLUX text-only gating | 6 bounded corpus caching | 9 gate-metadata reuse | 6 timing telemetry_
- **7** Rei CLI preview performance regression tests (new)
- _Explicit-theme syntax, preparation gating, automatic-theme history reuse, explain-mode evidence, default model, Strudel client reuse, console GitHub preservation_
- **22** Sam/Rei console performance regression tests (new)
- _Large-batch embedding correctness/reuse, content/model invalidation, batched tokenization/fallback, one snapshot per reload, refreshed tag relationships and graph, lazy Rei knowledge, shared music client, sparse external fallback, bounded history, one verification bar, voice completion, and chat metrics/errors_
- **30** Schedule performance and resource-cleanup regression tests (new)
- _17 preparation/grounding/report/cap/preview/error/timing cases | 13 actual-use FLUX lifecycle and cleanup cases_

---

## Schedule Performance Regressions

| Test file | Tests | Coverage |
| --------- | ----- | -------- |
| `tests/test_schedule_performance.py` | 17 | No unused GitHub enrichment; one avatar normalization; topic-specific grounding reuse; generated-content DoT metadata and fallback; early live caps matching SSI queue selection/order, including overflow under skewed allocation; uncapped/invalid cap behavior; full dry-run/YouTube; preserved hashtags/footer; generation-error cleanup; phase timings |
| `tests/test_schedule_cleanup.py` | 13 | Only-used remote unload; success/error state handling; no unused local-runtime import; continued cleanup after Ollama errors; disabled/minimal/DNS-failed/successful/failed-request FLUX usage tracking |

Run the focused suite:

```bash
source .venv/bin/activate && python -m pytest -q \
  tests/test_schedule_performance.py tests/test_schedule_cleanup.py \
  tests/test_scheduler_queue.py tests/test_flux_capacitor_schedule_integration.py \
  tests/test_flux_capacitor_pipeline.py tests/test_rei_preview_performance.py \
  tests/test_performance_flux_gating.py tests/test_performance.py
```

All scheduling/publishing, model generation, remote FLUX requests, and cleanup
clients are mocked in the new tests. They assert operation counts and selected
topic/output equivalence rather than hardware speed. The five-topic,
two-channel, one-slot test requires two live generations versus ten preview
generations. See [schedule runtime behavior](features/schedule-performance.md)
for the generated-content report scope and shutdown timings.

---

## Console Performance Regressions

| Test file | Tests | Coverage |
| --------- | ----- | -------- |
| `tests/test_console_performance.py` | 22 | 617-candidate semantic scoring across different queries; order/duplicates/model changes; incomplete batches; BM25 batching/content edits/fallback; snapshot and graph reloads; tag relationship refresh; sparse external fallback; Rei lazy templates and shared song/pattern clients; sticky switching/history bound; single verification; synchronous voice; Sam/Rei server timings and propagated errors; disabled reporting |

Run focused console coverage with the existing virtual environment:

```bash
source .venv/bin/activate && python -m pytest -q \
  tests/test_console_performance.py tests/test_rei_console_routing.py \
  tests/test_model2vec_service.py tests/test_knowledge_graph.py \
  tests/test_enhanced_console_routing.py tests/test_spacy_nlp.py \
  tests/test_rei_preview_performance.py tests/test_performance.py \
  tests/test_flux_capacitor_curate_console_integration.py
```

Tests use fake model embeddings, mocked chat/voice clients, and scripted console
input, without accessing Ollama, Piper, Suno, Strudel, or live Buffer accounts.
These assert removed operations and preserved behavior, not hardware latency.
See [console runtime behavior](features/console-performance.md) for timing stages,
expected voice/retry delays, and `/reload` semantics.

---

## Curation Performance Regressions

| Test file | Tests | Coverage |
| --------- | ----- | -------- |
| `tests/test_performance_flux_gating.py` | 10 | All source modes skip image-prompt LLM calls when disabled/minimal; enabled mode optimizes once |
| `tests/test_nlp_corpus_cache.py` | 6 | A 617-fact corpus parses once across sentences, unchanged overlap, model/content invalidation, bounded eviction, incomplete/oversized inputs and failed builds |
| `tests/test_curator_gate_metadata.py` | 9 | One gate pass through generation and channel formatting, retained removal penalties, stale metadata fallback, per-call reset |
| `tests/test_performance.py` | 6 | Wall-time units, repeated/decorated calls, propagated errors, server nanosecond conversion, explicit missing metrics, content-free logs |

Run the isolated suite without the two live Buffer tests:

```bash
source .venv/bin/activate && python -m pytest -q tests/ \
  --deselect=tests/test_buffer_service.py::test_get_scheduled_posts \
  --deselect=tests/test_buffer_service.py::test_get_published_posts
```

Normal INFO logs now include `Stage start` and `Stage end` records with `stage`, `elapsed_s`, and `status`:

- `ollama.chat`: client wall time for each primary/fallback request.
- `truth_gate`: filtering plus DoT scoring.
- `curation.confidence`: confidence assessment/routing; normally reuses generation metadata.
- `curation.candidate_logging`: NLP enrichment and candidate persistence.
- `buffer.channel_discovery`: organization/channel lookup.
- `buffer.graphql`: each Buffer request.
- `curation.channel`: the full single-channel pipeline, including generation, validation, and publishing.

Stages are nested: do not sum overlapping durations. `Ollama timing` records report server `load_s`, `prompt_eval_s`, `generation_s`, `total_s`, and token counts. `None` means the server did not supply a metric, not zero. Compare server load time with generation and client wall time before diagnosing model reloads or transport delays. Existing content logs are unchanged; the new timing records contain no prompts or post text.

The caching tests verify operation counts, not a production speedup estimate. Re-run the normal curation command to measure the actual improvement on the deployment hardware.

---

## Recent Bug Fixes Covered by Tests

### Rei CLI preview preparation and timing

`tests/test_rei_preview_performance.py` runs the CLI with isolated mocks: no live Ollama, GitHub, Suno, or Buffer calls. It verifies that explicit-theme previews skip unused avatar loading, auto-theme previews read history once, explain mode retains DoT evidence validation, both music modes reuse the CLI client, the default model remains unchanged, and console mode still receives GitHub context. Preview writes no song artifact or media and never submits to Suno. Tests also require concept/lyric/formatting stage records. See [runtime behavior](features/rei-toei/preview.md) for corrected command examples and retry expectations.

### Console/CLI Rei Toei lyric-language misalignment — `_rei_console.py` and `_suno_pipeline.py`

The console's direct-LLM song fallback (`_handle_llm_song_generation` → `_build_rei_system_prompt`), used when no extracted knowledge/themes are available, built its own system prompt with no reference to `REI_LYRIC_LANGUAGE` / `REI_JAPANESE_LYRIC_PROBABILITY`, so it silently ignored the language-mix policy that `--rei-generate` (CLI) always applied via `compose_lyrics`. Fixed by injecting the same `resolve_lyric_language()`-derived language instruction into `_build_rei_system_prompt`. Separately, `assemble_suno_prompt` unconditionally forced the chorus to ALL-CAPS regardless of `concept.lyric_language`, uppercasing Japanese/bilingual chorus text that should preserve natural script and casing; fixed to only uppercase when `lyric_language == "english"`. Covered by `test_assemble_suno_prompt_flips_japanese_first_bilingual_lines` in `tests/test_rei_toei_service.py`.

### Bilingual Japanese-line target enforcement — `_suno_pipeline.py`

`REI_JAPANESE_LYRIC_PROBABILITY` is a per-song target for lyric lines containing Japanese script, not the probability of selecting Japanese for an entire song. A bilingual draft must contain both languages and stay within a 0.50 ratio tolerance of the target (so a 15% target rejects drafts above 65% Japanese). The current composer permits five total attempts: attempt 2 adds hard constraints, later attempts add explicit per-section language assignments. If no Japanese script ever appears, rescue hooks are appended to the bridge; if the mix still fails after the final attempt, the built-in bilingual fallback lyrics are used. Generated JSON accepts literal lyric line breaks, expands leaked `\n` sequences before language validation, and removes serialized quote/punctuation artifacts during Suno formatting. A malformed retry revalidates the last parseable draft instead of bypassing the bilingual constraint. `run.sh` also rebuilds one-off `app` containers automatically so Docker cannot execute stale validation code. Covered by `test_compose_lyrics_bilingual_retries_when_first_attempt_is_single_language`, `test_compose_lyrics_rejects_bilingual_output_outside_target_ratio`, `test_compose_lyrics_rejects_serialized_all_japanese_draft_after_malformed_repairs`, `test_assemble_suno_prompt_normalizes_serialized_lyric_artifacts`, `test_bilingual_mix_counts_mixed_lines_as_japanese_lines`, `test_bilingual_mix_accepts_the_fifty_percent_tolerance_boundary`, and `test_parse_llm_json_payload_allows_literal_newlines_in_lyric_values` in `tests/test_rei_toei_service.py`, plus `test_one_off_app_run_rebuilds_image` in `tests/test_run_script.py`.

### Concurrent spaCy tokenizer access — `spacy_nlp.py`

Cached spaCy pipelines are shared process-wide, and the SudachiPy tokenizer behind `ja_core_news_md` is not re-entrant. Concurrent curation work failed with `summarize_article failed: Tokenizer is already in use`. Every pipeline returned by `_load_model()` is now wrapped in `_ThreadSafeNLP`, which serializes `nlp(...)` and `nlp.pipe(...)` with a per-model `RLock`; `pipe()` is materialized under the lock so a lazy generator cannot tokenize after release. Different language models still run in parallel. Covered by `tests/test_spacy_thread_safety.py`.

### Optional Japanese spaCy model warnings — `spacy_nlp.py`

Japanese text routing previously probed the optional `ja_core_news_sm` and `ja_core_news_lg` packages after the configured Japanese model was available, creating misleading missing-model warnings. Fallback routing now uses only the project's default `ja_core_news_md` model unless an alternative is explicitly configured in `SPACY_MODELS`. Covered by `test_japanese_fallback_only_tries_default_medium_model` in `tests/test_spacy_nlp.py`.

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

| Targeted Test File Vector                                 | Detailed Functional Coverage Matrix                                                                                                                                                                                                                                                                   |
| --------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tests/test_rei_console_routing.py`                       | Rei Toei console routing: command parsing, sticky Rei mode (`should_handle_rei_turn`), song/pattern heuristics, `_build_rei_system_prompt` identity and music-generation directive, Suno fallback to LLM when no extracted knowledge, `_handle_conversation` song re-routing, no Sam persona leakage. |
| `tests/test_avatar_state_loader.py`                       | Confirms graph structural configurations, narrative memory loading, malformed input recovery routines, and multi-file asset joining (`domain_knowledge_*.json`, including `domain_knowledge_romaji.json`).                                                                                            |
| `tests/test_buffer_service.py`                            | Exercises the GraphQL API wrapper connectivity layers, buffer item queues, and content idea generation.                                                                                                                                                                                               |
| `tests/test_scheduler_queue.py`                           | Verifies schedule mode sends all selected posts to Buffer's queue without explicit `scheduled_at` timestamps, even when legacy scheduler environment variables are present.                                                                                                                           |
| `tests/test_piper_service.py`                             | Verifies Wyoming Piper TTS protocol behaviors, header parsing, byte payload streaming, and sound device mapping.                                                                                                                                                                                      |
| `tests/test_confidence_scoring.py`                        | Tests extracted heuristic signals, routing rules, and execution scoring boundaries.                                                                                                                                                                                                                   |
| `tests/test_content_curator.py`                           | Drives RSS fetch pipelines, keyword screening constraints, SSI adaptive category shifts, and module routing layouts.                                                                                                                                                                                  |
| `tests/test_curator_extra_feeds.py`                       | Verifies `CURATOR_RSS_FEEDS_EXTRA` / `CURATOR_KEYWORDS_EXTRA` append semantics, URL/keyword dedup, and that built-in defaults are never mutated.                                                                                                                                                      |
| `tests/test_spacy_theme_groups.py`                        | Covers source-based entity/concept grouping, temporal-entity demotion, Japanese `。！？` sentence splitting, ASCII decimal preservation, and graceful degradation when a pipeline lacks `noun_chunks`.                                                                                                |
| `tests/test_spacy_thread_safety.py`                       | Verifies `_ThreadSafeNLP` serializes concurrent `__call__` and `pipe()` on a non-re-entrant tokenizer (SudachiPy simulation) and passes other attributes such as `pipe_names` through.                                                                                                                 |
| `tests/test_continual_learning.py`                        | Orchestrates comprehensive noise filtering regression, multi-source ingestion constraints, structural text normalization, and multi-URL exact statement uniqueness checks.                                                                                                                            |
| `tests/test_derivative_of_truth.py`                       | Evaluates gradient equations, factual annotation workflows, programmatic uncertainty logic, and core PLN evaluations.                                                                                                                                                                                 |
| `tests/test_evidence_mapping.py`                          | Targets factual ID tracking consistency, retrieval prioritization fallback loops, and conversational reasoning reporting.                                                                                                                                                                             |
| `tests/test_integration_flags.py`                         | Asserts CLI parameter parsing, flag registrations, environment bindings, and error routines on invalid parameter types.                                                                                                                                                                               |
| `tests/test_knowledge_graph.py`                           | Asserts NetworkX data states, link metadata schemas, localized node weights, serialization consistency, and network queries.                                                                                                                                                                          |
| `tests/test_learning_report.py`                           | Tracks JSONL moderation entry monitoring, analytics ingestion aggregators, and markdown formatting templates.                                                                                                                                                                                         |
| `tests/test_persona_graph_retrieval.py`                   | Assesses live profile data loading passes, keyword spot-check maps, and fallback routines.                                                                                                                                                                                                            |
| `tests/test_selection_learning.py`                        | Audits candidate data logging loops, buffer assignment routines, published state reconciliation tasks, and ranking adjustments.                                                                                                                                                                       |
| `tests/test_model2vec_service.py`                         | Evaluates lazy model loads, graceful degradation on missing runtimes, metadata analytics, and item prioritization scoring within selection learning.                                                                                                                                                  |
| `tests/test_buffer_mcp_agent.py`                          | Verifies Buffer MCP agent health checks, Ollama request generation/parsing, MCP initialize handshake, tool-call payload wrapping, and JSON-RPC passthrough behavior.                                                                                                                                  |
| `tests/test_strudel_mcp_agent.py`                         | Verifies Strudel MCP agent JSON-RPC stdio flow, health-check tool discovery, tool-envelope parsing, and success/error handling for init/edit/playback tool calls.                                                                                                                                     |
| `tests/test_strudel_ws_bridge.py`                         | Verifies WebSocket bridge message parsing, ping/pong health checks, eval validation, MCP success acknowledgments, and MCP execution failure envelopes.                                                                                                                                                |
| `tests/test_database_writers.py`                          | Verifies persona graph, domain knowledge, extracted knowledge, and narrative memory database writers, including dual-write file persistence and relationship mapping.                                                                                                                                 |
| `tests/test_suno_submission.py`                           | Verifies Suno API submission orchestration for immediate submission, empty API responses, completed polling, and error polling without live Suno network calls.                                                                                                                                       |
| `tests/test_flux_capacitor_pipeline.py`                   | Config validation, model contracts, style preset clamping, prompt assembly, GPU orchestrator state machine, pipeline disabled/deferred/FAILED paths, DNS-unreachable FLUX service TEXT_ONLY fallback, story artifact persistence, service singleton.                                                  |
| `tests/test_gpu_orchestration_policy.py`                  | Ollama-first queue ordering, TEXT_ONLY timeout fallback, slot acquire/release lifecycle, exception-safe context manager, concurrency safety with multiple FLUX requests.                                                                                                                              |
| `tests/test_flux_capacitor_schedule_integration.py`       | Schedule-flow wiring: skips YouTube channel, records rendered metadata, catches and wraps exceptions as failed result.                                                                                                                                                                                |
| `tests/test_flux_capacitor_curate_console_integration.py` | Curate-flow wiring: skips youtube/all channels, rendered/deferred/failed paths, SourceMode.CURATE propagation. Console-flow wiring: empty-text guard, rendered/deferred/failed paths, SourceMode.CONSOLE propagation, None topic hint.                                                                |
| `tests/test_database_session_singleton.py`                | Thread-safe DB singleton initialization for `get_engine`/`get_session_factory`, and listener-scoping validation to prevent duplicate Pool-level callback registration.                                                                                                                                |
| `tests/test_flux_service_singleton.py`                    | Concurrent `get_flux_service` access validation to ensure a single shared `FluxCapacitorService` instance is constructed process-wide.                                                                                                                                                                |
