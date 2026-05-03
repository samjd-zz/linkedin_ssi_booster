"""Truth gradient scoring core logic."""

from __future__ import annotations

import hashlib
import logging
from typing import Optional

from services.derivative_of_truth._constants import (
    EVIDENCE_WEIGHTS,
    REASONING_WEIGHTS,
    TRACK_TRUTH_TRAJECTORY,
    TRUTH_GRADIENT_FLAG_THRESHOLD,
    UNCERTAINTY_CONFLICT,
    UNCERTAINTY_LONG_CHAIN,
    UNCERTAINTY_LOW_CREDIBILITY,
    UNCERTAINTY_SPARSE,
    USE_PLN_ENHANCED_SCORING,
    _CONFLICT_PENALTY,
    _LONG_CHAIN_PENALTY,
    _LOW_CRED_PENALTY,
    _MAX_UNCERTAINTY_PENALTY,
    _SPARSE_PENALTY,
    _W_CREDIBILITY,
    _W_CREDIBILITY_OL,
    _W_EVIDENCE,
    _W_EVIDENCE_OL,
    _W_OVERLAP,
    _W_REASONING,
    _W_REASONING_OL,
)
from services.derivative_of_truth._models import (
    EvidencePath,
    TruthGradientResult,
    TruthTrajectory,
)
from services.pln_inference import (
    PLNTruthValue,
    aggregate_evidence_paths,
    compute_evidence_weight,
    compute_reasoning_weight,
)

logger = logging.getLogger(__name__)

# Global trajectory storage (in-memory for now, could be persisted to JSON/DB)
_TRAJECTORY_STORE: dict[str, TruthTrajectory] = {}


def score_claim_with_truth_gradient(
    claim: str,
    evidence_paths: list[EvidencePath],
    raw_confidence: float = 0.5,
    use_pln: bool = USE_PLN_ENHANCED_SCORING,
    track_trajectory: bool = TRACK_TRUTH_TRAJECTORY,
) -> TruthGradientResult:
    """Compute the truth gradient score for *claim* given its *evidence_paths*.
    
    Args:
        claim: The claim text to score
        evidence_paths: Supporting/undermining evidence paths
        raw_confidence: Prior confidence estimate [0,1]
        use_pln: If True, use PLN-enhanced scoring instead of legacy weights
                 (defaults to USE_PLN_ENHANCED_SCORING constant)
        track_trajectory: If True, store trajectory point for dT/dt tracking
                         (defaults to TRACK_TRUTH_TRAJECTORY constant)
    
    Returns:
        TruthGradientResult with truth_gradient, uncertainty, and optional truth_derivative
    """
    if not evidence_paths:
        result = TruthGradientResult(
            truth_gradient=0.0,
            uncertainty=1.0,
            confidence_penalty=max(0.0, raw_confidence),
            evidence_paths=[],
            uncertainty_sources=[UNCERTAINTY_SPARSE],
            flagged=True,
            explanation=(
                "No evidence paths provided. "
                "Claim cannot be supported by available knowledge."
            ),
            pln_mode=use_pln,
        )
        logger.debug(
            "TruthGradient[no-evidence] claim='%s...': gradient=0.0 flagged=True",
            claim[:60],
        )
        if track_trajectory:
            _update_trajectory(claim, result)
        return result

    if use_pln:
        # Phase 1: PLN-enhanced scoring
        base_gradient, evidence_paths = _score_with_pln(evidence_paths)
    else:
        # Legacy scoring with fixed weights
        base_gradient = _score_legacy(evidence_paths)


    total_penalty = 0.0
    uncertainty_sources: list[str] = []

    avg_path_uncertainty = sum(p.uncertainty for p in evidence_paths) / len(evidence_paths)
    if avg_path_uncertainty > 0.0:
        total_penalty += avg_path_uncertainty

    all_sources = {p.source for p in evidence_paths}
    has_conflicts = any(
        len(set(p.conflicts_with) & all_sources) > 0
        for p in evidence_paths
    )
    if has_conflicts:
        total_penalty += _CONFLICT_PENALTY
        uncertainty_sources.append(UNCERTAINTY_CONFLICT)

    max_chain = max(p.chain_length for p in evidence_paths)
    if max_chain > 3:
        extra_hops = max_chain - 3
        chain_penalty = _LONG_CHAIN_PENALTY * extra_hops
        total_penalty += chain_penalty
        uncertainty_sources.append(UNCERTAINTY_LONG_CHAIN)

    if len(evidence_paths) < 2:
        total_penalty += _SPARSE_PENALTY
        uncertainty_sources.append(UNCERTAINTY_SPARSE)

    low_cred_count = sum(1 for p in evidence_paths if p.credibility < 0.3)
    if low_cred_count > 0:
        total_penalty += _LOW_CRED_PENALTY * (low_cred_count / len(evidence_paths))
        uncertainty_sources.append(UNCERTAINTY_LOW_CREDIBILITY)

    clamped_penalty = min(total_penalty, _MAX_UNCERTAINTY_PENALTY)

    truth_gradient = base_gradient * (1.0 - clamped_penalty)
    truth_gradient = max(0.0, min(1.0, truth_gradient))

    confidence_penalty = max(0.0, raw_confidence - truth_gradient)

    flagged = truth_gradient < TRUTH_GRADIENT_FLAG_THRESHOLD

    explanation = _build_explanation(
        claim=claim,
        base_gradient=base_gradient,
        clamped_penalty=clamped_penalty,
        truth_gradient=truth_gradient,
        uncertainty_sources=uncertainty_sources,
        evidence_paths=evidence_paths,
        flagged=flagged,
    )

    logger.debug(
        "TruthGradient[%s] claim='%s...': base=%.3f penalty=%.3f gradient=%.3f flagged=%s",
        "PLN" if use_pln else "legacy",
        claim[:60],
        base_gradient,
        clamped_penalty,
        truth_gradient,
        flagged,
    )

    result = TruthGradientResult(
        truth_gradient=truth_gradient,
        uncertainty=clamped_penalty,
        confidence_penalty=confidence_penalty,
        evidence_paths=evidence_paths,
        uncertainty_sources=uncertainty_sources,
        flagged=flagged,
        explanation=explanation,
        pln_mode=use_pln,
    )
    
    # Phase 2: Track trajectory and compute dT/dt
    if track_trajectory:
        _update_trajectory(claim, result)
        trajectory = _get_trajectory(claim)
        if trajectory:
            result.truth_derivative = trajectory.current_derivative()
    
    return result


def _build_explanation(
    claim: str,
    base_gradient: float,
    clamped_penalty: float,
    truth_gradient: float,
    uncertainty_sources: list[str],
    evidence_paths: list[EvidencePath],
    flagged: bool,
) -> str:
    """Build a concise human-readable explanation of the truth gradient."""
    _ = claim
    n_paths = len(evidence_paths)
    ev_types = {p.evidence_type for p in evidence_paths}
    re_types = {p.reasoning_type for p in evidence_paths}
    avg_cred = (
        sum(p.credibility for p in evidence_paths) / n_paths if n_paths else 0.0
    )

    overlap_paths = [p for p in evidence_paths if p.overlap > 0.0]
    avg_overlap = (
        sum(p.overlap for p in overlap_paths) / len(overlap_paths)
        if overlap_paths else None
    )

    overlap_note = (
        f"; avg claim-evidence alignment: {avg_overlap:.2f}"
        if avg_overlap is not None
        else "; claim-evidence alignment: not computed"
    )
    parts = [
        f"Base gradient {base_gradient:.3f} from {n_paths} evidence path(s) "
        f"[types: {', '.join(sorted(ev_types))}; "
        f"reasoning: {', '.join(sorted(re_types))}; "
        f"avg credibility: {avg_cred:.2f}{overlap_note}].",
    ]
    if clamped_penalty > 0:
        parts.append(
            f"Uncertainty penalty {clamped_penalty:.3f} "
            f"({', '.join(uncertainty_sources) if uncertainty_sources else 'path uncertainty'})."
        )
    parts.append(f"Final truth gradient: {truth_gradient:.3f}.")
    if flagged:
        parts.append(
            f"Claim flagged - gradient below threshold ({TRUTH_GRADIENT_FLAG_THRESHOLD})."
        )
    return " ".join(parts)


def _score_legacy(evidence_paths: list[EvidencePath]) -> float:
    """Legacy scoring with fixed EVIDENCE_WEIGHTS and REASONING_WEIGHTS."""
    path_scores: list[float] = []
    for path in evidence_paths:
        ev_weight = EVIDENCE_WEIGHTS.get(path.evidence_type, 0.25)
        re_weight = REASONING_WEIGHTS.get(path.reasoning_type, 0.35)
        if path.overlap > 0.0:
            path_score = (
                _W_EVIDENCE_OL * ev_weight
                + _W_REASONING_OL * re_weight
                + _W_CREDIBILITY_OL * path.credibility
                + _W_OVERLAP * path.overlap
            )
        else:
            path_score = (
                _W_EVIDENCE * ev_weight
                + _W_REASONING * re_weight
                + _W_CREDIBILITY * path.credibility
            )
        path_scores.append(path_score)

    return sum(path_scores) / len(path_scores)


def _score_with_pln(
    evidence_paths: list[EvidencePath],
) -> tuple[float, list[EvidencePath]]:
    """PLN-enhanced scoring using dynamic inference formulas.
    
    Returns:
        (base_gradient, updated_evidence_paths with PLN truth values)
    """
    pln_tvs: list[PLNTruthValue] = []
    
    for path in evidence_paths:
        # Compute PLN truth value for evidence
        ev_tv = compute_evidence_weight(
            evidence_type=path.evidence_type,
            base_strength=1.0,
            source_credibility=path.credibility,
            chain_length=path.chain_length,
        )
        
        # Compute PLN truth value for reasoning
        re_tv = compute_reasoning_weight(
            reasoning_type=path.reasoning_type,
            premise_confidence=ev_tv.confidence,
        )
        
        # Combine evidence and reasoning (simplified: take average weighted by confidence)
        combined_strength = (
            ev_tv.strength * ev_tv.confidence + re_tv.strength * re_tv.confidence
        ) / (ev_tv.confidence + re_tv.confidence)
        combined_confidence = (ev_tv.confidence + re_tv.confidence) / 2.0
        
        # Factor in overlap if available
        if path.overlap > 0.0:
            # Overlap boosts strength proportionally
            combined_strength = combined_strength * (0.75 + 0.25 * path.overlap)
        
        pln_tv = PLNTruthValue(combined_strength, combined_confidence)
        pln_tvs.append(pln_tv)
        
        # Store PLN values in the evidence path for explainability
        path.pln_strength = pln_tv.strength
        path.pln_confidence = pln_tv.confidence
    
    # Aggregate all evidence paths using PLN revision
    aggregated = aggregate_evidence_paths(pln_tvs)
    
    # Base gradient is the aggregated strength weighted by confidence
    base_gradient = aggregated.strength * aggregated.confidence
    
    return base_gradient, evidence_paths


def _compute_claim_hash(claim: str) -> str:
    """Compute stable hash for claim text."""
    return hashlib.sha256(claim.encode("utf-8")).hexdigest()[:16]


def _get_trajectory(claim: str) -> Optional[TruthTrajectory]:
    """Retrieve truth trajectory for a claim."""
    claim_hash = _compute_claim_hash(claim)
    return _TRAJECTORY_STORE.get(claim_hash)


def _update_trajectory(claim: str, result: TruthGradientResult) -> None:
    """Update truth trajectory with a new gradient point."""
    claim_hash = _compute_claim_hash(claim)
    
    if claim_hash not in _TRAJECTORY_STORE:
        _TRAJECTORY_STORE[claim_hash] = TruthTrajectory(
            claim_hash=claim_hash,
            claim_text=claim,
        )
    
    trajectory = _TRAJECTORY_STORE[claim_hash]
    trajectory.add_point(
        truth_gradient=result.truth_gradient,
        uncertainty=result.uncertainty,
        evidence_count=len(result.evidence_paths),
        flagged=result.flagged,
    )
    
    logger.debug(
        "Trajectory updated for claim='%s...': %d points, dT/dt=%.4f",
        claim[:60],
        len(trajectory.history),
        trajectory.current_derivative() or 0.0,
    )


def get_all_trajectories() -> dict[str, TruthTrajectory]:
    """Get all stored truth trajectories (for testing/inspection)."""
    return _TRAJECTORY_STORE.copy()


def clear_trajectories() -> None:
    """Clear all stored trajectories (for testing)."""
    _TRAJECTORY_STORE.clear()
