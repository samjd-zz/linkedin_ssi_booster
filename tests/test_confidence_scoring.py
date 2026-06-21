"""T6.4 — Unit tests for confidence scoring and policy routing."""
import pytest

import services.avatar_intelligence._confidence as confidence_module
from services.avatar_intelligence import (
    ConfidenceSignals,
    ConfidenceResult,
    extract_confidence_signals,
    score_confidence,
    decide_publish_mode,
)


# ---------------------------------------------------------------------------
# Helpers to build signals at known levels
# ---------------------------------------------------------------------------


def _high_signals() -> ConfidenceSignals:
    """Signals that should produce a 'high' confidence level (score >= 0.70)."""
    return ConfidenceSignals(
        truth_gate_removed_count=0,
        truth_gate_reason_severity=0.0,
        grounding_coverage_ratio=1.0,
        unsupported_claim_pressure=0.0,
        channel_length_pressure=0.0,
        narrative_repetition_score=0.0,
    )


def _medium_signals() -> ConfidenceSignals:
    """Signals that produce a 'medium' confidence level (0.40 <= score < 0.70).

    Calibrated values:
    -0.315 (severity) -0.090 (pressure) -0.045 (removed) +0.060 (coverage)
    -0.020 (length) = raw 0.59 → medium.
    """
    return ConfidenceSignals(
        truth_gate_removed_count=3,
        truth_gate_reason_severity=0.90,
        grounding_coverage_ratio=0.60,
        unsupported_claim_pressure=0.30,
        channel_length_pressure=0.20,
        narrative_repetition_score=0.0,
    )


def _low_signals() -> ConfidenceSignals:
    """Signals that produce a 'low' confidence level (score < 0.40)."""
    return ConfidenceSignals(
        truth_gate_removed_count=10,
        truth_gate_reason_severity=1.0,
        grounding_coverage_ratio=0.0,
        unsupported_claim_pressure=1.0,
        channel_length_pressure=1.0,
        narrative_repetition_score=1.0,
    )


# ---------------------------------------------------------------------------
# score_confidence — determinism and level thresholds
# ---------------------------------------------------------------------------


def test_score_confidence_deterministic() -> None:
    signals = _medium_signals()
    r1 = score_confidence(signals)
    r2 = score_confidence(signals)
    assert r1.score == r2.score
    assert r1.level == r2.level


def test_score_confidence_high_level() -> None:
    result = score_confidence(_high_signals())
    assert result.level == "high"
    assert result.score >= 0.70


def test_score_confidence_medium_level() -> None:
    result = score_confidence(_medium_signals())
    assert result.level == "medium"
    assert 0.40 <= result.score < 0.70


def test_score_confidence_low_level() -> None:
    result = score_confidence(_low_signals())
    assert result.level == "low"
    assert result.score < 0.40


def test_score_confidence_score_in_range() -> None:
    for signals in (_high_signals(), _medium_signals(), _low_signals()):
        result = score_confidence(signals)
        assert 0.0 <= result.score <= 1.0


def test_score_confidence_dominant_signal_low() -> None:
    """Low confidence has a dominant negative signal."""
    result = score_confidence(_low_signals())
    assert result.dominant_signal is not None


def test_score_confidence_dominant_signal_high() -> None:
    """Perfect signals may have no negative dominant signal."""
    result = score_confidence(_high_signals())
    # dominant_signal could be None or a small contributor — just verify it doesn't crash
    assert isinstance(result.dominant_signal, (str, type(None)))


# ---------------------------------------------------------------------------
# extract_confidence_signals
# ---------------------------------------------------------------------------


def test_extract_confidence_signals_zero_removal() -> None:
    signals = extract_confidence_signals(
        removed_count=0,
        total_sentences=10,
        reason_codes=[],
        grounding_facts_count=5,
        max_grounding_facts=5,
        channel="linkedin",
        post_length=0,
    )
    assert signals.unsupported_claim_pressure == 0.0
    assert signals.grounding_coverage_ratio == 1.0
    assert signals.truth_gate_reason_severity == 0.0


def test_extract_confidence_signals_full_removal() -> None:
    signals = extract_confidence_signals(
        removed_count=10,
        total_sentences=10,
        reason_codes=["fabricated_detail"],
        grounding_facts_count=0,
        max_grounding_facts=5,
        channel="x",
        post_length=300,
    )
    assert signals.unsupported_claim_pressure == 1.0
    assert signals.truth_gate_reason_severity == 0.90  # fabricated_detail severity
    assert signals.grounding_coverage_ratio == 0.0
    assert signals.channel_length_pressure == 1.0  # 300 >= x budget (257)


def test_extract_confidence_signals_coverage_capped() -> None:
    signals = extract_confidence_signals(
        removed_count=0,
        total_sentences=5,
        reason_codes=[],
        grounding_facts_count=10,  # more than max
        max_grounding_facts=5,
    )
    assert signals.grounding_coverage_ratio == 1.0  # capped


def test_extract_confidence_signals_zero_total_sentences() -> None:
    """No division-by-zero when total_sentences is 0."""
    signals = extract_confidence_signals(
        removed_count=0,
        total_sentences=0,
        reason_codes=[],
        grounding_facts_count=0,
    )
    assert signals.unsupported_claim_pressure == 0.0


def test_extract_confidence_signals_unknown_reason_code() -> None:
    """Unknown reason code uses the default severity."""
    signals = extract_confidence_signals(
        removed_count=1,
        total_sentences=5,
        reason_codes=["totally_unknown_code"],
        grounding_facts_count=0,
    )
    assert signals.truth_gate_reason_severity == 0.50  # _DEFAULT_REASON_SEVERITY


# ---------------------------------------------------------------------------
# decide_publish_mode — policy matrix
# ---------------------------------------------------------------------------


def test_policy_strict_high_posts() -> None:
    decision = decide_publish_mode("strict", score_confidence(_high_signals()), "post")
    assert decision.route == "post"


def test_policy_strict_medium_idea() -> None:
    decision = decide_publish_mode("strict", score_confidence(_medium_signals()), "post")
    assert decision.route == "idea"


def test_policy_strict_low_blocks() -> None:
    decision = decide_publish_mode("strict", score_confidence(_low_signals()), "post")
    assert decision.route == "block"


def test_policy_balanced_high_posts() -> None:
    decision = decide_publish_mode("balanced", score_confidence(_high_signals()), "post")
    assert decision.route == "post"


def test_policy_balanced_medium_posts() -> None:
    decision = decide_publish_mode("balanced", score_confidence(_medium_signals()), "post")
    assert decision.route == "post"


def test_policy_balanced_low_idea() -> None:
    decision = decide_publish_mode("balanced", score_confidence(_low_signals()), "post")
    assert decision.route == "idea"


def test_policy_draft_first_always_idea() -> None:
    for signals_fn in (_high_signals, _medium_signals, _low_signals):
        decision = decide_publish_mode("draft-first", score_confidence(signals_fn()), "post")
        assert decision.route == "idea"


def test_policy_unknown_falls_back_to_balanced() -> None:
    """Unknown policy falls back to balanced behaviour."""
    high_result = score_confidence(_high_signals())
    decision = decide_publish_mode("nonexistent-policy", high_result, "post")
    # balanced: high → post
    assert decision.route == "post"
    assert decision.policy == "balanced"


def test_decide_publish_mode_confidence_level_in_decision() -> None:
    result = score_confidence(_high_signals())
    decision = decide_publish_mode("strict", result, "post")
    assert decision.confidence_level == "high"


def test_decide_publish_mode_reason_nonempty() -> None:
    result = score_confidence(_medium_signals())
    decision = decide_publish_mode("balanced", result, "post")
    assert len(decision.reason) > 0


def test_record_confidence_decision_dual_writes_db(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(confidence_module, "_is_database_enabled", lambda: True)

    captured: dict[str, object] = {}

    class DummySession:
        def commit(self) -> None:
            captured["committed"] = True

        def close(self) -> None:
            captured["closed"] = True

    monkeypatch.setattr(
        "services.database.session.get_session",
        lambda: iter([DummySession()]),
    )

    def _capture_create(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(
        "services.database.repositories.ConfidenceDecisionRepository.create",
        _capture_create,
    )

    result = score_confidence(_high_signals())
    decision = decide_publish_mode("balanced", result, "post")
    confidence_module.record_confidence_decision(
        decision=decision,
        confidence=result,
        channel="linkedin",
        article_ref="http://example.com",
    )

    assert captured["route"] == decision.route
    assert captured["policy"] == decision.policy
    assert captured["confidence_score"] == result.score
    assert captured["confidence_level"] == result.level
    assert captured["reason"] == decision.reason
    assert captured["committed"] is True
    assert captured["closed"] is True
