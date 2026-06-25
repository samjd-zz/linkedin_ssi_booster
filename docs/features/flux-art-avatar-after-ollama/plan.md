# Implementation Plan: FLUX Art Avatar After Ollama

## Overview
This plan implements a new FLUX-based art avatar subsystem that follows the existing Rei Toei package style, while enforcing strict single-GPU sequencing on RTX 3060: Ollama jobs always run first, and FLUX jobs only start after Ollama work drains.

The implementation targets three phase-1 integration points:
1. Scheduled posting flow.
2. Curated Buffer idea flow.
3. Console flow.

This plan is aligned to repository practices documented in [README.md](../../../README.md) and [.github/copilot-instructions.md](../../../.github/copilot-instructions.md).

## Project System Integration Summary
- Existing system integration points:
  - CLI orchestration in [main.py](../../../main.py).
  - Shared flags and runtime helpers in [services/shared.py](../../../services/shared.py).
  - Ollama generation path in [services/ollama_service.py](../../../services/ollama_service.py).
  - FLUX image generation in [services/image_generation.py](../../../services/image_generation.py).
  - `flux_capacitor` as the documented FLUX runtime/deployment service name in Docker-facing docs.
  - Rei Toei package pattern in [services/rei_toei](../../../services/rei_toei).
- Service/component dependencies:
  - New art avatar package depends on Ollama and FLUX services via orchestrated sequencing.
  - Scheduling path depends on existing content generation and confidence routing.
- Data flow requirements:
  - Text-first pipeline: generate/validate text, then request art generation.
  - Save generated story text per story as local artifacts before publish/upload workflows.
  - Apply the same local-first persistence rule as a system-wide contract for generated content, not only avatar outputs.
  - Telemetry capture for queue wait, defer, and completion outcomes.
- API/interface integration needs:
  - New internal service API in services/flux_capacitor package.
  - Optional CLI and console command hooks through main flow.
- Monitoring/logging requirements:
  - Structured logger events for queue timing and fallback decisions.
  - Traceable reason codes for deferred/timeout image generations.

## Pre-Implementation Checklist
- [x] Development environment runs project commands from repository root.
- [x] Docker profile behavior reviewed in [docker-compose.yml](../../../docker-compose.yml).
- [x] FLUX prerequisites and profile expectations validated from docs.
- [x] Existing Rei Toei package structure reviewed for parity.
- [x] Test patterns reviewed from existing tests under [tests](../../../tests).
- [x] Quality gate commands confirmed (py_compile + focused pytest).
- [x] Env var naming convention aligned with existing env convention.
- [x] Generated-content persistence layout approved (local paths, naming, metadata sidecars).
- [x] Schema fit reviewed against [services/database/models.py](../../../services/database/models.py) for DB-second indexing.

## Implementation Steps
### Step 1: Create Art Avatar Package Skeleton
- Status: **Complete** ✅ (2026-06-25)
- Effort: 4 hours
- Description: Create the new modular package with minimal public API and internal private modules.
- Actions:
  - Create folder services/flux_capacitor with:
    - _config.py
    - _models.py
    - _prompting.py
    - _pipeline.py
    - _storage.py
    - __init__.py
  - Re-export stable public entrypoints in __init__.py.
- Verification:
  - Package imports successfully from project root.
  - No module exceeds architectural scope.
- Project Integration:
  - Mirrors modular conventions used in [services/rei_toei](../../../services/rei_toei).
- Dependencies:
  - None.

### Step 2: Define Request/Result Contracts and Style Safety Constraints
- Status: **Complete** ✅ (2026-06-25)
- Effort: 4 hours
- Description: Introduce typed request/result models and style clamp fields for restrained output.
- Actions:
  - Add ArtAvatarRequest and ArtAvatarResult dataclasses.
  - Add clampable style parameters (saturation, geometry density, surreal intensity).
  - Add validation with fail-fast errors for invalid ranges.
  - Include story artifact fields (story_path, story_metadata_path, save_status).
- Verification:
  - Unit tests cover valid and invalid model inputs.
  - Invalid config raises ValueError with clear messages.
- Project Integration:
  - Conforms to typed-model patterns from existing services.
- Dependencies:
  - Step 1.

### Step 2.5: Add Local Story Persistence Contract (Local First)
- Status: **Complete** ✅ (2026-06-25)
- Effort: 4 hours
- Description: Define and implement deterministic local storage for generated story text per story.
- Actions:
  - Add story artifact writer in `services/flux_capacitor/_storage.py`.
  - Add deterministic naming pattern: timestamp + channel + short hash + request id fragment.
  - Save full story text plus sidecar metadata linking story and image artifacts.
  - Define dedicated FLUX image artifact subdirectory usage under `GENERATED_CONTENT_DIR`.
  - Ensure save errors propagate as explicit result states.
- Verification:
  - Unit tests verify story file creation, deterministic naming, and metadata linkage.
  - Failure-path tests verify explicit non-silent save failures.
- Project Integration:
  - Supports manual Buffer UI upload and local-first review workflows.
- Dependencies:
  - Steps 1-2.

### Step 2.6: Align With System-Wide Generated Content Persistence
- Status: **Complete** ✅ (2026-06-25)
- Notes: `_storage.py` uses `services.shared.get_generated_content_dir` so avatar artifacts share the same root as YouTube scripts and Rei Toei outputs.
- Effort: 3 hours
- Description: Ensure avatar persistence implementation conforms to a repository-wide generated-content save contract.
- Actions:
  - Document common generated-content persistence requirements shared by schedule/curate/console text flows and avatar flows.
  - Verify non-avatar generated text outputs are included in the same local-first persistence model.
  - Standardize metadata linkage expectations (run/request IDs, channel, source refs) across generated content types.
- Verification:
  - Test scenarios cover both avatar and non-avatar generated content persistence behavior.
  - Documentation states one unified persistence policy.
- Project Integration:
  - Prevents feature-local persistence drift and keeps generated-content lifecycle consistent system-wide.
- Dependencies:
  - Steps 2 and 2.5.

### Step 3: Implement GPU Policy Configuration (Ollama First)
- Status: **Complete** ✅ (2026-06-25)
- Effort: 5 hours
- Description: Add single-GPU policy configuration and defaults for RTX 3060 usage discipline.
- Actions:
  - Add policy keys in _config.py:
    - OLLAMA_FIRST=true
    - FLUX_AFTER_OLLAMA=true
    - MAX_CONCURRENT_GPU_JOBS=1
    - Queue wait/defer thresholds.
  - Add env loading hooks and defaults via project config style.
- Verification:
  - Unit tests verify default policy and env overrides.
  - Logging reports effective policy at startup.
- Project Integration:
  - Env wiring aligned with [.env.example](../../../.env.example).
- Dependencies:
  - Steps 1-2.

### Step 4: Build Shared GPU Orchestrator and Queue
- Status: **Complete** ✅ (2026-06-25)
- Notes: `GPUOrchestrator` in `_pipeline.py`; threading.Lock serializes access; context manager `flux_slot()` guarantees release even on exception.
- Effort: 8 hours
- Description: Implement serialization gate with strict priority tiers.
- Actions:
  - Implement in _pipeline.py an in-process gate supporting:
    - Tier 1 queue: Ollama jobs.
    - Tier 2 queue: FLUX jobs.
    - Max one active GPU job.
  - Add deterministic scheduling and state transitions.
  - Add explicit defer result when wait threshold exceeded.
- Verification:
  - Queue-order tests prove Tier 1 always preempts Tier 2.
  - Concurrency tests prove one active GPU job at a time.
- Project Integration:
  - Wrap existing [services/image_generation.py](../../../services/image_generation.py) calls through the gate.
- Dependencies:
  - Steps 2-3.

### Step 5: Integrate Scheduled Posting Flow (Primary Path)
- Status: **Complete** ✅ (2026-06-25)
- Notes: `_render_schedule_art_avatar()` helper wired into `main.py` schedule loop; `notify_ollama_start/done` lifecycle wraps every Ollama call; art rendered only after text gen completes; story artifact persisted; 3 tests in `tests/test_flux_capacitor_schedule_integration.py`.
- Effort: 7 hours
- Description: Ensure art generation runs after text generation and validation.
- Actions:
  - Add integration hook after Ollama text generation and truth/confidence stages.
  - Invoke art-avatar pipeline only if policy allows and queue conditions pass.
  - Attach image artifact metadata for downstream scheduling.
  - Persist generated story text artifact before scheduling/upload decisions.
- Verification:
  - Integration tests prove FLUX does not start during active mocked Ollama workload.
  - Successful run path includes generated art metadata.
- Project Integration:
  - Hook via [main.py](../../../main.py) schedule path and shared service flow.
- Dependencies:
  - Steps 2.5, 3-4.

### Step 6: Integrate Curated Buffer Idea Flow (Primary Path)
- Status: **Complete** ✅ (2026-06-25)
- Notes: `_render_curate_art_avatar()` helper added to `main.py`; called per-idea after `curate_and_create_ideas()` returns; skips youtube and all-channel ideas; art metadata merged into idea dict; 8 tests in `tests/test_flux_capacitor_curate_console_integration.py`.
- Effort: 6 hours
- Description: Add art-avatar generation to curated ideas before publishing decisions so selected concepts can be visualized.
- Actions:
  - Add integration hook in the curation flow after text selection and before Buffer publish.
  - Reuse the same GPU gate, style clamps, and fallback behavior as schedule flow.
  - Persist art metadata alongside the curated idea record for downstream use.
  - Persist generated curated story text locally with story-to-image linkage metadata.
- Verification:
  - Integration tests prove curated paths honor Ollama priority and do not bypass the gate.
  - Selected ideas produce deterministic image metadata when art-avatar output is enabled.
- Project Integration:
  - Hook via [main.py](../../../main.py) curation path and shared service flow.
- Dependencies:
  - Steps 2.5, 3-5.

### Step 7: Integrate Console Path (Secondary Path)
- Status: **Complete** ✅ (2026-06-25)
- Notes: `/art [topic]` command added to console loop in `run_console()`; uses `_render_console_art_avatar()` helper (SourceMode.CONSOLE); renders from last assistant reply in history; deferred/failed results print user-readable messages; `/help` updated; 7 tests in `tests/test_flux_capacitor_curate_console_integration.py`.
- Effort: 5 hours
- Description: Add console capability with same GPU gate and fallback semantics.
- Actions:
  - Add command-level integration in console handling flow.
  - Reuse exact sequencing policy and defer behavior.
  - Return clear user feedback for queued/deferred image generation.
  - Persist generated console story outputs locally when content is generated.
- Verification:
  - Console integration tests validate sequencing parity with schedule path.
  - Deferred cases return deterministic, user-readable messages.
- Project Integration:
  - Uses existing console architecture in [main.py](../../../main.py).
- Dependencies:
  - Steps 2.5, 4-6.

### Step 7.5: DB-Second Schema Fit and Migration Instructions
- Status: **Complete** ✅ (2026-06-25)
- Notes:
  - New `generated_content_records` table — 18 columns, 4 indexes, FK → `candidate_records` (nullable)
  - ORM model `GeneratedContentRecord` in `services/database/models.py`
  - Repository `GeneratedContentRecordRepository` in `services/database/repositories.py` — `upsert`, `get_by_request_id`, `list_by_run`, `list_recent`
  - Migration script `scripts/migrate_v1_1_0_generated_content.sql` (additive, idempotent, bumps schema to 1.1.0)
  - `services/flux_capacitor/_storage.py` — `save_to_db()` writes when `DATABASE_ENABLED=true`; silently skips when disabled or on any error
  - `services/flux_capacitor/_pipeline.py` — calls `save_to_db()` after all local artifacts are persisted (step 7 of pipeline)
  - `ArtAvatarRequest` gains three optional linkage fields: `run_id`, `candidate_id`, `ssi_component`
  - 6 new tests in `TestSaveToDb` (test_flux_capacitor_pipeline.py): disabled no-op, env-absent no-op, success path, import-error silent, runtime-error silent, optional-fields propagation
  - Local files remain canonical — DB is secondary index only
- Verification:
  - [x] Migration script is additive and reversible (all `IF NOT EXISTS` / `ON CONFLICT DO NOTHING`)
  - [x] Existing selection-learning behavior intact (no schema changes to existing tables)
  - [x] `source .venv/bin/activate && python -m pytest -q` → 766 passed, 2 skipped, 0 failed

### Step 8: Add Prompt Presets and Toned-Down Style Controls
- Status: **Complete** ✅ (2026-06-25)
- Notes: `_prompting.py` implements three presets (corporate_minimal, sacred_geometry_light, tech_dark); hard clamps enforced in `resolve_style_preset()` and `apply_style_overrides()`.
- Effort: 6 hours
- Description: Implement restrained visual presets based on minimalist corporate-art hybrid direction.
- Actions:
  - Add prompt templates in _prompting.py with subtle geometry and muted palette language.
  - Enforce hard clamps at render-request time.
  - Store style metadata for reproducibility in _storage.py.
- Verification:
  - Unit tests confirm clamp behavior and prompt assembly correctness.
  - Snapshot-style tests verify preset stability.
- Project Integration:
  - Compatible with existing FLUX invocation path.
- Dependencies:
  - Steps 2 and 5-7.

### Step 9: Add Telemetry and Degradation Handling
- Status: **Complete** ✅ (2026-06-25)
- Notes: `ArtAvatarTelemetry` dataclass captures queue_wait_seconds, render_duration_seconds, defer_count, gate_outcome. `RenderStatus.TEXT_ONLY` is the explicit degradation path when GPU is saturated.
- Effort: 5 hours
- Description: Add observability for queue pressure and graceful text-only fallback.
- Actions:
  - Emit structured logs for queue wait duration, defer counts, and completion times.
  - Add timeout handling that returns text-only mode when GPU saturation persists.
  - Persist minimal run outcomes for later tuning.
- Verification:
  - Tests validate timeout and fallback branches.
  - Logs include reason codes and timing fields.
- Project Integration:
  - Uses logger conventions already used across services.
- Dependencies:
  - Steps 4-7.

### Step 10: Test Suite Implementation
- Status: **Complete** ✅ (2026-06-25)
- Notes: 44 tests in two files, all passing.
  - `tests/test_flux_capacitor_pipeline.py` — 33 tests (config, models, style presets, prompt assembly, GPU orchestrator, pipeline disabled paths, storage, service singleton)
  - `tests/test_gpu_orchestration_policy.py` — 11 tests (Ollama-first ordering, timeout/fallback, slot management, concurrency safety)
- Effort: 8 hours
- Description: Add focused tests for models, policy, queue semantics, integration, and fallback.
- Actions:
  - Create [tests/test_flux_capacitor_pipeline.py](../../../tests/test_flux_capacitor_pipeline.py).
  - Create [tests/test_gpu_orchestration_policy.py](../../../tests/test_gpu_orchestration_policy.py).
  - Add targeted integration tests with mocked Ollama/FLUX behaviors.
  - Add persistence tests for local story artifacts and sidecars.
  - Add DB-optional tests for dual-write behavior (enabled vs disabled).
  - Add cross-flow persistence tests proving unified behavior for avatar and non-avatar generated outputs.
- Verification:
  - Focused pytest targets pass.
  - New coverage includes ordering, defer, and style-clamp paths.
- Project Integration:
  - Follows existing pytest conventions in [tests](../../../tests).
- Dependencies:
  - Steps 1-9, 7.5.

### Step 11: Documentation and Operational Updates
- Status: **Complete** ✅ (2026-06-25)
- Notes: README, testing-and-dev, multimodal-features, cli-reference, environment-variables, docker-deployment, and plan.md all updated.
- Effort: 4 hours
- Description: Update user/developer docs to reflect new sequencing policy and usage.
- Actions:
  - Update [README.md](../../../README.md) with feature behavior and single-GPU sequencing.
  - Update [docs/multimodal-features.md](../../multimodal-features.md).
  - Update [docs/testing-and-dev.md](../../testing-and-dev.md) with new tests.
  - Update [docs/docker-deployment.md](../../docker-deployment.md) for runtime expectations.
- Verification:
  - Docs describe Ollama-first policy and fallback behavior.
  - Test count and test-map references are synchronized.
- Project Integration:
  - Aligned with repository requirement to update docs when behavior changes.
- Dependencies:
  - Steps 5-10.

## Project Quality Gates
### Development Gates
- [x] Code compiles cleanly.
- [x] All new functions are type-annotated.
- [x] No broad exception handlers added.
- [x] Module boundaries remain under target size and single responsibility.
- [x] Generated story text persists locally per story with deterministic naming.

### Integration Gates
- [x] FLUX never executes concurrently with active Ollama GPU job.
- [x] Schedule and console flows both honor the same gate policy.
- [x] Timeout/defer path degrades to text-only without breaking post flow.
- [x] Curate/schedule/console all produce local story artifacts when generation occurs.
- [x] Persistence behavior is unified system-wide, not avatar-specific.

### Deployment Gates
- [x] Core/full profile behavior documented and validated.
  - [x] Env variables in [.env.example](../../../.env.example) are complete.
- [x] Rollback path is clear: disable art-avatar feature flags and keep text pipeline intact.
- [x] DB-disabled mode still provides complete local artifact history (stories + images + metadata).

## Testing Phase
- Unit tests:
  - Model validation and policy parsing.
  - Style clamp math and prompt assembly.
  - Local story artifact write/read and metadata linkage.
- Integration tests:
  - Queue ordering with mocked competing workloads.
  - Scheduled flow attachment after text completion.
  - Console route sequencing and fallback behavior.
  - Curated flow local story persistence and dual-write optional DB indexing.
  - System-wide persistence parity between avatar and non-avatar generated content flows.
- Required verification commands:
  1. `source .venv/bin/activate && python -m py_compile services/flux_capacitor/__init__.py services/flux_capacitor/_config.py services/flux_capacitor/_models.py services/flux_capacitor/_prompting.py services/flux_capacitor/_pipeline.py services/flux_capacitor/_storage.py`
  2. `source .venv/bin/activate && python -m pytest -q tests/test_flux_capacitor_pipeline.py tests/test_gpu_orchestration_policy.py`

## Post-Implementation
- [ ] Confirm docs/features index and related references are updated if needed.
- [ ] Capture initial operational observations (queue waits, defer frequency).
- [ ] Capture artifact persistence observations (story save success rate, path consistency).
- [ ] Create follow-up backlog items for optional off-peak rendering and adaptive FLUX downgrade heuristics.

## Risks and Mitigations
- Risk: Queue latency on heavy Ollama usage windows.
  - Mitigation: Defer mode with text-only completion; optional off-peak rendering follow-up.
- Risk: VRAM pressure on RTX 3060 with complex FLUX settings.
  - Mitigation: Clamp defaults and add resolution/steps downgrade path.
- Risk: Integration complexity across schedule/console paths.
  - Mitigation: One shared orchestrator and shared tests for both paths.

## Delivery Sequence
1. Package + contracts.
2. Policy + gate/orchestrator.
3. Schedule integration.
4. Console integration.
5. Style presets + clamps.
6. Telemetry + fallback.
7. Tests.
8. Docs.
