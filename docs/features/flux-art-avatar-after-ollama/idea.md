# Feature Idea: FLUX Art Avatar After Ollama

## Overview
Build a Rei-Toei-inspired art avatar subsystem that generates restrained FLUX imagery for the project while protecting Ollama as the first-priority GPU workload on the single RTX 3060. The art direction should stay intentionally toned down: minimalist corporate-art hybrid, subtle geometry, muted palette, and low surreal intensity.

This is not a separate image application. It is a local, policy-aware rendering path that plugs into the existing schedule, curate, and console workflows and only renders when the GPU gate says FLUX may run safely.

Generated-content persistence in this feature is defined as a whole-system requirement, not an avatar-only requirement. Art-avatar integration adopts and extends that system contract for local-first storage of generated outputs.

## Problem Statement
The repository already has local Ollama generation, FLUX image generation, and multiple content workflows, but the image path is not yet shaped into a dedicated art-avatar experience. The current challenge is twofold.

The first problem is sequencing. Ollama remains the primary GPU consumer, so FLUX cannot compete for VRAM or run concurrently on the same card without risking instability.

The second problem is scope clarity. The art avatar needs to serve real workflows, not become a sidecar feature. It should support scheduled posts, curated Buffer ideas, and console-driven requests using one consistent policy and one shared set of style rules.

## Proposed Solution
Create a new `services/flux_capacitor/` package that mirrors the modular Rei Toei pattern and acts as the single orchestration layer for art-avatar rendering.

The package should expose:
- request and result models for art renders
- environment-driven policy/config for single-GPU sequencing
- prompt assembly and style clamping for the toned-down visual direction
- an in-process GPU gate that serializes Ollama and FLUX work
- local artifact storage with metadata sidecars for reproducibility
- local story persistence that saves the generated post/script text per story alongside image artifacts

System persistence policy this feature must honor:
- all generated content artifacts across the project should be saved locally first (stories, scripts, and associated media metadata)
- avatar output follows the same contract and must not introduce a separate persistence model that diverges from the system baseline

The feature should integrate into three existing paths:
- `--schedule` for post-art generation after Ollama text generation and validation
- `--curate` for selected Buffer ideas that should be visualized before publish decisions
- `--console` for interactive art-avatar requests and explanation flows

## Expected Benefits
This feature gives the project a recognizable visual identity while keeping the runtime safe on a single consumer GPU.

It should:
- make scheduled content more distinctive and reusable across social channels
- let curated ideas carry visual context before publishing to Buffer
- give the console a multimodal creative path without adding a new top-level command
- preserve Ollama performance by preventing FLUX from running in parallel with active Ollama GPU work
- keep output visually coherent with the rest of the repo’s persona-grounded style

## Technical Considerations
The implementation should follow the existing local-first architecture and the repo’s modular package conventions.

Key constraints:
- Ollama must remain the first-class GPU consumer.
- FLUX should only begin after the Ollama queue drains or the gate explicitly allows it.
- The gate should return an explicit result such as `allowed`, `deferred`, or `text_only` fallback.
- The system should degrade cleanly when the GPU is saturated instead of blocking the entire user flow.
- All configuration should be environment-driven and deterministic in Docker `core`/`full` profiles.

Style constraints:
- muted contrast
- shallow sacred-geometry hints
- restrained symmetry
- polished but corporate-safe composition
- hard caps on saturation, geometry density, and surreal intensity

Storage constraints:
- keep image artifacts local
- write metadata sidecars with prompt summary, style preset, request ID, timing, and evidence IDs
- use deterministic filenames so downstream scheduling can attach media reliably
- save generated story text per story in local files first (human-reviewable and reproducible)
- persist story metadata that links story text files to image artifacts and request IDs
- treat database persistence as optional secondary indexing, not the primary source of truth

Generated-content persistence constraints:
- every generated story must have a stable local artifact (for example txt or md)
- story artifacts should be organized by timestamp and channel to support manual review and upload
- story save failure should not silently pass; it should return explicit status and fallback behavior
- this applies system-wide to generated outputs, including non-avatar generated text flows, with avatar artifacts treated as one subtype of generated content
- dedicated FLUX image subdirectory behavior should land under the generated-content root when implemented, not as a separate storage convention

## Project System Integration
This feature should build on the repo’s existing systems rather than introducing a new workflow.

System-level persistence alignment:
- generated-content saving is a repository-wide behavior contract
- art-avatar changes must align with existing generated-content save paths and extend them where needed, not fork them

Relevant integration points:
- [main.py](../../../main.py) for CLI routing and console flow integration
- [services/ollama_service.py](../../../services/ollama_service.py) for all LLM generation
- [services/image_generation.py](../../../services/image_generation.py) for FLUX inference
- `flux_capacitor` as the documented FLUX runtime/deployment service name in Docker-facing docs
- [services/rei_toei](../../../services/rei_toei) as the structural reference for package organization and config-led behavior
- [services/shared.py](../../../services/shared.py) for shared flags and runtime policy wiring
- [.env.example](../../../.env.example) for user-facing configuration defaults
- [docker-compose.yml](../../../docker-compose.yml) for core/full profile expectations
- [docs/multimodal-features.md](../../multimodal-features.md) and [docs/testing-and-dev.md](../../testing-and-dev.md) for feature and test documentation

Integration behavior:
- scheduled flow generates and validates text first, then requests art rendering
- curated flow may attach art to selected ideas before publishing decisions
- console flow may request art generation or ask for art-avatar-aware responses
- all three flows must respect the same GPU gate and fallback behavior

## Initial Scope
First release should include:
- `services/flux_capacitor/` package skeleton
- request/result models
- GPU policy config with Ollama-first defaults
- in-process GPU gate and defer behavior
- schedule, curate, and console integration points
- restrained prompt presets and style clamps
- local artifact storage with metadata sidecars
- local story text storage per generated story with deterministic naming
- story-to-image linkage metadata for manual-first publishing workflows
- telemetry for wait time, defer counts, and render duration
- focused unit and integration tests
- docs updates for usage, runtime assumptions, and testing

Out of scope for the first release:
- multi-GPU scheduling
- dynamic VRAM probing and advanced adaptive routing
- replacing the existing Ollama or FLUX backends
- introducing a new top-level CLI command just for art avatar generation

## Success Criteria
The feature is successful when:
- FLUX never runs concurrently with active Ollama GPU work on the single RTX 3060
- scheduled, curated, and console flows all use the same art-avatar policy
- art generation can fall back to text-only output when the GPU is busy
- the aesthetic stays within the restrained corporate-art hybrid direction
- render artifacts and metadata are saved locally and reproducibly
- generated story text is saved locally per story and linked to its render metadata
- generated-content persistence is implemented as a whole-system rule, with avatar generation conforming to the same local-first contract
- the design is testable, documented, and consistent with the repo’s modular architecture

## Schema Fit Notes (Local First, DB Second)
Review of [services/database/models.py](../../../services/database/models.py):
- Current selection-learning tables are oriented to snippets and selection telemetry, not full generated story bodies.
- `CandidateRecord` stores `text_snippet` and routing metadata; this is useful for ranking and reconciliation but not as a complete story archive.
- `PublishedRecord` also stores `text_snippet` and publish linkage, not full generated content.

Implication:
- The current schema does not fully satisfy a durable full-story archive requirement by itself.

Required approach for this feature:
- Local files are the primary source of truth for generated stories.
- Database storage is secondary and optional for indexing/search/analytics.

If DB archival of full stories is required later:
- add a dedicated table (or equivalent) for full generated content and artifact linkage
- include migration instructions and backward-compatible rollout
- keep local file persistence enabled even when DB writes are active

## Further Considerations
Current implementation reality note:
- the generated-content root is already being harmonized for text and script artifacts
- dedicated art-avatar image storage under a specific FLUX subdirectory is still part of the planned implementation, not a completed runtime behavior yet

If queue pressure becomes a problem, the next iteration could add off-peak batch rendering without relaxing Ollama priority during active workflows.

If VRAM pressure shows up during FLUX runs, the next iteration should prefer resolution or step downgrades before hard failure.

If the visual style drifts too far from the intended tone, a style-lint pass can be added to reject overly saturated or overly dense results before publish.