# Product Requirements Document: Persona-Grounded Comic Storyboard Generator

## 1. Executive Summary

The Persona-Grounded Comic Storyboard Generator adds a new multimodal content format to SSI Booster: deterministic 3-panel comic storyboards generated from grounded persona-aware source content.

The feature enables users to convert existing high-signal content inputs (curated article commentary, schedule drafts, console prompts) into visual narrative sequences suitable for LinkedIn carousel workflows, while preserving factual grounding, explainability, and Docker-first local execution.

Primary value:
- Increase content variety without sacrificing truth-gated quality.
- Improve engagement potential for SSI pillars tied to insight and brand authority.
- Reuse existing project assets (Ollama, FLUX, truth gate, DoT, confidence policy, learning logs).

## 2. Project Context

### 2.1 Current Product Context

SSI Booster already supports:
- Grounded text post generation.
- FLUX image generation (single-image workflows).
- Explainability and truth verification through truth gate and DoT.
- Curation and learning loops via selection learning.

Current gap:
- No native support for sequential visual narratives (panelized story flow).
- Users must manually split narratives into scenes for carousel formats.

### 2.2 User and Business Context

Target users:
- Individual technical professionals using SSI Booster for consistent thought leadership.
- Builders sharing architecture stories, implementation lessons, and practical insights.

Business outcome:
- Increase post variety and perceived depth.
- Improve dwell-time friendly format output for education-style content.

### 2.3 Inspiration from Grizz AI Module Review

Patterns identified from Grizz modules that inform this PRD:
- Split generators by source mode with shared core utilities.
- Story similarity checks to avoid duplicate outputs.
- Structured panel parsing with strict panel-count normalization.
- Multi-step image generation fallback chain.
- Explicit progress staging for long-running generation tasks.

This feature adopts those patterns while aligning with SSI Booster conventions and architecture.

## 3. User Stories

### Story 1: Console storyboard generation

As a console user, I want to generate a comic storyboard from my latest grounded answer, so that I can quickly produce a visual narrative without rewriting content manually.

Acceptance criteria:
1. Given a recent assistant response in console mode, when I run the comic command, then the system creates exactly 3 storyboard panels.
2. Panel captions include grounded narrative elements tied to source evidence.
3. If FLUX is unavailable, text-only storyboard artifacts are still produced with clear render status.

### Story 2: Curation-to-storyboard workflow

As a curation user, I want to generate a comic storyboard from a top-ranked curated item, so that I can repurpose research commentary into carousel-ready content.

Acceptance criteria:
1. Curation mode can invoke storyboard generation for selected candidate outputs.
2. The storyboard links back to article/source metadata.
3. Truth and confidence signals are included in artifact metadata.

### Story 3: Schedule variant generation

As a scheduler user, I want to produce a storyboard variant for a scheduled topic, so that I can test different content formats in my posting plan.

Acceptance criteria:
1. Schedule flow can optionally generate storyboard artifacts for selected slots.
2. Artifacts are persisted in deterministic folder paths.
3. Generation can run in dry-run mode without external publishing calls.

### Story 4: Deduplicated output reuse

As a frequent content producer, I want near-duplicate storyboard inputs to be detected, so that I avoid redundant visual outputs.

Acceptance criteria:
1. The module compares incoming source narrative against recent storyboard inputs.
2. Similarity threshold is configurable.
3. On duplicate detection, system returns existing artifact reference or skip reason.

### Story 5: Explainability and auditability

As a quality-focused user, I want panel-level provenance included in artifacts, so that I can trust and audit generated content.

Acceptance criteria:
1. Every storyboard artifact includes source reference and evidence identifiers.
2. Truth summary metadata is present.
3. Failure and fallback states are persisted and visible.

## 4. Functional Requirements

### FR-1: New storyboard generation mode

System shall provide a new comic storyboard generation mode callable from CLI and console.

Details:
- Support source types: schedule, curate, console.
- Default panel count is fixed to 3 for v1.

### FR-2: Structured panel script generation

System shall generate a structured storyboard script with three ordered panels.

Each panel must contain:
- Scene/setting description.
- Key action.
- Optional dialogue/text cue.
- Caption summary.

### FR-3: Caption normalization

System shall normalize panel captions to exactly three concise outputs even when model output is malformed.

### FR-4: Grounding and truth enforcement

System shall enforce grounding checks on storyboard captions and source-linked claims using existing project truth infrastructure.

### FR-5: Image rendering orchestration

System shall render 3 panel images through existing FLUX infrastructure with sequential GPU execution.

### FR-6: Fallback operation

System shall support graceful fallback when image rendering fails by emitting text-only storyboard artifacts.

### FR-7: Artifact persistence

System shall persist storyboard outputs to local-first storage under a deterministic directory structure.

Required persisted fields:
- storyboard_id
- source_type
- source_reference
- panel_scripts
- panel_captions
- panel_image_paths
- grounding_evidence_ids
- truth_gradient_summary
- render_status
- created_at

### FR-8: Progress staging

System shall expose deterministic generation stage statuses to support user feedback and troubleshooting.

Stages:
- Source resolution
- Script generation
- Grounding/validation
- Render panel 1
- Render panel 2
- Render panel 3
- Finalization

### FR-9: Dedupe behavior

System shall run a similarity check against recent storyboard inputs and support skip-or-reuse behavior.

### FR-10: Dry-run behavior

System shall support dry-run mode where no external publish calls occur and artifacts can be generated as text-only or metadata-only depending on flags.

## 5. Non-Functional Requirements

### NFR-1: Performance

- Script generation should complete within acceptable interactive CLI expectations under normal local conditions.
- Panel rendering must execute sequentially through existing GPU policy to avoid VRAM contention.

### NFR-2: Reliability

- Any partial failures must return deterministic final status and saved diagnostic metadata.
- Failures in one panel render must not crash the entire process without a final artifact status.

### NFR-3: Maintainability

- New implementation follows package modularization pattern with focused modules.
- Python files should remain within project size guidance (prefer <=500 lines).

### NFR-4: Security and privacy

- No hardcoded secrets.
- No external dependency introduction requiring mandatory cloud credentials for baseline operation.
- Reuse environment-driven configuration.

### NFR-5: Usability

- CLI and console command semantics should mirror existing command style.
- Errors and fallback outcomes must be clearly surfaced.

### NFR-6: Compatibility

- Must run in Docker full profile where FLUX is available.
- Must remain operational in core profile via text-only fallback path.

### NFR-7: Testability

- Unit tests must cover parser normalization, dedupe logic, fallback routing, and artifact persistence behavior.
- Integration tests should verify wiring from CLI/console entrypoints.

## 6. Project System Integration

### 6.1 Proposed package

Add new package:
- services/comic_storyboard

Proposed modules:
- __init__.py
- _models.py
- _prompting.py
- _parser.py
- _render.py
- _dedupe.py
- service.py

### 6.2 Existing system touchpoints

- services/ollama_service.py for panel script generation.
- services/flux_capacitor for image rendering.
- services/console_grounding and services/derivative_of_truth for grounding and truth summary.
- services/selection_learning for optional logging signals.

### 6.3 CLI and console integration

Proposed command entrypoints:
- CLI flag family for comic generation.
- Console slash command for comic generation from recent context.

### 6.4 Storage integration

Use GENERATED_CONTENT_DIR with deterministic path:
- comic_storyboards/date/storyboard_id

## 7. Dependencies

### Internal dependencies

- Ollama service wrappers.
- FLUX rendering pipeline.
- Truth gate and DoT systems.
- Shared config/environment loading.
- Existing logging conventions.

### External/runtime dependencies

- Docker full profile for FLUX rendering path.
- GPU availability for panel image generation.

### Data dependencies

- Persona graph and domain knowledge packs.
- Source content from schedule/curate/console contexts.

## 8. Success Metrics

### Product metrics

- Number of storyboard artifacts generated per week.
- Share of storyboard outputs that pass grounding checks without heavy filtering.
- User reuse rate of storyboard mode after first run.

### Quality metrics

- Percent of artifacts with complete 3-panel outputs.
- Text-only fallback rate (should be explainable and observable).
- Duplicate suppression rate for near-identical prompts.

### Operational metrics

- Median generation time by stage.
- Failure rate by stage (script, validation, render, finalize).

## 9. Timeline and Milestones

### Milestone 1: PRD sign-off

Deliverables:
- Approved PRD.
- Scope locked to v1 3-panel storyboard.

### Milestone 2: Design and architecture spec

Deliverables:
- Design doc for package structure and integration points.
- Artifact schema and command interface spec.

### Milestone 3: Core implementation

Deliverables:
- services/comic_storyboard package implemented.
- CLI and console entrypoint wiring.
- Text-only fallback working.

### Milestone 4: Rendering and validation integration

Deliverables:
- FLUX panel rendering path integrated.
- Grounding/truth metadata attached to artifacts.
- Dedupe path implemented.

### Milestone 5: Testing and docs

Deliverables:
- Unit and integration tests for new module paths.
- Updated feature docs and usage references.

## 10. Risks and Mitigations

### Risk A: Hallucinated panel details

Mitigation:
- Enforce grounded source selection and truth checks on panel captions.
- Persist evidence identifiers.

### Risk B: GPU bottlenecks

Mitigation:
- Sequential panel rendering and existing orchestration controls.
- Text-only fallback state.

### Risk C: Repetitive output

Mitigation:
- Similarity-based dedupe with configurable threshold.
- Integrate repetition-aware signals from existing learning systems where feasible.

### Risk D: Scope creep

Mitigation:
- Freeze v1 to 3 panels, CLI/console first, no web UI subsystem in initial release.

## 11. Out of Scope for v1

- Web UI, Flask/SSE style progress pages, or dedicated frontend module.
- Multi-page comics or variable panel counts.
- OCR speech bubble compositing.
- Dedicated social channel API workflow for carousel ordering and publish automation.

## 12. Open Questions

1. Should storyboard artifacts be fed into selection learning priors in v1 or deferred to v2?
2. Should panel captions inherit channel-specific formatting rules immediately or remain channel-neutral in v1?
3. Should audio narration be enabled by default for storyboard mode or opt-in only?
4. Should schedule mode auto-generate storyboard variants or require explicit opt-in per run?
