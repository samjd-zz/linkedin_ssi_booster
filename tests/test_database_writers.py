import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from services.database import writers
from services.database.models import DomainRelationship
from services.database.repositories import (
    ClaimRepository,
    DomainFactRepository,
    DomainRepository,
    ExtractedFactRepository,
    NarrativeMemoryRepository,
    PersonaGraphRepository,
    ProjectRepository,
    SkillRepository,
)


def test_parse_datetime_accepts_datetime_and_iso_z() -> None:
    existing = datetime(2026, 9, 5, tzinfo=timezone.utc)

    assert writers._parse_datetime(existing) is existing
    assert writers._parse_datetime("2026-09-05T12:34:56Z") == datetime(
        2026, 9, 5, 12, 34, 56, tzinfo=timezone.utc
    )


def test_parse_datetime_returns_none_for_empty_or_invalid(caplog: pytest.LogCaptureFixture) -> None:
    assert writers._parse_datetime(None) is None
    assert writers._parse_datetime("") is None
    assert writers._parse_datetime("not-a-date") is None
    assert "Could not parse datetime value" in caplog.text


def test_write_persona_graph_dual_persists_normalized_rows_and_file(db_session, tmp_path) -> None:
    persona_data = {
        "schemaVersion": "1.0",
        "person": {"name": "Test User"},
        "companies": [{"id": "company-1", "name": "Acme", "aliases": ["A"]}],
        "projects": [
            {
                "id": "project-1",
                "name": "Project One",
                "companyId": "company-1",
                "details": "Built a testable pipeline.",
                "url": "https://example.com/project",
                "skills": ["python"],
                "years": "2024-2026",
            }
        ],
        "skills": [{"id": "python", "name": "Python", "aliases": ["py"]}],
        "claims": [
            {
                "id": "claim-1",
                "text": "Project One shipped.",
                "projectIds": ["project-1", "missing-project"],
                "links": ["https://example.com/project"],
                "confidenceHint": "high",
            }
        ],
    }
    output_path = tmp_path / "avatar" / "persona_graph.json"

    persona_id = writers.write_persona_graph_dual(db_session, persona_data, output_path)

    latest = PersonaGraphRepository.get_latest(db_session)
    projects = ProjectRepository.list_by_persona(db_session, persona_id)
    skills = SkillRepository.list_by_persona(db_session, persona_id)
    claims = ClaimRepository.list_by_persona(db_session, persona_id)

    assert latest is not None
    assert latest.person == {"name": "Test User"}
    assert [project.name for project in projects] == ["Project One"]
    assert projects[0].company_id == "company-1"
    assert [skill.name for skill in skills] == ["Python"]
    assert len(claims) == 1
    assert claims[0].project_ids == ["project-1"]
    assert json.loads(output_path.read_text(encoding="utf-8")) == persona_data


def test_write_domain_knowledge_to_db_skips_unknown_domains_and_maps_relationships(
    db_session,
) -> None:
    domain_data = {
        "domains": [{"id": "music", "name": "Music", "description": "Production"}],
        "facts": [
            {
                "id": "fact-1",
                "domainId": "music",
                "statement": "Kick drums anchor the groove.",
                "tags": ["rhythm"],
                "confidence": "high",
                "scope": "production",
            },
            {
                "id": "fact-2",
                "domainId": "music",
                "statement": "Bass movement creates tension.",
            },
            {
                "id": "fact-missing",
                "domainId": "unknown",
                "statement": "This should not be inserted.",
            },
        ],
        "relationships": [
            {
                "id": "rel-1",
                "fromFactId": "fact-1",
                "toFactId": "fact-2",
                "relationType": "supports",
                "description": "Rhythm supports bass tension.",
            },
            {
                "id": "rel-missing",
                "fromFactId": "fact-1",
                "toFactId": "fact-missing",
                "relationType": "supports",
            },
        ],
    }

    domain_ids = writers.write_domain_knowledge_to_db(db_session, domain_data)

    domain = DomainRepository.get_by_name(db_session, "Music")
    assert domain is not None
    assert domain_ids == {"music": "music"}
    facts = DomainFactRepository.list_by_domain(db_session, domain.id)
    relationships = db_session.execute(select(DomainRelationship)).scalars().all()
    assert {fact.id for fact in facts} == {"fact-1", "fact-2"}
    assert len(relationships) == 1
    assert relationships[0].id == "rel-1"


def test_write_extracted_knowledge_dual_persists_facts_and_file(db_session, tmp_path) -> None:
    extracted_data = {
        "facts": [
            {
                "id": "extracted-1",
                "statement": "The tokenizer keeps Japanese boundaries intact.",
                "source_url": "https://example.com/article",
                "source_title": "Tokenizer Notes",
                "entities": ["spaCy"],
                "tags": ["nlp"],
                "primary_category": "engineering",
                "primary_ssi_component": "establish_brand",
                "confidence": "high",
                "extraction_method": "spacy_nlp",
                "extracted_at": "2026-09-05T10:00:00Z",
            }
        ]
    }
    output_path = tmp_path / "extracted_knowledge.json"

    written = writers.write_extracted_knowledge_dual(db_session, extracted_data, output_path)

    facts = ExtractedFactRepository.list_recent(db_session)
    assert written == 1
    assert len(facts) == 1
    assert facts[0].id == "extracted-1"
    assert facts[0].confidence == "high"
    assert facts[0].tags == ["nlp"]
    assert json.loads(output_path.read_text(encoding="utf-8")) == extracted_data


def test_write_narrative_memory_to_db_handles_empty_and_populated_payloads(db_session) -> None:
    assert writers.write_narrative_memory_to_db(db_session, {}) == 0
    assert NarrativeMemoryRepository.get_latest(db_session) is None

    written = writers.write_narrative_memory_to_db(
        db_session,
        {
            "recentThemes": ["japanese lyrics"],
            "recentClaims": ["Bilingual hooks improved."],
            "openNarrativeArcs": ["Rei keeps learning."],
        },
    )

    latest = NarrativeMemoryRepository.get_latest(db_session)
    assert written == 1
    assert latest is not None
    assert latest.recent_themes == ["japanese lyrics"]
    assert latest.recent_claims == ["Bilingual hooks improved."]
    assert latest.open_narrative_arcs == ["Rei keeps learning."]
