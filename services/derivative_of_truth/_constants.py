"""Constants for the Derivative of Truth scoring subsystem."""

from __future__ import annotations

# Evidence type hierarchy — stronger evidence carries higher weight
EVIDENCE_TYPE_PRIMARY = "primary"
EVIDENCE_TYPE_SECONDARY = "secondary"
EVIDENCE_TYPE_DERIVED = "derived"
EVIDENCE_TYPE_PATTERN = "pattern"

EVIDENCE_WEIGHTS: dict[str, float] = {
    EVIDENCE_TYPE_PRIMARY: 1.0,
    EVIDENCE_TYPE_SECONDARY: 0.75,
    EVIDENCE_TYPE_DERIVED: 0.5,
    EVIDENCE_TYPE_PATTERN: 0.25,
}

# Reasoning type hierarchy
REASONING_TYPE_LOGICAL = "logical"
REASONING_TYPE_STATISTICAL = "statistical"
REASONING_TYPE_ANALOGY = "analogy"
REASONING_TYPE_PATTERN = "pattern"

REASONING_WEIGHTS: dict[str, float] = {
    REASONING_TYPE_LOGICAL: 1.0,
    REASONING_TYPE_STATISTICAL: 0.85,
    REASONING_TYPE_ANALOGY: 0.55,
    REASONING_TYPE_PATTERN: 0.35,
}

# Uncertainty penalty sources
UNCERTAINTY_CONFLICT = "conflict"
UNCERTAINTY_LONG_CHAIN = "long_chain"
UNCERTAINTY_SPARSE = "sparse"
UNCERTAINTY_LOW_CREDIBILITY = "low_credibility"

# Claims with truth_gradient below this threshold are flagged as weak
TRUTH_GRADIENT_FLAG_THRESHOLD: float = 0.35

# Phase 1 & 2: PLN-enhanced mode configuration
USE_PLN_ENHANCED_SCORING: bool = True  # Toggle PLN vs. legacy scoring
TRACK_TRUTH_TRAJECTORY: bool = True  # Enable dT/dt trajectory tracking

# Weights for the composite truth gradient formula.
_W_EVIDENCE = 0.40
_W_REASONING = 0.35
_W_CREDIBILITY = 0.25

# With overlap: 0.30*ev + 0.25*reasoning + 0.20*cred + 0.25*overlap
_W_EVIDENCE_OL = 0.30
_W_REASONING_OL = 0.25
_W_CREDIBILITY_OL = 0.20
_W_OVERLAP = 0.25

# Uncertainty penalty caps
_MAX_UNCERTAINTY_PENALTY = 0.5
_CONFLICT_PENALTY = 0.20
_LONG_CHAIN_PENALTY = 0.10
_SPARSE_PENALTY = 0.15
_LOW_CRED_PENALTY = 0.10
