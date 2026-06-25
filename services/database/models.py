"""SQLAlchemy ORM models for LinkedIn SSI Booster database.

These models map to the PostgreSQL schema defined in scripts/init-db.sql.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    TIMESTAMP,
    Text,
    JSON,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import TypeDecorator

Base = declarative_base()


# Custom JSON type that uses JSONB for PostgreSQL and JSON for other databases
class JSONType(TypeDecorator):
    """Platform-independent JSON type.
    
    Uses JSONB for PostgreSQL (optimal performance) and JSON for others (SQLite, etc.)
    """
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(JSONB())
        else:
            return dialect.type_descriptor(JSON())


# ============================================================================
# PERSONA GRAPH & AVATAR STATE
# ============================================================================


class PersonaGraph(Base):
    """Root persona graph record."""

    __tablename__ = "persona_graph"

    id = Column(Integer, primary_key=True)
    schema_version = Column(String(10), nullable=False)
    person = Column(JSONType, nullable=False)
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())

    # Relationships
    projects = relationship("Project", back_populates="persona_graph", cascade="all, delete-orphan")
    companies = relationship("Company", back_populates="persona_graph", cascade="all, delete-orphan")
    skills = relationship("Skill", back_populates="persona_graph", cascade="all, delete-orphan")
    claims = relationship("Claim", back_populates="persona_graph", cascade="all, delete-orphan")


class Project(Base):
    """Project node from persona graph."""

    __tablename__ = "projects"

    id = Column(String(255), primary_key=True)
    persona_graph_id = Column(Integer, ForeignKey("persona_graph.id", ondelete="CASCADE"))
    name = Column(String(500), nullable=False)
    company_id = Column(String(255))  # Made nullable for now
    years = Column(String(50))
    url = Column(String(1000))
    details = Column(Text)
    skills = Column(JSONType, default=list)
    aliases = Column(JSONType, default=list)
    created_at = Column(TIMESTAMP, default=func.now())

    # Relationships
    persona_graph = relationship("PersonaGraph", back_populates="projects")


class Company(Base):
    """Company node from persona graph."""

    __tablename__ = "companies"

    id = Column(String(255), primary_key=True)
    persona_graph_id = Column(Integer, ForeignKey("persona_graph.id", ondelete="CASCADE"))
    name = Column(String(500), nullable=False)
    aliases = Column(JSONType, default=list)
    created_at = Column(TIMESTAMP, default=func.now())

    # Relationships
    persona_graph = relationship("PersonaGraph", back_populates="companies")


class Skill(Base):
    """Skill node from persona graph."""

    __tablename__ = "skills"

    id = Column(String(255), primary_key=True)
    persona_graph_id = Column(Integer, ForeignKey("persona_graph.id", ondelete="CASCADE"))
    name = Column(String(500), nullable=False)
    aliases = Column(JSONType, default=list)
    scope = Column(String(50), default="domain")
    created_at = Column(TIMESTAMP, default=func.now())

    # Relationships
    persona_graph = relationship("PersonaGraph", back_populates="skills")


class Claim(Base):
    """Claim node from persona graph."""

    __tablename__ = "claims"

    id = Column(String(255), primary_key=True)
    persona_graph_id = Column(Integer, ForeignKey("persona_graph.id", ondelete="CASCADE"))
    text = Column(Text, nullable=False)
    project_ids = Column(JSONType, default=list)
    links = Column(JSONType, default=list)
    confidence_hint = Column(String(50), default="medium")
    created_at = Column(TIMESTAMP, default=func.now())

    # Relationships
    persona_graph = relationship("PersonaGraph", back_populates="claims")


# ============================================================================
# DOMAIN KNOWLEDGE
# ============================================================================


class Domain(Base):
    """Domain area (e.g., 'AI & Machine Learning')."""

    __tablename__ = "domains"

    id = Column(String(255), primary_key=True)
    name = Column(String(500), nullable=False)
    description = Column(Text)
    created_at = Column(TIMESTAMP, default=func.now())

    # Relationships
    facts = relationship("DomainFact", back_populates="domain", cascade="all, delete-orphan")


class DomainFact(Base):
    """Domain-level fact not tied to a specific project."""

    __tablename__ = "domain_facts"

    id = Column(String(255), primary_key=True)
    domain_id = Column(String(255), ForeignKey("domains.id", ondelete="CASCADE"))
    statement = Column(Text, nullable=False)
    tags = Column(JSONType, default=list)
    confidence = Column(String(50), default="medium")
    scope = Column(String(100), default="general")
    created_at = Column(TIMESTAMP, default=func.now())

    # Relationships
    domain = relationship("Domain", back_populates="facts")
    from_relationships = relationship(
        "DomainRelationship",
        foreign_keys="DomainRelationship.from_fact_id",
        back_populates="from_fact",
        cascade="all, delete-orphan",
    )
    to_relationships = relationship(
        "DomainRelationship",
        foreign_keys="DomainRelationship.to_fact_id",
        back_populates="to_fact",
        cascade="all, delete-orphan",
    )


class DomainRelationship(Base):
    """Relationship between domain facts."""

    __tablename__ = "domain_relationships"

    id = Column(String(255), primary_key=True)
    from_fact_id = Column(String(255), ForeignKey("domain_facts.id", ondelete="CASCADE"))
    to_fact_id = Column(String(255), ForeignKey("domain_facts.id", ondelete="CASCADE"))
    relation_type = Column(String(100), nullable=False)
    description = Column(Text)
    created_at = Column(TIMESTAMP, default=func.now())

    # Relationships
    from_fact = relationship("DomainFact", foreign_keys=[from_fact_id], back_populates="from_relationships")
    to_fact = relationship("DomainFact", foreign_keys=[to_fact_id], back_populates="to_relationships")


# ============================================================================
# EXTRACTED KNOWLEDGE (NLP Pipeline)
# ============================================================================


class ExtractedFact(Base):
    """Fact extracted by NLP pipeline from external article."""

    __tablename__ = "extracted_facts"

    id = Column(String(255), primary_key=True)  # SHA-256[:12] of source_url + statement
    statement = Column(Text, nullable=False)
    source_url = Column(Text, nullable=False)
    source_title = Column(Text)
    extracted_at = Column(TIMESTAMP, nullable=False)
    entities = Column(JSONType, default=list)
    tags = Column(JSONType, default=list)
    confidence = Column(String(50), default="medium")
    extraction_method = Column(String(100), default="spacy_nlp")
    primary_category = Column(String(255))
    primary_ssi_component = Column(String(255))
    created_at = Column(TIMESTAMP, default=func.now())


# ============================================================================
# NARRATIVE MEMORY
# ============================================================================


class NarrativeMemory(Base):
    """Narrative memory state."""

    __tablename__ = "narrative_memory"

    id = Column(Integer, primary_key=True)
    recent_themes = Column(JSONType, default=list)
    recent_claims = Column(JSONType, default=list)
    open_narrative_arcs = Column(JSONType, default=list)
    last_updated = Column(TIMESTAMP)
    created_at = Column(TIMESTAMP, default=func.now())


# ============================================================================
# SELECTION LEARNING
# ============================================================================


class CandidateRecord(Base):
    """Generated post candidate captured at curation time."""

    __tablename__ = "candidate_records"

    candidate_id = Column(String(255), primary_key=True)
    timestamp = Column(TIMESTAMP, nullable=False)
    article_url = Column(Text, nullable=False)
    article_title = Column(Text)
    article_source = Column(String(255))
    ssi_component = Column(String(100))
    channel = Column(String(50))
    text_hash = Column(String(64), nullable=False)
    text_snippet = Column(Text)
    buffer_id = Column(String(255))
    route = Column(String(50))
    selected = Column(Boolean)
    selected_at = Column(TIMESTAMP)
    run_id = Column(String(255), nullable=False)
    themes = Column(JSONType, default=list)
    sentiment = Column(JSONType, default=dict)
    user_feedback = Column(JSONType, default=dict)
    primary_category = Column(String(255))
    primary_ssi_component = Column(String(255))
    category_confidence = Column(Float, default=0.0)
    created_at = Column(TIMESTAMP, default=func.now())

    # Relationships
    published_record = relationship("PublishedRecord", back_populates="candidate", uselist=False)


class PublishedRecord(Base):
    """Confirmed-published post fetched from Buffer (status=SENT)."""

    __tablename__ = "published_records"

    buffer_id = Column(String(255), primary_key=True)
    channel = Column(String(50), nullable=False)
    text_snippet = Column(Text)
    published_at = Column(TIMESTAMP, nullable=False)
    fetched_at = Column(TIMESTAMP, nullable=False)
    candidate_id = Column(String(255), ForeignKey("candidate_records.candidate_id"))
    created_at = Column(TIMESTAMP, default=func.now())

    # Relationships
    candidate = relationship("CandidateRecord", back_populates="published_record")


# ============================================================================
# LEARNING LOGS
# ============================================================================


class ModerationEvent(Base):
    """Truth gate moderation decision captured in learning log."""

    __tablename__ = "moderation_events"

    id = Column(Integer, primary_key=True)
    timestamp = Column(TIMESTAMP, nullable=False)
    channel = Column(String(50), nullable=False)
    reason_code = Column(String(100), nullable=False)
    decision = Column(String(50), nullable=False)  # 'kept' | 'removed'
    sentence_hash = Column(String(64), nullable=False)
    article_ref = Column(Text)
    project_refs = Column(JSONType, default=list)
    run_id = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP, default=func.now())


class ConfidenceDecision(Base):
    """Confidence policy decision captured in learning log."""

    __tablename__ = "confidence_decisions"

    id = Column(Integer, primary_key=True)
    timestamp = Column(TIMESTAMP, nullable=False)
    channel = Column(String(50), nullable=False)
    route = Column(String(50), nullable=False)
    policy = Column(String(100), nullable=False)
    confidence_score = Column(Float, nullable=False)
    confidence_level = Column(String(50), nullable=False)
    dominant_signal = Column(String(100))
    reason = Column(Text)
    article_ref = Column(Text)
    run_id = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP, default=func.now())


# ============================================================================
# TRUTH TRAJECTORIES (Derivative of Truth — Phase 2)
# ============================================================================


class TruthTrajectory(Base):
    """Truth trajectory for a claim over time."""

    __tablename__ = "truth_trajectories"

    id = Column(Integer, primary_key=True)
    claim_hash = Column(String(64), unique=True, nullable=False)
    claim_text = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, default=func.now())

    # Relationships
    points = relationship("TruthTrajectoryPoint", back_populates="trajectory", cascade="all, delete-orphan")


class TruthTrajectoryPoint(Base):
    """Single point in truth trajectory."""

    __tablename__ = "truth_trajectory_points"

    id = Column(Integer, primary_key=True)
    trajectory_id = Column(Integer, ForeignKey("truth_trajectories.id", ondelete="CASCADE"))
    timestamp = Column(TIMESTAMP, nullable=False)
    truth_gradient = Column(Float, CheckConstraint("truth_gradient BETWEEN 0 AND 1"), nullable=False)
    uncertainty = Column(Float, CheckConstraint("uncertainty BETWEEN 0 AND 1"), nullable=False)
    evidence_count = Column(Integer, nullable=False)
    flagged = Column(Boolean, nullable=False)
    created_at = Column(TIMESTAMP, default=func.now())

    # Relationships
    trajectory = relationship("TruthTrajectory", back_populates="points")


# ============================================================================
# GENERATED CONTENT RECORDS (local-first artifact index — DB second)
# ============================================================================


class GeneratedContentRecord(Base):
    """Secondary DB index for generated content artifacts (images + stories).

    Local artifact files remain the canonical source of truth.
    This table is an optional secondary index written only when
    DATABASE_ENABLED=true.  It never replaces or shadows the local files.

    Links back to candidate_records (optional) and carries enough metadata
    to reconstruct the full artifact context from the local filesystem.
    """

    __tablename__ = "generated_content_records"

    id = Column(String(255), primary_key=True)   # request_id from flux_capacitor
    run_id = Column(String(255), nullable=False)
    candidate_id = Column(
        String(255),
        ForeignKey("candidate_records.candidate_id", ondelete="SET NULL"),
        nullable=True,
    )

    # Content classification
    source_mode = Column(String(50), nullable=False)   # schedule | curate | console
    channel = Column(String(50))
    ssi_component = Column(String(100))

    # Source linkage
    source_url = Column(Text)
    source_title = Column(Text)

    # Local artifact paths (canonical store)
    story_path = Column(Text)
    story_metadata_path = Column(Text)
    image_path = Column(Text)
    image_metadata_path = Column(Text)

    # Render outcome
    render_status = Column(String(50), nullable=False)  # rendered | deferred | text_only | failed
    save_status = Column(String(50), nullable=False, default="saved")  # saved | failed | skipped

    # Style / prompt traceability
    style_preset = Column(String(100))
    prompt_text = Column(Text)
    evidence_ids = Column(JSONType, default=list)

    # Timing telemetry
    queue_wait_seconds = Column(Float, default=0.0)
    render_duration_seconds = Column(Float, default=0.0)

    generated_at = Column(TIMESTAMP, nullable=False)
    created_at = Column(TIMESTAMP, default=func.now())

    # Relationship
    candidate = relationship("CandidateRecord", foreign_keys=[candidate_id])


# ============================================================================
# SCHEMA MIGRATIONS
# ============================================================================


class SchemaMigration(Base):
    """Track schema migration versions."""

    __tablename__ = "schema_migrations"

    version = Column(String(50), primary_key=True)
    applied_at = Column(TIMESTAMP, default=func.now())
    description = Column(Text)