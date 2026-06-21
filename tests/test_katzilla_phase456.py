from services.avatar_intelligence import ExternalEvidenceFact, build_explain_output, format_explain_output
from services.content_curator._evidence_paths import external_fact_to_evidence_path
from services.console_grounding import build_katzilla_citation_reply
from services import katzilla_telemetry as kt


def _external_fact() -> ExternalEvidenceFact:
    return ExternalEvidenceFact(
        evidence_id="ext-xyz-001",
        statement="Congress advances AI governance bill",
        source_name="Congress.gov",
        source_url="https://example.com/congress",
        retrieved_at="2026-06-21T10:00:00Z",
        data_hash="hash-1",
        license="public",
        update_frequency="daily",
        request_url="https://katzilla.dev/api/government/congress-bills",
        confidence="high",
        uncertainty=0.12,
        agent="government",
        action="congress-bills",
        tags=["ai", "bill"],
    )


def test_external_fact_to_evidence_path_uses_katzilla_source_and_overlap():
    fact = _external_fact()
    path = external_fact_to_evidence_path(
        fact,
        "AI governance bill advances in congress",
    )
    assert path.source == "katzilla:government/congress-bills"
    assert path.credibility == 0.78
    assert path.reasoning_type == "statistical"
    assert path.uncertainty >= 0.12
    assert 0.0 <= path.overlap <= 1.0


def test_build_katzilla_citation_reply_contains_provenance_fields():
    reply = build_katzilla_citation_reply("ai bill", [_external_fact()])
    assert "Katzilla evidence for: ai bill" in reply
    assert "source: Congress.gov" in reply
    assert "url: https://example.com/congress" in reply
    assert "license: public" in reply


def test_explain_output_includes_external_evidence_section():
    explain = build_explain_output(
        evidence_facts=[],
        article_ref="ai bill",
        channel="linkedin",
        ssi_component="engage_with_insights",
        extracted_facts=[],
        external_facts=[_external_fact()],
    )
    rendered = format_explain_output(explain)
    assert "Katzilla External Evidence" in rendered
    assert "ext-xyz-001" in rendered


def test_katzilla_telemetry_records_and_enforces_call_budget(tmp_path, monkeypatch):
    telemetry_path = tmp_path / "katzilla_events.jsonl"
    monkeypatch.setattr(kt, "_KATZILLA_LOG_PATH", telemetry_path)

    kt.record_katzilla_event(
        status="success",
        agent="government",
        action="congress-bills",
        duration_ms=120,
        result_count=2,
        uncertainty_avg=0.2,
        query="ai bill",
    )

    usage = kt.get_daily_katzilla_usage()
    assert usage["calls"] == 1.0
    assert usage["uncertainty_sum"] == 0.2

    ok, reason = kt.can_call_katzilla(max_calls_per_day=2, max_uncertainty_per_day=1.0)
    assert ok is True
    assert reason == ""

    ok, reason = kt.can_call_katzilla(max_calls_per_day=1, max_uncertainty_per_day=1.0)
    assert ok is False
    assert reason == "daily_call_budget_exhausted"
