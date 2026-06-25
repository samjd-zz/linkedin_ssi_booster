"""BM25-backed evidence retrieval for the avatar_intelligence package."""

from __future__ import annotations

import os
import re
import logging
import time
from typing import Any, Sequence, TypeVar, Union, cast

from services.avatar_intelligence._models import (
    DomainEvidenceFact,
    EvidenceFact,
    ExternalEvidenceFact,
)

logger = logging.getLogger(__name__)

_EvidenceT = TypeVar("_EvidenceT", EvidenceFact, DomainEvidenceFact, ExternalEvidenceFact)

try:
    from rank_bm25 import BM25Okapi as _BM25Okapi
    _BM25_AVAILABLE = True
except ImportError:  # pragma: no cover
    _BM25_AVAILABLE = False


# ---------------------------------------------------------------------------
# Token builders
# ---------------------------------------------------------------------------


def _fact_tokens(fact: EvidenceFact) -> list[str]:
    """Build the BM25 document token list for one evidence fact.

    Concatenates project name, company, years, detail text, and skill names
    so the corpus field reflects everything the fact can match against.
    Skill tokens are repeated three times to weight them above plain detail
    words without hard-coded per-field multipliers.
    """
    base = f"{fact.project} {fact.company} {fact.years} {fact.details}"
    skill_boost = " ".join(fact.skills * 3)  # repeat for IDF weight boost
    return re.findall(r"[a-zA-Z0-9_+#.-]{2,}", (base + " " + skill_boost).lower())


def _domain_fact_tokens(fact: DomainEvidenceFact) -> list[str]:
    """Build the BM25 document token list for one domain fact.

    Concatenates domain name, statement, and tags.
    Tags are repeated three times to weight them above plain statement words.
    """
    base = f"{fact.domain} {fact.statement}"
    tag_boost = " ".join(fact.tags * 3)  # repeat for IDF weight boost
    return re.findall(r"[a-zA-Z0-9_+#.-]{2,}", (base + " " + tag_boost).lower())


# ---------------------------------------------------------------------------
# Configurable evidence split
# ---------------------------------------------------------------------------


def _get_evidence_split() -> tuple[int, int]:
    """Read EVIDENCE_PROJECT_COUNT and EVIDENCE_DOMAIN_COUNT from .env (default 3/2)."""
    try:
        project_count = int(os.getenv("EVIDENCE_PROJECT_COUNT", "3"))
        domain_count = int(os.getenv("EVIDENCE_DOMAIN_COUNT", "2"))
    except Exception:
        project_count, domain_count = 3, 2
    return project_count, domain_count


def _katzilla_action_allowlist_for_query(query: str, category_filter: str | None = None) -> list[tuple[str, str]]:
    """Return a small allowlist of Katzilla actions relevant to the query."""
    q = query.lower()
    actions: list[tuple[str, str]] = []

    if "bill" in q or "congress" in q or "legislation" in q:
        actions.append(("government", "congress-bills"))
    if "recall" in q or "fda" in q or "drug" in q or "device" in q:
        actions.append(("health", "fda-recalls"))
    if "earthquake" in q or "seismic" in q or "quake" in q or "usgs" in q:
        actions.append(("hazards", "usgs-earthquakes"))

    if category_filter:
        cf = category_filter.lower()
        if "government" in cf and ("government", "congress-bills") not in actions:
            actions.append(("government", "congress-bills"))
        if "health" in cf and ("health", "fda-recalls") not in actions:
            actions.append(("health", "fda-recalls"))
        if "hazard" in cf and ("hazards", "usgs-earthquakes") not in actions:
            actions.append(("hazards", "usgs-earthquakes"))

    return actions


def _retrieve_external_evidence(
    query: str,
    category_filter: str | None,
    limit: int,
) -> list[ExternalEvidenceFact]:
    """Retrieve optional Katzilla external evidence behind feature flags."""
    from services.shared import (
        KATZILLA_API_KEY,
        KATZILLA_BASE_URL,
        KATZILLA_DEFAULT_FORMAT,
        KATZILLA_ENABLED,
        KATZILLA_FIELD_ALLOWLIST,
        KATZILLA_MAX_EXTERNAL_RESULTS,
        KATZILLA_MAX_CALLS_PER_DAY,
        KATZILLA_MAX_UNCERTAINTY_PER_DAY,
        KATZILLA_TIMEOUT_SECONDS,
        KATZILLA_TELEMETRY_ENABLED,
    )

    if not KATZILLA_ENABLED:
        return []

    max_items = max(0, min(limit, KATZILLA_MAX_EXTERNAL_RESULTS))
    if max_items == 0:
        return []

    actions = _katzilla_action_allowlist_for_query(query, category_filter=category_filter)
    if not actions:
        return []

    fields = [f.strip() for f in KATZILLA_FIELD_ALLOWLIST.split(",") if f.strip()]

    from services.avatar_intelligence._katzilla_adapter import adapt_katzilla_envelope
    from services.katzilla_service import KatzillaService

    can_call = True
    budget_reason = ""
    if KATZILLA_TELEMETRY_ENABLED:
        from services.katzilla_telemetry import can_call_katzilla

        can_call, budget_reason = can_call_katzilla(
            max_calls_per_day=KATZILLA_MAX_CALLS_PER_DAY,
            max_uncertainty_per_day=KATZILLA_MAX_UNCERTAINTY_PER_DAY,
        )
    if not can_call:
        logger.info("Katzilla call skipped due to budget: %s", budget_reason)
        return []

    service = KatzillaService(
        api_key=KATZILLA_API_KEY,
        base_url=KATZILLA_BASE_URL,
        timeout_seconds=KATZILLA_TIMEOUT_SECONDS,
        default_format=KATZILLA_DEFAULT_FORMAT,
        max_retries=1,
    )

    collected: list[ExternalEvidenceFact] = []
    for agent, action in actions:
        if len(collected) >= max_items:
            break
        per_action_limit = max(1, max_items - len(collected))
        started = time.perf_counter()
        try:
            envelope = service.query_action(
                agent=agent,
                action=action,
                query=query,
                result_limit=per_action_limit,
                fields=fields,
            )
            adapted = adapt_katzilla_envelope(
                envelope=envelope,
                agent=agent,
                action=action,
                limit=per_action_limit,
            )
            collected.extend(adapted)

            if KATZILLA_TELEMETRY_ENABLED:
                from services.katzilla_telemetry import record_katzilla_event

                duration_ms = int((time.perf_counter() - started) * 1000)
                avg_uncertainty = 0.0
                if adapted:
                    avg_uncertainty = sum(f.uncertainty for f in adapted) / len(adapted)
                record_katzilla_event(
                    status="success",
                    agent=agent,
                    action=action,
                    duration_ms=duration_ms,
                    result_count=len(adapted),
                    uncertainty_avg=avg_uncertainty,
                    query=query,
                )
        except Exception as exc:
            if KATZILLA_TELEMETRY_ENABLED:
                from services.katzilla_telemetry import record_katzilla_event

                duration_ms = int((time.perf_counter() - started) * 1000)
                record_katzilla_event(
                    status="error",
                    agent=agent,
                    action=action,
                    duration_ms=duration_ms,
                    result_count=0,
                    uncertainty_avg=0.0,
                    query=query,
                    error_type=type(exc).__name__,
                )
            raise

    return collected[:max_items]


# ---------------------------------------------------------------------------
# BM25 + fallback retrieval — project evidence
# ---------------------------------------------------------------------------


def _retrieve_evidence_bm25(
    query: str,
    facts: list[EvidenceFact],
    limit: int,
) -> list[EvidenceFact]:
    """BM25Okapi-backed retrieval path."""
    corpus = [_fact_tokens(f) for f in facts]
    bm25 = _BM25Okapi(corpus)
    q_tokens = re.findall(r"[a-zA-Z0-9_+#.-]{2,}", query.lower())
    scores: list[float] = bm25.get_scores(q_tokens).tolist()

    ranked = sorted(zip(scores, facts), key=lambda x: x[0], reverse=True)
    top = [f for s, f in ranked if s > 0.0][:limit]
    if top:
        return top
    return [f for _, f in ranked[:limit]]


def _retrieve_evidence_fallback(
    query: str,
    facts: list[EvidenceFact],
    limit: int,
) -> list[EvidenceFact]:
    """Hand-weighted keyword fallback used when rank_bm25 is not installed."""
    q_lower = query.lower()
    q_words = set(q_lower.split())

    scored: list[tuple[int, Any]] = []
    for fact in facts:
        score = 0
        proj_lower = fact.project.lower()
        if proj_lower in q_lower or any(w in proj_lower for w in q_words):
            score += 5
        for skill in fact.skills:
            if skill.lower() in q_lower:
                score += 10
        detail_words = set(fact.details.lower().split())
        overlap = q_words & detail_words
        score += len(overlap) * 3
        score += min(len(fact.details) // 100, 2)
        scored.append((score, fact))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [f for s, f in scored if s > 0][:limit]
    if top:
        return top
    return [f for _, f in scored[:limit]]


# ---------------------------------------------------------------------------
# BM25 + fallback retrieval — domain evidence
# ---------------------------------------------------------------------------


def _retrieve_domain_evidence_bm25(
    query: str,
    facts: list[DomainEvidenceFact],
    limit: int,
) -> list[DomainEvidenceFact]:
    """BM25Okapi-backed retrieval path for domain evidence facts."""
    corpus = [_domain_fact_tokens(f) for f in facts]
    bm25 = _BM25Okapi(corpus)
    q_tokens = re.findall(r"[a-zA-Z0-9_+#.-]{2,}", query.lower())
    scores: list[float] = bm25.get_scores(q_tokens).tolist()

    ranked = sorted(zip(scores, facts), key=lambda x: x[0], reverse=True)
    top = [f for s, f in ranked if s > 0.0][:limit]
    if top:
        return top
    return [f for _, f in ranked[:limit]]


def _retrieve_domain_evidence_fallback(
    query: str,
    facts: list[DomainEvidenceFact],
    limit: int,
) -> list[DomainEvidenceFact]:
    """Hand-weighted keyword fallback for domain facts when rank_bm25 is not installed."""
    q_lower = query.lower()
    q_words = set(q_lower.split())

    scored: list[tuple[int, DomainEvidenceFact]] = []
    for fact in facts:
        score = 0
        domain_lower = fact.domain.lower()
        if domain_lower in q_lower or any(w in domain_lower for w in q_words):
            score += 5
        for tag in fact.tags:
            if tag.lower() in q_lower:
                score += 10
        statement_words = set(fact.statement.lower().split())
        overlap = q_words & statement_words
        score += len(overlap) * 3
        score += min(len(fact.statement) // 100, 2)
        scored.append((score, fact))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [f for s, f in scored if s > 0][:limit]
    if top:
        return top
    return [f for _, f in scored[:limit]]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def retrieve_domain_evidence(
    query: str,
    facts: list[DomainEvidenceFact],
    limit: int = 5,
) -> list[DomainEvidenceFact]:
    """Score and retrieve the most relevant domain evidence facts for a query.

    Uses BM25Okapi (rank_bm25) when available — with domain-specific tokenization.
    Falls back to hand-weighted keyword overlap when rank_bm25 is not installed.
    Returns up to *limit* facts; falls back to all facts when nothing scores.
    """
    if not facts:
        return []

    if _BM25_AVAILABLE:
        return _retrieve_domain_evidence_bm25(query, facts, limit)
    return _retrieve_domain_evidence_fallback(query, facts, limit)


def retrieve_evidence(
    query: str,
    facts: Sequence[_EvidenceT],
    limit: int = 5,
    category_filter: str | None = None,
) -> list[_EvidenceT]:
    """Score and retrieve the most relevant evidence facts for a query.

    Uses BM25Okapi (rank_bm25) when available — accounts for term-frequency
    saturation and corpus-level IDF so rare skills score higher than common
    words like 'python'.  Falls back to hand-weighted keyword overlap when
    rank_bm25 is not installed.

    Returns up to *limit* facts; falls back to all facts when nothing scores.
    The split between project and domain evidence is configurable via .env.

    Args:
        query: The search query string
        facts: Sequence of evidence facts to search
        limit: Maximum number of facts to return
        category_filter: Optional category name to filter domain facts by
                        (e.g., "Artificial Intelligence", "Technology")
    """
    if not facts:
        return []

    project_count, domain_count = _get_evidence_split()
    total = project_count + domain_count
    if limit < total:
        scale = limit / total
        project_count = max(1, int(round(project_count * scale)))
        domain_count = max(1, limit - project_count)
    elif limit > total:
        extra = limit - total
        project_count += extra // 2
        domain_count += extra - (extra // 2)

    evidence_facts: list[EvidenceFact] = [f for f in facts if isinstance(f, EvidenceFact)]
    domain_facts: list[DomainEvidenceFact] = [f for f in facts if isinstance(f, DomainEvidenceFact)]
    external_facts: list[ExternalEvidenceFact] = [f for f in facts if isinstance(f, ExternalEvidenceFact)]

    # Apply category filter to domain facts if specified
    if category_filter and domain_facts:
        category_lower = category_filter.lower()
        domain_facts = [
            f for f in domain_facts
            if category_lower in f.domain.lower() or any(category_lower in tag.lower() for tag in f.tags)
        ]
        logger.debug("Category filter '%s' reduced domain facts from %d to %d", category_filter, len([f for f in facts if isinstance(f, DomainEvidenceFact)]), len(domain_facts))

    results: list[EvidenceFact | DomainEvidenceFact | ExternalEvidenceFact] = []
    n_evidence = min(project_count, len(evidence_facts))
    n_domain = min(domain_count, len(domain_facts))

    if evidence_facts and n_evidence > 0:
        if _BM25_AVAILABLE:
            results.extend(_retrieve_evidence_bm25(query, evidence_facts, n_evidence))
        else:
            results.extend(_retrieve_evidence_fallback(query, evidence_facts, n_evidence))
    if domain_facts and n_domain > 0:
        if _BM25_AVAILABLE:
            results.extend(_retrieve_domain_evidence_bm25(query, domain_facts, n_domain))
        else:
            results.extend(_retrieve_domain_evidence_fallback(query, domain_facts, n_domain))

    if len(results) < limit:
        all_facts = list(evidence_facts) + list(domain_facts) + list(external_facts)
        seen_ids = {getattr(f, "evidence_id", id(f)) for f in results}
        for f in all_facts:
            fid = getattr(f, "evidence_id", id(f))
            if fid not in seen_ids:
                results.append(f)
                seen_ids.add(fid)
            if len(results) >= limit:
                break

    # Optional Phase 3 Katzilla branch: append bounded external evidence while
    # preserving existing ranking semantics (internal results first).
    if len(results) < limit:
        try:
            remaining = limit - len(results)
            external = _retrieve_external_evidence(
                query=query,
                category_filter=category_filter,
                limit=remaining,
            )
            if external:
                seen_ids = {getattr(f, "evidence_id", id(f)) for f in results}
                for item in external:
                    if item.evidence_id in seen_ids:
                        continue
                    results.append(item)
                    seen_ids.add(item.evidence_id)
                    if len(results) >= limit:
                        break
        except Exception as exc:  # degrade gracefully; local retrieval remains primary
            logger.warning("Katzilla retrieval degraded to local-only path: %s", exc)

    return cast(list[_EvidenceT], results[:limit])
