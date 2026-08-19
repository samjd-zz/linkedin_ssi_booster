# Product Requirements Document: LinkedIn SSI Booster Platform

## Executive Summary

LinkedIn SSI Booster is a CLI-first AI publishing platform that helps a technical professional consistently grow LinkedIn SSI by generating, curating, validating, and scheduling high-quality social content grounded in real profile/project facts.

The product balances automation with control:

- Automation: content planning, generation, curation, formatting, and scheduling.
- Control: deterministic grounding, truth-gate filtering, dry-run previews, and configurable environment settings.

This PRD defines the full product scope represented in the current system: strategy planning, multi-channel output, deterministic safety, and weekly SSI feedback loops.

## Project Context

### Business Context

Users need a repeatable, low-friction workflow to publish consistent thought leadership without sacrificing authenticity or technical accuracy.

### Target Users

- Primary user: solo technical creator/operator improving personal SSI.
- Secondary user: engineering professional who wants reusable, grounded social publishing workflows.

### User Goals

- Publish consistently (3+ weekly posts).
- Keep writing voice authentic and technically credible.
- Minimize factual errors or fabricated personal claims.
- Reuse one workflow across LinkedIn, X, Bluesky, and YouTube script generation.
- Track SSI progress and adjust strategy by weakest pillar.

## Product Objectives

1. Increase weekly publishing consistency with low manual overhead.
2. Improve output authenticity through profile/project-grounded generation.
3. Reduce hallucinated personal claims via deterministic checks.
4. Support channel-specific constraints without separate toolchains.
5. Create a measurable SSI improvement loop through score tracking and reports.

## User Stories

1. As a technical creator, I want to generate a week of posts from a content calendar so that I can maintain a consistent posting cadence.

- Acceptance criteria:
- Running `python main.py --generate --week N --dry-run` prints complete posts with mapped SSI components.
- Running `python main.py --generate --schedule --week N` schedules posts according to configured slots.

2. As a technical creator, I want to curate relevant AI/GovTech articles so that I can engage with fresh insights without manual research each day.

- Acceptance criteria:
- Running `python main.py --curate` fetches RSS entries, filters by keywords, deduplicates, and sends ideas to Buffer.
- Running `python main.py --curate --type post` schedules posts directly.

3. As a creator protecting my credibility, I want outputs grounded in my real projects so that fabricated or misattributed claims are minimized.

- Acceptance criteria:
- Retrieved profile facts are injected for generation/curation.
- Truth gate removes unsupported specific claims and logs reason codes.

4. As a multi-platform publisher, I want one command flow that adapts to channel rules so that I do not rewrite posts per platform.

- Acceptance criteria:
- LinkedIn/X/Bluesky/YouTube script outputs follow channel constraints.
- URL/hashtag append behavior is deterministic per channel policy.

5. As a growth-focused user, I want SSI history and reports so that I can prioritize the weakest SSI pillar each week.

- Acceptance criteria:
- `--save-ssi` stores component snapshots.
- `--report` shows trend-aware guidance by component.

## Functional Requirements

### FR-1: Content Strategy and Planning

- The system shall load a 4-week topic calendar with title, angle, SSI component, and hashtags.
- The system shall preserve topic uniqueness within a given week during scheduling.
- The system shall allocate scheduled slots based on SSI focus weights.

### FR-2: AI Generation Workflow

- The system shall generate posts from calendar topics using persona/system instructions.
- The system shall support `--dry-run` to print outputs without external publish calls.
- The system shall format output for channel-specific policies.

### FR-3: Curation Workflow

- The system shall fetch RSS entries from configured feeds.
- The system shall filter entries by configurable keyword set.
- The system shall deduplicate submissions using local cache.
- The system shall support idea mode and direct-post mode.

### FR-4: Deterministic Grounding and Validation

- The system shall parse project facts from profile context.
- The system shall retrieve relevant facts per topic/article.
- The system shall apply prompt balance rules requiring grounded factual claims.
- The system shall apply truth-gate filtering after generation.
- The system shall log removal reasons for unsupported claims.

### FR-5: Multi-Channel Distribution

- The system shall support channels: LinkedIn, X, Bluesky, YouTube script mode.
- The system shall enforce channel-aware constraints (length, structure, formatting).
- The system shall append URL/hashtags deterministically according to channel policy.
- The system shall continue processing available channels when one channel is unavailable.

### FR-6: Scheduling and Buffer Integration

- The system shall push ideas/posts via Buffer GraphQL API.
- The system shall schedule posts based on configured weekday/time slots and timezone.
- The system shall support direct scheduling for generated and curated workflows.

### FR-7: SSI Tracking and Reporting

- The system shall store SSI component scores over time.
- The system shall generate reports with trend-aware insights.
- The system shall provide component-level focus guidance for strategy iteration.

### FR-8: Configuration and Runtime Controls

- The system shall be configurable through `.env` variables.
- The system shall provide sane defaults when optional settings are unset.
- The system shall fail fast for missing required config values.

## Non-Functional Requirements

### NFR-1: Performance

- Weekly generation dry run should complete within practical local runtime for typical week input.
- Curation runtime should remain bounded by feed and per-feed limits.

### NFR-2: Reliability

- External API failures shall be handled with specific exceptions and clear logging.
- Single-channel failures in multi-channel mode should not crash the full run.

### NFR-3: Security and Secrets

- Secrets shall only be loaded from environment variables.
- No secrets shall be hardcoded or written to committed source files.

### NFR-4: Maintainability

- Service responsibilities shall remain modular (`buffer_service`, `ollama_service`, `content_curator`, `ssi_tracker`, `console_grounding`).
- Imports shall follow project-root absolute import conventions.
- Logging shall use module loggers.

### NFR-5: Usability

- CLI flags shall be discoverable and composable.
- Dry-run output shall be review-friendly.
- Error messages shall be actionable for config/runtime fixes.

### NFR-6: Observability

- Truth-gate removals shall log reason codes and aggregate summary.
- Workflow warnings (short article, channel unavailability, cache skips) shall be explicit.

## Project System Integration

### Existing Components

- `main.py`: CLI orchestration and profile context assembly.
- `scheduler.py`: posting slot planning.
- `content_calendar.py`: topic source of truth.
- `services/ollama_service.py`: generation/curation prompts and channel shaping.
- `services/console_grounding.py`: deterministic grounding and truth gate.
- `services/content_curator.py`: RSS ingestion/filtering/dedup.
- `services/buffer_service.py`: Buffer API interaction.
- `services/ssi_tracker.py`: SSI persistence/reporting.

### Data and State Artifacts

- `published_ideas_cache.json`: dedup cache for curated entries.
- `ssi_history.json`: SSI historical snapshots.
- GitHub context caches for repository metadata and README summaries.

### Integration Rules

- Preserve single-responsibility service boundaries.
- Do not bypass service modules for external API calls.
- Keep deterministic safety checks in the grounding/truth-gate layer.

## Dependencies

### External Services

- Buffer API for scheduling/ideas.
- Ollama local server for model inference.
- RSS feed endpoints for curation inputs.

### Runtime/Library Dependencies

- Python 3.11+
- Feed parsing and scheduling/runtime libs from `requirements.txt`.

### Configuration Dependencies

- Required env values for persona/profile and APIs.
- Optional env controls for channels, grounding, and context budgets.

## Assumptions

- User maintains meaningful `PROFILE_CONTEXT` with project bullets.
- User reviews dry-run outputs before enabling direct-post workflows.
- Connected channels in Buffer are correctly configured externally.

## Constraints

- CLI-first interaction model (no mandatory web UI).
- Content quality depends on model behavior and source article quality.
- Deterministic checks protect identity claims but do not fully fact-check all external article facts.

## Success Metrics

### Product Metrics

- Weekly post execution rate using scheduled generation.
- Curated idea throughput with low duplication rate.
- Percentage of successful multi-channel publishing runs.

### Quality Metrics

- Truth-gate removal rate by reason code.
- False-removal incident count reported by user review.
- Persona-consistency acceptance rate in dry-run review.

### Outcome Metrics

- SSI component trend direction over rolling 4-week windows.
- Improvement in weakest SSI pillar after targeted focus adjustments.

## AI-TDD Implementation Milestones

### Milestone 1: Baseline Workflow Hardening

- Validate generate/curate/schedule/report happy paths.
- Standardize dry-run outputs and error handling.
- Confirm required env validation and fail-fast behavior.

### Milestone 2: Grounding and Validation Depth

- Maintain strict balance rules for factual claims.
- Expand deterministic truth-gate edge-case coverage.
- Track reason-code removal metrics for tuning cycles.

### Milestone 3: Multi-Channel Robustness

- Verify all channel constraints and append rules.
- Improve fallback behavior when channel connections are absent.
- Add channel-specific regression checks.

### Milestone 4: Feedback Loop Optimization

- Strengthen SSI report actionability.
- Tune scheduler allocations from SSI focus outcomes.
- Add release-quality checks tied to deterministic safety signals.

## Risks and Mitigations

- Risk: Overly strict filtering removes useful content.
- Mitigation: Reason-code logs, targeted keyword/expansion tuning, iterative dry-run review.

- Risk: Under-filtering allows subtle misattribution.
- Mitigation: Expand deterministic checks and fixture-based regression cases.

- Risk: Prompt/context growth increases latency.
- Mitigation: Enforce context budgets and configurable limits.

- Risk: External API instability affects publish reliability.
- Mitigation: Explicit error handling and partial-failure tolerance in multi-channel flows.

## Out of Scope (Current PRD)

- Full browser UI and visual analytics dashboard.
- Autonomous engagement automation (auto-comments/auto-DMs).
- Fully automated external factual verification against third-party sources.

## Timeline and Milestones (High-Level)

- Phase 1 (0-2 weeks): baseline workflow validation and config hardening.
- Phase 2 (2-4 weeks): grounding/truth-gate improvements and regression checks.
- Phase 3 (4-6 weeks): multi-channel robustness and operational reliability improvements.
- Phase 4 (6+ weeks): SSI optimization loop enhancements and release quality instrumentation.

## Release Readiness Criteria

1. Generate/curate/schedule/report flows pass manual smoke tests.
2. Truth-gate logs provide actionable reason-coded diagnostics.
3. Multi-channel runs succeed with graceful degradation on disconnected channels.
4. README and env guidance are synchronized with implemented behavior.
