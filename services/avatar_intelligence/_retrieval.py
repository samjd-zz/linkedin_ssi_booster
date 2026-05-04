"""BM25-backed evidence retrieval for the avatar_intelligence package."""

from __future__ import annotations

import os
import re
import logging
from typing import Any, Sequence, TypeVar, Union, cast

from services.avatar_intelligence._models import (
    DomainEvidenceFact,
    EvidenceFact,
)

logger = logging.getLogger(__name__)

_EvidenceT = TypeVar("_EvidenceT", EvidenceFact, DomainEvidenceFact)

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

    # Apply category filter to domain facts if specified
    if category_filter and domain_facts:
        category_lower = category_filter.lower()
        domain_facts = [
            f for f in domain_facts
            if category_lower in f.domain.lower() or any(category_lower in tag.lower() for tag in f.tags)
        ]
        logger.debug("Category filter '%s' reduced domain facts from %d to %d", category_filter, len([f for f in facts if isinstance(f, DomainEvidenceFact)]), len(domain_facts))

    results: list[Union[EvidenceFact, DomainEvidenceFact]] = []
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
        all_facts = list(evidence_facts) + list(domain_facts)
        seen_ids = {getattr(f, "evidence_id", id(f)) for f in results}
        for f in all_facts:
            fid = getattr(f, "evidence_id", id(f))
            if fid not in seen_ids:
                results.append(f)
                seen_ids.add(fid)
            if len(results) >= limit:
                break

    return cast(list[_EvidenceT], results[:limit])
