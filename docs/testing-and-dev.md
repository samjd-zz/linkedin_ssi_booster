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
source .venv/bin/activate && python -m pytest --cov=services --cov=agents --cov=main --cov=cli --cov=scheduler --cov=content_calendar --cov-report=term-missing:skip-covered -q

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
| **1714** | **1712** | **0** | **0** | **2** | Previous run: **74%** | All executed tests passed |

- **Latest Run Date:** November 5, 2026 (local time)
- **Bounded lyric retries without canned songs:** Every language mode now permits five total lyric attempts. Malformed JSON, non-object payloads, leaked schema instructions, missing required sections, and short Choruses can recover on attempt five; otherwise composition raises `LyricCompositionError` with the final reason. No whole-song, Chorus, framing-section, or Japanese rescue-hook templates remain, and malformed retries cannot restore rejected drafts. Nine cases in `tests/test_rei_lyric_retries.py` cover recovery and exhaustion. Two additional CLI cases verify exit status 1, no traceback, failed-stage timing, and no formatting, saving, validation, or submission; console parity tests verify a reported failure with conversation history intact.
- **Intro semicolon regression:** Splitting a leading vocalization now also cleans the newly exposed lyric, so `(Ahh) ; lyric` cannot leave a leading semicolon behind. Concatenated Japanese vocalizations such as `(アッハアッハ)` and `(オオオ)` are recognized and separated before Romaji generation, keeping Japanese lyrics under Intro Verse and vocalizations out of pronunciation cues. Eight new cases bring `tests/test_rei_leading_semicolons.py` to 19 cases, including ASCII/fullwidth separators, clean hook selection, retained mid-line punctuation, empty tails, and idempotent assembly.
- **Latest Rei lyric cleanup:** Parenthetical `(Fade out)` and `(Chill)` directions become bracketed tags, inline `[Silence]`/`[Chaos]` cues move off sung lines, unmatched parentheses in Solo directions are closed, and Japanese-script vocalizations such as `（アッハ アッハ アッハ）` become `(Ahh ahh ahh)`. The composition gate retries a Chorus with fewer than two sung lines and fails explicitly if all five attempts remain too short. 7 cases in `tests/test_rei_suno_output_polish.py` cover these paths.
- **Configurable Rei stage profiles:** 43 cases in `tests/test_rei_stage_policy.py` verify explicit profile selection, the cyberpunk preset, required/optional and sung/instrumental sections, configurable headings, required cues and intro primers, profile-aware prompts/retries/failures, Japanese cue preservation, metadata, idempotent structured/freeform formatting, and fail-fast invalid configuration. `cyberpop` preserves the previous mandatory arrangement; `cyberpunk`, `acoustic`, `rock`, `hip_hop`, and `ambient` provide alternatives. See [stage-cue configuration and the genre catalog](rei-toei-stage-cues.md).
- **Console lyric parity:** 25 cases exercise structured CLI-equivalent console songs, including bare `/rei` auto-theme songs and rerouted freeform chat replies, with or without extracted themes, batched translation, Argos translation fallback, ratio and hook limits, direct-generation retries, explicit languages, retry directions, unsung stage cues, and reported errors without canned lyric replacements.
- **Latest Changes:** Large-file refactor with no behavior change: `main.py` command handlers moved into the `cli/` package (2,450 → 1,036 lines), `ContentCurator` channel/reporting/article code moved into mixins (`curator.py` 1,157 → 410 lines), and the Suno lyric pipeline split into focused `_suno_*`/`_lyric_*` helpers (`_suno_pipeline.py` 2,248 → 424 lines). Moved functions were AST-compared against the originals, `--help` output is unchanged, and tests that patched moved names now target `cli._flux_render`, `cli._schedule_cli`, `cli._rei_suno`, `cli._rei_strudel`, and `services.rei_toei._suno_themes`. 7 new curator article-helper cases (`tests/test_curator_articles.py`) verify concurrent prefetch targeting, invalid worker settings, all four `--learn` log variants, and swallowed extraction errors. 11 new garbled-output guard cases verify that token-salad replies (Latin glued to Chinese characters, code identifiers, symbol runs, stray scripts) are detected while English, Japanese teaching, mixed Japanese/English, technical, and French replies pass; that `chat_as_persona` unloads the model and retries once, then raises `GarbledOutputError`; and that a failed console turn is dropped from history. 8 new console truth-gate cases verify the separate `/truth-gate` toggle (off by default) shows the filtered reply with its layout kept, report toggles score quietly without removal logs, and quiet logging works in the gate itself. 16 new Rei song-tidy cases verify that leaked character-count notes such as `(34 chars)` or `(38 chars, UPPERCASE)` are removed whole instead of leaving `()` behind, and that echo parentheticals such as `PULSE CODE (Pulse Code)` are removed, stray `[Heavy Bass Drop]` cues outside the Drop are dropped, Bridge lines copied from the Chorus are removed, and dangling `、` endings are stripped. 11 new Rei hook-translation and Suno-cleanup cases verify that a 0.33 Japanese ratio now places several translated lines per section (default cap raised from 8 to 40), translation runs in batches of 10 with numbered JSON so partial replies keep their good lines, Ollama polite endings (`消えます`, `死にます`) become plain form, Japanese lines with leftover English words fall back to Argos, and `(Blank Line)` placeholders become real blank lines. 40 Rei hook-translation cases cover the English-first bilingual strategy (one song call plus one batched translation call, with an offline Argos en→ja fallback); legacy one-pass bilingual tests pin `REI_BILINGUAL_STRATEGY=generate`. 11 new Rei cases verify Chinese-grammar detection and repair (`在空中` → `が空に舞う` with a refreshed cue) and retries when the Chorus, Verse 2, or Bridge copies lines from earlier sections. 12 new Rei song-structure cases verify that a Verse 2 copying Verse 1 is detected and retried with targeted feedback, and that concept and lyric prompts request a central chorus metaphor, a post-turning-point Verse 2, and a climactic bridge. 19 Romaji-coverage cases verify joined verb endings (`sareru`, `hikatte`, `mirarenakatta`), re-joining of existing split cues such as `[segumentoka sa reru]`, and a cue on every uncued Japanese line, alongside 68 Rei lyric-cue cases covering contextual Japanese readings, explicit and ambiguous cue formats, inline pronunciations, translations and stage cues, particle pronunciation, unknown characters, tokenizer fallbacks, technical acronyms, prompt leakage, and CLI/console formatting. Prior Romaji cue-hygiene, Rei enforcement, nav-chrome, launcher, relevance, and performance regressions remain.
- **Latest Change:** Suno best practices are now scoped to `V6_MINI`, the app's default API model. The knowledge distinguishes official v6-family facts (including v6-mini), SunoAPI.org proxy model/field limits, and community lyric-format/Japanese guidance not specifically verified for v6-mini. The API client defaults to `V6_MINI` and caps titles at the proxy's documented 80 characters. Japanese prompt rules are sent only when the lyric-writing model generates Japanese or bilingual text. The parentheses rule no longer mentions ad-libs and forbids repeated-word echoes such as `(Shine shine)`. 8 cases in `tests/test_rei_suno_best_practices.py` cover model scope, source limits, prompt rule caps, empty sections, language filtering, and the no-echo rule; 19 cases in `tests/test_rei_word_echo_cleanup.py` verify that repeated-word ad-libs such as `(Shine shine)` are stripped from every section (standalone or trailing a lyric) while `(Ahh ahh ahh)`, `(Oh oh oh)`, `(Yeah yeah)` and other real vocalizations are kept; the API request test verifies the v6-mini default and title cap. The default profile's lyric quality gate requires Intro (with a sung Intro Verse), Verse 1, Chorus, Verse 2, Bridge, Drop (sung lines after `[Heavy Bass Drop]`), Solo, and Outro, judged after tidying; retries name the missing sections and fail if required content is still absent after five attempts, without borrowing sections from a canned song. 24 cases in `tests/test_rei_required_sections.py` cover this. Suno assembly now fits the tempo to the finished lyrics: the median syllables per sung line (Japanese mora weighted 0.6) raises, never lowers, the concept BPM (145 at 9 syllables, +6.25 per syllable, capped at 175) and adds a matching vocal-delivery style tag; 16 cases in `tests/test_rei_song_tempo.py` cover syllable and mora counting, the 170 BPM calibration, caps, overrides, and tag placement. Simplified-Chinese kanji in translated lines (脉动→脈動, 辉→輝, 发→発, …) are now mapped to Japanese forms, with simplified words such as 网络 and 重组 matched first; a translated hook that still has a non-Japanese or unreadable kanji is rejected so the English line stays, and the unreadable-kanji warning is logged once per lyric line with the line text. 25 cases in `tests/test_rei_simplified_kanji.py` cover this. Stray semicolons the model puts at the start of a lyric line or cue (`; signals…`, `[; Epic Guitar Solo]`, `；（アッハ）…`) are stripped before translation and again when sections are assembled; semicolon-only lines are dropped and mid-line semicolons are kept. 19 cases in `tests/test_rei_leading_semicolons.py` cover this.
- **Latest Fix:** English meanings are now sung instead of bracketed. A cue line such as `[Akai sureddo ga yami o hodoku] [Red threads unravel the dark]` under its Japanese line becomes `[akai sureddo ga yami o hodoku]` plus a sung `Red threads unravel the dark` line (skipped if the next line already sings it), acronyms such as `SQL` keep their capitals, and production cues such as `[Synth sweep]` stay bracketed. Lyric prompts and the customization guide use the same format. Malformed lyric JSON from Ollama is also repaired before retrying: stray inner quotes are escaped and orphan string lines are merged into the previous value (the `Expecting ':' delimiter` case). Unparseable revisions retry within the five-attempt budget and then fail without restoring a rejected draft. 8 gloss stage-cue cases, 5 JSON-repair cases (`tests/test_rei_suno_json_repair.py`), and 1 translate-mode retry case cover these paths. An inline `[Heavy Bass Drop]` prefix on a sung Drop line is also removed, so the Drop keeps exactly one cue (2 cases).
- **Previous Fix:** Intro vocalizations are always parenthesized (`[Ahh ahh ahh]` → `(Ahh ahh ahh)`), while parenthesized production directions such as `(Start with glitchy synth tones)` under `[Instrumental Build]` become bracketed. Echoed `(Instrumental Build)`/`Intro Verse` labels inside intro lines are removed, and duplicate intro vocalizations are dropped, so the `[Intro Verse]` holds only sung lyrics.
- **Previous Fix:** Standalone sung `Heavy Bass Drop` and `Bass Drop` cues, recognized Japanese translations, and their Romaji are removed before hook selection and during final formatting, while the bracketed drop cue and real lyrics remain. Exact chaos cues become `[Chaos]`, including parenthetical or standalone forms. 43 stage-cue cases plus one console-parity case cover both paths, prompt instructions, and preservation of sung lyrics and instrumental tags.
- **Previous Fix:** Rei lyrics no longer carry emoji such as `📐` into Suno output. Hook translations that contain emoji are rejected so Argos or the English line is used, hook text reaches the translators without emoji, the draft tidy pass strips emoji and drops emoji-only lines, and Suno assembly strips any remaining emoji before Romaji cues are generated; Japanese marks such as `ー`, `〜`, and `・` are kept. 24 cases cover the stripping rules, rejected translations with Argos fallback, the tidy pass, and emoji-free assembled sections and cues. The earlier fix routed bare `/rei` in `--console` through the same structured pipeline as `--rei-generate` with an auto-selected theme and replaced chat replies containing song sheets with structured songs (16 cases). 31 solo-palette regressions cover the loaded persona-aligned options, structured and console prompts, model-selected solos, custom and missing options, explicit invalid-configuration errors, stage-cue handling, preserved vocal parentheses, and structured/freeform cleanup. 4 prior Drop/Outro regressions cover parenthetical production directions and vocal ad-libs; 16 required-section/Solo regressions cover automatic repairs and instrumental formatting.
- **Latest Run Scope:** Entire suite except the two live Buffer API tests, explicitly deselected to avoid account/network access: **1,712 passed, 0 failed, 2 deselected** in 56.11 seconds. One existing non-terminal `term_image` warning remains. Coverage was not rerun.
- **Environment Specs:** Python 3.12.3, pytest 9.0.3, pytest-cov 7.1.0, coverage 7.17.0
- **Coverage Scope:** `services`, `agents`, `main`, `cli`, and `scheduler` measured with pytest-cov. `content_calendar` was also requested but never imported, producing a coverage warning; it is not included in the reported denominator.
- **Persona retrieval regression fix:** `test_persona_graph_retrieval.py` no longer hard-codes a private persona's project count. It compares loaded project IDs/order with the configured source JSON and verifies one evidence fact per project, including IDs, names, details, years, and skills. Fixture path overrides are restored even if loading fails. All 12 tests in that module pass; no persona data or production normalization behavior was changed.

### What These Results Measure

The latest run executed **1,712 of 1,714 collected tests**, all passing with
zero failures. The two live Buffer tests were explicitly deselected, not skipped
or counted as passing; live API behavior was not verified by this run.

The **74% source-coverage figure was measured November 4, 2026 (local time)**:
14,367 executable statements, 3,767 missed, and 10,600 executed (rounded to
74% by the report). A prior recorded measurement had 14,297 statements and
3,761 missed; the historical October 28 figure was 70%.
It measures statement coverage, not branch coverage or live API correctness.
`content_calendar` was not imported by the suite and is absent from the total.
Entry-point coverage was 55% for `main.py`, 66% for the `cli/` handlers split out of it
(61% combined), and 68% for `scheduler.py`.

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
  --cov=services --cov=agents --cov=main --cov=cli --cov=scheduler --cov=content_calendar \
  --cov-report=term-missing:skip-covered
```

Inspect both the test summary and coverage report before updating the badges.
The persona integration checks require the maintainer's local graph; when that
private graph is not configured, those checks retain their existing skip behavior.

### Test Suite Breakdown

- **565** Original core logic assertions
- Rei Toei validation covers foundation, Suno, Strudel, console routing, and CLI integration flags.
- **25** console/CLI lyric-parity cases (bare `/rei` auto-theme songs, rerouted freeform chat replies, theme selection, bilingual batching and retries, language modes, unsung stage cues, fallbacks, and error reporting)
- **51** Rei stage-cue cleanup cases (intro vocalizations normalized to `(Ahh ahh ahh)`, parenthesized production directions bracketed, echoed `(Instrumental Build)` labels and duplicates removed, English and Japanese bass-drop echoes, associated Romaji, preserved instrumental tags and real lyrics, bracketed chaos cues, prompt instructions, and structured/freeform output)
- **68** Rei lyric-cue regression cases (including parameterized reading and formatting cases)
- **23** Rei Romaji-coverage cases (joined verb endings, re-joined split cues, simplified-Chinese word replacement, and every-line cue backfill)
- **25** Rei Romaji-bracket cases (bare Romaji/pinyin wrapped in `[]`, extra guesses after a cue kept but bracketed, nested English glosses ignored, single-pass idempotent formatting, English lyrics and stage cues untouched)
- **53** Rei hook-translation cases (English-first bilingual songs: ratio-driven hook selection led by the chorus with several lines per section, content-free batch progress after lyric composition with no progress for empty or skipped batches, numbered-JSON translation with partial salvage, misaligned, Chinese, emoji, or mixed-English replies rejected, emoji removed from translator input, plain-form endings for Ollama and Argos output, Argos fallback, Japanese inserted above its English echo)
- **55** Rei Suno-cleanup cases (`(Blank Line)` placeholders removed, Chinese-grammar detection such as `在空中` → `が空に舞う` with a refreshed Romaji cue, parenthetical Japanese glosses moved to their own line without a Romaji duplicate, traditional-Chinese characters and syntax converted, `(bass drop)` turned into `[Heavy Bass Drop]`, sung intro lines tagged `[Intro Verse]`, emoji stripped while Japanese marks stay, emoji-only lines dropped, and assembled sections and Romaji cues kept emoji-free)
- **15** Rei song-structure cases (lines borrowed across sections retried with the copies named, natural rhyme/meter prompt rules, Verse 2 repetition retry, bridge depth, bridge-before-drop order, metaphor/turning-point prompts)
- **17** Rei song-tidy cases (leaked `(N chars)` notes and empty `()` removed, echo parentheticals removed while `(Oh oh oh)` and glosses stay, drop cues kept only in `[Drop]`, Bridge chorus copies removed unless the Bridge would be empty, dangling `、` stripped from Japanese lines and translations, emoji stripped before hook selection)
- **8** console truth-gate cases (`/truth-gate` toggle off by default, filtered reply shown with its line layout kept, report toggles score quietly, `log_removals=False` keeps gate removals at DEBUG)
- **11** garbled-output guard cases (token salad flagged, 6 clean reply styles pass, retry after model unload, clear error after a second garbled reply, failed console turn dropped from history)
- **14** JSON-grammar compatibility and translation-failure cases (native format policies, invalid config, JSON thread contracts, fallback models, and batch failure followed by Argos without losing prior results)
- **16** required-section/Solo quality cases (intro/drop repairs, Japanese hook cues, section order and metadata, canonical labels, instrumental directions, no nested brackets, and console normalization idempotency)
- **31** Rei solo-palette cases (persona options, both prompts, dynamic choice, configuration validation, stage-cue protection, and vocal parentheses)
- **4** Drop/Outro production-cue cases (bracketed production directions, vocal ad-libs left in parentheses, and parentheticals outside Drop/Outro unchanged)

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
- **24** Article-evidence relevance regressions (new)
- _English/Japanese content matching, capitalized names, no duplicate lemma/raw credit, metadata/stopword/year rejection, per-type maximums, hybrid/fallback filtering, prompt safety, actual-evidence explanations, current-article learning, and full extracted IDs_
- **10** Docker launcher/model-initializer tests (replace the prior forced-build test)
- _Six Compose argument scenarios each exercise successful and failed cached-only GPU probes; four initializer cases cover fully cached models, missing fallback, no fallback, and fail-fast pulls._

---

## Cache-First Launcher Regressions

`tests/test_run_script.py` runs the real shell scripts with fake Docker/Ollama
executables. It verifies Compose arguments are unchanged (including quoted values),
explicit `run --build` / `up --build` / `build app` work, ordinary launches add no
build flags, and the GPU probe always uses `--pull=never`. Cached primary/fallback
models issue only local `show` calls; missing models pull, and failed pulls stop
initialization without a success message. No containers or live downloads are used.

```bash
bash -n run.sh
sh -n scripts/ensure-ollama-models.sh
source .venv/bin/activate && python -m pytest -q tests/test_run_script.py
```

CPU/NVIDIA and Intel/WSL Compose initializer wiring was checked, and all three GPU
override configurations passed `docker compose config -q` validation. These checks
do not certify real GPU passthrough or full-stack disconnected operation.
See [running with cached images/models](features/docker-cache-first.md).

## Article-Evidence Relevance Regressions

`tests/test_evidence_relevance.py` contains 24 deterministic cases. Language-model
tokenization is mocked to cover both lemma behavior and missing-model fallback;
no Ollama, Buffer, external retrieval, or knowledge-file writes are needed.
`services/evidence_relevance.py` has **100% statement coverage (33 statements)**.
The existing extracted-grounding prompt test additionally verifies genuinely
related “Managed Agents” context is retained with the installed English tokenizer.

```bash
source .venv/bin/activate && python -m pytest -q \
  tests/test_evidence_relevance.py tests/test_ollama_extracted_grounding.py \
  tests/test_content_curator.py tests/test_continual_learning.py \
  tests/test_performance_flux_gating.py tests/test_console_performance.py
```

Separately, a read-only check against the local 617-fact corpus rejected all five
festival facts from the reported Replit and Google headlines, returned no stored
matches for the Replit headline alone, and found Japanese music facts for a
Japanese music query without the local Japanese spaCy model. These observations
are corpus-specific, not unit-test fixtures or a claim of semantic correctness.
See [curation relevance safeguards](learning-pipeline.md#curation-relevance-safeguards).

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

Log prefixes distinguish ▶️ stage start, ✅ successful completion, ❌ failed
completion, 🤖 Ollama request, and ⏱️ Ollama server timings. Existing field
names, log levels, and timing units are unchanged; failed stages still propagate
their exceptions. Icon/field assertions are included in the existing six
`tests/test_performance.py` tests (no test-count change). The focused
timing/console/schedule/cleanup/Rei-preview run passed **65 tests**.
Stage-start and Ollama-timing messages use two ASCII spaces after their icons
(`▶️  Stage start`, `⏱️  Ollama timing`) for clearance with wide emoji rendering. The exact spacing
is covered by the existing timing tests; the spacing-only validation passed **6 tests**.
Ollama timing records also append `done_reason` exactly as returned by the server:
`stop` indicates a normal stop (including stop sequences), `length` indicates a
generation-limit stop, and `None` means the server did not supply a reason.
Other values are preserved rather than reclassified. This adds tracing only;
it does not alter token limits, retries, or output handling. Existing timing tests
cover these values, missing reasons, and propagation through `_chat` without
logging prompts or generated content (no test-count change). The focused
timing/console/Rei-preview run passed **35 tests**.

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

`tests/test_rei_preview_performance.py` runs the CLI with isolated mocks: no live Ollama, GitHub, Suno, or Buffer calls. It verifies that explicit-theme previews skip unused avatar loading, auto-theme previews read history once, explain mode retains DoT evidence validation, both music modes reuse the CLI client, the default model remains unchanged, and console mode still receives GitHub context. Preview writes no song artifact or media and never submits to Suno. Tests also require concept/lyric/formatting stage records. Failed lyric composition in preview and normal runs exits with status 1 and no traceback, records a failed timing stage, and never formats, saves, validates, or submits the song. See [runtime behavior](features/rei-toei/preview.md) for corrected command examples and retry expectations.

### Rei Japanese lyric-cue repair

`tests/test_rei_lyric_cue_repair.py` covers explicit and ambiguous Romaji/meaning formats, contextual SudachiPy plus pykakasi readings, particles, unreadable-character warnings, fallback behavior, technical acronym line breaks, leaked prompt instructions, assembled songs, and standalone freeform formatting. `tests/test_rei_romaji_coverage.py` checks that auxiliary verbs and conjunctive particles stay joined to their verb, that existing cues split only by spacing are re-joined while macrons and capitals are preserved, and that every uncued Japanese line receives a cue while English lines stay sung. `tests/test_rei_romaji_brackets.py` checks that bare Romaji or pinyin guesses under Japanese lines are bracketed, extra guesses below an existing cue are kept but bracketed (never deleted), and English lyrics and stage cues are left alone. `tests/test_rei_suno_cleanup.py` checks that `English (日本語 romaji)` glosses become an English line plus a Japanese line with no phonetic duplicate (Romaji cue lines under the gloss are dropped, while English meaning lines, meta tags and ordinary Japanese-line cues stay), that `信號`/`由程式重塑` become `信号`/`プログラムで再構築`, that own-line instrument cues become Suno meta tags while vocalizations stay in parentheses, and that sung intro lines move to `[Intro Verse]`. Generated Japanese and English meanings remain subject to human review; no live LLM or Suno call is made by these tests.

### Console/CLI Rei Toei lyric-language misalignment — `_rei_console.py` and `_suno_pipeline.py`

CLI and console song requests now share `generate_song_concept`, `compose_lyrics`, and `assemble_suno_prompt`, including translation batches, Argos fallback, and `generate`-mode mix validation. The console uses a user topic without loading extracted knowledge, or selects a theme from that knowledge, Rei's metaphor library, or a general digital-creativity theme. Propagated failures are reported instead of falling back to an unvalidated freeform song. A bare `/rei` composes on an auto-selected theme, like `--rei-generate` without `--rei-theme`; Rei's chat prompt does not request song sheets, and a chat reply containing section-tagged lyrics or a `Suno Prompt:` line is replaced by a structured song. Retry directions remain in both structured prompts. English mode now requests English-only lyrics; this is a prompt, not a language guarantee. `tests/test_rei_console_song_parity.py` exercises these paths with mocked Ollama and Argos. `test_assemble_suno_prompt_flips_japanese_first_bilingual_lines` in `tests/test_rei_toei_service.py` also checks that only English choruses are forced to ALL-CAPS.

### Bilingual Japanese-line target enforcement — `_suno_pipeline.py`

With the default `REI_BILINGUAL_STRATEGY=translate`, the song is written in English and selected hook lines are translated toward the target; the final ratio can vary with available hooks and translation results (see `tests/test_rei_hook_translation.py`). The rest of this paragraph describes the `generate` strategy. `REI_JAPANESE_LYRIC_PROBABILITY` is a per-song target for lyric lines containing Japanese script, not the probability of selecting Japanese for an entire song. A bilingual draft must contain both languages and stay within a ratio tolerance of `max(0.33, 1 / total_lines)` (so a 15% target normally rejects drafts above 48% Japanese). The composer permits five total attempts: attempt 2 adds hard constraints, later attempts add explicit per-section language assignments. Missing Japanese script or an invalid final mix causes an explicit composition failure without rescue hooks or canned lyrics. Generated JSON accepts literal lyric line breaks, expands leaked `\n` sequences before language validation, and removes serialized quote/punctuation artifacts during Suno formatting. A malformed retry consumes an attempt without restoring the rejected draft. After validation-code changes, explicitly rebuild the app (`run --build` or `build app`); normal launches reuse the existing image. Covered by `test_compose_lyrics_bilingual_retries_when_first_attempt_is_single_language`, `test_compose_lyrics_rejects_bilingual_output_outside_target_ratio`, `test_compose_lyrics_rejects_serialized_all_japanese_draft_after_malformed_repairs`, `test_assemble_suno_prompt_normalizes_serialized_lyric_artifacts`, `test_bilingual_mix_counts_mixed_lines_as_japanese_lines`, `test_bilingual_mix_accepts_the_tolerance_boundary`, and `test_parse_llm_json_payload_allows_literal_newlines_in_lyric_values` in `tests/test_rei_toei_service.py`, plus `test_launcher_preserves_compose_arguments` in `tests/test_run_script.py`.

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
| `cli/`                          | ✅ Active     | **8 Focused Submodules:** `_parser`, `_admin`, `_schedule_cli`, `_curate_cli`, `_rei_cli`, `_rei_suno`, `_rei_strudel`, `_flux_render` — command handlers dispatched by `main.main()`. |
| `services/content_curator/`     | ✅ Active     | **12 Focused Submodules:** `curator`, `_curator_base`, `_articles`, `_channel_all`, `_channel_single`, `_reporting`, `_config`, `_rss_fetcher`, `_ssi_picker`, `_evidence_paths`, `_text_utils`, `_grounding`. |
| `services/avatar_intelligence/` | ✅ Active     | **10 Focused Submodules:** `_paths`, `_models`, `_loaders`, `_normalizers`, `_retrieval`, `_grounding`, `_learning`, `_confidence`, `_narrative`, `_extraction`. |
| `services/console_grounding/`   | ✅ Active     | **6 Focused Submodules:** `_config`, `_models`, `_profile_parser`, `_retrieval`, `_gate_helpers`, `_truth_gate`.                                                 |
| `services/selection_learning/`  | ✅ Active     | **10 Focused Submodules:** `_constants`, `_models`, `_storage`, `_text`, `_logging`, `_published`, `_reconcile`, `_priors`, `_ranking`, `_feedback`.             |
| `services/rei_toei/`            | ✅ Active     | **Focused Submodules:** `_config`, `_models`, `_loaders`, `_lyric_romaji`, `_lyric_checks`, `_lyric_prompts`, `_hook_translation`, `_argos_fallback`, `_solo_options`, `_suno_client`, `_suno_pipeline` (orchestration) plus `_suno_*` helpers (concept, themes, tags, sections, blocks, JSON, cleanup, quality, validation, submission, fallback), `_strudel_pipeline`, `service`. |
| `services/flux_capacitor/`      | ✅ Active     | **7 Focused Submodules:** `_config`, `_models`, `_prompting`, `_pipeline`, `_storage`, `_terminal`, `__init__` — GPUOrchestrator, FluxCapacitorService, style presets, terminal display. |

---

## Comprehensive Test File Mapping

| Targeted Test File Vector                                 | Detailed Functional Coverage Matrix                                                                                                                                                                                                                                                                   |
| --------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tests/test_rei_lyric_cue_repair.py`                      | Contextual Japanese readings, cue verification, safe fallbacks, prompt cleanup, technical acronyms, and structured/freeform song formatting.                                                                                                                                                                  |
| `tests/test_rei_romaji_coverage.py`                       | Joined verb-ending Romaji, re-joined split cues, and cue backfill for every uncued Japanese line.                                                                                                                                                                                                                            |
| `tests/test_rei_romaji_brackets.py`                       | Bare Romaji and extra guesses bracketed, English and stage cues untouched.                                                                                                                                                                                                                                             |
| `tests/test_rei_suno_cleanup.py`                         | Gloss lines split without Romaji, Chinese fixed, emoji stripped, cue tags, intro verse.                                                                                                                                                                                                                               |
| `tests/test_rei_stage_cue_cleanup.py`                    | Bass-drop cue echoes removed; one `[Heavy Bass Drop]` per Drop; chaos bracketed; intro vocalizations parenthesized; bracketed English meanings become sung lines; real lyrics and stage tags preserved. |
| `tests/test_rei_suno_best_practices.py`                  | v6-mini-specific domain scope, sourced model limits, capped prompt rules, language filtering, and the no-echo parentheses rule. API request test verifies the v6-mini default and title cap. |
| `tests/test_rei_word_echo_cleanup.py`                    | Repeated-word parenthetical ad-libs such as `(Shine shine)` are removed in every section, standalone or after a lyric; real vocalizations and the intro primer are kept. |
| `tests/test_rei_required_sections.py`                    | Required-section gate: every section present and sung (Intro Verse, Drop lines, Solo directions, Outro), retry feedback naming missing sections, and explicit failure without framing or full-song replacement. |
| `tests/test_rei_lyric_retries.py`                        | Five-attempt recovery from malformed/non-object JSON, schema leakage, missing sections, or short Choruses; bounded failure in every language mode with no hook translation or rejected-draft reuse. |
| `tests/test_rei_stage_policy.py`                         | 43 domain-driven stage-profile cases: shipped genre profiles, mandatory/optional content, cue and primer controls, prompt/retry/fallback parity, custom headings, metadata, Japanese cue safety, idempotence, and invalid settings. |
| `tests/test_rei_song_tempo.py`                           | Lyric-fitted tempo: English syllable and Japanese mora counts, dense lyrics raised to about 170 BPM, short lines kept, cap and domain overrides, delivery tag placement, and assembly metadata. |
| `tests/test_rei_simplified_kanji.py`                     | Simplified-kanji repair: mappings to Japanese forms, whole-word precedence, rejection of non-Japanese or unreadable translations (English kept), and one unreadable-kanji warning per line with its text. |
| `tests/test_rei_leading_semicolons.py`                   | 19 cases: `;`/`；` stripped at line/cue starts and after vocalization splitting, clean hook selection, concatenated Japanese vocalizations normalized before Romaji, semicolon-only lines dropped, mid-line punctuation and idempotent assembly preserved. |
| `tests/test_rei_suno_output_polish.py`                   | Stage directions become bracketed cues, inline sound tags move to their own lines, Japanese vocalizations are normalized, malformed Solo parentheses are repaired, and an undersized Chorus is retried or fails explicitly. |
| `tests/test_rei_suno_json_repair.py`                     | Malformed lyric JSON repair: stray inner quotes escaped, orphan string lines merged, valid JSON untouched. |
| `tests/test_rei_solo_options.py`                         | Configurable solo palette, both generation prompts, dynamic choice, validation, stage cues, and preserved vocal parentheses. |
| `tests/test_rei_song_structure.py`                        | Verse 2 repetition detection and retry, bridge depth, bridge-before-drop order, and song-development prompt contracts.                                                                                                                                                                                                                                 |
| `tests/test_rei_console_routing.py`                       | Rei Toei console routing: command parsing, sticky Rei mode, song/pattern heuristics, user topics, autonomous theme selection, bare `/rei` auto-theme songs, freeform-song detection and reroute, conversation-only prompt, and persona isolation. |
| `tests/test_rei_console_song_parity.py`                   | Shared structured song pipeline, translation batches and Argos fallback, language and hook settings, direct-generation retries, user directions, bare `/rei` and rerouted chat songs, and error handling. |
| `tests/test_avatar_state_loader.py`                       | Confirms graph structural configurations, narrative memory loading, malformed input recovery routines, and multi-file asset joining (`domain_knowledge_*.json`, including `domain_knowledge_romaji.json`).                                                                                            |
| `tests/test_buffer_service.py`                            | Exercises the GraphQL API wrapper connectivity layers, buffer item queues, and content idea generation.                                                                                                                                                                                               |
| `tests/test_scheduler_queue.py`                           | Verifies schedule mode sends all selected posts to Buffer's queue without explicit `scheduled_at` timestamps, even when legacy scheduler environment variables are present.                                                                                                                           |
| `tests/test_piper_service.py`                             | Verifies Wyoming Piper TTS protocol behaviors, header parsing, byte payload streaming, and sound device mapping.                                                                                                                                                                                      |
| `tests/test_confidence_scoring.py`                        | Tests extracted heuristic signals, routing rules, and execution scoring boundaries.                                                                                                                                                                                                                   |
| `tests/test_content_curator.py`                           | Drives RSS fetch pipelines, keyword screening constraints, SSI adaptive category shifts, and module routing layouts.                                                                                                                                                                                  |
| `tests/test_curator_articles.py`                          | Curator article prefetch targeting, invalid worker settings, `--learn` log variants with prefetched text, and swallowed extraction errors.                                                                                                                                                            |
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
