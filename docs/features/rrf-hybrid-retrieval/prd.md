# Product Requirements Document: RRF Hybrid Retrieval

## 1. Executive Summary

This feature introduces Reciprocal Rank Fusion (RRF) and bounded query-local graph expansion to the LinkedIn SSI Booster retrieval pipeline. It will combine BM25, Model2Vec semantic similarity, graph proximity, and claim-support rankings without relying solely on incomparable raw-score weights.

The feature will produce a deterministic, deduplicated, evidence-type-balanced shortlist before facts enter Ollama prompts, truth-gate scoring, avatar explanations, or Derivative of Truth reports. Leiden community detection is explicitly deferred until measurements show that query-local retrieval is insufficient.

## 2. Project Context

The application currently combines BM25, Model2Vec, NetworkX graph signals, claim support, and truth-gate validation. As persona, domain, and extracted knowledge grow, broad candidate retrieval can increase latency, prompt size, and the chance that unrelated facts influence generation.

The current weighted hybrid formula is sensitive to score calibration. BM25, semantic similarity, graph proximity, and claim support do not naturally share the same scale or distribution. RRF is appropriate because it fuses ranked lists rather than pretending their raw scores are directly comparable.

## 3. User Stories

- **As a content creator**, I want only relevant persona and domain facts passed to generation, so posts remain grounded and avoid unrelated claims.
- **As a console user**, I want retrieval to remain fast as the knowledge graph grows, so interactive responses stay responsive.
- **As a reviewer**, I want explain reports to show the selected evidence and contributing rank sources, so I can understand why facts were chosen.
- **As a developer**, I want a rank-fusion strategy that tolerates missing retrieval signals, so degraded environments remain usable without Model2Vec or graph support.
- **As an operator**, I want retrieval limits and quotas to be configurable, so prompt size and runtime cost remain predictable.

## 4. Functional Requirements

### FR-1: Independent Ranked Lists

The retriever shall produce ranked candidate lists for available signals:

- BM25 lexical relevance
- Model2Vec semantic similarity
- NetworkX graph proximity
- Claim-support score

Missing signals shall produce an empty list or neutral contribution rather than failing retrieval.

### FR-2: RRF Fusion

The retriever shall combine ranked lists using configurable RRF constant `k`:

`RRF(fact) = sum(1 / (k + rank_i(fact)))`

The implementation shall use stable evidence IDs for identity and deduplication. Equal inputs shall produce deterministic ordering, including deterministic tie-breaking.

### FR-3: Bounded Candidate Processing

The retriever shall cap the number of candidates entering fusion and graph expansion. Graph expansion shall be query-local and limited to at most one hop in the initial release.

The retriever shall not traverse or serialize the whole knowledge graph for ordinary generation requests.

### FR-4: Evidence Quotas

After fusion, the retriever shall apply configurable quotas for persona, domain, extracted, and external evidence where candidates exist. Quotas shall prevent one evidence type from consuming the entire final context.

### FR-5: Final Evidence Boundary

The final result shall be limited by configured fact count and, where applicable, context-character limits before prompt construction. Duplicate evidence IDs shall never reach grounding context or explain reports.

### FR-6: Explainability

When explainability is enabled, the system shall retain enough metadata to report selected evidence IDs and the rank sources that contributed to selection. Reports shall describe the bounded selected set, not the full graph.

### FR-7: Compatibility and Fallback

The existing `find_facts()` contract shall remain compatible for current callers. The existing weighted hybrid strategy shall remain available during evaluation. Retrieval shall degrade gracefully when rank_bm25, Model2Vec, or NetworkX is unavailable.

### FR-8: Configuration

The implementation shall support configuration for:

- RRF constant `k`
- Candidate pool limit
- Graph expansion limit and hop count
- Final evidence limit
- Evidence-type quotas
- Feature enablement or comparison mode

Defaults shall preserve bounded, conservative behavior.

## 5. Non-Functional Requirements

- **Performance:** RRF and bounded expansion must not increase median retrieval latency by more than 10% over the current weighted retriever on representative fixtures.
- **Prompt size:** Final grounding context shall remain at or below the configured evidence/context limits.
- **Determinism:** Identical query, graph, and evidence inputs shall produce identical result ordering.
- **Reliability:** Missing optional retrieval components shall not break generation or console mode.
- **Maintainability:** New ranking logic shall be modular, typed, and covered by focused unit tests.
- **Observability:** Retrieval timing, candidate count, final count, quota usage, and contributing rank sources shall be available at debug level or in explain metadata.
- **Compatibility:** Existing console, schedule, curate, avatar-explain, dot-report, and truth-gate flows shall continue to operate.

## 6. Acceptance Criteria

- RRF rankings are correct for single-source and multi-source fixtures.
- Duplicate facts with the same evidence ID are emitted once.
- Missing BM25, semantic, or graph signals do not raise errors.
- Candidate and final-result caps are respected.
- Evidence-type quotas are respected when enough candidates exist.
- One-hop graph expansion never exceeds its configured cap.
- Console and CLI grounding use the bounded final evidence set.
- Avatar-explain and dot-report do not display unrelated full-corpus records.
- Focused retrieval, console, and truth-gate tests pass without live external services.
- A benchmark fixture records baseline versus RRF latency, candidate count, final count, and context size.

## 7. Project System Integration

- `services/hybrid_retriever.py`: ranked-list generation, RRF fusion, quotas, and result metadata.
- `services/knowledge_graph.py`: bounded one-hop expansion.
- `services/model2vec_service.py`: semantic ranking input.
- `services/avatar_intelligence/_retrieval.py`: evidence types and stable IDs.
- `services/console_grounding/`: console grounding boundaries and truth validation.
- `services/ollama_service.py`: bounded grounding context passed to Ollama.
- `services/derivative_of_truth/`: evidence paths for selected facts only.
- `main.py`: preserve existing top-facts flow for console and CLI generation.

## 8. Dependencies and Risks

Dependencies are existing BM25, Model2Vec, NetworkX, and evidence-normalization services. No new native graph dependency is required for the initial release.

Primary risks include retrieval-quality regressions, over-constraining graph expansion, unstable evidence quotas, and stale rank metadata after reload or continual learning. These risks are mitigated by compatibility mode, deterministic tests, cache invalidation, and baseline benchmarks.

Leiden clustering remains a follow-up investigation. It should be added only if graph-scale measurements demonstrate that bounded query-local expansion is insufficient.

## 9. Success Metrics

- At least 95% of generated requests stay within configured evidence and context limits.
- Zero duplicate evidence IDs in final grounding contexts.
- No measurable increase in hallucination-related truth-gate failures on the regression fixture.
- Median retrieval latency remains within the 10% NFR budget.
- Explain reports show fewer irrelevant evidence records while preserving relevant selected facts.
- Retrieval-source contribution is inspectable for representative queries.

## 10. Milestones

1. Define stable evidence identity and ranking metadata.
2. Implement RRF fusion with deterministic tie-breaking.
3. Add candidate caps, one-hop graph expansion, and evidence quotas.
4. Integrate bounded results with console, schedule, curate, and reports.
5. Add regression tests and benchmark fixtures.
6. Compare RRF against the existing weighted strategy and decide whether to enable it by default.
7. Document configuration and revisit Leiden only after measurement.
