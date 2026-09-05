"""Data models for console grounding."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProjectFact:
    project: str
    company: str
    years: str
    details: str
    source: str
    tags: set[str]


@dataclass
class TruthGateMeta:
    """Metadata about what truth_gate evaluated — used for confidence scoring (Phase 1C).

    Extended with Derivative of Truth (DoT) fields:
    - truth_gradient: composite truth gradient score ∈ [0, 1] for the full post
    - dot_uncertainty: aggregate uncertainty penalty from DoT scoring
    - dot_flagged: True if truth_gradient is below the flag threshold
    - dot_uncertainty_sources: list of uncertainty reason codes
    - dot_per_sentence_scores: DoT gradient per kept/checked sentence (Part B)
    - spacy_sim_scores: spaCy similarity scores per sentence vs article (Part C)
    - fact_sim_scores: best spaCy sim per sentence vs persona/domain fact pool (Part E)
    """

    removed_count: int
    total_sentences: int
    reason_codes: list[str] = field(default_factory=list)
    truth_gradient: float = 1.0
    dot_uncertainty: float = 0.0
    dot_flagged: bool = False
    dot_uncertainty_sources: list[str] = field(default_factory=list)
    dot_per_sentence_scores: list[float] = field(default_factory=list)
    spacy_sim_scores: dict[str, float] = field(default_factory=dict)
    fact_sim_scores: dict[str, float] = field(default_factory=dict)


@dataclass
class QueryConstraints:
    require_projects: bool
    require_companies: bool
    require_domain_knowledge: bool
    tech_tags: set[str]
    explicit_artifact_request: bool = False  # User explicitly asks to see artifacts
    list_domain_characters: bool = False  # User asks to list all domain knowledge characters
    list_domain_terms: bool = False  # User asks to list domain terms/concepts with meanings
    use_learned_knowledge: bool = False  # User asks to use "learned knowledge"
    search_learned_knowledge: bool = False  # User asks to search learned knowledge
    has_image_request: bool = False  # User asks for an image / artwork / drawing
    is_japanese_art_request: bool = False  # Request is specifically for Japanese character or art
    is_kanji_teaching_request: bool = False  # User asks Sam to teach Japanese kanji
    art_subject_hint: str = ""  # Extracted subject or character name for image render
    route_mode: str = "llm_with_context"  # "llm_with_context", "deterministic_citation", "learned_context"

    @property
    def requires_grounding(self) -> bool:
        """Legacy property - now only returns True for explicit artifact requests."""
        return self.explicit_artifact_request

    @property
    def requires_context(self) -> bool:
        """Returns True if artifacts should be used as LLM context (default behavior)."""
        return (
            self.require_projects
            or self.require_companies
            or self.require_domain_knowledge
            or bool(self.tech_tags)
        ) and not self.explicit_artifact_request
