# Feature Idea: Truth Gate — DoT + spaCy Deep Integration

## Overview

The current truth gate is a two-layer system: BM25 sentence scoring followed by
regex-based token matching. The Derivative of Truth (DoT) subsystem exists and
produces a `truth_gradient` score, but it is applied post-hoc to the whole kept
post text and does not influence which sentences are removed. The `overlap` field
on `EvidencePath` — which activates 25% of the DoT scoring formula — is never
populated. spaCy's `compute_similarity` and NER capabilities are loaded per run
but are unused during validation.

This feature closes these gaps: DoT and spaCy become active participants in the
per-sentence removal decision, and the evidence paths passed to DoT are enriched
with real token-overlap and proper source-type annotations.

---

## Implemented Runtime Optimizations (October 2026)

- Similarity candidates are cached as complete, model-specific corpora, including pools larger than 256 facts. The corpus cache keeps four entries of at most 4,096 texts each; larger inputs still work without being cached. Text or model changes cause a fresh parse.
- DoT fact tokenization uses the existing language-routed batch tokenizer. Its separate corpus cache reuses the parsed fact text across sentences and channels; overlap, credibility, evidence types, and thresholds are unchanged.
- Curation retains the first gate's `TruthGateMeta` and passes it through source-link formatting and truncation to confidence scoring. Original removal counts and reason codes therefore affect routing instead of disappearing in a second assessment of already-filtered text. Final channel length is still assessed separately.
- Nonstandard callers without matching metadata retain the validation fallback, using the requested channel and article reference.
- INFO stage timings expose truth-gate wall time separately from Ollama generation and confidence scoring. No prompts or generated content are included in these new timing records.

See [performance regression coverage](../../testing-and-dev.md#curation-performance-regressions) for operation-count tests and log interpretation.

---

## Problem Statement

Four concrete deficiencies exist in the current implementation:

1. **DoT `overlap` is always 0.0.** `EvidencePath` has an `overlap` field and the
   scoring formula (`_W_OVERLAP = 0.25`) is only used when `overlap > 0`. No call
   site ever computes or sets it. The richer 4-term formula is permanently dead code.

2. **DoT is post-hoc and advisory only.** `score_claim_with_truth_gradient` is
   called once on the entire kept text after all sentence decisions are final. It
   can set `meta.dot_flagged = True` and log a warning, but it cannot remove or
   re-examine any sentence. A low truth gradient is invisible to the routing logic.

3. **spaCy `compute_similarity` is never used for validation.** The semantic
   similarity method can detect paraphrased hallucinations that BM25 misses
   (different words, same meaning). It is only called in `suggest_matching_facts`,
   which is interactive-mode only. No non-interactive validation path uses it.

4. **Org-name check is brittle regex.** `_ORG_NAME_RE` catches patterns like
   `"at Google Cloud"` but misses many real org-name patterns. spaCy NER already
   identifies `ORG` entities at the sentence level with far higher recall.

---

## Proposed Solution

### Part A — Enrich evidence paths with real `overlap`

In `truth_gate_result`, before calling `score_claim_with_truth_gradient`, compute
token overlap between each sentence and each `ProjectFact`'s detail text using
the same BM25 tokenizer already in use (`_tokenize_for_bm25`). Set the `overlap`
field on the corresponding `EvidencePath` so the 4-term DoT formula activates.

Also use `annotate_evidence_and_reasoning` (already in `derivative_of_truth.py`)
to derive evidence type, reasoning type, and credibility from each fact's `source`
field (`avatar:*` → PRIMARY, `domain:*` → SECONDARY) instead of the current
hardcoded `EVIDENCE_TYPE_SECONDARY / 0.7`.

### Part B — Move DoT scoring to per-sentence scope

Instead of scoring the whole post once, score each flagged sentence individually
before the keep/remove decision. A sentence that passes BM25 but scores a DoT
`truth_gradient` below `TRUTH_GRADIENT_FLAG_THRESHOLD` (default 0.35) is treated
as an additional flag reason (`weak_dot_gradient`). The existing interactive
override flow is preserved — the user still sees the reason and can keep it.

This makes DoT an active filter, not just a reporting metric.

### Part C — spaCy `compute_similarity` as semantic safety net

After BM25 passes a sentence (score ≥ threshold), compute spaCy cosine similarity
between the sentence and the article text. If similarity is below a configurable
floor (suggested default `TRUTH_GATE_SPACY_SIM_FLOOR=0.10`) and the sentence
contains a numeric or org-name pattern, flag it as `low_semantic_similarity`. This
catches paraphrased hallucinations where the words are different but the claim is
unsupported.

Graceful degradation: if spaCy model is unavailable or has no vectors (e.g.
`en_core_web_sm`), this check is silently skipped — no behaviour change.

### Part D — Replace regex org-name check with spaCy NER

Replace `_ORG_NAME_RE` pattern matching with a spaCy NER pass to extract `ORG`
entities from the sentence. Check each detected org against the `allowed` token
set. Falls back to the existing regex when spaCy is unavailable, preserving current
behaviour exactly.

---

## Expected Benefits

- **More accurate per-sentence removal** — DoT gradient becomes an active gate,
  catching confidently-stated but poorly-supported claims that pass BM25 because
  they share vocabulary with the article.
- **Dead code activated** — The 4-term DoT overlap formula (`_W_OVERLAP = 0.25`)
  becomes live, producing more discriminating truth gradient scores.
- **Better org-name recall** — spaCy NER catches org names that `_ORG_NAME_RE`
  misses (single-word brands, all-caps names, abbrevs).
- **Semantic paraphrase detection** — `compute_similarity` adds a layer that BM25
  cannot provide: catching claims that use different words to say the same false
  thing.
- **No new dependencies** — All components (`rank_bm25`, `spacy`, `derivative_of_truth`)
  are already installed and loaded per run.

---

## Technical Considerations

### Project Integration

- All changes are confined to `services/console_grounding.py` (truth gate logic)
  and `services/derivative_of_truth.py` (evidence path construction helpers).
- No changes to `avatar_intelligence.py`, `ollama_service.py`, or `content_curator.py`.
- `TruthGateMeta` may gain two new fields: `dot_per_sentence_scores` (list of
  floats, one per removed sentence) and `spacy_sim_scores` (dict of sentence →
  similarity). Both optional/defaulted to maintain backward compatibility.

### Graceful Degradation Chain

```
DoT overlap enrichment   → falls back to overlap=0.0 (current behaviour)
DoT per-sentence scoring → falls back to skip if evidence paths empty
spaCy similarity check   → skipped entirely if no vectors or model missing
spaCy NER org check      → falls back to existing _ORG_NAME_RE regex
```

### Performance

- DoT per-sentence: ~0.1 ms each (pure Python, no model calls).
- spaCy NER + similarity: ~5–20 ms per sentence depending on model. Lazy-loaded,
  cached globally — no per-sentence model reload.
- Net overhead on a 10-sentence LinkedIn post: < 200 ms on `en_core_web_sm`.
  Negligible relative to Ollama generation time.

### Config / .env

One optional new env var:

```
# Minimum spaCy cosine similarity for a numeric/org sentence to pass
# semantic check (default: 0.10 — very permissive, avoids false positives).
TRUTH_GATE_SPACY_SIM_FLOOR=0.10
```

---

## System Integration

- `console_grounding.truth_gate_result` — primary change site (Parts B, C, D)
- `console_grounding.truth_gate_result` + `derivative_of_truth.py` — Part A (overlap)
- `derivative_of_truth.annotate_evidence_and_reasoning` — reused as-is
- `spacy_nlp.SpacyNLP.compute_similarity` — reused as-is
- `spacy_nlp.SpacyNLP.extract_themes` — reused for NER org extraction (Part D)
- `avatar_intelligence.record_moderation_event` — gains new reason codes:
  `weak_dot_gradient`, `low_semantic_similarity`

---

## Initial Scope

- [x] Part A: compute `overlap` per fact-sentence pair; use `annotate_evidence_and_reasoning`
- [x] Part B: per-sentence DoT scoring before keep/remove decision
- [x] Part C: spaCy similarity floor check for numeric/org sentences
- [x] Part D: spaCy NER org-name extraction replacing `_ORG_NAME_RE`
- [x] New unit tests in `tests/test_truth_gate_dot.py`
- [x] Existing `test_confidence_scoring.py` and `test_derivative_of_truth.py` must still pass

**Implementation completed April 30, 2026. All 325 tests pass (30 new in `test_truth_gate_dot.py`).**

---

## Success Criteria

- `EvidencePath.overlap` is non-zero for at least one path per sentence when
  article text and facts are both non-empty.
- A sentence that passes BM25 but has `truth_gradient < 0.35` is flagged with
  `weak_dot_gradient` in non-interactive mode (auto-removed).
- A sentence containing a numeric claim with `spacy_similarity < 0.10` is flagged
  with `low_semantic_similarity` when spaCy vectors are available.
- spaCy NER org check catches at least the same set of org names as the current
  regex on the existing test fixtures.
- All existing tests pass. No new required env vars (new var is optional with safe default).
