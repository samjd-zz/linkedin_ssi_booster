"""Avatar Intelligence package — public re-exports.

This module re-exports every name that external code and tests import from
``services.avatar_intelligence``, preserving full backward-compatibility
after the split from the original monolithic module.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
from services.avatar_intelligence._models import (
    AvatarState,
    ClaimNode,
    CompanyNode,
    ConfidenceDecision,
    ConfidenceDecisionEvent,
    ConfidenceResult,
    ConfidenceSignals,
    DomainEvidenceFact,
    DomainFact,
    DomainKnowledge,
    DomainNode,
    DomainRelationship,
    EvidenceFact,
    ExplainOutput,
    ExternalEvidenceFact,
    ExtractedEvidenceFact,
    ExtractedFact,
    ExtractedKnowledgeGraph,
    LearningRecommendation,
    LearningReport,
    ModerationEvent,
    NarrativeMemory,
    PersonaGraph,
    PersonNode,
    ProjectNode,
    SkillNode,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
from services.avatar_intelligence._paths import (
    _DATA_DIR,
    DOMAIN_KNOWLEDGE_PATH,
    EXTRACTED_KNOWLEDGE_PATH,
    LEARNING_LOG_PATH,
    NARRATIVE_MEMORY_PATH,
    PERSONA_GRAPH_PATH,
)

# ---------------------------------------------------------------------------
# Loaders (including private helpers needed by tests)
# ---------------------------------------------------------------------------
from services.avatar_intelligence._loaders import (
    _load_domain_knowledge,
    _load_extracted_knowledge,
    _load_narrative_memory,
    _load_persona_graph,
    _validate_domain_knowledge,
    _validate_extracted_knowledge,
    _validate_narrative_memory,
    _validate_persona_graph,
)
from services.avatar_intelligence._loaders import load_avatar_state as _load_avatar_state_impl


def load_avatar_state() -> "AvatarState":
    """Load persona graph, narrative memory, and domain knowledge from disk.

    Path constants are resolved from this module so tests can monkeypatch them.
    """
    import services.avatar_intelligence as _pkg
    return _load_avatar_state_impl(
        persona_graph_path=getattr(_pkg, "PERSONA_GRAPH_PATH", PERSONA_GRAPH_PATH),
        narrative_memory_path=getattr(_pkg, "NARRATIVE_MEMORY_PATH", NARRATIVE_MEMORY_PATH),
        domain_knowledge_path=getattr(_pkg, "DOMAIN_KNOWLEDGE_PATH", DOMAIN_KNOWLEDGE_PATH),
        extracted_knowledge_path=getattr(_pkg, "EXTRACTED_KNOWLEDGE_PATH", EXTRACTED_KNOWLEDGE_PATH),
    )

# ---------------------------------------------------------------------------
# Normalizers (including private helpers needed by tests)
# ---------------------------------------------------------------------------
from services.avatar_intelligence._normalizers import (
    _make_evidence_id,
    domain_facts_to_project_facts,
    evidence_facts_to_project_facts,
    normalize_domain_facts,
    normalize_evidence_facts,
    normalize_extracted_facts,
)

# ---------------------------------------------------------------------------
# Retrieval (including private helpers needed by tests)
# ---------------------------------------------------------------------------
from services.avatar_intelligence._retrieval import (
    _BM25_AVAILABLE,
    _domain_fact_tokens,
    _fact_tokens,
    _get_evidence_split,
    retrieve_domain_evidence,
    retrieve_evidence,
)

# ---------------------------------------------------------------------------
# Grounding
# ---------------------------------------------------------------------------
from services.avatar_intelligence._grounding import (
    build_external_grounding_context,
    build_domain_grounding_context,
    build_extracted_grounding_context,
    build_grounding_context,
    get_grounding_context_for_query,
)

# ---------------------------------------------------------------------------
# Learning (including private helpers needed by tests)
# ---------------------------------------------------------------------------
from services.avatar_intelligence._learning import (
    _HEURISTIC_MIN_COUNT,
    _RUN_ID,
    _apply_heuristics,
    _load_learning_events,
    build_explain_output,
    build_learning_report,
    format_explain_output,
    format_learning_report,
    record_moderation_event,
)

# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------
from services.avatar_intelligence._confidence import (
    decide_publish_mode,
    extract_confidence_signals,
    record_confidence_decision,
    score_confidence,
)

# ---------------------------------------------------------------------------
# Narrative continuity
# ---------------------------------------------------------------------------
from services.avatar_intelligence._narrative import (
    _CLAIM_PATTERNS,
    _THEME_STOPWORDS,
    build_continuity_context,
    compute_repetition_score,
    extract_narrative_updates,
    save_narrative_memory,
    update_narrative_memory,
)

# ---------------------------------------------------------------------------
# Extraction / continual learning (including private helpers needed by tests)
# ---------------------------------------------------------------------------
from services.avatar_intelligence._extraction import (
    _extracted_fact_tokens,
    _make_extracted_evidence_id,
    _make_extracted_fact_id,
    extract_and_append_knowledge,
    save_extracted_knowledge,
)

__all__ = [
    # Models
    "AvatarState",
    "ClaimNode",
    "CompanyNode",
    "ConfidenceDecision",
    "ConfidenceDecisionEvent",
    "ConfidenceResult",
    "ConfidenceSignals",
    "DomainEvidenceFact",
    "DomainFact",
    "DomainKnowledge",
    "DomainNode",
    "DomainRelationship",
    "EvidenceFact",
    "ExplainOutput",
    "ExternalEvidenceFact",
    "ExtractedEvidenceFact",
    "ExtractedFact",
    "ExtractedKnowledgeGraph",
    "LearningRecommendation",
    "LearningReport",
    "ModerationEvent",
    "NarrativeMemory",
    "PersonaGraph",
    "PersonNode",
    "ProjectNode",
    "SkillNode",
    # Paths
    "_DATA_DIR",
    "DOMAIN_KNOWLEDGE_PATH",
    "EXTRACTED_KNOWLEDGE_PATH",
    "LEARNING_LOG_PATH",
    "NARRATIVE_MEMORY_PATH",
    "PERSONA_GRAPH_PATH",
    # Loaders
    "_load_domain_knowledge",
    "_load_extracted_knowledge",
    "_load_narrative_memory",
    "_load_persona_graph",
    "_validate_domain_knowledge",
    "_validate_extracted_knowledge",
    "_validate_narrative_memory",
    "_validate_persona_graph",
    "load_avatar_state",
    # Normalizers
    "_make_evidence_id",
    "domain_facts_to_project_facts",
    "evidence_facts_to_project_facts",
    "normalize_domain_facts",
    "normalize_evidence_facts",
    "normalize_extracted_facts",
    # Retrieval
    "_BM25_AVAILABLE",
    "_domain_fact_tokens",
    "_fact_tokens",
    "_get_evidence_split",
    "retrieve_domain_evidence",
    "retrieve_evidence",
    # Grounding
    "build_domain_grounding_context",
    "build_external_grounding_context",
    "build_extracted_grounding_context",
    "build_grounding_context",
    "get_grounding_context_for_query",
    # Learning
    "_HEURISTIC_MIN_COUNT",
    "_RUN_ID",
    "_apply_heuristics",
    "_load_learning_events",
    "build_explain_output",
    "build_learning_report",
    "format_explain_output",
    "format_learning_report",
    "record_moderation_event",
    # Confidence
    "decide_publish_mode",
    "extract_confidence_signals",
    "record_confidence_decision",
    "score_confidence",
    # Narrative
    "_CLAIM_PATTERNS",
    "_THEME_STOPWORDS",
    "build_continuity_context",
    "compute_repetition_score",
    "extract_narrative_updates",
    "save_narrative_memory",
    "update_narrative_memory",
    # Extraction
    "_extracted_fact_tokens",
    "_make_extracted_evidence_id",
    "_make_extracted_fact_id",
    "extract_and_append_knowledge",
    "save_extracted_knowledge",
]
