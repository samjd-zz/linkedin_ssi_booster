from services.avatar_intelligence._models import EvidenceFact, ExternalEvidenceFact
from services.avatar_intelligence._retrieval import retrieve_evidence


def _base_fact() -> EvidenceFact:
    return EvidenceFact(
        evidence_id="ev-001",
        project="GovAI",
        company="Scale AI",
        years="2024-2025",
        details="Built RAG and retrieval pipelines.",
        skills=["rag", "python"],
        source_project_id="proj-1",
    )


def _external_fact() -> ExternalEvidenceFact:
    return ExternalEvidenceFact(
        evidence_id="ext-001",
        statement="Congress advances AI governance bill",
        source_name="Congress",
        source_url="https://example.com/bill",
        retrieved_at="2026-06-21T10:00:00Z",
        data_hash="hash-1",
        license="public",
        update_frequency="daily",
        request_url="https://api.example.com",
        confidence="high",
        uncertainty=0.1,
        agent="government",
        action="congress-bills",
        tags=["ai", "bill"],
    )


def test_retrieve_evidence_disabled_mode(monkeypatch):
    monkeypatch.setattr(
        "services.avatar_intelligence._retrieval._retrieve_external_evidence",
        lambda query, category_filter, limit: [],
    )

    results = retrieve_evidence("rag retrieval", [_base_fact()], limit=2)
    assert any(getattr(r, "evidence_id", "") == "ev-001" for r in results)


def test_retrieve_evidence_enabled_mode_appends_external(monkeypatch):
    monkeypatch.setattr(
        "services.avatar_intelligence._retrieval._retrieve_external_evidence",
        lambda query, category_filter, limit: [_external_fact()],
    )

    results = retrieve_evidence("ai bill", [_base_fact()], limit=3)
    ids = [getattr(r, "evidence_id", "") for r in results]
    assert "ev-001" in ids
    assert "ext-001" in ids


def test_retrieve_evidence_external_error_fallback(monkeypatch):
    def _boom(query, category_filter, limit):
        raise RuntimeError("network issue")

    monkeypatch.setattr(
        "services.avatar_intelligence._retrieval._retrieve_external_evidence",
        _boom,
    )

    results = retrieve_evidence("earthquake", [_base_fact()], limit=2)
    ids = [getattr(r, "evidence_id", "") for r in results]
    assert "ev-001" in ids


def test_retrieve_evidence_bounded_external_results(monkeypatch):
    ext1 = _external_fact()
    ext2 = ExternalEvidenceFact(
        evidence_id="ext-002",
        statement="USGS reports seismic activity",
        source_name="USGS",
        source_url="https://example.com/quake",
        retrieved_at="2026-06-21T10:00:00Z",
        data_hash="hash-2",
        license="public",
        update_frequency="hourly",
        request_url="https://api.example.com/quake",
        confidence="medium",
        uncertainty=0.2,
        agent="hazards",
        action="usgs-earthquakes",
        tags=["earthquake"],
    )

    monkeypatch.setattr(
        "services.avatar_intelligence._retrieval._retrieve_external_evidence",
        lambda query, category_filter, limit: [ext1, ext2][:limit],
    )

    results = retrieve_evidence("hazards", [_base_fact()], limit=2)
    ids = [getattr(r, "evidence_id", "") for r in results]
    assert len(ids) == 2
    assert "ext-002" not in ids
