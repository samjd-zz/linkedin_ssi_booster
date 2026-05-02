"""All dataclass models for the avatar_intelligence package."""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Persona graph nodes
# ---------------------------------------------------------------------------


@dataclass
class PersonNode:
    name: str
    title: str
    location: str
    links: list[str] = field(default_factory=list)


@dataclass
class ProjectNode:
    id: str
    name: str
    company_id: str
    years: str
    details: str
    skills: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)


@dataclass
class CompanyNode:
    id: str
    name: str
    aliases: list[str] = field(default_factory=list)


@dataclass
class SkillNode:
    id: str
    name: str
    aliases: list[str] = field(default_factory=list)
    scope: str = "domain"  # domain | project_specific


@dataclass
class ClaimNode:
    id: str
    text: str
    project_ids: list[str] = field(default_factory=list)
    confidence_hint: str = "medium"


# ---------------------------------------------------------------------------
# Domain knowledge
# ---------------------------------------------------------------------------


@dataclass
class DomainNode:
    """A domain area (e.g., 'AI & Machine Learning', 'Software Engineering')."""
    id: str
    name: str
    description: str


@dataclass
class DomainFact:
    """A general domain-level truth not tied to a specific project."""
    id: str
    domain_id: str
    statement: str
    tags: list[str] = field(default_factory=list)
    confidence: str = "medium"
    scope: str = "general"


@dataclass
class DomainRelationship:
    """Relationship between domain facts."""
    id: str
    from_fact_id: str
    to_fact_id: str
    relation_type: str
    description: str = ""


@dataclass
class DomainKnowledge:
    """Domain knowledge graph containing general professional expertise."""
    schema_version: str
    domains: list[DomainNode]
    facts: list[DomainFact]
    relationships: list[DomainRelationship]


# ---------------------------------------------------------------------------
# Extracted knowledge
# ---------------------------------------------------------------------------


@dataclass
class ExtractedFact:
    """A fact extracted by the NLP pipeline from an external article or feed.

    Fields:
    - id:                SHA-256[:12] of source_url + statement (dedup key).
    - statement:         The extracted factual statement.
    - source_url:        URL of the originating article or feed item.
    - source_title:      Title of the originating article or feed item.
    - extracted_at:      ISO-8601 UTC timestamp of extraction.
    - entities:          Named entities detected by spaCy (PERSON, ORG, etc.).
    - tags:              Keyword tags derived from themes/entities.
    - confidence:        'high' | 'medium' | 'low'.
    - extraction_method: Which pipeline produced this fact (e.g. 'spacy_nlp').
    """

    id: str
    statement: str
    source_url: str
    source_title: str
    extracted_at: str
    entities: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    confidence: str = "medium"
    extraction_method: str = "spacy_nlp"


@dataclass
class ExtractedKnowledgeGraph:
    """Container for all NLP-extracted facts, persisted to extracted_knowledge.json."""

    schema_version: str
    facts: list[ExtractedFact]


# ---------------------------------------------------------------------------
# Persona graph + avatar state
# ---------------------------------------------------------------------------


@dataclass
class PersonaGraph:
    schema_version: str
    person: PersonNode
    projects: list[ProjectNode]
    companies: list[CompanyNode]
    skills: list[SkillNode]
    claims: list[ClaimNode]


@dataclass
class NarrativeMemory:
    recent_themes: list[str]
    recent_claims: list[str]
    open_narrative_arcs: list[str]
    last_updated: str | None


@dataclass
class AvatarState:
    persona_graph: PersonaGraph | None
    narrative_memory: NarrativeMemory | None
    domain_knowledge: DomainKnowledge | None
    extracted_knowledge: "ExtractedKnowledgeGraph | None"
    is_loaded: bool
    load_errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Evidence facts (normalized from graph nodes)
# ---------------------------------------------------------------------------


@dataclass
class EvidenceFact:
    """A normalized fact from the persona graph with a stable evidence ID."""

    evidence_id: str
    project: str
    company: str
    years: str
    details: str
    skills: list[str]
    source_project_id: str


@dataclass
class DomainEvidenceFact:
    """A normalized fact from the domain knowledge graph with a stable evidence ID."""

    evidence_id: str
    domain: str
    statement: str
    tags: list[str]
    confidence: str
    source_fact_id: str


@dataclass
class ExtractedEvidenceFact:
    """A normalized fact from the extracted knowledge graph with a stable evidence ID."""

    evidence_id: str
    statement: str
    source_url: str
    source_title: str
    tags: list[str]
    entities: list[str]
    confidence: str
    source_fact_id: str


# ---------------------------------------------------------------------------
# Learning / moderation
# ---------------------------------------------------------------------------


@dataclass
class ModerationEvent:
    """One interactive truth-gate decision captured in the learning log.

    Fields:
    - timestamp:     ISO-8601 UTC string.
    - channel:       linkedin | x | bluesky | threads | youtube | all.
    - reason_code:   truth-gate reason string (e.g. unsupported_numeric).
    - decision:      'kept' (user overrode removal) or 'removed'.
    - sentence_hash: SHA-256[:16] of the flagged sentence (privacy-preserving).
    - article_ref:   URL or title of the source article.
    - project_refs:  project IDs or names referenced in the sentence.
    - run_id:        UUID identifying the current tool run.
    """

    timestamp: str
    channel: str
    reason_code: str
    decision: str          # 'kept' | 'removed'
    sentence_hash: str
    article_ref: str
    project_refs: list[str]
    run_id: str


@dataclass
class ExplainOutput:
    """Explain-mode summary of evidence used and confidence for one generation."""

    evidence_ids: list[str]
    evidence_summaries: list[str]   # one human-readable line per fact (persona + domain)
    article_ref: str
    channel: str
    ssi_component: str
    # Truth-gate internals — populated when gate_meta is passed to build_explain_output
    dot_per_sentence_scores: list[float] = field(default_factory=list)
    spacy_sim_scores: dict[str, float] = field(default_factory=dict)
    # Extracted knowledge facts used as evidence (NLP-extracted from past articles)
    extracted_summaries: list[str] = field(default_factory=list)
    # Article used as external evidence — "title | url" or empty
    article_evidence: str = ""


@dataclass
class LearningRecommendation:
    category: str       # 'domain_term' | 'retrieval_expansion' | 'prompt_length'
    suggestion: str
    confidence: str     # 'high' | 'medium' | 'low'
    evidence_count: int


@dataclass
class LearningReport:
    total_events: int
    kept_count: int
    removed_count: int
    top_reason_codes: list[tuple[str, int]]       # (reason_code, count), sorted desc
    kept_vs_removed: list[tuple[str, int, int]]   # (reason_code, kept, removed)
    recommendations: list[LearningRecommendation]


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------


@dataclass
class ConfidenceSignals:
    """Normalized input signals for confidence scoring (all values 0.0–1.0 unless noted)."""

    truth_gate_removed_count: int      # raw count of sentences removed by truth gate
    truth_gate_reason_severity: float  # max severity of removal reason codes (0–1)
    grounding_coverage_ratio: float    # evidence facts used / max available (0–1)
    unsupported_claim_pressure: float  # removed / total_sentences ratio (0–1)
    channel_length_pressure: float     # post_length / channel_budget, capped at 1.0
    narrative_repetition_score: float  # reserved for Phase 1D; always 0.0 until then


@dataclass
class ConfidenceResult:
    """Scored confidence output for one generation."""

    score: float                    # 0.0–1.0
    level: str                      # 'high' | 'medium' | 'low'
    signals: ConfidenceSignals
    dominant_signal: str | None     # name of the signal with largest negative contribution


@dataclass
class ConfidenceDecision:
    """Output of decide_publish_mode — publish route + human-readable reason."""

    route: str              # 'post' | 'idea' | 'block'
    reason: str
    policy: str
    confidence_level: str   # mirrors ConfidenceResult.level


@dataclass
class ConfidenceDecisionEvent:
    """One confidence-policy decision captured in the learning log (T3.6)."""

    timestamp: str
    channel: str
    route: str
    policy: str
    confidence_score: float
    confidence_level: str
    dominant_signal: str | None
    reason: str
    article_ref: str
    run_id: str
