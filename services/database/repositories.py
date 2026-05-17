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
        description: Optional[str] = None,
        url: Optional[str] = None,
        skills: Optional[List[str]] = None,
    ) -> Project:
        """Create a new project."""
        import hashlib
        import time
        
        # Generate a unique ID for the project
        project_id = hashlib.sha256(f"{name}{time.time()}".encode()).hexdigest()[:12]
        
        project = Project(
            id=project_id,
            persona_graph_id=persona_id,
            name=name,
            details=description,
            skills=skills or [],
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
    ) -> Company:
        """Create a new company record."""
        import hashlib
        import time
        
        # Generate a unique ID for the company
        company_id = hashlib.sha256(f"{name}{time.time()}".encode()).hexdigest()[:12]
        
        company = Company(
            id=company_id,
            persona_graph_id=persona_id,
            name=name,
            aliases=[],
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
    ) -> Skill:
        """Create a new skill."""
        import hashlib
        import time
        
        # Generate a unique ID for the skill
        skill_id = hashlib.sha256(f"{name}{time.time()}".encode()).hexdigest()[:12]
        
        skill = Skill(
            id=skill_id,
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
    ) -> Claim:
        """Create a new claim."""
        import hashlib
        import time
        
        # Generate a unique ID for the claim
        claim_id = hashlib.sha256(f"{claim_text}{time.time()}".encode()).hexdigest()[:12]
        
        claim = Claim(
            id=claim_id,
            persona_graph_id=persona_id,
            text=claim_text,
            project_ids=[],
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
    def create(session: Session, name: str) -> Domain:
        """Create a new domain."""
        import hashlib
        import time
        
        # Generate a unique ID for the domain
        domain_id = hashlib.sha256(f"{name}{time.time()}".encode()).hexdigest()[:12]
        
        domain = Domain(id=domain_id, name=name)
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
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DomainFact:
        """Create a new domain fact."""
        import hashlib
        import time
        
        # Generate a unique ID for the fact
        fact_id = hashlib.sha256(f"{fact_text}{time.time()}".encode()).hexdigest()[:12]
        
        fact = DomainFact(
            id=fact_id,
            domain_id=domain_id,
            statement=fact_text,
            tags=[],
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
    ) -> DomainRelationship:
        """Create a new domain relationship (triple)."""
        import hashlib
        import time
        
        # Generate a unique ID for the relationship
        rel_id = hashlib.sha256(f"{from_fact_id}{to_fact_id}{time.time()}".encode()).hexdigest()[:12]
        
        rel = DomainRelationship(
            id=rel_id,
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
        entities: Optional[List[str]] = None,
        themes: Optional[List[str]] = None,
        sentiment: Optional[Dict[str, Any]] = None,
    ) -> ExtractedFact:
        """Create a new extracted fact."""
        import hashlib
        from datetime import datetime, UTC
        
        # Generate a unique ID for the fact
        fact_id = hashlib.sha256(f"{source_url}{fact_text}".encode()).hexdigest()[:12]
        
        fact = ExtractedFact(
            id=fact_id,
            statement=fact_text,
            source_url=source_url or "",
            extracted_at=datetime.now(UTC),
            entities=entities or [],
            tags=themes or [],
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
        post_text: str,
        ssi_component: str,
        score: float,
        curated_date: datetime,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CandidateRecord:
        """Create a new candidate record."""
        candidate = CandidateRecord(
            post_text=post_text,
            ssi_component=ssi_component,
            score=score,
            curated_date=curated_date,
            metadata=metadata or {},
        )
        session.add(candidate)
        session.flush()
        return candidate

    @staticmethod
    def list_unpublished(session: Session, limit: int = 50) -> List[CandidateRecord]:
        """List candidates that haven't been published yet."""
        stmt = (
            select(CandidateRecord)
            .where(CandidateRecord.published_record_id.is_(None))
            .order_by(CandidateRecord.score.desc())
            .limit(limit)
        )
        return list(session.execute(stmt).scalars().all())


class PublishedRecordRepository:
    """Repository for published_records table."""

    @staticmethod
    def create(
        session: Session,
        candidate_id: int,
        buffer_update_id: str,
        published_date: datetime,
        engagement: Optional[Dict[str, Any]] = None,
    ) -> PublishedRecord:
        """Create a new published record."""
        published = PublishedRecord(
            candidate_record_id=candidate_id,
            buffer_update_id=buffer_update_id,
            published_date=published_date,
            engagement=engagement or {},
        )
        session.add(published)
        session.flush()
        
        # Link back to candidate
        stmt_update = (
            update(CandidateRecord)
            .where(CandidateRecord.id == candidate_id)
            .values(published_record_id=published.id)
        )
        session.execute(stmt_update)
        
        return published

    @staticmethod
    def list_recent(session: Session, limit: int = 50) -> List[PublishedRecord]:
        """List most recently published records."""
        stmt = select(PublishedRecord).order_by(PublishedRecord.published_date.desc()).limit(limit)
        return list(session.execute(stmt).scalars().all())


# ============================================================================
# LEARNING LOGS REPOSITORIES
# ============================================================================


class ModerationEventRepository:
    """Repository for moderation_events table."""

    @staticmethod
    def create(
        session: Session,
        candidate_id: int,
        action: str,
        reason: str,
    ) -> ModerationEvent:
        """Create a new moderation event."""
        event = ModerationEvent(
            candidate_record_id=candidate_id,
            action=action,
            reason=reason,
        )
        session.add(event)
        session.flush()
        return event


class ConfidenceDecisionRepository:
    """Repository for confidence_decisions table."""

    @staticmethod
    def create(
        session: Session,
        candidate_id: int,
        decision: str,
        confidence_score: float,
        reason: str,
    ) -> ConfidenceDecision:
        """Create a new confidence decision."""
        decision_rec = ConfidenceDecision(
            candidate_record_id=candidate_id,
            decision=decision,
            confidence_score=confidence_score,
            reason=reason,
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
        statement: str,
        initial_gradient: float,
        initial_uncertainty: float,
    ) -> TruthTrajectory:
        """Create a new truth trajectory."""
        trajectory = TruthTrajectory(
            statement=statement,
            initial_gradient=initial_gradient,
            initial_uncertainty=initial_uncertainty,
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
        truth_gradient: float,
        uncertainty: float,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> TruthTrajectoryPoint:
        """Create a new trajectory point."""
        point = TruthTrajectoryPoint(
            trajectory_id=trajectory_id,
            truth_gradient=truth_gradient,
            uncertainty=uncertainty,
            evidence=evidence or {},
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
            .order_by(TruthTrajectoryPoint.measured_at)
        )
        return list(session.execute(stmt).scalars().all())