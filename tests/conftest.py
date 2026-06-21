"""Shared pytest fixtures for LinkedIn SSI Booster tests."""
import json
import os
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# ---------------------------------------------------------------------------
# Minimal valid JSON fixtures
# ---------------------------------------------------------------------------

MINIMAL_PERSONA_GRAPH: dict = {
    "schemaVersion": "1.0",
    "person": {
        "name": "Test User",
        "title": "Software Engineer",
        "location": "Toronto, ON",
    },
    "projects": [
        {
            "id": "proj-alpha",
            "name": "Alpha Project",
            "companyId": "comp-acme",
            "years": "2021-2023",
            "details": "Built a scalable API with Python and FastAPI.",
            "skills": ["python", "fastapi", "api"],
        },
        {
            "id": "proj-beta",
            "name": "Beta Project",
            "companyId": "comp-acme",
            "years": "2023-2024",
            "details": "Machine learning pipeline using scikit-learn and pandas.",
            "skills": ["python", "ml", "scikit-learn"],
        },
    ],
    "companies": [
        {"id": "comp-acme", "name": "Acme Corp"},
    ],
    "skills": [
        {"id": "python", "name": "Python"},
        {"id": "fastapi", "name": "FastAPI"},
        {"id": "api", "name": "API"},
        {"id": "ml", "name": "Machine Learning"},
        {"id": "scikit-learn", "name": "scikit-learn"},
    ],
    "claims": [],
}

MINIMAL_NARRATIVE_MEMORY: dict = {
    "recentThemes": ["python", "api"],
    "recentClaims": [],
    "openNarrativeArcs": [],
}


@pytest.fixture(scope="function")
def test_engine():
    """Create an in-memory SQLite database for testing."""
    from services.database.models import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db_session(test_engine):
    """Create a new database session for each test."""
    SessionLocal = sessionmaker(bind=test_engine)
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def avatar_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temp avatar data dir and point AVATAR_DATA_DIR at it.

    Also writes valid persona_graph.json + narrative_memory.json so callers
    that just need a fully-loaded state can import after this fixture runs.
    The fixture does NOT reload avatar_intelligence module-level constants
    automatically; callers must import functions after the env var is set,
    or use the helpers provided in this module.
    """
    monkeypatch.setenv("AVATAR_DATA_DIR", str(tmp_path))
    (tmp_path / "persona_graph.json").write_text(
        json.dumps(MINIMAL_PERSONA_GRAPH), encoding="utf-8"
    )
    (tmp_path / "narrative_memory.json").write_text(
        json.dumps(MINIMAL_NARRATIVE_MEMORY), encoding="utf-8"
    )
    return tmp_path
