"""
Unit tests for database repositories.

Tests the repository layer without requiring a live PostgreSQL instance
by using SQLite in-memory database for fast test execution.
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.database.models import Base
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
)


@pytest.fixture(scope="function")
def test_engine():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def test_session(test_engine):
    """Create a new database session for each test."""
    SessionLocal = sessionmaker(bind=test_engine)
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


# ============================================================================
# PERSONA GRAPH REPOSITORY TESTS
# ============================================================================


def test_persona_graph_create(test_session):
    """Test creating a persona graph."""
    graph_data = {
        "schemaVersion": "1.0",
        "person": {
            "name": "Test User",
            "title": "Software Engineer",
            "location": "Remote",
            "links": ["https://example.com"]
        },
        "projects": [],
        "companies": [],
        "skills": [],
        "claims": []
    }
    
    persona = PersonaGraphRepository.create(test_session, graph_data)
    test_session.commit()
    
    assert persona.id is not None
    assert persona.person["name"] == "Test User"  # type: ignore[index]


def test_persona_graph_get_latest(test_session):
    """Test getting the latest persona graph."""
    # Create two persona graphs with a small delay to ensure different timestamps
    import time
    
    graph_data_1 = {"schemaVersion": "1.0", "person": {"name": "User 1"}}
    graph_data_2 = {"schemaVersion": "1.0", "person": {"name": "User 2"}}
    
    PersonaGraphRepository.create(test_session, graph_data_1)
    test_session.commit()
    
    # Small delay to ensure different updated_at timestamp
    time.sleep(0.01)
    
    persona_2 = PersonaGraphRepository.create(test_session, graph_data_2)
    test_session.commit()
    
    latest = PersonaGraphRepository.get_latest(test_session)
    assert latest is not None  # type: ignore[comparison-overlap]
    assert latest.person["name"] == "User 2"  # type: ignore[index]


# ============================================================================
# PROJECT REPOSITORY TESTS
# ============================================================================


def test_project_create(test_session):
    """Test creating a project."""
    # Create persona first
    graph_data = {"schemaVersion": "1.0", "person": {"name": "Test"}}
    persona = PersonaGraphRepository.create(test_session, graph_data)
    test_session.flush()
    
    project = ProjectRepository.create(
        test_session,
        persona_id=persona.id,  # type: ignore[arg-type]
        name="Test Project",
        description="A test project",
        skills=["Python", "FastAPI"]
    )
    test_session.commit()
    
    assert project.id is not None
    assert project.name == "Test Project"  # type: ignore[comparison-overlap]
    assert "Python" in project.skills


def test_project_get_by_name(test_session):
    """Test getting a project by name."""
    graph_data = {"schemaVersion": "1.0", "person": {"name": "Test"}}
    persona = PersonaGraphRepository.create(test_session, graph_data)
    test_session.flush()
    
    ProjectRepository.create(
        test_session,
        persona_id=persona.id,  # type: ignore[arg-type]
        name="Unique Project",
        description="Test"
    )
    test_session.commit()
    
    project = ProjectRepository.get_by_name(test_session, "Unique Project")
    assert project is not None  # type: ignore[comparison-overlap]
    assert project.name == "Unique Project"  # type: ignore[comparison-overlap]


def test_project_list_by_persona(test_session):
    """Test listing projects for a persona."""
    graph_data = {"schemaVersion": "1.0", "person": {"name": "Test"}}
    persona = PersonaGraphRepository.create(test_session, graph_data)
    test_session.flush()
    
    ProjectRepository.create(test_session, persona.id, "Project 1", "Desc 1")  # type: ignore[arg-type]
    ProjectRepository.create(test_session, persona.id, "Project 2", "Desc 2")  # type: ignore[arg-type]
    test_session.commit()
    
    projects = ProjectRepository.list_by_persona(test_session, persona.id)  # type: ignore[arg-type]
    assert len(projects) == 2
    assert {p.name for p in projects} == {"Project 1", "Project 2"}


# ============================================================================
# DOMAIN REPOSITORY TESTS
# ============================================================================


def test_domain_create(test_session):
    """Test creating a domain."""
    domain = DomainRepository.create(test_session, "Python Development")
    test_session.commit()
    
    assert domain.id is not None
    assert domain.name == "Python Development"  # type: ignore[comparison-overlap]


def test_domain_get_by_name(test_session):
    """Test getting domain by name."""
    DomainRepository.create(test_session, "AI Engineering")
    test_session.commit()
    
    domain = DomainRepository.get_by_name(test_session, "AI Engineering")
    assert domain is not None  # type: ignore[comparison-overlap]
    assert domain.name == "AI Engineering"  # type: ignore[comparison-overlap]


def test_domain_list_all(test_session):
    """Test listing all domains."""
    DomainRepository.create(test_session, "Python")
    DomainRepository.create(test_session, "Java")
    DomainRepository.create(test_session, "AI")
    test_session.commit()
    
    domains = DomainRepository.list_all(test_session)
    assert len(domains) == 3
    assert {d.name for d in domains} == {"Python", "Java", "AI"}


# ============================================================================
# DOMAIN FACT REPOSITORY TESTS
# ============================================================================


def test_domain_fact_create(test_session):
    """Test creating a domain fact."""
    domain = DomainRepository.create(test_session, "Test Domain")
    test_session.flush()
    
    fact = DomainFactRepository.create(
        test_session,
        domain_id=domain.id,  # type: ignore[arg-type]
        fact_text="Python is a high-level language",
        metadata={"confidence": "high"}
    )
    test_session.commit()
    
    assert fact.id is not None
    assert fact.statement == "Python is a high-level language"  # type: ignore[comparison-overlap]


def test_domain_fact_list_by_domain(test_session):
    """Test listing facts for a domain."""
    domain = DomainRepository.create(test_session, "Python")
    test_session.flush()
    
    DomainFactRepository.create(test_session, domain.id, "Fact 1")  # type: ignore[arg-type]
    DomainFactRepository.create(test_session, domain.id, "Fact 2")  # type: ignore[arg-type]
    test_session.commit()
    
    facts = DomainFactRepository.list_by_domain(test_session, domain.id)  # type: ignore[arg-type]
    assert len(facts) == 2
    assert {f.statement for f in facts} == {"Fact 1", "Fact 2"}


# ============================================================================
# EXTRACTED FACT REPOSITORY TESTS
# ============================================================================


def test_extracted_fact_create(test_session):
    """Test creating an extracted fact."""
    fact = ExtractedFactRepository.create(
        test_session,
        fact_text="AI is transforming software development",
        source_url="https://example.com/article",
        entities=["AI", "software development"],
        themes=["technology", "AI"],
        sentiment={"positive": 0.8, "negative": 0.1}
    )
    test_session.commit()
    
    assert fact.id is not None
    assert fact.statement == "AI is transforming software development"  # type: ignore[comparison-overlap]
    assert "AI" in fact.entities  # type: ignore[operator]


def test_extracted_fact_list_recent(test_session):
    """Test listing recent extracted facts."""
    # Create multiple facts
    for i in range(5):
        ExtractedFactRepository.create(
            test_session,
            fact_text=f"Fact {i}",
            source_url=f"https://example.com/{i}"
        )
    test_session.commit()
    
    facts = ExtractedFactRepository.list_recent(test_session, limit=3)
    assert len(facts) == 3


# ============================================================================
# NARRATIVE MEMORY REPOSITORY TESTS
# ============================================================================


def test_narrative_memory_create(test_session):
    """Test creating a narrative memory."""
    narrative = NarrativeMemoryRepository.create(
        test_session,
        themes=["RAG", "search", "project"]
    )
    test_session.commit()
    
    assert narrative.id is not None
    assert len(narrative.recent_themes) > 0  # type: ignore[arg-type]


def test_narrative_memory_list_by_tags(test_session):
    """Test listing narratives by tags."""
    NarrativeMemoryRepository.create(
        test_session,
        themes=["Python", "AI"]
    )
    NarrativeMemoryRepository.create(
        test_session,
        themes=["Java", "Spring"]
    )
    NarrativeMemoryRepository.create(
        test_session,
        themes=["Python", "FastAPI"]
    )
    test_session.commit()
    
    # Find narratives with "Python" theme
    python_narratives = NarrativeMemoryRepository.list_by_themes(test_session, ["Python"])
    assert len(python_narratives) >= 1  # At least one narrative with Python theme


# ============================================================================
# CASCADE DELETE TESTS
# ============================================================================


def test_persona_delete_cascades_to_projects(test_session):
    """Test that deleting a persona cascades to projects."""
    graph_data = {"schemaVersion": "1.0", "person": {"name": "Test"}}
    persona = PersonaGraphRepository.create(test_session, graph_data)
    test_session.flush()
    
    ProjectRepository.create(test_session, persona.id, "Project 1", "Desc")  # type: ignore[arg-type]
    test_session.commit()
    
    # Delete persona
    test_session.delete(persona)
    test_session.commit()
    
    # Projects should be deleted
    projects = ProjectRepository.list_by_persona(test_session, persona.id)  # type: ignore[arg-type]
    assert len(projects) == 0


def test_domain_delete_cascades_to_facts(test_session):
    """Test that deleting a domain cascades to facts."""
    domain = DomainRepository.create(test_session, "Test Domain")
    test_session.flush()
    
    DomainFactRepository.create(test_session, domain.id, "Fact 1")  # type: ignore[arg-type]
    test_session.commit()
    
    # Delete domain
    test_session.delete(domain)
    test_session.commit()
    
    # Facts should be deleted
    facts = DomainFactRepository.list_by_domain(test_session, domain.id)  # type: ignore[arg-type]
    assert len(facts) == 0