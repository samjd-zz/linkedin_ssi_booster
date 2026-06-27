"""
Repository pattern for database access.

Provides clean, reusable data access methods for all database models,
abstracting SQLAlchemy queries from business logic.
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import Session

from services.database.models import (
    PersonaGraph,
    Project,
    Company,
    Skill,
    Claim,
    Domain,
    DomainFact,
    DomainRelationship,
    ExtractedFact,
    NarrativeMemory,
    CandidateRecord,
    PublishedRecord,
    ModerationEvent,
    ConfidenceDecision,
    TruthTrajectory,
    TruthTrajectoryPoint,
    GeneratedContentRecord,
)

logger = logging.getLogger(__name__)


# ============================================================================
# PERSONA GRAPH REPOSITORIES
# ============================================================================


class PersonaGraphRepository:
    """Repository for persona_graph table operations."""

    @staticmethod
    def get_latest(session: Session) -> Optional[PersonaGraph]:
        """Get the most recent persona graph."""
        stmt = select(PersonaGraph).order_by(PersonaGraph.id.desc()).limit(1)
        return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def create(session: Session, graph_data: Dict[str, Any]) -> PersonaGraph:
        """
        Create a new persona graph record.

        Args:
            session: Database session
            graph_data: Dictionary with 'schemaVersion', 'person', etc.

        Returns:
            Created PersonaGraph instance
        """
        persona = PersonaGraph(
            schema_version=graph_data.get("schemaVersion", "1.0"),
            person=graph_data.get("person", {})
        )
        session.add(persona)
        session.flush()
        return persona

    @staticmethod
    def update_graph(session: Session, graph_id: int, graph_data: Dict[str, Any]) -> PersonaGraph:
        """Update an existing persona graph."""
        stmt = (
            update(PersonaGraph)
            .where(PersonaGraph.id == graph_id)
            .values(
                schema_version=graph_data.get("schemaVersion", "1.0"),
                person=graph_data.get("person", {}),
                updated_at=func.now()
            )
            .returning(PersonaGraph)
        )
        result = session.execute(stmt)
        return result.scalar_one()


class ProjectRepository:
    """Repository for projects table."""

    @staticmethod
    def get_by_name(session: Session, name: str) -> Optional[Project]:
        """Get project by name."""
        stmt = select(Project).where(Project.name == name)
        return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def create(
        session: Session,
        persona_id: int,
        name: str,
        company_id: Optional[str] = None,
        description: Optional[str] = None,
        url: Optional[str] = None,
        skills: Optional[List[str]] = None,
        years: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Project:
        """Create a new project."""
        project = Project(
            id=project_id or name,
            persona_graph_id=persona_id,
            name=name,
            company_id=company_id,
            url=url,
            details=description,
            skills=skills or [],
            years=years,
        )
        session.add(project)
        session.flush()
        return project

    @staticmethod
    def list_by_persona(session: Session, persona_id: int) -> List[Project]:
        """List all projects for a persona."""
        stmt = select(Project).where(Project.persona_graph_id == persona_id)
        return list(session.execute(stmt).scalars().all())


class CompanyRepository:
    """Repository for companies table."""

    @staticmethod
    def get_by_name(session: Session, name: str) -> Optional[Company]:
        """Get company by name."""
        stmt = select(Company).where(Company.name == name)
        return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def create(
        session: Session,
        persona_id: int,
        name: str,
        role: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skills: Optional[List[str]] = None,
        aliases: Optional[List[str]] = None,
        company_id: Optional[str] = None,
    ) -> Company:
        """Create a new company record."""
        company = Company(
            id=company_id or name,
            persona_graph_id=persona_id,
            name=name,
            aliases=aliases or [],
        )
        session.add(company)
        session.flush()
        return company


class SkillRepository:
    """Repository for skills table."""

    @staticmethod
    def get_by_name(session: Session, name: str) -> Optional[Skill]:
        """Get skill by name."""
        stmt = select(Skill).where(Skill.name == name)
        return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def create(
        session: Session,
        persona_id: int,
        name: str,
        aliases: Optional[List[str]] = None,
        skill_id: Optional[str] = None,
    ) -> Skill:
        """Create a new skill."""
        skill = Skill(
            id=skill_id or name,
            persona_graph_id=persona_id,
            name=name,
            aliases=aliases or [],
        )
        session.add(skill)
        session.flush()
        return skill

    @staticmethod
    def list_by_persona(session: Session, persona_id: int) -> List[Skill]:
        """List all skills for a persona."""
        stmt = select(Skill).where(Skill.persona_graph_id == persona_id)
        return list(session.execute(stmt).scalars().all())


class ClaimRepository:
    """Repository for claims table."""

    @staticmethod
    def create(
        session: Session,
        persona_id: int,
        claim_text: str,
        tags: Optional[List[str]] = None,
        project_ids: Optional[List[str]] = None,
        links: Optional[List[str]] = None,
        confidence_hint: Optional[str] = None,
        claim_id: Optional[str] = None,
    ) -> Claim:
        """Create a new claim."""
        claim = Claim(
            id=claim_id or claim_text,
            persona_graph_id=persona_id,
            text=claim_text,
            project_ids=project_ids or [],
            links=links or [],
            confidence_hint=confidence_hint or "medium",
        )
        session.add(claim)
        session.flush()
        return claim

    @staticmethod
    def list_by_persona(session: Session, persona_id: int) -> List[Claim]:
        """List all claims for a persona."""
        stmt = select(Claim).where(Claim.persona_graph_id == persona_id)
        return list(session.execute(stmt).scalars().all())


# ============================================================================
# DOMAIN KNOWLEDGE REPOSITORIES
# ============================================================================


class DomainRepository:
    """Repository for domains table."""

    @staticmethod
    def get_by_name(session: Session, name: str) -> Optional[Domain]:
        """Get domain by name."""
        stmt = select(Domain).where(Domain.name == name)
        return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def create(session: Session, name: str, description: str = "", domain_id: Optional[str] = None) -> Domain:
        """Create a new domain."""
        domain = Domain(id=domain_id or name, name=name, description=description)
        session.add(domain)
        session.flush()
        return domain

    @staticmethod
    def list_all(session: Session) -> List[Domain]:
        """List all domains."""
        stmt = select(Domain).order_by(Domain.name)
        return list(session.execute(stmt).scalars().all())


class DomainFactRepository:
    """Repository for domain_facts table."""

    @staticmethod
    def create(
        session: Session,
        domain_id: str,
        fact_text: str,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        fact_id: Optional[str] = None,
    ) -> DomainFact:
        """Create a new domain fact."""
        metadata = metadata or {}
        fact = DomainFact(
            id=fact_id or fact_text,
            domain_id=domain_id,
            statement=fact_text,
            tags=tags or [],
            confidence=metadata.get("confidence", "medium"),
            scope=metadata.get("scope", "general"),
        )
        session.add(fact)
        session.flush()
        return fact

    @staticmethod
    def list_by_domain(session: Session, domain_id: str) -> List[DomainFact]:
        """List all facts for a domain."""
        stmt = select(DomainFact).where(DomainFact.domain_id == domain_id)
        return list(session.execute(stmt).scalars().all())


class DomainRelationshipRepository:
    """Repository for domain_relationships table."""

    @staticmethod
    def create(
        session: Session,
        from_fact_id: str,
        to_fact_id: str,
        relation_type: str,
        description: Optional[str] = None,
        rel_id: Optional[str] = None,
    ) -> DomainRelationship:
        """Create a new domain relationship (triple)."""
        rel = DomainRelationship(
            id=rel_id or f"{from_fact_id}:{to_fact_id}",
            from_fact_id=from_fact_id,
            to_fact_id=to_fact_id,
            relation_type=relation_type,
            description=description,
        )
        session.add(rel)
        session.flush()
        return rel

    @staticmethod
    def list_by_domain(session: Session, domain_id: str) -> List[DomainRelationship]:
        """List all relationships for a domain."""
        # NOTE: This needs to be updated to join through domain_facts
        # For now, return empty list
        return []


# ============================================================================
# EXTRACTED KNOWLEDGE REPOSITORY
# ============================================================================


class ExtractedFactRepository:
    """Repository for extracted_facts table."""

    @staticmethod
    def create(
        session: Session,
        fact_text: str,
        source_url: Optional[str] = None,
        source_title: Optional[str] = None,
        entities: Optional[List[str]] = None,
        themes: Optional[List[str]] = None,
        primary_category: Optional[str] = None,
        primary_ssi_component: Optional[str] = None,
        sentiment: Optional[Dict[str, Any]] = None,
        fact_id: Optional[str] = None,
        extracted_at: Optional[datetime] = None,
        extraction_method: Optional[str] = None,
    ) -> ExtractedFact:
        """Create a new extracted fact."""
        from datetime import datetime, UTC
        sentiment = sentiment or {}
        fact = ExtractedFact(
            id=fact_id or f"{source_url}{fact_text}",
            statement=fact_text,
            source_url=source_url or "",
            source_title=source_title or "",
            extracted_at=extracted_at or datetime.now(UTC),
            entities=entities or [],
            tags=themes or [],
            confidence=sentiment.get("confidence", "medium"),
            extraction_method=extraction_method or sentiment.get("extraction_method", "spacy_nlp"),
            primary_category=primary_category or "",
            primary_ssi_component=primary_ssi_component or "",
        )
        session.add(fact)
        session.flush()
        return fact

    @staticmethod
    def list_recent(session: Session, limit: int = 100) -> List[ExtractedFact]:
        """List most recently extracted facts."""
        stmt = select(ExtractedFact).order_by(ExtractedFact.extracted_at.desc()).limit(limit)
        return list(session.execute(stmt).scalars().all())


# ============================================================================
# NARRATIVE MEMORY REPOSITORY
# ============================================================================


class NarrativeMemoryRepository:
    """Repository for narrative_memory table."""

    @staticmethod
    def get_latest(session: Session) -> Optional[NarrativeMemory]:
        """Get the most recently created narrative memory row."""
        stmt = select(NarrativeMemory).order_by(NarrativeMemory.created_at.desc()).limit(1)
        return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def create(
        session: Session,
        themes: Optional[List[str]] = None,
        claims: Optional[List[str]] = None,
        narrative_arcs: Optional[List[str]] = None,
    ) -> NarrativeMemory:
        """Create a new narrative memory entry."""
        from datetime import datetime, UTC
        
        narrative = NarrativeMemory(
            recent_themes=themes or [],
            recent_claims=claims or [],
            open_narrative_arcs=narrative_arcs or [],
            last_updated=datetime.now(UTC),
        )
        session.add(narrative)
        session.flush()
        return narrative

    @staticmethod
    def list_by_themes(session: Session, themes: List[str]) -> List[NarrativeMemory]:
        """
        List narratives that contain any of the specified themes.
        
        Uses PostgreSQL JSONB containment operator.
        """
        # NOTE: This requires PostgreSQL-specific JSONB operators
        # For simple theme filtering, we can use SQLAlchemy's JSONB support
        stmt = select(NarrativeMemory).order_by(NarrativeMemory.created_at.desc())
        results = session.execute(stmt).scalars().all()
        
        # Filter in Python (for cross-database compatibility)
        # In production, use PostgreSQL JSONB operators for better performance
        return [n for n in results if any(theme in (n.recent_themes or []) for theme in themes)]


# ============================================================================
# SELECTION LEARNING REPOSITORIES
# ============================================================================


class CandidateRecordRepository:
    """Repository for candidate_records table."""

    @staticmethod
    def create(
        session: Session,
        candidate_id: str,
        timestamp: datetime,
        article_url: str,
        article_title: str,
        article_source: str,
        ssi_component: str,
        channel: str,
        text_hash: str,
        text_snippet: str,
        buffer_id: Optional[str],
        route: str,
        run_id: str,
        themes: Optional[List[str]] = None,
        sentiment: Optional[Dict[str, Any]] = None,
    ) -> CandidateRecord:
        """Create a new candidate record from selection_learning data."""
        # Check for existing record to avoid duplicate key violations across runs.
        existing = session.get(CandidateRecord, candidate_id)
        if existing is not None:
            return existing
        candidate = CandidateRecord(
            candidate_id=candidate_id,
            timestamp=timestamp,
            article_url=article_url,
            article_title=article_title,
            article_source=article_source,
            ssi_component=ssi_component,
            channel=channel,
            text_hash=text_hash,
            text_snippet=text_snippet,
            buffer_id=buffer_id,
            route=route,
            run_id=run_id,
            themes=themes or [],
            sentiment=sentiment or {},
        )
        session.add(candidate)
        session.flush()
        return candidate

    @staticmethod
    def update_selected(
        session: Session,
        candidate_id: str,
        selected: bool,
        selected_at: datetime,
    ) -> None:
        """Update selected status and timestamp on a candidate record."""
        stmt = (
            update(CandidateRecord)
            .where(CandidateRecord.candidate_id == candidate_id)
            .values(selected=selected, selected_at=selected_at)
        )
        session.execute(stmt)
        session.flush()

    @staticmethod
    def list_unpublished(session: Session, limit: int = 50) -> List[CandidateRecord]:
        """List candidates that haven't been published yet."""
        from sqlalchemy import and_, not_

        stmt = (
            select(CandidateRecord)
            .where(~CandidateRecord.published_record.has())
            .order_by(CandidateRecord.created_at.desc())
            .limit(limit)
        )
        return list(session.execute(stmt).scalars().all())


class PublishedRecordRepository:
    """Repository for published_records table."""

    @staticmethod
    def create(
        session: Session,
        buffer_id: str,
        channel: str,
        text_snippet: str,
        published_at: datetime,
        fetched_at: datetime,
        candidate_id: Optional[str] = None,
    ) -> PublishedRecord:
        """Create a new published record from selection_learning data."""
        published = PublishedRecord(
            buffer_id=buffer_id,
            channel=channel,
            text_snippet=text_snippet,
            published_at=published_at,
            fetched_at=fetched_at,
            candidate_id=candidate_id,
        )
        session.add(published)
        session.flush()
        return published

    @staticmethod
    def list_recent(session: Session, limit: int = 50) -> List[PublishedRecord]:
        """List most recently published records."""
        stmt = select(PublishedRecord).order_by(PublishedRecord.published_at.desc()).limit(limit)
        return list(session.execute(stmt).scalars().all())


# ============================================================================
# LEARNING LOGS REPOSITORIES
# ============================================================================


class ModerationEventRepository:
    """Repository for moderation_events table."""

    @staticmethod
    def create(
        session: Session,
        timestamp: datetime,
        channel: str,
        reason_code: str,
        decision: str,
        sentence_hash: str,
        article_ref: str,
        project_refs: Optional[List[str]],
        run_id: str,
    ) -> ModerationEvent:
        """Create a new moderation event."""
        event = ModerationEvent(
            timestamp=timestamp,
            channel=channel,
            reason_code=reason_code,
            decision=decision,
            sentence_hash=sentence_hash,
            article_ref=article_ref,
            project_refs=project_refs or [],
            run_id=run_id,
        )
        session.add(event)
        session.flush()
        return event


class ConfidenceDecisionRepository:
    """Repository for confidence_decisions table."""

    @staticmethod
    def create(
        session: Session,
        timestamp: datetime,
        channel: str,
        route: str,
        policy: str,
        confidence_score: float,
        confidence_level: str,
        dominant_signal: Optional[str],
        reason: str,
        article_ref: str,
        run_id: str,
    ) -> ConfidenceDecision:
        """Create a new confidence decision."""
        decision_rec = ConfidenceDecision(
            timestamp=timestamp,
            channel=channel,
            route=route,
            policy=policy,
            confidence_score=confidence_score,
            confidence_level=confidence_level,
            dominant_signal=dominant_signal,
            reason=reason,
            article_ref=article_ref,
            run_id=run_id,
        )
        session.add(decision_rec)
        session.flush()
        return decision_rec


# ============================================================================
# TRUTH TRAJECTORY REPOSITORIES
# ============================================================================


class TruthTrajectoryRepository:
    """Repository for truth_trajectories table."""

    @staticmethod
    def create(
        session: Session,
        claim_hash: str,
        claim_text: str,
    ) -> TruthTrajectory:
        """Create a new truth trajectory."""
        trajectory = TruthTrajectory(
            claim_hash=claim_hash,
            claim_text=claim_text,
        )
        session.add(trajectory)
        session.flush()
        return trajectory

    @staticmethod
    def get_by_id(session: Session, trajectory_id: int) -> Optional[TruthTrajectory]:
        """Get trajectory by ID."""
        stmt = select(TruthTrajectory).where(TruthTrajectory.id == trajectory_id)
        return session.execute(stmt).scalar_one_or_none()


class TruthTrajectoryPointRepository:
    """Repository for truth_trajectory_points table."""

    @staticmethod
    def create(
        session: Session,
        trajectory_id: int,
        timestamp: datetime,
        truth_gradient: float,
        uncertainty: float,
        evidence_count: int,
        flagged: bool,
    ) -> TruthTrajectoryPoint:
        """Create a new trajectory point."""
        point = TruthTrajectoryPoint(
            trajectory_id=trajectory_id,
            timestamp=timestamp,
            truth_gradient=truth_gradient,
            uncertainty=uncertainty,
            evidence_count=evidence_count,
            flagged=flagged,
        )
        session.add(point)
        session.flush()
        return point

    @staticmethod
    def list_by_trajectory(session: Session, trajectory_id: int) -> List[TruthTrajectoryPoint]:
        """List all points for a trajectory, ordered by timestamp."""
        stmt = (
            select(TruthTrajectoryPoint)
            .where(TruthTrajectoryPoint.trajectory_id == trajectory_id)
            .order_by(TruthTrajectoryPoint.timestamp)
        )
        return list(session.execute(stmt).scalars().all())


# ============================================================================
# GENERATED CONTENT RECORDS
# ============================================================================


class GeneratedContentRecordRepository:
    """Repository for generated_content_records table operations.

    Provides optional DB indexing for FLUX art-avatar artifacts.  The local
    filesystem remains the canonical store — this repo is DB-second only.
    """

    @staticmethod
    def upsert(
        session: Session,
        request_id: str,
        run_id: str,
        source_mode: str,
        render_status: str,
        generated_at: datetime,
        *,
        candidate_id: Optional[str] = None,
        channel: Optional[str] = None,
        ssi_component: Optional[str] = None,
        source_url: Optional[str] = None,
        source_title: Optional[str] = None,
        story_path: Optional[str] = None,
        story_metadata_path: Optional[str] = None,
        image_path: Optional[str] = None,
        image_metadata_path: Optional[str] = None,
        save_status: str = "saved",
        style_preset: Optional[str] = None,
        prompt_text: Optional[str] = None,
        evidence_ids: Optional[List[str]] = None,
        queue_wait_seconds: float = 0.0,
        render_duration_seconds: float = 0.0,
    ) -> GeneratedContentRecord:
        """Insert or update a generated content record by request_id."""
        existing = session.execute(
            select(GeneratedContentRecord).where(
                GeneratedContentRecord.id == request_id
            )
        ).scalar_one_or_none()

        if existing is None:
            record = GeneratedContentRecord(
                id=request_id,
                run_id=run_id,
                candidate_id=candidate_id,
                source_mode=source_mode,
                channel=channel,
                ssi_component=ssi_component,
                source_url=source_url,
                source_title=source_title,
                story_path=story_path,
                story_metadata_path=story_metadata_path,
                image_path=image_path,
                image_metadata_path=image_metadata_path,
                render_status=render_status,
                save_status=save_status,
                style_preset=style_preset,
                prompt_text=prompt_text,
                evidence_ids=evidence_ids or [],
                queue_wait_seconds=queue_wait_seconds,
                render_duration_seconds=render_duration_seconds,
                generated_at=generated_at,
            )
            session.add(record)
        else:
            # Update mutable fields in place
            setattr(existing, "render_status", render_status)
            setattr(existing, "save_status", save_status)
            setattr(existing, "story_path", story_path or existing.story_path)
            setattr(existing, "story_metadata_path", story_metadata_path or existing.story_metadata_path)
            setattr(existing, "image_path", image_path or existing.image_path)
            setattr(existing, "image_metadata_path", image_metadata_path or existing.image_metadata_path)
            setattr(existing, "render_duration_seconds", render_duration_seconds)
            record = existing

        session.flush()
        return record

    @staticmethod
    def get_by_request_id(
        session: Session, request_id: str
    ) -> Optional[GeneratedContentRecord]:
        """Fetch a single record by its request_id."""
        return session.execute(
            select(GeneratedContentRecord).where(
                GeneratedContentRecord.id == request_id
            )
        ).scalar_one_or_none()

    @staticmethod
    def list_by_run(
        session: Session, run_id: str
    ) -> List[GeneratedContentRecord]:
        """Fetch all records for a run, newest first."""
        stmt = (
            select(GeneratedContentRecord)
            .where(GeneratedContentRecord.run_id == run_id)
            .order_by(GeneratedContentRecord.generated_at.desc())
        )
        return list(session.execute(stmt).scalars().all())

    @staticmethod
    def list_recent(
        session: Session,
        limit: int = 20,
        source_mode: Optional[str] = None,
    ) -> List[GeneratedContentRecord]:
        """Fetch the most-recent generated content records."""
        stmt = select(GeneratedContentRecord)
        if source_mode:
            stmt = stmt.where(GeneratedContentRecord.source_mode == source_mode)
        stmt = stmt.order_by(GeneratedContentRecord.generated_at.desc()).limit(limit)
        return list(session.execute(stmt).scalars().all())
        return list(session.execute(stmt).scalars().all())