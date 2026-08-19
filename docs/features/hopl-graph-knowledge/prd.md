# Product Requirements Document: Typed Predicate Knowledge Graph

## Executive Summary

The LinkedIn SSI Booster already combines persona facts, domain knowledge,
NetworkX graph relationships, BM25 retrieval, spaCy extraction, PLN scoring,
Derivative of Truth (DoT), and a post-generation truth gate. These components
provide useful evidence, but factual relationships are still primarily stored
as text and are not consistently queryable by subject, predicate, object,
polarity, or qualifier.

This feature adds a small, typed, provenance-aware predicate layer over the
existing knowledge system. It will support conservative structured extraction,
predicate-aware retrieval, bounded one-hop and two-hop derivation, contradiction
review candidates, and explanations that link every result to source text and
premises.

The first release is not a higher-order logic engine. It will not implement
unrestricted quantifiers, lambda calculus, theorem proving, causal certainty,
or a new graph database. Existing text facts, BM25 retrieval, NetworkX graph
behavior, PLN scoring, and truth-gate validation remain authoritative and
backward compatible.

## Project Context

Users are the owner/editor reviewing grounded LinkedIn content and developers
maintaining persona, domain, retrieval, learning, and explainability behavior.
Facts come from persona data, domain packs, and article extraction; BM25 and
graph signals retrieve evidence; local Ollama generates; DoT/PLN, confidence
policy, and the truth gate run before Buffer publication.

Constraints are Python 3.12+, typed serializable models, absolute imports,
existing NetworkX/spaCy/BM25/avatar/PLN reuse, deterministic tests, no LLM-only
parsing, focused modules below the repository's 300-500 line limit, and no
dependency on optional PostgreSQL mode.

## Goals and Non-Goals

### Goals

1. Represent selected factual relationships explicitly and conservatively.
2. Preserve source text, source fact ID, confidence, parse status, and qualifiers.
3. Improve bounded predicate retrieval without reducing BM25 recall or breaking text-only fallback.
4. Make bounded derivations inspectable, PLN-scored, and distinct from direct evidence.
5. Surface possible contradictions for human review without auto-rejecting
   claims or publishing inferred facts as persona truth.

### Non-goals

- Full HOPL, higher-order variables, lambda calculus, or general unification.
- General theorem proving, unrestricted rule execution, or causal claims.
- Replacing the existing NetworkX graph, text facts, BM25, truth gate, DoT, or
  persona/domain formats.
- Requiring every existing fact or domain pack to parse successfully.
- Automatic promotion of derived results into first-party persona claims.
- Adding rdflib, Prolog, Neo4j, or another logic dependency in the MVP.

## User Stories and Acceptance Criteria

### US-1: Inspect a structured fact

**As a** developer or editorial reviewer, **I want to** see a selected fact as
a subject-predicate-object relationship with provenance, **so that** I can
understand what the system believes the source sentence expresses.

**Acceptance criteria:**

- An accepted fact exposes stable subject and object identifiers, a normalized
  predicate, polarity, confidence, parse status, source fact ID, and source
  text.
- Optional version, numeric, time, source, scope, degree, and comparison-target
  qualifiers are retained with the original statement.
- A failed or ambiguous parse remains text-only or is marked `uncertain`; it is
  never silently stored as a high-confidence accepted relation.

### US-2: Retrieve by predicate pattern

**As a** user asking a factual question, **I want to** match a bounded pattern
such as `improved(Python, ?object)`, **so that** relevant relationships are
distinguished from keyword co-occurrence.

**Acceptance criteria:**

- Patterns can constrain subject, predicate, object, polarity, and supported
  qualifier filters.
- Predicate matching is applied after broad BM25 candidate selection or has a
  documented text-only fallback when no predicate parse exists.
- Results include matched fact, source, confidence, qualifiers, and provenance.

### US-3: Review bounded derivations

**As a** reviewer, **I want to** inspect a one-hop or two-hop conclusion and its
premises, **so that** inferred content is not confused with directly observed
evidence.

**Acceptance criteria:**

- A derivation records premise IDs, rule or inference type, hop count, result,
  PLN truth value, and source links.
- Direct and derived results have distinct statuses and are distinguishable in
  retrieval and generation context.
- Inference confidence does not exceed the supported direct evidence by default
  and any confidence revision is explicit.

### US-4: Review possible contradictions

**As a** reviewer, **I want to** see potentially conflicting claims with their
scope and provenance, **so that** I can investigate them before publication.

**Acceptance criteria:**

- The system reports review candidates, not proven contradictions.
- Candidate comparison considers polarity and available time, scope, workload,
  comparison-target, and source qualifiers.
- Facts with opposing values remain separate when the available context does
  not establish incompatibility.

### US-5: Ground and explain generated content

**As a** content author, **I want to** provide structured evidence alongside
source text to generation and explanation paths, **so that** generated claims
can be audited without weakening the existing truth gate.

**Acceptance criteria:**

- Grounding context can include subject, predicate, object, qualifiers, source,
  confidence, and parse status.
- Existing DoT, confidence routing, and truth-gate validation still run for
  generated output.
- Predicate data cannot bypass unsupported-claim filtering or cause Buffer
  publication by itself.

## Functional Requirements

### FR-1: Typed model and validation

- Define serializable models for `PredicateFact`, parse results, bounded
  patterns, derivations, and contradiction candidates using repository naming
  and dataclass conventions.
- Validate identifiers, normalized predicates, polarity, confidence, and parse
  status at the model boundary.
- Treat absent predicates as unknown, never as negative polarity.
- Support binary relations and subject-property-value facts; allow a nullable
  object for property/value cases.

### FR-2: Conservative extraction

- Use the existing spaCy dependency/NLP pipeline as the initial deterministic
  parser boundary.
- Cover reviewed fixtures for active/passive voice, negation, coordination,
  qualifiers, and ambiguous or implicit subjects/objects.
- Return failure reasons and uncertainty rather than guessing unsupported
  structures.
- Preserve original source text and source fact identity for every candidate.

### FR-3: Existing graph integration

- Extend or companion the existing `KnowledgeGraphManager`; do not create a
  separate graph implementation.
- Reuse stable entity/fact IDs and add clearly named predicate metadata/edges.
- Keep existing graph proximity, claim-support, persistence, and explanation
  behavior unchanged for unparsed facts and packs.
- Reload serialized predicate data without changing existing domain pack schemas.

### FR-4: Predicate-aware retrieval

- Provide a focused internal pattern object rather than a general query
  language.
- Support bounded subject, predicate, object, polarity, and qualifier filters.
- Use predicate matches as filtering or reranking signals after broad retrieval.
- Return text-only evidence when no accepted predicate match is available.

### FR-5: Bounded inference

- Implement only explicit, tested one-hop and two-hop deduction rules in the
  initial release.
- Delegate truth-value calculations to existing PLN functions.
- Persist derivations separately from direct facts with hop count, premises,
  inference type, and truth value.
- Keep inferred results out of persona claims unless explicitly reviewed or
  independently supported.

### FR-6: Contradiction review

- Detect only narrow, configured incompatible predicate/value combinations.
- Include available scope, time, polarity, source, and comparison metadata.
- Expose candidates through an inspection API or report; do not automatically
  delete, reject, or rewrite facts.

### FR-7: Grounding and explainability

- Add structured predicate evidence to grounding context only when traceable to
  source text.
- Explain direct facts and derived conclusions with source links and premise
  paths.
- Retain DoT annotations and truth-gate reason codes as separate validation
  signals rather than treating predicate structure as proof.

## Non-Functional Requirements

- **Backward compatibility:** Existing JSON/domain packs, text retrieval,
  learning, console, curation, and generation work without parsing.
- **Determinism:** The same source fixture and configuration produce the same
  parse status, normalized relation, and derivation result.
- **Auditability:** Accepted/derived results trace to source text; derived results also trace to premise IDs and a rule.
- **Safety:** Uncertain parses, negative polarity, contradictions, and inferred
  conclusions remain reviewable and cannot bypass the truth gate.
- **Performance:** Extraction, matching, and derivation latency must be
  benchmarked against the actual graph size before a numeric SLO is adopted.
- **Maintainability:** Use focused modules, typed APIs, absolute imports,
  specific exceptions, and logging instead of diagnostic `print()`.
- **Testability:** Unit tests cover models, parser abstention, serialization,
  matching, inference boundaries, contradiction candidates, and fallbacks.
- **Language boundary:** The model can carry language/script metadata, but English parsing is the only MVP scope; Japanese parsing must not rely on English-only assumptions.

## Project System Integration

- `services/avatar_intelligence/_extraction.py`: produce candidates while
  retaining ordinary text storage.
- `services/knowledge_graph.py`: persist predicate relationships and reuse graph
  entities, metadata, and explanation paths.
- `services/hybrid_retriever.py`: apply matching after BM25 and preserve
  graph/text fallback behavior.
- `services/spacy_nlp.py` and `services/pln_inference.py`: provide deterministic
  parse signals and score bounded derivations.
- DoT, console truth gate, loaders, and domain packs remain additive and
  independent of predicate acceptance.
- Defer PostgreSQL persistence until file serialization and behavior are proven.

## Data and API Contract

Expose a small package-level API following local conventions:

```python
PredicateGraph.parse_statement(statement) -> ParseResult
PredicateGraph.add_predicate_fact(fact) -> str
PredicateGraph.query_pattern(pattern) -> list[PredicateFact]
PredicateGraph.find_contradiction_candidates() -> list[ContradictionCandidate]
PredicateGraph.derive(premises, rule) -> DerivationResult
PredicateGraph.explain(conclusion_id) -> Derivation
```

Names may follow neighboring conventions. No custom text grammar is required
until the predicate vocabulary and query patterns are stable.

## Dependencies and Risks

The MVP uses existing spaCy, NetworkX, BM25, avatar models/loaders, PLN, DoT,
and truth-gate infrastructure. New formal-logic dependencies are explicitly
out of scope until a tested requirement demonstrates their need.

Risks include parser overreach, scope-dependent false contradictions,
multi-hop confidence inflation, migration pressure on active packs, and English
assumptions applied to Japanese facts. Mitigate with abstention, provenance,
bounded rules, direct/derived status, additive storage, and a language-aware
model boundary.

## Success Metrics

1. **Parse precision:** reviewed accepted fixtures are correctly represented;
   report the measured percentage and fixture size rather than assuming a
   target before the benchmark exists.
2. **Abstention quality:** ambiguous and unsupported fixtures are marked
   uncertain or remain text-only instead of becoming accepted false relations.
3. **Retrieval quality:** predicate-aware retrieval improves precision on a
   representative query set without materially reducing BM25 baseline recall.
4. **Provenance completeness:** 100% of accepted facts and derived results have
   source text; derived results also have premise IDs and derivation metadata.
5. **Inference calibration:** bounded conclusions are visibly lower-confidence
   or explicitly revised relative to direct premises unless independent evidence
   supports them.
6. **Contradiction usefulness:** reviewer evaluation measures useful candidates
   and false-positive rate before any automated enforcement is considered.
7. **Regression safety:** existing focused and full pytest suites pass, with no
   loss of text-only fallback behavior.

## Delivery Plan and Milestones

1. **Model and extraction spike:** Define models, validation, parser boundaries,
   fixture tests, and precision/abstention reporting; uncertain results remain
   text facts.
2. **Graph integration:** Persist accepted facts through the existing graph,
   reuse IDs, test reload, and verify unchanged pack loading.
3. **Pattern retrieval:** Add bounded post-BM25 matching/reranking,
   explanations, and fallback tests.
4. **Inference and review:** Add tested one-hop/two-hop deductions, PLN scoring,
   derivation persistence, and review-only contradiction candidates.
5. **Evaluation:** Measure parser/retrieval quality before considering Japanese
   semantics, CLI inspection, visualization, or database persistence.

## Open Decisions and Definition of Done

Resolve storage location, first fact categories, entity normalization for
`Python`/`Python 3.12`/`CPython`, incompatible predicate pairs, and the reviewed
fixture benchmark during implementation. Done means typed deterministic models
and parser tests, distinguishable accepted/uncertain/rejected/direct/derived
states, tested provenance and reload, preserved existing fallbacks, focused and
full pytest runs, updated docs, and explicit wording that predicate facts and
PLN derivations are evidence-grounded representations rather than proof.
