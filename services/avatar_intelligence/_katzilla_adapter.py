"""Katzilla envelope adapter for avatar_intelligence retrieval."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from typing import Any

from services.avatar_intelligence._models import ExternalEvidenceFact
from services.katzilla_service import KatzillaEnvelope


def _make_external_evidence_id(agent: str, action: str, statement: str, source_url: str) -> str:
    raw = f"{agent}|{action}|{statement}|{source_url}".encode("utf-8")
    return f"ext-{hashlib.sha256(raw).hexdigest()[:12]}"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _build_statement(record: Any) -> str:
    if isinstance(record, str):
        return record.strip()
    if isinstance(record, dict):
        for key in ("summary", "title", "name", "statement", "description"):
            value = record.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return json.dumps(record, sort_keys=True)[:300]
    return str(record)


def _record_to_external_fact(
    record: Any,
    envelope: KatzillaEnvelope,
    agent: str,
    action: str,
) -> ExternalEvidenceFact:
    citation = envelope.citation or {}
    quality = envelope.quality or {}

    item: dict[str, Any] = record if isinstance(record, dict) else {}
    statement = _build_statement(record)

    source_name = str(item.get("source_name") or citation.get("source_name") or "katzilla")
    source_url = str(item.get("source_url") or citation.get("source_url") or "")
    retrieved_at = str(item.get("retrieved_at") or citation.get("retrieved_at") or "")
    data_hash = str(item.get("data_hash") or citation.get("data_hash") or "")
    license_value = str(item.get("license") or citation.get("license") or "")
    update_frequency = str(item.get("update_frequency") or citation.get("update_frequency") or "")
    request_url = str(item.get("request_url") or citation.get("request_url") or "")

    confidence = str(quality.get("confidence") or quality.get("credibility") or "medium")
    uncertainty = _safe_float(quality.get("uncertainty"), default=0.0)

    tags: list[str] = []
    raw_tags = item.get("tags")
    if isinstance(raw_tags, list):
        tags = [str(tag) for tag in raw_tags if str(tag).strip()]

    return ExternalEvidenceFact(
        evidence_id=_make_external_evidence_id(agent, action, statement, source_url),
        statement=statement,
        source_name=source_name,
        source_url=source_url,
        retrieved_at=retrieved_at,
        data_hash=data_hash,
        license=license_value,
        update_frequency=update_frequency,
        request_url=request_url,
        confidence=confidence,
        uncertainty=uncertainty,
        agent=agent,
        action=action,
        tags=tags,
    )


def adapt_katzilla_envelope(
    envelope: KatzillaEnvelope,
    agent: str,
    action: str,
    limit: int,
) -> list[ExternalEvidenceFact]:
    """Convert Katzilla envelope payload to normalized external evidence facts."""
    data = envelope.data
    if isinstance(data, list):
        records = data
    else:
        records = [data]

    facts: list[ExternalEvidenceFact] = []
    for record in records:
        fact = _record_to_external_fact(record, envelope=envelope, agent=agent, action=action)
        facts.append(fact)
        if len(facts) >= limit:
            break

    # Deduplicate by evidence_id preserving order.
    deduped: list[ExternalEvidenceFact] = []
    seen: set[str] = set()
    for fact in facts:
        if fact.evidence_id in seen:
            continue
        seen.add(fact.evidence_id)
        deduped.append(fact)
    return deduped


def external_fact_to_dict(fact: ExternalEvidenceFact) -> dict[str, Any]:
    """Helper for logging/inspection in tests and diagnostics."""
    return asdict(fact)
