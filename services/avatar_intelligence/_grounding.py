"""Grounding context builders for the avatar_intelligence package."""

from __future__ import annotations

import re
import logging
from typing import Union

from services.avatar_intelligence._models import (
    AvatarState,
    DomainEvidenceFact,
    EvidenceFact,
    ExternalEvidenceFact,
    ExtractedEvidenceFact,
)
from services.avatar_intelligence._normalizers import (
    normalize_domain_facts,
    normalize_evidence_facts,
)
from services.avatar_intelligence._retrieval import (
    _BM25_AVAILABLE,
    _domain_fact_tokens,
    _fact_tokens,
    _get_evidence_split,
    retrieve_evidence,
)

try:
    from rank_bm25 import BM25Okapi as _BM25Okapi
except ImportError:  # pragma: no cover
    _BM25Okapi = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)


def build_grounding_context(evidence_facts: list[EvidenceFact]) -> str:
    """Build a prompt-ready grounding block from evidence facts.

    Includes evidence IDs to support --avatar-explain (Phase 1B).
    Returns an empty string when the fact list is empty.
    """
    if not evidence_facts:
        return ""

    lines = [
        "Your background — weave these in naturally when they genuinely connect to the topic:"
    ]
    for fact in evidence_facts:
        line = (
            f"- [{fact.evidence_id}] Project: {fact.project}"
            f" | Company: {fact.company}"
            f" | Years: {fact.years}"
            f" | Detail: {fact.details}"
        )
        if fact.skills:
            line += f" | Skills: {', '.join(fact.skills)}"
        lines.append(line)
    return "\n".join(lines)


def build_domain_grounding_context(domain_facts: list[DomainEvidenceFact]) -> str:
    """Build a prompt-ready grounding block from domain evidence facts.

    Returns an empty string when the fact list is empty.
    """
    if not domain_facts:
        return ""

    lines = [
        "Domain expertise — general knowledge you can reference when relevant:"
    ]
    for fact in domain_facts:
        line = f"- [{fact.evidence_id}] {fact.statement}"
        if fact.tags:
            line += f" (Tags: {', '.join(fact.tags)})"
        lines.append(line)
    return "\n".join(lines)


def build_extracted_grounding_context(extracted_facts: list[ExtractedEvidenceFact]) -> str:
    """Build a prompt-ready grounding block from NLP-extracted evidence facts.

    Returns an empty string when the fact list is empty.
    """
    if not extracted_facts:
        return ""

    lines = [
        "Recently learned context — new knowledge extracted from external sources:"
    ]
    for fact in extracted_facts:
        line = f"- [{fact.evidence_id}] {fact.statement}"
        if fact.tags:
            line += f" (Tags: {', '.join(fact.tags[:5])})"
        if fact.source_title:
            line += f" [Source: {fact.source_title[:60]}]"
        lines.append(line)
    return "\n".join(lines)


def build_external_grounding_context(external_facts: list[ExternalEvidenceFact]) -> str:
    """Build a prompt-ready grounding block from external Katzilla evidence."""
    if not external_facts:
        return ""

    lines = [
        "External evidence — recent cited records fetched from trusted sources:",
    ]
    for fact in external_facts:
        line = f"- [{fact.evidence_id}] {fact.statement}"
        if fact.source_name:
            line += f" | Source: {fact.source_name}"
        if fact.source_url:
            line += f" | URL: {fact.source_url}"
        lines.append(line)
    return "\n".join(lines)


def get_grounding_context_for_query(
    query: str,
    state: AvatarState | None = None,
    limit: int = 5,
    include_domain_facts: bool = True,
) -> str:
    """Retrieve and format grounding context for a generation query.

    When *state* is None or not loaded, returns an empty string so the
    caller can fall back to the existing PROFILE_CONTEXT-based flow.

    When *include_domain_facts* is True (default), domain knowledge facts
    are included in the retrieval corpus alongside project facts.

    This is the primary integration point for ollama_service / content_curator
    to request graph-backed grounding.
    """
    if state is None or not state.is_loaded:
        return ""

    facts = normalize_evidence_facts(state)
    domain_facts = normalize_domain_facts(state) if include_domain_facts else []

    if not facts and not domain_facts:
        return ""

    # Use the same split logic as retrieve_evidence
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

    # BM25 path
    if _BM25_AVAILABLE and _BM25Okapi is not None and (facts or domain_facts):
        project_corpus = [_fact_tokens(f) for f in facts]
        domain_corpus = [_domain_fact_tokens(f) for f in domain_facts]
        combined_corpus = project_corpus + domain_corpus

        bm25 = _BM25Okapi(combined_corpus)
        q_tokens = re.findall(r"[a-zA-Z0-9_+#.-]{2,}", query.lower())
        scores: list[float] = bm25.get_scores(q_tokens).tolist()

        project_scores = scores[:len(facts)]
        domain_scores = scores[len(facts):]

        project_ranked = sorted(zip(project_scores, facts), key=lambda x: x[0], reverse=True)
        domain_ranked = sorted(zip(domain_scores, domain_facts), key=lambda x: x[0], reverse=True)

        n_evidence = min(project_count, len(facts))
        n_domain = min(domain_count, len(domain_facts))

        top_projects = [f for s, f in project_ranked if s > 0.0][:n_evidence]
        top_domains = [f for s, f in domain_ranked if s > 0.0][:n_domain]

        context_parts = []
        if top_projects:
            context_parts.append(build_grounding_context(top_projects))
        if top_domains:
            context_parts.append(build_domain_grounding_context(top_domains))
        if context_parts:
            return "\n\n".join(context_parts)

        # Tiny corpora can produce zero/non-positive BM25 scores even for a
        # useful token match. Fall back to the retrieval helper so callers still
        # get grounding context instead of a blank prompt block.
        relevant = retrieve_evidence(query, facts + domain_facts, limit=limit)
        project_facts_sel = [f for f in relevant if isinstance(f, EvidenceFact)]
        domain_facts_sel = [f for f in relevant if isinstance(f, DomainEvidenceFact)]
        external_facts_sel = [f for f in relevant if isinstance(f, ExternalEvidenceFact)]
        fallback_parts = []
        if project_facts_sel:
            fallback_parts.append(build_grounding_context(project_facts_sel))
        if domain_facts_sel:
            fallback_parts.append(build_domain_grounding_context(domain_facts_sel))
        if external_facts_sel:
            fallback_parts.append(build_external_grounding_context(external_facts_sel))
        return "\n\n".join(fallback_parts) if fallback_parts else ""
    else:
        # Fallback: use retrieve_evidence (which now uses the same split)
        relevant = retrieve_evidence(query, facts + domain_facts, limit=limit)
        project_facts_sel = [f for f in relevant if isinstance(f, EvidenceFact)]
        domain_facts_sel = [f for f in relevant if isinstance(f, DomainEvidenceFact)]
        external_facts_sel = [f for f in relevant if isinstance(f, ExternalEvidenceFact)]
        context_parts = []
        if project_facts_sel:
            context_parts.append(build_grounding_context(project_facts_sel))
        if domain_facts_sel:
            context_parts.append(build_domain_grounding_context(domain_facts_sel))
        if external_facts_sel:
            context_parts.append(build_external_grounding_context(external_facts_sel))
        return "\n\n".join(context_parts) if context_parts else ""
