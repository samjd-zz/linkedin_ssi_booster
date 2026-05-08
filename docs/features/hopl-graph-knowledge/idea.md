# HOPL Graph Knowledge: Logical Expression to Graph Representation

## Overview

Transform natural language sentences into higher-order predicate logic (HOPL) expressions and represent them as graph structures. This enhances our knowledge representation by making logical structure explicit, enabling formal inference and multi-hop reasoning.

## Problem Statement

Current knowledge representation stores facts as text strings with metadata. While effective for retrieval, this approach:

- Lacks explicit logical structure
- Makes compositional reasoning difficult
- Cannot easily detect logical contradictions
- Limits formal inference capabilities
- Requires LLM interpretation for every logical operation

## Proposed Solution

Implement a pipeline: **Sentence → HOPL Expression → Graph Structure**

### Example Transformation

```
Natural Language:
"Python 3.12 improved async performance significantly"

↓ Parse to HOPL ↓

∃x,y,z [Python(x) ∧ Version(x,3.12) ∧ Feature(y,async) ∧
       Improved(x,y,z) ∧ Significance(z,high)]

↓ Convert to Graph ↓

Nodes:
- x (type: Language, label: "Python")
- v1 (type: Version, label: "3.12")
- y (type: Feature, label: "async")
- z (type: Metric, label: "performance")
- sig (type: Degree, label: "high")

Edges:
- x --[HasVersion]--> v1
- x --[Improved]--> y
- Improved --[affects]--> z
- z --[HasDegree]--> sig
```

## Current System Integration Points

### Existing Infrastructure

1. **KnowledgeGraphManager** (`services/knowledge_graph.py`)
   - NetworkX MultiDiGraph backend
   - Typed nodes and edges with metadata
   - Graph proximity and claim support scoring

2. **PLN Inference** (`services/pln_inference.py`)
   - Probabilistic Logic Networks with truth values
   - Deduction, induction, abduction rules
   - Strength + confidence calculations

3. **NLP Pipeline** (`services/spacy_nlp.py`)
   - Entity extraction
   - Dependency parsing
   - Semantic similarity

### What's Missing

- **Logical expression parser** (sentence → HOPL)
- **Logic-to-graph mapper** (HOPL → nodes/edges)
- **Graph-based unification** for logical inference
- **Contradiction detection** via graph patterns
- **Compositional query interface**

## Implementation Approaches

### Option A: Lightweight (SVO Triples)

**Complexity**: Low  
**Coverage**: ~80% of factual statements  
**Timeline**: 2-3 days

**Components**:

- `LogicalTripleExtractor` using spaCy dependency parsing
- Extract Subject-Verb-Object patterns
- Map to simple predicate logic: `Predicate(Subject, Object)`
- Store as typed graph edges

**Example**:

```python
sentence = "Python improved async performance"
triple = extract_svo(sentence)
# → ("Python", "improved", "async performance")

# Graph representation:
add_node("python_lang", NODE_LANGUAGE, label="Python")
add_node("async_perf", NODE_FEATURE, label="async performance")
link_entities("python_lang", "async_perf", EDGE_IMPROVED)
```

**Pros**:

- Quick to implement
- Handles most factual claims
- Integrates directly with current graph structure

**Cons**:

- Cannot handle complex logic (quantifiers, nested clauses)
- Loses nuance in complex sentences
- No support for negation or conditional logic

### Option B: Full HOPL (Lambda Calculus)

**Complexity**: High  
**Coverage**: ~95% of logical statements  
**Timeline**: 2-3 weeks

**Components**:

- Integrate formal logic parser (NLTK logic, or custom)
- Lambda calculus representations for complex sentences
- Bi-directional mapping: logic ↔ graph
- Graph-based unification algorithm

**Example**:

```python
sentence = "All Python versions after 3.5 support async"
logic = parse_to_hopl(sentence)
# → ∀x,y [Python(x) ∧ Version(x,y) ∧ GreaterThan(y,3.5) → Supports(x,async)]

# Graph representation:
# Nodes: x (quantified), y (quantified), "3.5", "async"
# Edges: x --[HasVersion]--> y
#        y --[GreaterThan]--> "3.5"  (with metadata: {"implies": True})
#        x --[Supports]--> "async"   (with metadata: {"conditional": True})
# Metadata: {"quantifier": "universal", "variables": ["x", "y"]}
```

**Pros**:

- Handles complex logical structure
- Enables formal theorem proving
- Can detect contradictions automatically
- Supports full logical inference

**Cons**:

- Complex to implement and maintain
- Higher computational cost
- May be overkill for current use cases

### Option C: Hybrid (Staged Approach)

**Recommended**: Start with Option A, extend to Option B as needed

1. **Phase 1**: SVO triple extraction (weeks 1-2)
2. **Phase 2**: Add quantifiers and negation (weeks 3-4)
3. **Phase 3**: Full HOPL with lambda calculus (weeks 5-8)

## Use Cases

### 1. Enhanced Fact Retrieval

**Current**: Keyword matching + BM25  
**Enhanced**: Logical query → subgraph pattern matching

```python
query = "What features did Python improve?"
# Current: searches for keywords "python", "improve", "features"
# Enhanced: query_pattern = "?x Improved ?y WHERE Python(?x) AND Feature(?y)"
#           → returns structured results with logical provenance
```

### 2. Contradiction Detection

**Current**: Manual review or LLM-based detection  
**Enhanced**: Automatic graph pattern detection

```python
# Detect: "Python is fast" ∧ "Python is slow"
find_contradictions(graph)
# → [("claim:123", "claim:456", "opposing_predicates: [fast, slow]")]
```

### 3. Multi-Step Reasoning

**Current**: Single-hop retrieval  
**Enhanced**: Chain logical inferences

```python
# Given: "Python 3.12 has async" ∧ "async improves I/O performance"
# Infer: "Python 3.12 improves I/O performance"

chain = find_reasoning_chain(
    start="Python 3.12",
    end="I/O performance",
    max_hops=3
)
# → Returns logical derivation with PLN truth values
```

### 4. Structured Prompt Generation

**Current**: Template-based prompts  
**Enhanced**: Generate prompts from logical structure

```python
# For content creation:
relevant_facts = query_logical_graph(
    pattern="Improved(?x, ?y) WHERE Python(?x)",
    confidence_threshold=0.8
)
prompt = generate_from_logic(relevant_facts)
# → "Given that Python 3.12 improved async (confidence: 0.85) and
#     async affects I/O performance (confidence: 0.90), write about..."
```

## Technical Design

### Data Structures

```python
# LogicalExpression (new)
class LogicalExpression:
    """Represents a parsed logical formula."""
    predicates: list[Predicate]
    variables: list[Variable]
    quantifiers: dict[str, str]  # {variable: "exists"|"forall"}
    operators: list[LogicalOperator]  # AND, OR, NOT, IMPLIES

# Predicate (new)
class Predicate:
    name: str
    arguments: list[Term]
    truth_value: PLNTruthValue

# LogicalGraphNode (extends current node metadata)
{
    "id": "node123",
    "type": "Claim",
    "label": "Python improved async",
    "metadata": {
        "source": "article",
        "confidence": "high",
        "logical_structure": {  # NEW
            "predicates": [
                {"name": "Improved", "args": ["python", "async"]},
                {"name": "Python", "args": ["python"]},
                {"name": "Feature", "args": ["async"]}
            ],
            "quantifiers": {},
            "operators": ["AND"]
        }
    }
}
```

### API Design

```python
# New module: services/logical_graph.py

class LogicalGraphManager(KnowledgeGraphManager):
    """Extends KnowledgeGraphManager with logical reasoning."""

    def parse_sentence_to_logic(
        self,
        sentence: str
    ) -> LogicalExpression:
        """Convert natural language to logical expression."""
        pass

    def add_logical_fact(
        self,
        sentence: str,
        metadata: dict
    ) -> str:
        """Parse sentence, create nodes/edges for logical structure."""
        pass

    def query_logical_pattern(
        self,
        pattern: str
    ) -> list[dict]:
        """Query graph using logical pattern matching."""
        # pattern: "Improved(?x, ?y) WHERE Python(?x)"
        pass

    def find_contradictions(self) -> list[tuple[str, str, str]]:
        """Detect logical contradictions in graph."""
        pass

    def derive_inference(
        self,
        premises: list[str],
        inference_type: str
    ) -> PLNTruthValue:
        """Apply PLN inference rules over logical graph."""
        pass

    def explain_derivation(
        self,
        conclusion_id: str
    ) -> list[dict]:
        """Return logical derivation path to conclusion."""
        pass
```

### Integration with Existing Systems

```python
# In services/avatar_intelligence/_extraction.py
# Enhance extract_knowledge to include logical structure

def extract_knowledge(content: str) -> ExtractedKnowledge:
    facts = extract_facts(content)

    # NEW: Add logical parsing
    logical_facts = []
    for fact in facts:
        logic_expr = parse_sentence_to_logic(fact.statement)
        fact.logical_structure = logic_expr
        logical_facts.append(fact)

    return ExtractedKnowledge(facts=logical_facts)

# In services/hybrid_retriever.py
# Enhance find_facts with logical query

def find_facts(query: str, use_logical: bool = True) -> list[dict]:
    # Existing BM25 retrieval
    bm25_results = bm25_retrieve(query)

    if use_logical:
        # NEW: Parse query to logical pattern
        query_logic = parse_query_to_pattern(query)
        logical_results = logical_graph.query_logical_pattern(query_logic)

        # Combine results
        results = merge_and_rerank(bm25_results, logical_results)
    else:
        results = bm25_results

    return results
```

## Implementation Roadmap

### Phase 1: Foundation (Week 1-2)

- [ ] Create `services/logical_graph.py` module
- [ ] Implement basic SVO triple extraction using spaCy
- [ ] Add `logical_structure` field to node metadata schema
- [ ] Write unit tests for triple extraction
- [ ] Document logical graph schema

### Phase 2: Graph Integration (Week 3-4)

- [ ] Implement `add_logical_fact()` method
- [ ] Create mapping from predicates to graph edges
- [ ] Add logical metadata to existing facts in knowledge graph
- [ ] Implement basic pattern matching query
- [ ] Write integration tests

### Phase 3: Inference (Week 5-6)

- [ ] Implement `derive_inference()` using PLN rules
- [ ] Add multi-hop reasoning over logical graph
- [ ] Create `explain_derivation()` for provenance tracking
- [ ] Integrate with `HybridRetriever`
- [ ] Add logical grounding to content generation

### Phase 4: Advanced Logic (Week 7-8)

- [ ] Add quantifier support (∃, ∀)
- [ ] Implement negation and conditional logic
- [ ] Add contradiction detection
- [ ] Create visualization for logical derivations
- [ ] Performance optimization for large graphs

### Phase 5: Production (Week 9-10)

- [ ] Add caching for parsed logical expressions
- [ ] Create CLI commands for logical queries
- [ ] Add logging and monitoring
- [ ] Write comprehensive documentation
- [ ] Create example use cases in README

## Success Metrics

1. **Coverage**: % of extracted facts with valid logical structure (target: 80%+)
2. **Precision**: Accuracy of logical parsing (target: 90%+ for SVO triples)
3. **Inference Quality**: PLN confidence in derived facts (target: >0.7 for 1-hop)
4. **Performance**: Query time for logical pattern matching (target: <100ms)
5. **Contradiction Detection**: False positive rate (target: <5%)

## Dependencies

### Required Packages

```bash
pip install nltk>=3.8  # For logic parsing (Option B)
# spaCy already installed
# networkx already installed
```

### Optional Enhancements

- **rdflib**: For RDF/OWL export compatibility
- **owlready2**: For ontology-based reasoning
- **prolog**: For advanced logical inference

## Related Work

- **OpenCog Hyperon**: AtomSpace + MeTTa for logical knowledge graphs
- **Stanford CoreNLP**: Dependency parsing to logical forms
- **AllenNLP**: Semantic role labeling for predicate extraction
- **NLTK Logic**: Lambda calculus and first-order logic

## Open Questions

1. **Storage**: Should we persist logical expressions in JSON or use a dedicated format (e.g., N-Triples)?
2. **Scope**: Which logical operators are essential vs. nice-to-have?
3. **Ambiguity**: How to handle sentences with multiple valid logical interpretations?
4. **Performance**: At what graph size do we need to consider graph databases (Neo4j)?
5. **UI**: Should we create a visualization tool for logical derivations?

## Next Steps

**Decision needed**: Which implementation approach?

- Option A (SVO triples): Fast, practical, limited expressiveness
- Option B (Full HOPL): Powerful, complex, longer timeline
- Option C (Hybrid): Staged rollout, balanced approach

**Recommendation**: Start with Option A (SVO triples) to validate the approach, then extend based on real-world use cases.
