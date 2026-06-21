"""
DoT (Derivative of Truth) evidence path builders for the content curator.
Converts persona facts, articles, and extracted knowledge into EvidencePath
objects used for truth gradient scoring.
"""

import re
from typing import Any
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Publisher credibility tiers (article_to_evidence_path)
# ---------------------------------------------------------------------------

_TIER_HIGH: frozenset[str] = frozenset({
    "thenewstack.io", "martinfowler.com", "engineering.atspotify.com",
    "netflixtechblog.com", "research.google", "arxiv.org", "huggingface.co",
})
_TIER_MED: frozenset[str] = frozenset({
    "medium.com", "dev.to", "hackernoon.com", "infoq.com",
    "dzone.com", "towardsdatascience.com",
})


def fact_to_evidence_path(fact: Any, claim_text: str) -> Any:
    """Convert a ProjectFact to a real EvidencePath with differentiated scoring.

    - avatar:* facts → primary evidence, logical reasoning, credibility scaled
      by years of direct experience parsed from the years field
    - domain:* facts → secondary evidence, statistical reasoning, credibility
      scaled by tag count (proxy for fact specificity)
    - uncertainty: derived from token overlap between fact details and claim
      text — lower overlap means the fact is less directly relevant.
    """
    from services.derivative_of_truth import (
        EvidencePath,
        EVIDENCE_TYPE_PRIMARY,
        EVIDENCE_TYPE_SECONDARY,
        REASONING_TYPE_LOGICAL,
        REASONING_TYPE_STATISTICAL,
    )

    source = getattr(fact, "source", str(fact))
    is_avatar = source.startswith("avatar:")
    is_domain = source.startswith("domain:")
    # Domain knowledge is user-curated (1st/2nd-hand) — treat as primary, logical
    evidence_type = EVIDENCE_TYPE_PRIMARY if (is_avatar or is_domain) else EVIDENCE_TYPE_SECONDARY
    reasoning_type = REASONING_TYPE_LOGICAL if (is_avatar or is_domain) else REASONING_TYPE_STATISTICAL

    # Credibility
    if is_avatar:
        years_str = getattr(fact, "years", "") or ""
        year_nums = re.findall(r"\b(19|20)\d{2}\b", years_str)
        if len(year_nums) >= 2:
            span = abs(int(year_nums[-1]) - int(year_nums[0]))
        else:
            nums = re.findall(r"\d+", years_str)
            span = int(nums[0]) if nums and "year" in years_str.lower() else 0
        if span >= 10:
            credibility = 0.95
        elif span >= 6:
            credibility = 0.90
        elif span >= 3:
            credibility = 0.85
        else:
            credibility = 0.80
    elif is_domain:
        # User-curated domain knowledge — just under persona, scaled by tag specificity
        tag_count = len(getattr(fact, "tags", set()) or set())
        credibility = 0.88 if tag_count >= 6 else (0.82 if tag_count >= 3 else 0.76)
    else:
        tag_count = len(getattr(fact, "tags", set()) or set())
        credibility = 0.72 if tag_count >= 6 else (0.65 if tag_count >= 3 else 0.58)

    # Uncertainty via token overlap
    details = getattr(fact, "details", "") or ""
    claim_tokens = set(re.findall(r"[a-z]{3,}", claim_text.lower()))
    fact_tokens = set(re.findall(r"[a-z]{3,}", details.lower()))
    if claim_tokens:
        overlap = len(claim_tokens & fact_tokens) / len(claim_tokens)
        uncertainty = round(max(0.0, 0.25 * (1.0 - min(overlap * 3, 1.0))), 3)
    else:
        overlap = 0.0
        uncertainty = 0.10

    return EvidencePath(
        source=source,
        evidence_type=evidence_type,
        reasoning_type=reasoning_type,
        credibility=credibility,
        uncertainty=uncertainty,
        chain_length=1,
        overlap=round(min(overlap * 3, 1.0), 3) if claim_tokens else 0.0,
    )


def article_to_evidence_path(article: dict[str, Any], claim_text: str) -> Any:
    """Convert the source article into an EvidencePath for DoT scoring.

    Credibility is based on publisher tier; uncertainty is derived from
    token overlap between the article summary and the generated claim text.
    """
    from services.derivative_of_truth import (
        EvidencePath,
        EVIDENCE_TYPE_SECONDARY,
        REASONING_TYPE_STATISTICAL,
    )

    link: str = article.get("link", "")
    try:
        domain = urlparse(link).netloc.lower().lstrip("www.")
    except Exception:
        domain = ""

    if domain in _TIER_HIGH:
        credibility = 0.82
    elif domain in _TIER_MED:
        credibility = 0.65
    elif domain:
        credibility = 0.55
    else:
        credibility = 0.45

    summary = article.get("summary", "") or ""
    claim_tokens = set(re.findall(r"[a-z]{3,}", claim_text.lower()))
    art_tokens = set(re.findall(r"[a-z]{3,}", summary.lower()))
    if claim_tokens and art_tokens:
        overlap = len(claim_tokens & art_tokens) / len(claim_tokens)
        uncertainty = round(max(0.05, 0.30 * (1.0 - min(overlap * 2, 1.0))), 3)
    else:
        overlap = 0.0
        uncertainty = 0.20

    source_label = f"article:{domain}" if domain else "article:unknown"
    return EvidencePath(
        source=source_label,
        evidence_type=EVIDENCE_TYPE_SECONDARY,
        reasoning_type=REASONING_TYPE_STATISTICAL,
        credibility=credibility,
        uncertainty=uncertainty,
        chain_length=1,
        overlap=round(min(overlap * 2, 1.0), 3) if (claim_tokens and art_tokens) else 0.0,
    )


def extracted_fact_to_evidence_path(extracted_fact: Any, claim_text: str) -> Any:
    """Convert one extracted knowledge fact into an EvidencePath for DoT scoring."""
    from services.derivative_of_truth import (
        EvidencePath,
        EVIDENCE_TYPE_SECONDARY,
        REASONING_TYPE_STATISTICAL,
    )

    confidence = str(getattr(extracted_fact, "confidence", "medium") or "medium").lower()
    credibility = {"high": 0.85, "medium": 0.65, "low": 0.45}.get(confidence, 0.65)

    statement = str(getattr(extracted_fact, "statement", "") or "")
    source_id = str(getattr(extracted_fact, "source_fact_id", "unknown") or "unknown")
    source = f"extracted_knowledge:{source_id[:8]}"

    claim_tokens = set(re.findall(r"[a-z]{3,}", claim_text.lower()))
    fact_tokens = set(re.findall(r"[a-z]{3,}", statement.lower()))
    overlap = 0.0
    if claim_tokens and fact_tokens:
        overlap = len(claim_tokens & fact_tokens) / len(claim_tokens)

    uncertainty = round(max(0.05, 0.35 * (1.0 - min(overlap * 3, 1.0))), 3)

    return EvidencePath(
        source=source,
        evidence_type=EVIDENCE_TYPE_SECONDARY,
        reasoning_type=REASONING_TYPE_STATISTICAL,
        credibility=credibility,
        uncertainty=uncertainty,
        chain_length=1,
        overlap=round(min(overlap * 3, 1.0), 3) if claim_tokens else 0.0,
    )


def external_fact_to_evidence_path(external_fact: Any, claim_text: str) -> Any:
    """Convert one Katzilla external fact into an EvidencePath for DoT scoring."""
    from services.derivative_of_truth import (
        EvidencePath,
        EVIDENCE_TYPE_SECONDARY,
        REASONING_TYPE_STATISTICAL,
    )

    confidence = str(getattr(external_fact, "confidence", "medium") or "medium").lower()
    credibility = {"high": 0.78, "medium": 0.64, "low": 0.50}.get(confidence, 0.64)

    statement = str(getattr(external_fact, "statement", "") or "")
    agent = str(getattr(external_fact, "agent", "unknown") or "unknown")
    action = str(getattr(external_fact, "action", "unknown") or "unknown")
    source = f"katzilla:{agent}/{action}"

    claim_tokens = set(re.findall(r"[a-z]{3,}", claim_text.lower()))
    fact_tokens = set(re.findall(r"[a-z]{3,}", statement.lower()))
    overlap = 0.0
    if claim_tokens and fact_tokens:
        overlap = len(claim_tokens & fact_tokens) / len(claim_tokens)

    uncertainty_hint = float(getattr(external_fact, "uncertainty", 0.0) or 0.0)
    overlap_uncertainty = max(0.05, 0.28 * (1.0 - min(overlap * 2.5, 1.0)))
    uncertainty = round(min(0.60, max(overlap_uncertainty, uncertainty_hint)), 3)

    return EvidencePath(
        source=source,
        evidence_type=EVIDENCE_TYPE_SECONDARY,
        reasoning_type=REASONING_TYPE_STATISTICAL,
        credibility=credibility,
        uncertainty=uncertainty,
        chain_length=1,
        overlap=round(min(overlap * 2.5, 1.0), 3) if claim_tokens else 0.0,
    )
