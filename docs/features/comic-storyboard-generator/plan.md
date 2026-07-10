# Implementation Plan: Persona-Grounded Comic Storyboard Generator

## Overview

This plan implements the comic storyboard feature defined in [idea.md](idea.md), [prd.md](prd.md), and [design.md](design.md). The target is a v1 CLI/console-first subsystem that generates deterministic 3-panel storyboard artifacts with grounding metadata and FLUX-backed rendering (with text-only fallback).

Scope is intentionally constrained to avoid web UI complexity and preserve existing schedule/curate/console stability.

## Project System Integration Summary

Primary integration points:
- `main.py` (CLI flag routing and entrypoint wiring)
- `services/ollama_service.py` (panel script generation)
- `services/flux_capacitor/` (panel rendering)
- `services/console_grounding/` + `services/derivative_of_truth/` (grounding/truth summaries)
- `GENERATED_CONTENT_DIR` local-first artifact persistence

New package target:
- `services/comic_storyboard/`

Expected docs to keep in sync:
- `docs/features/comic-storyboard-generator/idea.md`
- `docs/features/comic-storyboard-generator/prd.md`
- `docs/features/comic-storyboard-generator/design.md`
- `docs/testing-and-dev.md` (if test counts change)
- `README.md` and `docs/cli-reference.md` (if CLI flags are added)

## Pre-Implementation Checklist

- [ ] Confirm Docker full profile is available for FLUX render path.
- [ ] Confirm `GENERATED_CONTENT_DIR` behavior and writable artifact path policy.
- [ ] Confirm truth gate + DoT call points for caption-level validation.
- [ ] Confirm console command namespace for `/comic` (no collisions).
- [ ] Confirm v1 dedupe threshold default and skip policy behavior.

## Implementation Steps

### Step 1: Scaffold comic storyboard package

Status: [ ] Not Started
Effort: 4-6 hours
Description: Create new package skeleton and core models/config contracts.
Actions:
- Add package files under `services/comic_storyboard/`:
  - `__init__.py`
  - `_config.py`
  - `_models.py`
  - `_prompting.py`
  - `_parser.py`
  - `_grounding.py`
  - `_dedupe.py`
  - `_render.py`
  - `_storage.py`
  - `service.py`
- Define strongly typed dataclasses and status enums (`rendered`, `text_only`, `failed`, `skipped_duplicate`).
- Add env-driven defaults in `_config.py` (`COMIC_DEDUPE_THRESHOLD`, `COMIC_ALLOW_TEXT_ONLY_FALLBACK`, etc.).
Verification:
- `python -m py_compile` passes for new files.
- Imports work from project root without `sys.path` changes.
Dependencies:
- None
Project Integration:
- Establishes stable service boundary for later CLI/console wiring.

### Step 2: Implement script prompting + parsing normalization

Status: [ ] Not Started
Effort: 6-8 hours
Description: Generate structured panel script and normalize malformed output into exactly 3 panels.
Actions:
- Implement prompt builder for source modes (`schedule|curate|console`).
- Implement parser that extracts panel fields (`frame`, `setting`, `action`, `dialogue`, `caption`).
- Add normalization fallback to guarantee exactly 3 panel payloads.
- Add defensive handling for missing sections and malformed model output.
Verification:
- Unit tests cover well-formed, partial, and malformed outputs.
- Parser always returns 3 panels and 3 captions.
Dependencies:
- Step 1
Project Integration:
- Uses `services/ollama_service.py` as exclusive text generation interface.

### Step 3: Integrate grounding + truth metadata

Status: [ ] Not Started
Effort: 4-6 hours
Description: Attach evidence IDs and truth summary metadata for storyboard captions.
Actions:
- Add grounding adapter in `_grounding.py` to call existing grounding/DoT surfaces.
- Map per-caption checks into artifact-level summary.
- Define warning behavior when grounding is partial but generation continues.
Verification:
- Unit tests for success and partial-failure grounding cases.
- Result object includes `grounding_evidence_ids` and `truth_gradient_summary`.
Dependencies:
- Step 2
Project Integration:
- Reuses `services/console_grounding/` and `services/derivative_of_truth/`.

### Step 4: Implement dedupe gate

Status: [ ] Not Started
Effort: 3-5 hours
Description: Prevent near-duplicate storyboard generation from repeated source narratives.
Actions:
- Add source-hash + similarity comparison logic in `_dedupe.py`.
- Implement configurable threshold and skip/reuse result semantics.
- Persist dedupe decision into run metadata.
Verification:
- Unit tests for unique, near-duplicate, and threshold edge cases.
- `skipped_duplicate` status returned deterministically when triggered.
Dependencies:
- Step 1
Project Integration:
- Optional future hook to selection-learning signals.

### Step 5: Implement render pipeline + text-only fallback

Status: [ ] Not Started
Effort: 8-12 hours
Description: Render panel images sequentially through FLUX capacitor while preserving fallback behavior.
Actions:
- Implement `_render.py` to call FLUX capacitor for each panel in order.
- Enforce single-job sequential rendering and timeout-aware fallback.
- Support explicit text-only mode and implicit fallback on render failure/unavailability.
- Ensure stage timing/status tracking is collected.
Verification:
- Integration tests for FLUX-available path (`rendered`).
- Integration tests for FLUX-unavailable path (`text_only`).
- Partial panel failure behavior validated.
Dependencies:
- Step 2
Project Integration:
- Uses existing GPU orchestration policy from `services/flux_capacitor/`.

### Step 6: Implement artifact storage contract

Status: [ ] Not Started
Effort: 4-6 hours
Description: Persist storyboard artifacts and sidecar metadata under deterministic local paths.
Actions:
- Implement `_storage.py` writing to `${GENERATED_CONTENT_DIR}/comic_storyboards/<date>/<storyboard_id>/`.
- Persist:
  - `storyboard.json`
  - `run_meta.json`
  - `captions.txt`
  - `evidence.json`
  - `panel_1.png`, `panel_2.png`, `panel_3.png` (if rendered)
- Store relative paths and source hash for traceability/dedupe.
Verification:
- Unit tests validate file set across all terminal statuses.
- Failed runs still persist metadata artifacts.
Dependencies:
- Steps 3-5
Project Integration:
- Aligns with repo local-first generated content conventions.

### Step 7: Wire CLI entrypoints

Status: [ ] Not Started
Effort: 5-7 hours
Description: Add CLI flags and route generation calls from `main.py`.
Actions:
- Add `--comic` and related flag family (`--comic-source`, `--comic-style`, `--comic-text-only`, `--comic-dot-report`).
- Validate source mode combinations and error messaging.
- Route through `services/comic_storyboard/service.py`.
- Respect `--dry-run` behavior.
Verification:
- CLI smoke tests for each source mode.
- Invalid flag combinations produce actionable errors.
Dependencies:
- Steps 1-6
Project Integration:
- Must not regress existing `--schedule`, `--curate`, `--console` flows.

### Step 8: Wire console `/comic` command

Status: [ ] Not Started
Effort: 4-6 hours
Description: Add console command to generate storyboard from recent assistant context or explicit topic.
Actions:
- Add `/comic [optional hint]` handling in console command router.
- Resolve source text from recent session context when no explicit hint is provided.
- Return result summary with artifact path and status.
Verification:
- Console interaction test for default and hinted modes.
- Error handling test when no usable prior context exists.
Dependencies:
- Steps 1-7
Project Integration:
- Coexists with current console commands (`/verify`, `/dot-report`, etc.).

### Step 9: Testing and regression coverage

Status: [ ] Not Started
Effort: 8-12 hours
Description: Add unit/integration/regression tests for new package and wiring.
Actions:
- Add tests:
  - `tests/test_comic_storyboard_parser.py`
  - `tests/test_comic_storyboard_dedupe.py`
  - `tests/test_comic_storyboard_storage.py`
  - `tests/test_comic_storyboard_service.py`
  - CLI/console integration tests (targeted)
- Mock FLUX/Ollama where required for deterministic test runs.
Verification:
- `python -m pytest` targeted tests pass.
- Full suite passes.
Dependencies:
- Steps 1-8
Project Integration:
- Preserve test isolation and existing suite stability.

### Step 10: Documentation updates and release readiness

Status: [ ] Not Started
Effort: 3-5 hours
Description: Update user/developer docs and complete release checks.
Actions:
- Update `docs/cli-reference.md` with comic flags.
- Update `README.md` feature and usage sections.
- Update `docs/testing-and-dev.md` test counts if changed.
- Cross-link final docs in `docs/features/comic-storyboard-generator/`.
Verification:
- Markdown lint/sanity checks.
- Commands and examples validated against actual CLI behavior.
Dependencies:
- Steps 7-9
Project Integration:
- Ensures docs parity with implementation.

## Project Quality Gates

Development gates:
- [ ] All new Python files compile (`python -m py_compile`).
- [ ] New package follows modular file-size and responsibility constraints.
- [ ] No hardcoded secrets or cloud-only required credentials.

Integration gates:
- [ ] CLI + console wiring validated end-to-end.
- [ ] FLUX render and text-only fallback paths both validated.
- [ ] Grounding and truth metadata included in persisted artifacts.

Testing gates:
- [ ] New targeted tests pass.
- [ ] Full test suite passes.
- [ ] No regressions in existing schedule/curate/console workflows.

Documentation gates:
- [ ] README and CLI docs updated.
- [ ] Testing docs updated if counts change.
- [ ] Feature docs (`idea/prd/design/plan`) are consistent.

## Testing Phase Plan

1. Unit-first on parser/dedupe/storage contracts.
2. Service integration tests with mocked model/render dependencies.
3. CLI/console routing tests.
4. Docker full profile manual smoke test for rendered panels.
5. Core profile smoke test for text-only fallback.
6. Full regression run before merge.

## Post-Implementation

Completion checklist:
- [ ] Feature behavior matches PRD acceptance criteria.
- [ ] Artifacts are deterministic and reusable.
- [ ] Fallback behavior is user-visible and auditable.
- [ ] Docs and tests are fully synchronized.

Potential next-phase items (out of v1):
- Buffer carousel ordering and auto-attach workflow.
- Optional variable panel count.
- Advanced caption layout/compositing.
- Selection-learning feedback integration for storyboard quality scoring.
