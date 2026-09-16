# Feature Idea: Reciprocal Rank Fusion for Grounded Hybrid Retrieval

## Overview

Improve evidence retrieval by combining lexical BM25 ranking, Model2Vec semantic ranking, and NetworkX graph signals with Reciprocal Rank Fusion (RRF). The feature will produce a stable, bounded evidence shortlist for console answers, content generation, avatar explanations, and Derivative of Truth reports.

The first version will use query-local graph expansion rather than whole-graph community clustering. Leiden clustering may be evaluated later if graph size and retrieval measurements show that clustering provides a meaningful benefit.

## Problem Statement

The current hybrid retriever combines BM25, semantic similarity, graph proximity, and claim support using weighted raw scores. These scores have different scales and calibration behavior, so a single weighted formula can overvalue one signal or make tuning fragile as the knowledge graph grows.

Broad graph retrieval also creates two risks:

- Irrelevant nodes can enter the grounding context and increase hallucination pressure.
- Larger fact pools increase retrieval, serialization, and prompt costs.

The system needs rank-aware fusion and an explicit candidate boundary before facts reach Ollama or truth-scoring reports.

## Proposed Solution

Add an RRF-based ranking stage to `HybridRetriever`:

1. Build independent ranked lists for BM25, Model2Vec semantic similarity, graph proximity, and claim support.
2. Fuse the lists using a configurable RRF constant:

   `RRF(fact) = sum(1 / (k + rank_i(fact)))`

3. Deduplicate facts by stable evidence ID.
4. Apply evidence-type quotas for persona, domain, extracted, and external evidence.
5. Return only the configured top-N facts for prompt grounding and reports.

For graph signals, retrieve only a small top-ranked lexical/semantic candidate set and expand at most one graph hop. Do not traverse or serialize the full graph for an ordinary generation request.

## Expected Benefits

- More stable retrieval when BM25 and semantic scores use different distributions.
- Less tuning pressure from raw-score weighting.
- Smaller and more relevant grounding contexts.
- Lower hallucination risk from unrelated graph nodes.
- More consistent evidence selection across console, schedule, and curate workflows.
- Better explainability because each selected fact can retain its contributing ranks.

## Technical Considerations

- Preserve the existing `HybridRetriever.find_facts()` API where practical.
- Make RRF opt-in initially or protect it with a configuration flag for comparison.
- Use stable evidence IDs for deduplication; do not use object identity as the primary key.
- Keep existing BM25, Model2Vec, and graph caches intact.
- Apply quotas after fusion so one evidence type cannot crowd out all others.
- Cap candidate lists before graph expansion and cap final context size before prompt construction.
- Preserve fallback behavior when rank_bm25, Model2Vec, or NetworkX are unavailable.
- Avoid adding `leidenalg` or `python-igraph` to the initial implementation.

## Project System Integration

- `services/hybrid_retriever.py`: rank-list generation and RRF fusion.
- `services/knowledge_graph.py`: bounded one-hop candidate expansion.
- `services/avatar_intelligence/_retrieval.py`: compatible evidence IDs and type quotas.
- `services/console_grounding/`: console fact selection and truth-gate evidence boundaries.
- `services/ollama_service.py`: receives only the final bounded evidence context.
- `services/derivative_of_truth/`: reports the selected evidence paths, not the full graph.
- `main.py`: console and CLI flows continue to consume the existing top-facts contract.

## Initial Scope

- Add RRF fusion for BM25 and graph/semantic ranked lists.
- Add configurable candidate and final-result limits.
- Add stable-ID deduplication and evidence-type quotas.
- Add bounded one-hop graph expansion for selected candidates.
- Preserve current weighted hybrid ranking behind a compatibility option during evaluation.
- Add tests for rank fusion, ties, duplicate evidence IDs, missing signals, quotas, and graph caps.
- Capture basic retrieval measurements: selected fact count, context characters, rank-source contribution, and retrieval latency.

## Out Of Scope

- Leiden community detection and new native graph dependencies.
- Whole-graph clustering at startup.
- Model training or embedding-model replacement.
- Changes to the truth-gate scoring formula.
- Changes to persona or domain data schemas.

## Success Criteria

- RRF returns deterministic rankings for identical inputs.
- No duplicate evidence IDs reach the grounding context.
- Final evidence count and context size remain within configured limits.
- Persona/domain/extracted quotas are respected when candidates exist.
- Console, schedule, curate, avatar-explain, and dot-report paths continue to work.
- Focused retrieval and console tests pass without live services.
- Retrieval latency and prompt size do not regress against the current weighted retriever on representative fixtures.
- A follow-up measurement determines whether Leiden clustering is justified by graph size or retrieval quality.
