# Feature AI-TDD Idea: End-to-End LinkedIn SSI Booster

## Overview

This document defines the end-to-end AI-TDD feature idea for the LinkedIn SSI Booster project: an AI-assisted publishing workflow that turns personal expertise into consistently high-quality, grounded multi-channel content, with deterministic safeguards and measurable SSI progress loops.

This idea document covers the complete system in the README: content planning, generation, curation, scheduling, deterministic grounding, channel adaptation, and reporting.

## Problem Statement (Project Context)

Professionals with deep technical experience often fail to maintain consistent, high-quality social output due to time constraints, context switching, and writing fatigue. The result is lower reach, weaker audience resonance, and slower SSI growth.

Current manual workflow pain points:

- Writing 3+ credible posts per week is hard to sustain.
- Curating domain-relevant news with authentic commentary is time-intensive.
- Maintaining factual consistency with real projects is error-prone.
- Platform formatting differences (LinkedIn, X, Bluesky, YouTube script mode) add friction.
- Feedback loops are weak without explicit SSI trend tracking.

## Proposed Solution

Deliver a production-ready CLI platform that combines AI generation with deterministic validation and operational scheduling.

Core product capabilities:

1. Structured content strategy via a four-week SSI-mapped calendar.
2. Persona-grounded generation for planned topics (`--generate`).
3. RSS-driven article curation and commentary (`--curate`).
4. Deterministic grounding and truth-gate validation to prevent fabricated claims.
5. Channel-specific output shaping for LinkedIn/X/Bluesky/YouTube script flows.
6. Scheduling and queue management through Buffer.
7. SSI tracking and reporting for weekly improvement loops.

## Expected Benefits (Project User Impact)

- Consistent posting cadence without daily writing overhead.
- Stronger authenticity through profile/project-grounded outputs.
- Lower hallucination risk via post-generation deterministic filtering.
- Better audience fit through channel-aware format rules.
- Faster iteration using dry-run workflows and configurable environment controls.
- Quantifiable SSI progress through saved score history and reports.

## Technical Considerations (Project Integration)

Technology alignment:

- Python 3.11+ CLI architecture (`main.py`) remains the orchestration entrypoint.
- LLM execution stays centralized in `services/ollama_service.py`.
- Buffer API interactions remain isolated in `services/buffer_service.py`.
- RSS curation remains in `services/content_curator.py`.
- Deterministic grounding and truth-gate logic remains in `services/console_grounding.py`.
- SSI trend and action guidance remains in `services/ssi_tracker.py`.

Configuration and reliability:

- Environment-driven behavior with safe defaults and explicit overrides.
- `--dry-run` for preview-only execution without external side effects.
- Caching for GitHub context and published-idea deduplication.
- Deterministic post-processing stage to protect factual identity claims.

Performance and scalability:

- Bounded context budgets for prompt stability and latency control.
- Feed and article limits for predictable runtime.
- Channel-by-channel scheduling to avoid all-or-nothing failures.

## Project System Integration

### 1) Strategy Layer

- `content_calendar.py` defines angles, hashtags, and SSI component mapping.
- Scheduler allocation uses SSI focus weights from `.env`.

### 2) Intelligence Layer

- Persona + profile + GitHub context compose the identity frame.
- SSI component instructions shape objective by pillar.
- Balance rules enforce factual discipline at prompt level.

### 3) Deterministic Safety Layer

- Relevant facts retrieved from parsed profile context.
- Truth gate removes unsupported claims (numeric/date/org/project-claim mismatch).
- Reason-coded logs expose why sentences were removed.

### 4) Distribution Layer

- Buffer queue and idea workflows support review-first and direct-post modes.
- Channel-specific output policies adapt length, format, and append behavior.

### 5) Measurement Layer

- SSI snapshots saved to history.
- Reports provide trend and next-action guidance by component.

## AI-TDD Delivery Slices

### Slice A: Core Generation Reliability

Goal: Stable, persona-consistent generated posts with strict formatting.

Deliverables:

- Hardened prompt templates and SSI instruction mapping.
- Dry-run snapshots for weekly topics.
- Unit checks for output cleanup and formatting behavior.

### Slice B: Curation Quality and Relevance

Goal: High-signal article intake and useful commentary.

Deliverables:

- RSS fetch/filter/dedup pipeline robustness.
- Configurable keyword/feed controls.
- Regression fixtures for common curation failure patterns.

### Slice C: Deterministic Grounding and Truth Gate

Goal: Minimize fabricated personal claims and project-tech misattribution.

Deliverables:

- Project-fact retrieval improvements.
- Prompt balance-rule strictness for attribution.
- Truth-gate coverage for numeric/date/org/project-claim checks.
- Logging improvements for removal reason observability.

### Slice D: Multi-Channel Publishing

Goal: Reliable output adaptation across LinkedIn/X/Bluesky/YouTube script modes.

Deliverables:

- Channel policy checks (length, structure, append behavior).
- Safe fallbacks when connected channels are unavailable.
- End-to-end dry-run test paths per channel.

### Slice E: SSI Feedback Loop

Goal: Actionable, measurable improvement cycle.

Deliverables:

- Save/report workflows with trend interpretation.
- Baseline-to-current comparisons by SSI pillar.
- Suggested weekly action prompts tied to weakest components.

## Initial Scope

In scope:

- Complete CLI-driven authoring and curation lifecycle.
- Deterministic grounding in console/generate/curate flows.
- Buffer scheduling + idea workflows for supported channels.
- SSI score recording and progress reporting.

Out of scope (current phase):

- Full web UI/dashboard.
- Autonomous social engagement actions (commenting/DM automation).
- Third-party external fact-check integrations.

## Success Criteria

Product outcomes:

1. User can run weekly generation, curation, and scheduling without manual code edits.
2. Grounding layer consistently prevents unsupported personal/project claims.
3. Multi-channel output remains compliant with channel-specific constraints.
4. Weekly SSI recording/reporting provides visible trend direction.

Quality outcomes:

1. `--dry-run` outputs are reviewable, coherent, and persona-aligned.
2. Truth-gate reason codes are actionable for tuning configs/prompts.
3. Changes to prompts or grounding rules can be validated with deterministic checks before release.

Operational outcomes:

1. No required secrets are hardcoded.
2. Failures in one channel do not crash full multi-channel runs.
3. Dedup and caching reduce repeated work and duplicate submissions.

## Risks and Mitigations

Risk: Over-filtering removes useful sentences.
Mitigation: Reason-coded logs and iterative keyword/tag-expansion tuning.

Risk: Under-filtering allows subtle hallucinations.
Mitigation: Expand deterministic checks and improve fixture-based regressions.

Risk: Model drift impacts output quality.
Mitigation: Versioned model settings, dry-run review gates, and release validation routines.

Risk: Prompt/context bloat increases latency.
Mitigation: Maintain context budgets and configurable caps.

## Implementation Feasibility

Complexity: Medium-high, but incremental and practical.

Why feasible:

- Strong existing modular service boundaries.
- CLI-first architecture simplifies orchestration and testing.
- Deterministic components already in place and extensible.
- Configuration-first design supports fast adaptation without heavy refactors.

## Future Expansion Opportunities

- CI-integrated regression suite for generated output quality signals.
- Release-quality scorecards tied to version tags.
- Lightweight analytics export for month-over-month SSI and content performance correlation.
