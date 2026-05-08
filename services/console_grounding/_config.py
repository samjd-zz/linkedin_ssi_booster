"""Configuration constants and environment-driven config readers for console grounding."""

from __future__ import annotations

import logging as _logging
import os

_logger = _logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default tech keywords used for tag extraction and query constraint detection.
# ---------------------------------------------------------------------------

DEFAULT_TECH_KEYWORDS = {
    # Persona / project stack
    "java", "spring", "spring boot", "spring ai", "spring batch", "jms",
    "python", "fastapi", "scikit-learn", "gymnasium", "stable-baselines3",
    "elasticsearch", "solr", "lucene", "neo4j", "rag", "mcp", "fastmcp",
    "oracle", "weblogic", "jsf", "adf", "vaadin", "hibernate", "tomcat",
    # Domain knowledge terms
    "llm", "bm25", "knn", "k-nearest", "vector search", "embeddings",
    "semantic search", "microservices", "prompt engineering", "retrieval",
    "fine-tuning", "machine learning", "deep learning", "neural network",
    "transformer", "agent", "agentic", "api", "rest", "graphql",
    "docker", "kubernetes", "kafka", "data pipeline", "etl",
    "information retrieval", "ranking", "similarity", "reranking",
}

# Phrases that indicate the user is asking for knowledge / explanation
DOMAIN_KNOWLEDGE_PHRASES: frozenset[str] = frozenset([
    "what is", "what are", "what does", "what do",
    "explain", "how does", "how do", "how is",
    "tell me about", "know about", "what do you know",
    "expertise", "domain knowledge", "define", "describe",
    "can you explain", "teach me", "what's",
])

# Phrases that explicitly request direct artifact routing (deterministic citation)
EXPLICIT_ARTIFACT_PHRASES: frozenset[str] = frozenset([
    "show me extracted knowledge",
    "list extracted knowledge",
    "show extracted knowledge",
    "show me persona",
    "list persona",
    "show persona",
    "show me domain knowledge",
    "list domain knowledge",
    "show domain knowledge",
    "from extracted knowledge",
    "from persona",
    "from domain knowledge",
])

# Phrases that request using learned knowledge as context
LEARNED_KNOWLEDGE_PHRASES: frozenset[str] = frozenset([
    "from your learned knowledge",
    "from your learning",
    "from what you learned",
    "based on what you learned",
    "using your learned knowledge",
    "with your learned knowledge",
])

DEFAULT_TAG_EXPANSIONS: dict[str, set[str]] = {
    "java": {"spring", "jms", "oracle", "weblogic", "solr", "lucene", "elasticsearch"},
}


# ---------------------------------------------------------------------------
# Environment config readers
# ---------------------------------------------------------------------------

def get_truth_gate_bm25_threshold() -> float:
    """Return the minimum BM25 score threshold for truth gate validation.

    Env format:
      TRUTH_GATE_BM25_THRESHOLD=1.0 (float, defaults to 1.0)

    Recommended values:
      - 0.5: Permissive (allows paraphrased claims with weak evidence)
      - 1.0: Balanced (default - good for most use cases)
      - 2.0: Strict (requires strong evidence overlap)
      - 5.0: Very strict (requires very strong evidence match)
    """
    raw = os.getenv("TRUTH_GATE_BM25_THRESHOLD", "").strip()
    if not raw:
        return 1.0
    try:
        threshold = float(raw)
        return max(0.0, min(threshold, 100.0))
    except ValueError:
        _logger.warning(
            "Invalid TRUTH_GATE_BM25_THRESHOLD value: %r, using default 1.0", raw
        )
        return 1.0


def get_truth_gate_spacy_sim_floor() -> float:
    """Return the minimum spaCy cosine similarity floor for numeric/org sentence validation.

    Env format:
      TRUTH_GATE_SPACY_SIM_FLOOR=0.10 (float, defaults to 0.10)

    When a sentence contains a numeric claim, year, dollar amount, or org name,
    and its spaCy cosine similarity to the article text is below this floor (and
    non-zero — zero means vectors unavailable), it is flagged as
    ``low_semantic_similarity``.  Default is very permissive (0.10) to avoid
    false positives; raise to 0.25–0.40 for stricter enforcement.
    """
    raw = os.getenv("TRUTH_GATE_SPACY_SIM_FLOOR", "").strip()
    if not raw:
        return 0.10
    try:
        return max(0.0, min(1.0, float(raw)))
    except ValueError:
        _logger.warning(
            "Invalid TRUTH_GATE_SPACY_SIM_FLOOR value: %r, using default 0.10", raw
        )
        return 0.10


def get_truth_gate_fact_sim_floor() -> float:
    """Return the minimum spaCy cosine similarity floor for sentence vs persona/domain facts.

    Env format:
      TRUTH_GATE_FACT_SIM_FLOOR=0.05 (float, defaults to 0.05)

    For every sentence that passes BM25, the best spaCy cosine similarity across
    all persona/domain facts is computed. If it falls below this floor (and is
    non-zero — zero means vectors unavailable), the sentence is flagged as
    ``low_fact_similarity``. Default is very permissive (0.05) because persona
    facts are short fragments; raise to 0.10–0.20 for stricter enforcement.
    """
    raw = os.getenv("TRUTH_GATE_FACT_SIM_FLOOR", "").strip()
    if not raw:
        return 0.05
    try:
        return max(0.0, min(1.0, float(raw)))
    except ValueError:
        _logger.warning(
            "Invalid TRUTH_GATE_FACT_SIM_FLOOR value: %r, using default 0.05", raw
        )
        return 0.05


def get_whitelisted_phrases() -> set[str]:
    """Return a set of whitelisted phrases (case-insensitive, stripped) from env.

    Env format:
      TRUTH_GATE_WHITELISTED_PHRASES=what's up — sam here,hello world (comma-separated)

    Sentences matching any of these phrases will always be kept by the truth gate.
    """
    raw = os.getenv("TRUTH_GATE_WHITELISTED_PHRASES", "").strip()
    if not raw:
        return set()
    return {_normalize_phrase(part) for part in raw.split(",") if part.strip()}


def _normalize_phrase(phrase: str) -> str:
    """Normalize a phrase for robust comparison: lowercase, strip, remove trailing
    punctuation, normalize dashes, collapse whitespace."""
    import unicodedata  # noqa: F401 — reserved for future NFC normalization
    s = phrase.strip().lower()
    s = s.replace("—", "-").replace("–", "-")
    s = s.rstrip(".!?;,:\")")
    s = " ".join(s.split())
    s = s.strip("\"'")
    return s


def get_console_grounding_keywords() -> set[str]:
    """Return tech keywords used by console grounding from env with defaults."""
    raw = os.getenv("CONSOLE_GROUNDING_TECH_KEYWORDS", "").strip()
    if not raw:
        return set(DEFAULT_TECH_KEYWORDS)
    parsed = {part.strip().lower() for part in raw.split(",") if part.strip()}
    return parsed or set(DEFAULT_TECH_KEYWORDS)


def get_console_grounding_tag_expansions_from_graph(
    domain_knowledge=None,
) -> dict[str, set[str]]:
    """Build tag expansion relationships from the domain knowledge graph.

    Each tag in a fact is expanded to include tags from related facts (via
    relationships).  If *domain_knowledge* is None, attempts to load it from
    avatar_intelligence.
    """
    if domain_knowledge is None:
        try:
            from services.avatar_intelligence import load_avatar_state
            state = load_avatar_state()
            domain_knowledge = state.domain_knowledge
        except Exception:
            domain_knowledge = None
    if not domain_knowledge or not getattr(domain_knowledge, "facts", None):
        return {}

    fact_tags = {f.id: set(map(str.lower, f.tags)) for f in domain_knowledge.facts}
    expansions: dict[str, set[str]] = {}

    for rel in getattr(domain_knowledge, "relationships", []):
        from_tags = fact_tags.get(rel.from_fact_id, set())
        to_tags = fact_tags.get(rel.to_fact_id, set())
        for tag in from_tags:
            if tag not in expansions:
                expansions[tag] = set()
            expansions[tag].update(to_tags)
    return expansions
