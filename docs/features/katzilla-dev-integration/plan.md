# Implementation Plan: Katzilla.dev Integration (Phases 1-6)

## Status

Implementation complete across Phases 1-6.

## Scope Decision

This feature now covers Phases 1-6.

Implemented scope:
- Phase 1: API client foundation
- Phase 2: Evidence model adapter
- Phase 3: Retrieval integration (controlled rollout)
- Phase 4: Truth-gate and DoT wiring
- Phase 5: Console and curation UX expansion
- Phase 6: Persistence and observability hardening

## Objectives

1. Add a safe, feature-flagged Katzilla integration path with no behavior change by default.
2. Normalize Katzilla response envelopes into internal evidence objects without losing citation provenance.
3. Enable selective external evidence retrieval in avatar grounding, behind explicit rollout controls.

## Non-Goals

- No truth-gate scoring changes in this feature.
- No auto-insertion of Katzilla claims into generated output by default.
- No mandatory external dependency for normal local runs.

## Project Integration Summary

Primary integration touchpoints:
- services/katzilla_service.py (new)
- services/avatar_intelligence/_models.py (extension for external evidence typing)
- services/avatar_intelligence/_retrieval.py (optional Katzilla retrieval branch)
- services/shared.py (feature flags and defaults)
- docs/environment-variables.md (new env variables)
- tests/test_katzilla_service.py (new)
- tests/test_katzilla_adapter.py (new)
- tests/test_katzilla_retrieval.py (new)

## Preconditions

- Existing test suite is green before start.
- Katzilla API key available for integration testing (optional for local unit tests).
- All new behavior remains disabled when KATZILLA_ENABLED is false.

## Phase 1: API Client Foundation

### Deliverables

- New Katzilla client module with:
  - X-API-Key authentication
  - Standard request path for agent/action invocation
  - Envelope parsing for data, quality, citation, meta
  - Error mapping for auth, rate limit, quota, input, upstream, server categories
- Config and defaults:
  - KATZILLA_ENABLED (default false)
  - KATZILLA_API_KEY (required when enabled)
  - KATZILLA_BASE_URL
  - KATZILLA_TIMEOUT_SECONDS
  - KATZILLA_DEFAULT_FORMAT (compact)

### Tasks

1. Implement KatzillaService class with a single query method.
2. Add strict request/response validators for required envelope shape.
3. Implement safe retries for retryable categories only.
4. Add tests using mocked HTTP responses for success and each error category.
5. Document env variables and failure modes.

### Acceptance Criteria

- Unit tests validate envelope parse and error handling paths.
- With KATZILLA_ENABLED false, no Katzilla code path is executed.
- With KATZILLA_ENABLED true and missing key, startup fails fast with clear error.

## Phase 2: Evidence Model Adapter

### Deliverables

- Adapter that converts Katzilla responses into internal external-evidence records.
- Provenance preservation contract for citation metadata:
  - source_name
  - source_url
  - retrieved_at
  - data_hash
  - license
  - update_frequency
  - request_url (if present)
- Quality-to-confidence mapping utility for future DoT use.

### Tasks

1. Add typed dataclass(es) for Katzilla external evidence metadata.
2. Build adapter function(s) from envelope to normalized evidence records.
3. Add credibility and uncertainty derivation helper from quality fields.
4. Add tests for complete citation, partial citation, and missing optional quality fields.
5. Add safeguards to prevent external evidence objects from replacing persona/domain evidence ordering by default.

### Acceptance Criteria

- Citation metadata is preserved intact in adapted records.
- Adapter handles both full and compact response formats.
- No mutation to existing EvidenceFact and DomainEvidenceFact behavior.

## Phase 3: Retrieval Integration (Controlled Rollout)

### Deliverables

- Optional Katzilla branch in retrieval path.
- Small allowlist of initial actions for controlled release.
- Token-optimized request defaults for cost and latency control.

### Initial Action Allowlist

Start with a narrow, high-value set:
- government / congress-bills
- health / fda-recalls
- hazards / usgs-earthquakes

### Tasks

1. Add gated branch in retrieve_evidence workflow to request external facts only when enabled.
2. Add rollout guards:
  - explicit feature flag
  - per-query hard cap for external results
  - short timeout and graceful fallback to existing local retrieval
3. Add token optimization defaults for every Katzilla call:
  - compact format
  - explicit field allowlist
  - bounded result limits
4. Add retrieval merge logic that appends external evidence without breaking existing ranking semantics.
5. Add tests for:
  - disabled mode
  - enabled mode with success
  - enabled mode with timeout/error fallback
  - bounded external result counts

### Acceptance Criteria

- Existing retrieval behavior is unchanged when flag is off.
- When flag is on, retrieval returns a blended list with external entries bounded by configured limits.
- External errors do not fail generation flow; they degrade to existing local retrieval.

## Test Strategy

Unit tests:
- Katzilla service envelope parsing and error mapping
- Adapter data normalization and provenance persistence
- Retrieval branch gating and fallback behavior

Integration tests:
- Mocked end-to-end path from query to normalized external evidence merge

Regression checks:
- Run project test suite and verify no breakage in current grounding pipelines.

## Risks and Mitigations

1. Risk: External API latency affects generation timing.
- Mitigation: Tight timeouts, bounded calls, fail-open fallback.

2. Risk: Citation contract drift from vendor changes.
- Mitigation: Response shape validation with explicit warnings and safe defaults.

3. Risk: Cost growth from broad action usage.
- Mitigation: Action allowlist, compact format, strict per-query limits.

4. Risk: Feature leaks into default flow.
- Mitigation: Default-off flags and explicit startup/runtime checks.

## Operational Controls

- Feature flag is default off.
- Max external evidence items per query is capped.
- Retry policy applies only to retryable categories.
- All Katzilla calls produce debug logs with redacted secrets.

## Definition of Done for This Feature

1. Phase 1 deliverables complete with tests.
2. Phase 2 deliverables complete with tests.
3. Phase 3 deliverables complete with tests.
4. Documentation updated for env variables and rollout controls.
5. Regression test pass confirmed.
6. Phase 4 deliverables complete with tests.
7. Phase 5 deliverables complete with tests.
8. Phase 6 deliverables complete with tests.
