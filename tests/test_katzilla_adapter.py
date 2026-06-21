from services.avatar_intelligence._katzilla_adapter import adapt_katzilla_envelope
from services.katzilla_service import KatzillaEnvelope


def test_adapt_katzilla_envelope_preserves_citation_metadata() -> None:
    envelope = KatzillaEnvelope(
        data=[
            {
                "title": "FDA expands recall",
                "source_url": "https://example.com/recall",
                "tags": ["fda", "recall"],
            }
        ],
        quality={"confidence": "high", "uncertainty": 0.2},
        citation={
            "source_name": "FDA",
            "retrieved_at": "2026-06-21T10:00:00Z",
            "data_hash": "abc123",
            "license": "public",
            "update_frequency": "daily",
            "request_url": "https://api.example.com/recalls",
        },
        meta={"provider": "katzilla"},
    )

    facts = adapt_katzilla_envelope(
        envelope=envelope,
        agent="health",
        action="fda-recalls",
        limit=3,
    )

    assert len(facts) == 1
    fact = facts[0]
    assert fact.statement == "FDA expands recall"
    assert fact.source_name == "FDA"
    assert fact.source_url == "https://example.com/recall"
    assert fact.retrieved_at == "2026-06-21T10:00:00Z"
    assert fact.data_hash == "abc123"
    assert fact.license == "public"
    assert fact.update_frequency == "daily"
    assert fact.request_url == "https://api.example.com/recalls"
    assert fact.confidence == "high"
    assert abs(fact.uncertainty - 0.2) < 1e-9


def test_adapt_katzilla_envelope_handles_missing_optional_quality() -> None:
    envelope = KatzillaEnvelope(
        data={"summary": "USGS detected M4.1 earthquake"},
        quality={},
        citation={"source_name": "USGS"},
        meta={},
    )

    facts = adapt_katzilla_envelope(
        envelope=envelope,
        agent="hazards",
        action="usgs-earthquakes",
        limit=1,
    )

    assert len(facts) == 1
    fact = facts[0]
    assert fact.statement == "USGS detected M4.1 earthquake"
    assert fact.source_name == "USGS"
    assert fact.confidence == "medium"
    assert fact.uncertainty == 0.0
