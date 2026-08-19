# Typed Predicate Knowledge Graph

## Overview

Add a typed, provenance-aware representation for selected facts in the avatar's
knowledge graph.

The near-term goal is not to build a complete higher-order predicate-logic
engine. The goal is to make important factual relationships explicit enough to
support better retrieval, bounded multi-hop reasoning, contradiction
candidates, and explanations of how a conclusion was formed.

The proposed pipeline is:

```text
natural-language statement
  -> candidate predicate fact
  -> validated graph representation
  -> logical-pattern retrieval or bounded derivation
  -> PLN scoring and provenance
  -> grounded generation or review
```

This feature should be treated as an additional semantic layer over the current
knowledge system. It should not replace the existing text facts, BM25
retrieval, NetworkX graph, or truth-gate validation.

## Why This Is Worth Adding

The current system already has substantial infrastructure:

- `services/knowledge_graph.py` stores typed nodes and edges in a NetworkX
  `MultiDiGraph`, with graph proximity, claim support, and explanation paths.
- `services/hybrid_retriever.py` combines BM25 ranking with graph proximity and
  claim-support signals.
- `services/avatar_intelligence/_extraction.py` extracts and persists factual
  statements from articles.
- Domain knowledge packs, including the Japanese language and kanji packs, are
  loaded as structured facts and relationships.
- `services/pln_inference.py` provides deduction, induction, abduction,
  revision, and evidence-weight calculations.
- Derivative of Truth annotations provide evidence and reasoning metadata, but
  they are scoring and validation signals rather than a formal proof system.

What is missing is a stable representation connecting these capabilities. A
fact is generally available as text and metadata, while its subject,
predicate, object, polarity, scope, and qualifiers are not consistently
queryable.

For example, the system can retrieve a statement containing `Python`,
`improved`, and `async`, but it cannot yet reliably distinguish:

```text
Python --improved--> async performance
```

from a statement that merely mentions those words in unrelated roles.

Typed predicate facts would improve the structure and auditability of that
existing workflow.

## Scope And Terminology

The original idea called this feature HOPL, or higher-order predicate logic.
That name implies considerably more than the first implementation should
promise: higher-order variables, lambda calculus, quantifier semantics,
unification, theorem proving, and a formally specified model of truth.

The first implementation should instead be called a **typed predicate
knowledge graph**. It can later become a source for richer logical forms if
the project develops concrete requirements for them.

The system should distinguish three levels:

1. **Structured extraction**: a candidate interpretation of a sentence.
2. **Graph representation**: a persisted relationship with provenance and
   confidence.
3. **Inference**: a bounded, explicitly recorded derivation scored by PLN.

None of these should be described as proof of objective truth. They are
evidence-grounded representations and estimates that remain subject to source
quality, parser uncertainty, ambiguity, and truth-gate review.

## Proposed Data Model

Add a small, serializable model rather than embedding an unbounded logic
language in every graph node.

```python
@dataclass
class PredicateFact:
    id: str
    subject_id: str
    predicate: str
    object_id: str | None
    source_fact_id: str
    source_text: str
    qualifiers: dict[str, str] = field(default_factory=dict)
    polarity: str = "positive"
    confidence: str = "medium"
    parse_status: str = "accepted"
```

Recommended fields and meanings:

- `subject_id`: stable entity or concept identifier.
- `predicate`: normalized relation such as `improved`, `supports`,
  `has_version`, or `located_in`.
- `object_id`: stable entity or concept identifier, when the relation has an
  object.
- `source_fact_id`: link back to the existing domain or extracted fact.
- `source_text`: original text retained for auditability and generation.
- `qualifiers`: optional values such as `version`, `time`, `degree`, `scope`,
  or `comparison_target`.
- `polarity`: initially `positive` or `negative`; absence of a predicate must
  not be interpreted as negation.
- `confidence`: confidence in the extraction or relation, not a claim of
  universal truth.
- `parse_status`: for example `accepted`, `uncertain`, or `rejected`.

An event or claim node should be used when a statement has several qualifiers:

```text
Python 3.12
    |
    | subject
    v
ImprovementClaim
    | predicate
    v
improved
    |
    | object
    v
async performance

ImprovementClaim --has_version--> 3.12
ImprovementClaim --has_degree--> significant
ImprovementClaim --supported_by--> article-fact
```

This is preferable to placing arbitrary qualifiers directly on a binary edge,
because it preserves the identity and provenance of the claim or event.

## Initial Supported Semantics

The first version should support only semantics that can be tested reliably:

- binary subject-predicate-object relations;
- subject-property-value facts;
- explicit positive and negative polarity;
- version, numeric, time, source, and scope qualifiers;
- provenance back to the original fact;
- extraction confidence and parse status;
- stable entity identifiers and normalized predicate names.

It should not initially claim to support unrestricted quantifiers, modal
logic, causal certainty, nested lambda expressions, or general theorem
proving.

Statements that are ambiguous should produce an uncertain candidate or remain
text-only. A parser that guesses a relation should not silently promote that
guess to a high-confidence graph fact.

## Relationship To Existing Components

### Knowledge graph

Extend the existing `KnowledgeGraphManager` through a focused helper or
companion module. Do not create a second unrelated graph implementation.

The existing graph remains responsible for nodes, edges, metadata, proximity,
claim support, persistence, and explanation paths. Predicate facts add
normalized semantic metadata and carefully named relationship edges.

### NLP extraction

Use the current spaCy pipeline and dependency information as the first parser
source. The extractor should be deterministic and return a parse result with
confidence and failure reasons.

It should be conservative about:

- passive voice;
- coordination and multiple clauses;
- pronouns and unresolved references;
- negation;
- comparative language;
- numeric and version scope;
- statements where the subject or object is implicit.

An LLM may eventually propose alternative parses, but it should not be the
only source of logical structure and it should not bypass provenance or
validation.

### Hybrid retrieval

Keep BM25 as the broad candidate selector. Add predicate-aware filtering or
reranking only after candidate selection:

```text
BM25 candidates
  -> optional predicate-pattern match
  -> graph proximity and claim support
  -> DoT / PLN evidence signals
  -> final ranked evidence
```

This preserves the current graceful fallback behavior and avoids requiring
every fact to have a successful parse.

### PLN inference

PLN already supplies truth-value calculations. The new graph layer should
provide explicit premises and derivation records for those functions.

For example:

```text
Python 3.12 --has_feature--> async
async --improves--> I/O performance
```

may support a bounded candidate conclusion:

```text
Python 3.12 --improves--> I/O performance
```

The derivation should record its premises, inference type, hop count, and
resulting `PLNTruthValue`. The result is an inferred candidate, not a new
first-party fact. It must retain lower confidence than direct evidence unless
independent evidence supports it.

### Domain knowledge packs

Existing packs such as `domain_knowledge_kanji_200.json` already express useful
relationships through statements, tags, domains, and relationship records.
They should continue to load unchanged.

Predicate extraction can be added incrementally to selected facts or generated
at load time. The feature must not require rewriting all existing domain packs
before the system remains usable.

## User And System Use Cases

### Predicate-aware retrieval

```text
Question: What did Python improve?

Pattern: improved(Python, ?object)

Result: the matching fact, source, confidence, qualifiers, and provenance
```

This is more precise than relying on keyword co-occurrence alone, while still
retaining BM25 for recall.

### Bounded multi-hop reasoning

```text
Premise 1: Python 3.12 has async support.
Premise 2: async support improves I/O performance.

Candidate conclusion: Python 3.12 improves I/O performance.
```

The system should return the derivation path and confidence degradation rather
than presenting the conclusion as directly observed.

### Contradiction candidates

Detect potentially conflicting claims such as:

```text
Python --property--> fast
Python --property--> slow
```

The first version should report these for review only. It should consider
scope, time, comparison target, polarity, and source before calling two facts
incompatible. “Fast” and “slow” may both be valid under different workloads.

### Grounded generation

Provide the generator with structured evidence alongside the original text:

```text
subject: Python 3.12
predicate: improved
object: async performance
source: article URL
confidence: medium
parse_status: accepted
```

This improves prompt grounding and explanation. It does not guarantee that
generated prose will preserve every logical qualifier, so the existing truth
gate and post-generation validation remain necessary.

## Proposed API Surface

Prefer a focused service or module over making `KnowledgeGraphManager` a
large reasoning object.

```python
class PredicateGraph:
    def parse_statement(self, statement: str) -> ParseResult:
        """Return a conservative candidate predicate fact."""

    def add_predicate_fact(self, fact: PredicateFact) -> str:
        """Persist a validated predicate fact and its provenance."""

    def query_pattern(self, pattern: PredicatePattern) -> list[PredicateFact]:
        """Return facts matching a bounded predicate pattern."""

    def find_contradiction_candidates(self) -> list[ContradictionCandidate]:
        """Return review candidates, not automatically proven contradictions."""

    def derive(self, premises: list[str], rule: str) -> DerivationResult:
        """Create a bounded, provenance-preserving inference candidate."""

    def explain(self, conclusion_id: str) -> Derivation:
        """Return premises, rules, scores, and source links for a conclusion."""
```

The exact public names should follow existing package conventions after the
first implementation slice is tested. Avoid exposing a custom text grammar
until the supported pattern vocabulary is stable.

## Recommended Implementation Plan

### Phase 1: Model and extraction spike

- Define `PredicateFact`, `ParseResult`, and provenance fields.
- Implement deterministic extraction for a small set of English factual
  patterns.
- Add tests for active voice, passive voice, negation, coordination,
  qualifiers, and ambiguous sentences.
- Measure parse acceptance and precision on a small, reviewed fixture set.
- Keep failed or uncertain parses as ordinary text facts.

### Phase 2: Graph integration

- Map accepted predicate facts into the existing NetworkX graph.
- Reuse existing fact IDs and entity IDs where possible.
- Add stable predicate names and metadata without changing existing pack
  schemas.
- Preserve source fact, source URL, original statement, confidence, and parse
  status.
- Add serialization and reload tests.

### Phase 3: Pattern retrieval

- Implement a small internal pattern object rather than a full query language.
- Support subject, predicate, object, polarity, and simple qualifier filters.
- Use predicate matches as a reranking or filtering signal after BM25.
- Return explanations showing the matched relation and source fact.

### Phase 4: Bounded inference and review signals

- Implement only explicit, tested one-hop and two-hop deduction rules.
- Call the existing PLN functions for strength and confidence calculations.
- Persist derivation records separately from direct facts.
- Add contradiction candidates for narrow, known-incompatible predicate/value
  pairs.
- Keep inferred results out of first-party persona claims unless explicitly
  reviewed or independently supported.

### Phase 5: Evaluation and selective expansion

- Add Japanese-language handling only after the English semantic contract is
  stable, or introduce a language-aware parser boundary from the beginning.
- Evaluate whether domain packs such as the kanji knowledge graph benefit from
  explicit predicates beyond their current statements and relationships.
- Add CLI inspection and visualization only if debugging or editorial review
  demonstrates a need.

Full quantifiers, lambda calculus, richer unification, and external RDF or
Prolog integration should remain future options, not Phase 1 requirements.

## Success Metrics

Use measured behavior rather than assumed coverage percentages.

1. **Parse precision**: percentage of accepted predicate facts judged correct by
   a reviewed test set.
2. **Parse abstention quality**: ambiguous statements should be marked
   uncertain rather than confidently misrepresented.
3. **Retrieval quality**: compare predicate-aware retrieval with the existing
   BM25-plus-graph baseline on representative queries.
4. **Provenance completeness**: every accepted predicate fact and derived result
   links back to source text and, where applicable, source URL and premises.
5. **Inference calibration**: multi-hop conclusions must show lower or
   appropriately revised confidence than their premises.
6. **Contradiction review precision**: measure useful review candidates and
   false positives before considering automated enforcement.
7. **Performance**: measure extraction, pattern query, and derivation latency
   against the actual graph size; do not commit to `<100 ms` until a benchmark
   exists.

## Risks And Guardrails

### Semantic overreach

Dependency parsing can identify grammatical structure without fully resolving
meaning. Every parse needs an uncertainty state and a path back to the source
sentence.

### False contradictions

Opposing adjectives or values are not necessarily contradictions. Scope,
time, workload, comparison class, and polarity must be considered.

### Confidence inflation

PLN confidence is a modelled weight of evidence. It is not proof that a parsed
or derived statement is true. Direct, derived, and inferred facts must remain
distinguishable in storage and prompts.

### Schema migration pressure

The current knowledge packs and extracted knowledge files are useful and
actively loaded. The new layer should be additive and backward compatible.

### Language coverage

The current extraction assumptions are primarily English-oriented. Japanese
facts, kanji knowledge, and future bilingual lyric workflows need a parser
boundary that can represent language, script, reading, and segmentation without
forcing English spaCy assumptions onto Japanese text.

## Dependencies

No new logic framework is required for the initial implementation.

Use the existing:

- spaCy and dependency parsing;
- NetworkX graph;
- avatar knowledge models and loaders;
- BM25 retrieval;
- PLN inference functions;
- Derivative of Truth annotations and truth-gate validation.

Consider `nltk`, `rdflib`, `owlready2`, or a Prolog runtime only when a tested
requirement cannot be met by the focused predicate model. Adding a formal logic
dependency before the semantic contract is proven would increase maintenance
cost without guaranteeing better grounding.

## Open Questions

1. Which fact categories produce enough retrieval or reasoning value to justify
   parsing first: domain facts, extracted article facts, persona claims, or all
   three?
2. Should predicate facts be persisted in a separate JSON artifact, embedded in
   graph metadata, or stored in the optional PostgreSQL schema?
3. What entity-normalization rules prevent `Python`, `Python 3.12`, and
   `CPython` from being incorrectly merged?
4. Which predicate pairs are genuinely incompatible, and what scope fields are
   required before flagging them?
5. How should Japanese predicates, readings, and mixed Japanese-English facts be
   represented without depending on an English-only tokenizer?
6. Which reviewed fixture set will be the acceptance benchmark for parser
   precision and abstention?

## Recommendation

Proceed with a small implementation spike in the near future, but name and
scope it accurately:

> Build a typed predicate layer over the existing knowledge graph to improve
> structured retrieval, bounded provenance-aware inference, and contradiction
> review.

Start with a reversible, additive Phase 1. Do not begin with full HOPL,
quantifier semantics, theorem proving, or a new graph database. The feature is
worth adding because it can make the current graph and PLN capabilities more
useful; its value depends on measured precision, conservative abstention, and
clear separation between direct evidence and inferred candidates.
