"""Confidence scoring and publish policy for the avatar_intelligence package."""

from __future__ import annotations

import json
import logging
import sys
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone

from services.avatar_intelligence._learning import _RUN_ID
from services.avatar_intelligence._models import (
    ConfidenceDecision,
    ConfidenceDecisionEvent,
    ConfidenceResult,
    ConfidenceSignals,
)
from services.avatar_intelligence._paths import LEARNING_LOG_PATH as _DEFAULT_LEARNING_LOG_PATH

logger = logging.getLogger(__name__)


def _learning_log_path():
    """Return the current LEARNING_LOG_PATH, respecting monkeypatching on the package."""
    pkg = sys.modules.get("services.avatar_intelligence")
    if pkg is not None:
        return getattr(pkg, "LEARNING_LOG_PATH", _DEFAULT_LEARNING_LOG_PATH)
    return _DEFAULT_LEARNING_LOG_PATH

# Severity weights per reason code — higher means more concern.
_REASON_SEVERITY: dict[str, float] = {
    "fabricated_detail":    0.90,
    "unsupported_numeric":  0.80,
    "unsupported_claim":    0.70,
    "unsupported_dollar":   0.75,
    "unsupported_year":     0.65,
    "speculative":          0.50,
    "unsupported_org":      0.55,
    "project_claim":        0.40,
    "out_of_scope":         0.30,
}
_DEFAULT_REASON_SEVERITY = 0.50

# Per-channel character budgets used for length-pressure normalization.
_CHANNEL_LENGTH_BUDGETS: dict[str, int] = {
    "linkedin": 3000,
    "x":        257,   # 280 - 23 URL chars
    "bluesky":  300,
    "threads":  500,
    "youtube":  500,
    "all":      3000,
}


def extract_confidence_signals(
    *,
    removed_count: int,
    total_sentences: int,
    reason_codes: list[str],
    grounding_facts_count: int,
    max_grounding_facts: int = 5,
    channel: str = "linkedin",
    post_length: int = 0,
    narrative_repetition_score: float = 0.0,
) -> ConfidenceSignals:
    """Extract normalized confidence signals from generation + truth-gate metadata.

    All output values are normalized to [0.0, 1.0].

    Args:
        removed_count:              Sentences removed by truth gate.
        total_sentences:            Total sentences in the draft.
        reason_codes:               Reason codes from removed sentences.
        grounding_facts_count:      Number of evidence facts used in grounding.
        max_grounding_facts:        Upper bound for grounding coverage ratio.
        channel:                    Target channel (used for length-budget lookup).
        post_length:                Final post character count.
        narrative_repetition_score: Phase 1D signal; pass 0.0 until implemented.
    """
    severities = [_REASON_SEVERITY.get(rc, _DEFAULT_REASON_SEVERITY) for rc in reason_codes]
    max_severity = max(severities, default=0.0)

    coverage = (
        min(grounding_facts_count / max_grounding_facts, 1.0)
        if max_grounding_facts > 0
        else 0.0
    )

    claim_pressure = (
        min(removed_count / total_sentences, 1.0) if total_sentences > 0 else 0.0
    )

    budget = _CHANNEL_LENGTH_BUDGETS.get(channel, 3000)
    length_pressure = min(post_length / budget, 1.0) if budget > 0 else 0.0

    return ConfidenceSignals(
        truth_gate_removed_count=removed_count,
        truth_gate_reason_severity=max_severity,
        grounding_coverage_ratio=coverage,
        unsupported_claim_pressure=claim_pressure,
        channel_length_pressure=length_pressure,
        narrative_repetition_score=narrative_repetition_score,
    )


def score_confidence(signals: ConfidenceSignals) -> ConfidenceResult:
    """Compute a deterministic confidence score from normalized signals.

    Scoring formula (contributions sum against base 1.0):
    - truth_gate_reason_severity   : up to -0.35
    - unsupported_claim_pressure   : up to -0.30
    - truth_gate_removed_count     : up to -0.15 (normalized /10)
    - channel_length_pressure      : up to -0.10
    - narrative_repetition_score   : up to -0.10
    - grounding_coverage_ratio     : up to +0.10 (bonus)

    Level thresholds: high ≥ 0.70, medium ≥ 0.40, low < 0.40.
    """
    contributions: dict[str, float] = {
        "truth_gate_reason_severity":  -signals.truth_gate_reason_severity  * 0.35,
        "unsupported_claim_pressure":  -signals.unsupported_claim_pressure  * 0.30,
        "truth_gate_removed_count":    -min(signals.truth_gate_removed_count / 10.0, 1.0) * 0.15,
        "grounding_coverage_ratio":    +signals.grounding_coverage_ratio    * 0.10,
        "channel_length_pressure":     -signals.channel_length_pressure     * 0.10,
        "narrative_repetition_score":  -signals.narrative_repetition_score  * 0.10,
    }

    raw = 1.0 + sum(contributions.values())
    score = round(max(0.0, min(1.0, raw)), 4)

    if score >= 0.70:
        level = "high"
    elif score >= 0.40:
        level = "medium"
    else:
        level = "low"

    negative = {k: v for k, v in contributions.items() if v < 0}
    dominant = min(negative, key=lambda k: negative[k]) if negative else None

    return ConfidenceResult(
        score=score,
        level=level,
        signals=signals,
        dominant_signal=dominant,
    )


def decide_publish_mode(
    policy: str,
    confidence: ConfidenceResult,
    requested_mode: str,
) -> ConfidenceDecision:
    """Apply config §7.2 policy matrix to produce a publish route decision.

    Policy matrix:
    - strict:       high → post; medium → idea; low → block
    - balanced:     high/medium → post; low → idea
    - draft-first:  all → idea

    *requested_mode* is the caller's intent — recorded in the reason string
    for traceability but does not override the policy decision.

    Falls back to 'balanced' behaviour for unrecognised policy values.
    """
    level = confidence.level

    if policy == "draft-first":
        return ConfidenceDecision(
            route="idea",
            reason=f"draft-first policy: all outputs buffered as ideas (score={confidence.score:.2f})",
            policy=policy,
            confidence_level=level,
        )

    if policy == "strict":
        if level == "high":
            return ConfidenceDecision(
                route="post",
                reason=f"strict policy: high confidence ({confidence.score:.2f}) → direct post",
                policy=policy,
                confidence_level=level,
            )
        elif level == "medium":
            return ConfidenceDecision(
                route="idea",
                reason=f"strict policy: medium confidence ({confidence.score:.2f}) → idea for review",
                policy=policy,
                confidence_level=level,
            )
        else:
            return ConfidenceDecision(
                route="block",
                reason=f"strict policy: low confidence ({confidence.score:.2f}) → blocked",
                policy=policy,
                confidence_level=level,
            )

    # balanced (default — also catches unknown policy values)
    if policy not in ("strict", "balanced", "draft-first"):
        logger.warning("Unknown confidence policy '%s'; falling back to 'balanced'", policy)

    if level in ("high", "medium"):
        return ConfidenceDecision(
            route="post",
            reason=f"balanced policy: {level} confidence ({confidence.score:.2f}) → direct post",
            policy="balanced",
            confidence_level=level,
        )
    return ConfidenceDecision(
        route="idea",
        reason=f"balanced policy: low confidence ({confidence.score:.2f}) → idea for review",
        policy="balanced",
        confidence_level=level,
    )


def record_confidence_decision(
    *,
    decision: ConfidenceDecision,
    confidence: ConfidenceResult,
    channel: str,
    article_ref: str,
) -> None:
    """Append one ConfidenceDecisionEvent to learning_log.jsonl (T3.6).

    Failures emit a warning and do not interrupt the publish path.
    """
    event = ConfidenceDecisionEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        channel=channel,
        route=decision.route,
        policy=decision.policy,
        confidence_score=confidence.score,
        confidence_level=confidence.level,
        dominant_signal=confidence.dominant_signal,
        reason=decision.reason,
        article_ref=article_ref,
        run_id=_RUN_ID,
    )
    try:
        log_path = _learning_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(event)) + "\n")
    except OSError as exc:
        logger.warning("Learning log write failed (confidence event, continuing): %s", exc)
