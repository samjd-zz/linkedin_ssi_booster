"""Unit tests for PLN truth-value inference formulas."""

import pytest

from services.pln_inference import (
    MAX_CONFIDENCE,
    MIN_CONFIDENCE,
    PLNTruthValue,
    aggregate_evidence_paths,
    compute_evidence_weight,
    compute_reasoning_weight,
    pln_abduction,
    pln_deduction,
    pln_induction,
    pln_revision,
)


def test_truth_value_repr_formats_strength_and_confidence() -> None:
    assert repr(PLNTruthValue(0.75, 0.5)) == "<s=0.750, c=0.500>"


def test_deduction_multiplies_strength_and_combines_confidence() -> None:
    result = pln_deduction(PLNTruthValue(0.8, 0.7), PLNTruthValue(0.5, 0.6))

    assert result.strength == pytest.approx(0.4)
    assert result.confidence == pytest.approx((0.7 * 0.6) / (0.7 + 0.6 - 0.7 * 0.6))


def test_deduction_floors_zero_confidence_and_caps_overconfidence() -> None:
    zero = pln_deduction(PLNTruthValue(0.8, 0.0), PLNTruthValue(0.6, 0.0))
    high = pln_deduction(PLNTruthValue(0.8, 1.0), PLNTruthValue(0.6, 1.0))

    assert zero.confidence == MIN_CONFIDENCE
    assert high.confidence == MAX_CONFIDENCE


@pytest.mark.parametrize(
    ("observations", "total_count", "expected_strength", "expected_confidence"),
    [
        ([], 5, 0.5, MIN_CONFIDENCE),
        ([PLNTruthValue(0.9, 0.8)], 0, 0.5, MIN_CONFIDENCE),
        (
            [PLNTruthValue(1.0, 1.0), PLNTruthValue(0.0, 1.0)],
            2,
            0.5,
            2 / 3,
        ),
    ],
)
def test_induction_handles_empty_inputs_and_applies_smoothing(
    observations: list[PLNTruthValue],
    total_count: int,
    expected_strength: float,
    expected_confidence: float,
) -> None:
    result = pln_induction(observations, total_count)

    assert result.strength == pytest.approx(expected_strength)
    assert result.confidence == pytest.approx(expected_confidence)


def test_induction_uses_confidence_weighted_observation_strength() -> None:
    result = pln_induction(
        [PLNTruthValue(1.0, 0.9), PLNTruthValue(0.0, 0.1)],
        total_count=4,
    )

    weighted_average = 0.9
    assert result.strength == pytest.approx((weighted_average * 2 + 1) / 6)
    assert result.confidence == pytest.approx(0.8)


@pytest.mark.parametrize(
    ("observation", "prior", "expected_strength"),
    [
        (PLNTruthValue(0.8, 0.9), 0.5, 0.8),
        (PLNTruthValue(1.0, 0.8), 0.0, 0.0),
        (PLNTruthValue(0.2, 0.6), 0.0, 0.0),
        (PLNTruthValue(0.2, 0.6), 1.0, 1.0),
    ],
)
def test_abduction_computes_posterior_and_prior_confidence(
    observation: PLNTruthValue, prior: float, expected_strength: float,
) -> None:
    result = pln_abduction(observation, hypothesis_prior=prior)

    assert result.strength == pytest.approx(expected_strength)
    assert result.confidence == pytest.approx(max(MIN_CONFIDENCE, observation.confidence * 0.5))


def test_revision_uses_confidence_weighted_strength_and_combines_evidence() -> None:
    result = pln_revision(PLNTruthValue(0.8, 0.6), PLNTruthValue(0.2, 0.4))

    assert result.strength == pytest.approx(0.56)
    assert result.confidence == pytest.approx(1.0 / (1 + 0.24))


def test_revision_handles_zero_confidence_and_caps_combined_confidence() -> None:
    no_evidence = pln_revision(PLNTruthValue(0.1, 0.0), PLNTruthValue(0.9, 0.0))
    strong_evidence = pln_revision(PLNTruthValue(0.1, 1.0), PLNTruthValue(0.9, 1.0))

    assert no_evidence == PLNTruthValue(0.5, MIN_CONFIDENCE)
    assert strong_evidence.confidence == MAX_CONFIDENCE


@pytest.mark.parametrize(
    ("evidence_type", "expected_confidence"),
    [
        ("primary", 0.9),
        ("secondary", 0.7),
        ("derived", 0.5),
        ("pattern", 0.3),
        ("unknown", 0.5),
    ],
)
def test_evidence_weight_selects_type_confidence_and_source_strength(
    evidence_type: str, expected_confidence: float,
) -> None:
    result = compute_evidence_weight(
        evidence_type,
        base_strength=0.8,
        source_credibility=0.5,
    )

    assert result == PLNTruthValue(0.4, expected_confidence)


def test_evidence_weight_degrades_confidence_over_chain_and_clamps_floor() -> None:
    chained = compute_evidence_weight("primary", chain_length=3)
    long_chain = compute_evidence_weight("pattern", chain_length=100)

    assert chained.confidence == pytest.approx(0.9 * 0.9 * 0.9)
    assert long_chain.confidence == MIN_CONFIDENCE


@pytest.mark.parametrize(
    ("reasoning_type", "expected_strength", "base_confidence"),
    [
        ("logical", 1.0, 0.95),
        ("statistical", 0.9, 0.8),
        ("analogy", 0.7, 0.6),
        ("pattern", 0.5, 0.4),
        ("unknown", 0.5, 0.5),
    ],
)
def test_reasoning_weight_maps_types_and_scales_premise_confidence(
    reasoning_type: str, expected_strength: float, base_confidence: float,
) -> None:
    result = compute_reasoning_weight(reasoning_type, premise_confidence=0.5)

    assert result.strength == expected_strength
    assert result.confidence == pytest.approx(base_confidence * 0.5)


def test_reasoning_weight_applies_confidence_floor_and_ceiling() -> None:
    low = compute_reasoning_weight("pattern", premise_confidence=0.0)
    high = compute_reasoning_weight("logical", premise_confidence=1.0)

    assert low.confidence == MIN_CONFIDENCE
    assert high.confidence == 0.95


def test_aggregate_evidence_paths_handles_empty_single_and_multiple_inputs() -> None:
    first = PLNTruthValue(0.6, 0.5)
    second = PLNTruthValue(0.8, 0.7)

    assert aggregate_evidence_paths([]) == PLNTruthValue(0.0, MIN_CONFIDENCE)
    assert aggregate_evidence_paths([first]) is first
    assert aggregate_evidence_paths([first, second]) == pln_revision(first, second)
