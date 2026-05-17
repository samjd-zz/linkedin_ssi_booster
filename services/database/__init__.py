"""Database package for PostgreSQL integration via SQLAlchemy.

This package provides:
- ORM models for all database tables
- Session management and connection pooling
- Repository pattern for data access
"""

from services.database.models import (
    Base,
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
from services.database.session import (
    get_session,
    init_db,
    get_engine,
    check_database_connection,
    close_database_connections,
)
from services.database.repositories import (
    PersonaGraphRepository,
    ProjectRepository,
    CompanyRepository,
    SkillRepository,
    ClaimRepository,
    DomainRepository,
    DomainFactRepository,
    DomainRelationshipRepository,
    ExtractedFactRepository,
    NarrativeMemoryRepository,
    CandidateRecordRepository,
    PublishedRecordRepository,
    ModerationEventRepository,
    ConfidenceDecisionRepository,
    TruthTrajectoryRepository,
    TruthTrajectoryPointRepository,
)

__all__ = [
    # Base
    "Base",
    # Session management
    "get_session",
    "init_db",
    "get_engine",
    "check_database_connection",
    "close_database_connections",
    # Models
    "PersonaGraph",
    "Project",
    "Company",
    "Skill",
    "Claim",
    "Domain",
    "DomainFact",
    "DomainRelationship",
    "ExtractedFact",
    "NarrativeMemory",
    "CandidateRecord",
    "PublishedRecord",
    "ModerationEvent",
    "ConfidenceDecision",
    "TruthTrajectory",
    "TruthTrajectoryPoint",
    # Repositories
    "PersonaGraphRepository",
    "ProjectRepository",
    "CompanyRepository",
    "SkillRepository",
    "ClaimRepository",
    "DomainRepository",
    "DomainFactRepository",
    "DomainRelationshipRepository",
    "ExtractedFactRepository",
    "NarrativeMemoryRepository",
    "CandidateRecordRepository",
    "PublishedRecordRepository",
    "ModerationEventRepository",
    "ConfidenceDecisionRepository",
    "TruthTrajectoryRepository",
    "TruthTrajectoryPointRepository",
]