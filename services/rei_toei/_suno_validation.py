"""Derivative-of-Truth validation for Rei Toei Suno lyrics."""

import logging
from typing import Dict, List, TYPE_CHECKING

from ._config import ReiToeiConfig
from ._models import Lyrics, LyricsValidationResult

if TYPE_CHECKING:
    from services.avatar_intelligence._models import ExtractedEvidenceFact

logger = logging.getLogger(__name__)


def validate_lyrics_with_dot(
    lyrics: Lyrics,
    extracted_facts: "List[ExtractedEvidenceFact]",
) -> LyricsValidationResult:
    """
    Validate lyrics against extracted knowledge using Derivative of Truth (DoT) scoring.

    Follows the same pattern as curator.py: accepts a flat list of ExtractedEvidenceFact
    objects (the normalized form returned by normalize_extracted_facts()), not the raw
    ExtractedKnowledgeGraph container.
    """
    from services.derivative_of_truth._scoring import score_claim_with_truth_gradient
    from services.derivative_of_truth._models import EvidencePath

    logger.info("Validating lyrics with Derivative of Truth")

    config = ReiToeiConfig()

    if not config.dot_validation_enabled:
        logger.info("DoT validation disabled - skipping")
        return LyricsValidationResult(
            valid=True,
            flagged_claims=[],
            truth_gradients={},
            overall_truth_score=1.0,
            warnings=["DoT validation disabled"]
        )

    all_text = "\n".join([
        lyrics.intro or "",
        lyrics.verse_1,
        lyrics.pre_chorus or "",
        lyrics.chorus,
        lyrics.verse_2,
        lyrics.drop or "",
        lyrics.bridge,
        lyrics.solo or "",
        lyrics.outro or ""
    ])

    sentences = [s.strip() for s in all_text.split("\n") if s.strip()]

    technical_keywords = [
        "algorithm", "data", "system", "process", "code", "compile",
        "execute", "buffer", "cache", "thread", "async", "parallel",
        "neural", "model", "train", "inference", "optimize", "kernel",
        "memory", "cpu", "gpu", "bandwidth", "latency", "throughput"
    ]

    claims = []
    for sentence in sentences:
        sentence_lower = sentence.lower()
        if any(keyword in sentence_lower for keyword in technical_keywords):
            if not any(metaphor in sentence_lower for metaphor in [
                "collide", "fade", "whisper", "echo", "shimmer", "pulse"
            ]):
                claims.append(sentence)

    if not claims:
        logger.info("No technical claims found in lyrics - validation passed")
        return LyricsValidationResult(
            valid=True,
            flagged_claims=[],
            truth_gradients={},
            overall_truth_score=1.0,
            warnings=["No technical claims detected in lyrics"]
        )

    logger.info(f"Validating {len(claims)} technical claims from lyrics")

    flagged_claims = []
    truth_gradients: Dict[str, float] = {}

    for claim in claims:
        relevant_facts = []
        claim_lower = claim.lower()

        for fact in extracted_facts:
            fact_statement = getattr(fact, "statement", "") or ""
            fact_keywords = set(fact_statement.lower().split())
            claim_keywords = set(claim_lower.split())

            overlap = len(fact_keywords & claim_keywords)
            if overlap >= 2:
                relevant_facts.append((fact, overlap))

        relevant_facts.sort(key=lambda x: x[1], reverse=True)

        evidence_paths = []
        for fact, overlap in relevant_facts[:5]:
            credibility_map = {"high": 0.9, "medium": 0.7, "low": 0.5}
            fact_confidence = getattr(fact, "confidence", "medium")
            credibility = credibility_map.get(fact_confidence, 0.7)

            fact_statement = getattr(fact, "statement", "") or ""
            total_keywords = len(set(claim_lower.split()) | set(fact_statement.lower().split()))
            alignment = overlap / total_keywords if total_keywords > 0 else 0.0

            fact_ref = getattr(fact, "evidence_id", None) or getattr(fact, "source_fact_id", "unknown")

            evidence_path = EvidencePath(
                source=f"extracted_fact_{fact_ref}",
                evidence_type="external_source",
                reasoning_type="direct_evidence",
                credibility=credibility,
                uncertainty=0.1,
                chain_length=1,
                conflicts_with=[],
                overlap=alignment
            )
            evidence_paths.append(evidence_path)

        if evidence_paths:
            result = score_claim_with_truth_gradient(
                claim=claim,
                evidence_paths=evidence_paths,
                raw_confidence=0.5
            )

            truth_gradients[claim] = result.truth_gradient

            if result.flagged:
                flagged_claims.append(claim)
                logger.warning(
                    f"Claim flagged (gradient={result.truth_gradient:.3f}): {claim[:80]}..."
                )
        else:
            truth_gradients[claim] = 0.0
            flagged_claims.append(claim)
            logger.warning(f"No evidence found for claim: {claim[:80]}...")

    overall_truth_score = (
        sum(truth_gradients.values()) / len(truth_gradients)
        if truth_gradients else 0.0
    )

    valid = overall_truth_score >= config.dot_min_truth_gradient or not flagged_claims

    warnings = []
    if flagged_claims:
        warnings.append(
            f"{len(flagged_claims)} claim(s) flagged with low truth gradient "
            f"(threshold: {config.dot_min_truth_gradient})"
        )

    result = LyricsValidationResult(
        valid=valid,
        flagged_claims=flagged_claims,
        truth_gradients=truth_gradients,
        overall_truth_score=overall_truth_score,
        warnings=warnings
    )

    logger.info(
        f"Lyrics validation complete: valid={valid}, "
        f"overall_score={overall_truth_score:.3f}, "
        f"flagged={len(flagged_claims)}"
    )

    return result
