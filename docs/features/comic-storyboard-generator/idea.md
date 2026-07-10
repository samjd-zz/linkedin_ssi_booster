# Feature Idea: Persona-Grounded Comic Storyboard Generator

## Overview

Add a comic generator module to SSI Booster that turns grounded post ideas into 3-panel comic storyboards with panel captions, optional narration, and channel-ready outputs.

This feature is inspired by the modular generation flow in `grizz-ai/src/modules` (daily/custom/media generators, shared core parsing, image fallback orchestration, duplicate checks, and progress staging), but adapted to SSI Booster's truth-gated persona architecture and Docker-first runtime.

## Problem Statement (Project Context)

SSI Booster already produces high-quality text posts, FLUX visuals, and music artifacts, but it does not support narrative visual sequences.

Current gap:
- Single-image generation is strong, but there is no native "story progression" format for carousel/comic-style content.
- Users who want engaging educational content (architecture explainers, lessons learned, technical debates) need to manually split stories into scenes.
- There is no built-in path to generate panel-level captions and reusable storyboard metadata for LinkedIn carousel workflows.

Business and user impact:
- Carousel-style posts can increase dwell time and save/share behavior, especially for SSI components `establish_brand` and `engage_with_insights`.
- A storyboard module can repurpose existing grounded content and reduce creative friction.
- Supports the project's multimodal direction without introducing cloud-only dependencies.

## Proposed Solution

Create a new package `services/comic_storyboard/` that converts a grounded source narrative into a deterministic 3-panel storyboard pipeline.

High-level flow:
1. Source selection:
- Input from curated article commentary, scheduled post draft, or console prompt.
2. Grounded script generation:
- Produce a 3-panel structured script (`Panel 1..3`) with scene/action/dialogue-like fields.
3. Panel caption extraction:
- Parse panel summaries and normalize to exactly 3 concise captions.
4. Image rendering:
- Render 3 panel images using FLUX pipeline with style consistency controls.
5. Validation and routing:
- Run truth/grounding checks on captions and source claims.
6. Artifact persistence:
- Save storyboard JSON, panel images, and optional audio narration metadata.

## Expected Benefits (Project User Impact)

- Faster creation of educational visual narratives from existing grounded content.
- Better content variety across channels while preserving persona and factuality.
- Improved reuse of existing systems: truth gate, derivative-of-truth, confidence policy, FLUX orchestration.
- Strong explainability via stored evidence IDs and panel-level provenance.

## Technical Considerations (Project Integration)

### Architecture alignment

Use the existing package modularization pattern and keep files under 300-500 lines:

- `services/comic_storyboard/__init__.py`
- `services/comic_storyboard/_models.py`
- `services/comic_storyboard/_prompting.py`
- `services/comic_storyboard/_parser.py`
- `services/comic_storyboard/_render.py`
- `services/comic_storyboard/_dedupe.py`
- `services/comic_storyboard/service.py`

### Key patterns adapted from Grizz AI

From reviewed `grizz-ai/src/modules` patterns:
- Keep: generator separation (daily/custom/media analog -> source-specific entrypoints).
- Keep: shared core parsing for panel summaries and consistent 3-panel output.
- Keep: duplicate checks using similarity thresholds before regenerating near-identical stories.
- Keep: staged progress semantics for long-running generation flows.
- Keep: image-provider fallback mindset from `image_generation_handler.py` (attempt chain + clear failure states).

Adjust for SSI Booster:
- Use Ollama-first and existing FLUX orchestrator policy instead of OpenAI-first image/text assumptions.
- Use persona graph + truth gate constraints during panel script generation.
- Use existing storage conventions under `GENERATED_CONTENT_DIR` and project artifact subdirs.
- Preserve Docker-first operation and avoid introducing Flask blueprint/task-state patterns.

### Data and storage

Artifact schema (JSON) per storyboard:
- `storyboard_id`
- `source_type` (`schedule|curate|console`)
- `source_reference` (post/article hash or ID)
- `panel_scripts` (structured fields)
- `panel_captions` (exactly 3)
- `panel_image_paths` (exactly 3)
- `grounding_evidence_ids`
- `truth_gradient_summary`
- `created_at`

Store under:
- `${GENERATED_CONTENT_DIR}/comic_storyboards/<date>/<storyboard_id>/`

### Model and rendering strategy

Text:
- Use `services/ollama_service.py` only.

Images:
- Primary: existing FLUX service orchestration.
- Fallback mode: if FLUX unavailable, produce text-only storyboard artifact (`render_status=text_only`) so user can still post carousel captions or regenerate later.

### Safety and grounding

- Run panel captions through existing truth/grounding checks.
- Reuse content filtering/sanitization logic before rendering prompts.
- Carry evidence IDs into artifact for explainability.

### Performance and resource handling

- Sequential 3-panel rendering (single GPU slot) to avoid VRAM spikes.
- Explicit progress states: script generation -> validation -> panel 1/2/3 render -> finalize.
- Memory hygiene hooks should align with existing FLUX/Ollama unload/stop guidance in docs.

## Project System Integration

### CLI integration

Add new command mode:
- `python main.py --comic --source curate --dry-run`

Optional flags:
- `--comic-style`
- `--comic-panels 3` (fixed to 3 in v1)
- `--comic-text-only`
- `--comic-dot-report`

### Existing service touchpoints

- `services/ollama_service.py` for script generation.
- `services/flux_capacitor/` for panel rendering.
- `services/console_grounding/` and `services/derivative_of_truth/` for validation/explainability.
- `services/selection_learning/` optional logging of accepted/rejected storyboard outputs.

### UX and output integration

- Console: add `/comic` command that uses recent assistant context or explicit prompt.
- Curate pipeline: optional comic generation for top-ranked article/commentary.
- Schedule pipeline: optional storyboard variant for selected weekly post slot.

## Initial Scope

In scope (v1):
- 3-panel storyboard generation from text sources.
- FLUX rendering for 3 panel images.
- Structured JSON artifact + captions + provenance.
- Console + CLI integration with dry-run support.

Out of scope (v1):
- Full web app UI or SSE progress stream.
- Multi-page comics (>3 panels).
- Speech bubble OCR compositing.
- External social auto-publish specialized for carousel ordering.

## Success Criteria

Functional:
- Generate valid storyboard artifacts with exactly 3 panels and captions.
- Each panel image is produced or marked with deterministic fallback state.
- Captions remain grounded and pass configured truth thresholds.

Quality:
- No regression in existing schedule/curate/console flows.
- Clear explainability metadata (`evidence_ids`, truth summary) per artifact.
- Deterministic file layout and recoverability for reruns.

Operational:
- Runs in Docker full profile with current GPU policy.
- Supports dry-run text-only generation without Buffer/API writes.
- Adds focused unit tests for parser, dedupe, orchestration, and fallback paths.

## Risks and Mitigations

- Risk: Hallucinated panel details.
- Mitigation: force panel script generation from grounded evidence packs + truth gate filtering.

- Risk: GPU saturation with multi-panel rendering.
- Mitigation: sequential rendering through existing orchestrator and fallback `text_only` mode.

- Risk: Repetitive storyboards for similar topics.
- Mitigation: similarity-based dedupe and memory/repetition penalties from existing systems.

- Risk: Complexity creep.
- Mitigation: keep v1 to 3 panels, CLI-first, no web subsystem.

## Notes from Grizz AI Module Review

The following concrete ideas informed this feature proposal:
- Shared generator entrypoints with common core utilities (`daily/custom/media` pattern).
- `is_similar_story` dedupe check to skip near-duplicate generation.
- Structured panel parsing and hard cap to 3 panel summaries.
- Image generation fallback chain with progress callbacks and clear failure handling.
- Relative-path artifact persistence for portable rendering outputs.

These are intentionally adapted to SSI Booster's current standards (Docker-first, local Ollama/FLUX services, truth-gated persona grounding, and package modularization).
