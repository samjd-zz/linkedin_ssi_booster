"""T6.3 — Unit tests for learning report aggregation and recommendation heuristics."""
import json
from pathlib import Path

import pytest

import services.avatar_intelligence as ai
import services.avatar_intelligence._learning as learning_module
from services.avatar_intelligence import (
    _HEURISTIC_MIN_COUNT,
    _apply_heuristics,
    _load_learning_events,
    build_learning_report,
    format_learning_report,
    record_moderation_event,
    LearningReport,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_events(log_path: Path, events: list[dict]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")


def _project_claim_kept_events(count: int) -> list[dict]:
    return [
        {
            "timestamp": "2024-01-01T00:00:00+00:00",
            "channel": "linkedin",
            "reason_code": "project_claim",
            "decision": "kept",
            "sentence_hash": f"abc{i:04x}",
            "article_ref": "http://example.com",
            "project_refs": [],
            "run_id": "test-run",
        }
        for i in range(count)
    ]


def _numeric_removed_events(count: int) -> list[dict]:
    return [
        {
            "timestamp": "2024-01-01T00:00:00+00:00",
            "channel": "linkedin",
            "reason_code": "unsupported_numeric",
            "decision": "removed",
            "sentence_hash": f"def{i:04x}",
            "article_ref": "http://example.com",
            "project_refs": [],
            "run_id": "test-run",
        }
        for i in range(count)
    ]


def _channel_removed_events(channel: str, count: int) -> list[dict]:
    return [
        {
            "timestamp": "2024-01-01T00:00:00+00:00",
            "channel": channel,
            "reason_code": "unsupported_claim",
            "decision": "removed",
            "sentence_hash": f"ghi{i:04x}",
            "article_ref": "http://example.com",
            "project_refs": [],
            "run_id": "test-run",
        }
        for i in range(count)
    ]


# ---------------------------------------------------------------------------
# _load_learning_events
# ---------------------------------------------------------------------------


def test_load_learning_events_empty_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = tmp_path / "learning_log.jsonl"
    monkeypatch.setattr(ai, "LEARNING_LOG_PATH", log)
    events = _load_learning_events()
    assert events == []


def test_load_learning_events_no_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai, "LEARNING_LOG_PATH", tmp_path / "nonexistent.jsonl")
    events = _load_learning_events()
    assert events == []


def test_load_learning_events_valid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = tmp_path / "learning_log.jsonl"
    _write_events(log, _project_claim_kept_events(3))
    monkeypatch.setattr(ai, "LEARNING_LOG_PATH", log)
    events = _load_learning_events()
    assert len(events) == 3


def test_load_learning_events_skips_malformed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = tmp_path / "learning_log.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as fh:
        fh.write('{"valid": "event"}\n')
        fh.write("{broken json line\n")
        fh.write('{"another": "valid"}\n')
    monkeypatch.setattr(ai, "LEARNING_LOG_PATH", log)
    events = _load_learning_events()
    assert len(events) == 2  # malformed line is skipped


# ---------------------------------------------------------------------------
# record_moderation_event → _load_learning_events round-trip
# ---------------------------------------------------------------------------


def test_record_moderation_event_appends(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = tmp_path / "learning_log.jsonl"
    monkeypatch.setattr(ai, "LEARNING_LOG_PATH", log)
    record_moderation_event(
        sentence="The model achieved 98% accuracy.",
        reason_code="unsupported_numeric",
        decision="removed",
        channel="linkedin",
        article_ref="http://example.com",
    )
    events = _load_learning_events()
    assert len(events) == 1
    assert events[0]["reason_code"] == "unsupported_numeric"
    assert events[0]["decision"] == "removed"


def test_record_moderation_event_dual_writes_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = tmp_path / "learning_log.jsonl"
    monkeypatch.setattr(ai, "LEARNING_LOG_PATH", log)
    monkeypatch.setattr(learning_module, "_is_database_enabled", lambda: True)

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
        "services.database.repositories.ModerationEventRepository.create",
        _capture_create,
    )

    record_moderation_event(
        sentence="The model achieved 98% accuracy.",
        reason_code="unsupported_numeric",
        decision="removed",
        channel="linkedin",
        article_ref="http://example.com",
        project_refs=["proj-1"],
    )

    assert captured["reason_code"] == "unsupported_numeric"
    assert captured["decision"] == "removed"
    assert captured["channel"] == "linkedin"
    assert captured["project_refs"] == ["proj-1"]
    assert captured["committed"] is True
    assert captured["closed"] is True


# ---------------------------------------------------------------------------
# _apply_heuristics
# ---------------------------------------------------------------------------


def test_apply_heuristics_empty() -> None:
    assert _apply_heuristics([]) == []


def test_apply_heuristics_below_min_count() -> None:
    """Exactly _HEURISTIC_MIN_COUNT - 1 events should produce no recommendations."""
    events = _project_claim_kept_events(_HEURISTIC_MIN_COUNT - 1)
    recs = _apply_heuristics(events)
    assert not any(r.category == "domain_term" for r in recs)


def test_apply_heuristics_rule1_project_claim_kept(tmp_path: Path) -> None:
    """Rule 1 fires when >= _HEURISTIC_MIN_COUNT project_claim kept events exist."""
    events = _project_claim_kept_events(_HEURISTIC_MIN_COUNT)
    recs = _apply_heuristics(events)
    assert any(r.category == "domain_term" for r in recs)


def test_apply_heuristics_rule1_confidence_high_when_5_plus(tmp_path: Path) -> None:
    events = _project_claim_kept_events(5)
    recs = _apply_heuristics(events)
    domain_recs = [r for r in recs if r.category == "domain_term"]
    assert domain_recs[0].confidence == "high"


def test_apply_heuristics_rule1_confidence_medium_below_5() -> None:
    events = _project_claim_kept_events(_HEURISTIC_MIN_COUNT)
    recs = _apply_heuristics(events)
    domain_recs = [r for r in recs if r.category == "domain_term"]
    assert domain_recs[0].confidence == "medium"


def test_apply_heuristics_rule2_numeric_removals() -> None:
    events = _numeric_removed_events(_HEURISTIC_MIN_COUNT)
    recs = _apply_heuristics(events)
    assert any(r.category == "retrieval_expansion" for r in recs)


def test_apply_heuristics_rule2_below_min_count() -> None:
    events = _numeric_removed_events(_HEURISTIC_MIN_COUNT - 1)
    recs = _apply_heuristics(events)
    assert not any(r.category == "retrieval_expansion" for r in recs)


def test_apply_heuristics_rule3_channel_prompt_length() -> None:
    """Rule 3 fires when >= 2 * _HEURISTIC_MIN_COUNT removals on same channel."""
    threshold = _HEURISTIC_MIN_COUNT * 2
    events = _channel_removed_events("x", threshold)
    recs = _apply_heuristics(events)
    assert any(r.category == "prompt_length" for r in recs)


def test_apply_heuristics_rule3_below_threshold() -> None:
    threshold = _HEURISTIC_MIN_COUNT * 2
    events = _channel_removed_events("x", threshold - 1)
    recs = _apply_heuristics(events)
    assert not any(r.category == "prompt_length" for r in recs)


# ---------------------------------------------------------------------------
# build_learning_report
# ---------------------------------------------------------------------------


def test_build_learning_report_empty_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai, "LEARNING_LOG_PATH", tmp_path / "nonexistent.jsonl")
    report = build_learning_report()
    assert report.total_events == 0
    assert report.kept_count == 0
    assert report.removed_count == 0
    assert report.recommendations == []
    assert report.top_reason_codes == []


def test_build_learning_report_counts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = tmp_path / "learning_log.jsonl"
    events = _project_claim_kept_events(3) + _numeric_removed_events(2)
    _write_events(log, events)
    monkeypatch.setattr(ai, "LEARNING_LOG_PATH", log)

    report = build_learning_report()
    assert report.total_events == 5
    assert report.kept_count == 3
    assert report.removed_count == 2


def test_build_learning_report_top_reason_codes_sorted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = tmp_path / "learning_log.jsonl"
    events = _project_claim_kept_events(4) + _numeric_removed_events(2)
    _write_events(log, events)
    monkeypatch.setattr(ai, "LEARNING_LOG_PATH", log)

    report = build_learning_report()
    codes = [code for code, _ in report.top_reason_codes]
    counts = [count for _, count in report.top_reason_codes]
    assert codes[0] == "project_claim"
    assert counts == sorted(counts, reverse=True)


def test_build_learning_report_recommendations_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = tmp_path / "learning_log.jsonl"
    events = _project_claim_kept_events(_HEURISTIC_MIN_COUNT)
    _write_events(log, events)
    monkeypatch.setattr(ai, "LEARNING_LOG_PATH", log)

    report = build_learning_report()
    assert len(report.recommendations) >= 1


# ---------------------------------------------------------------------------
# format_learning_report
# ---------------------------------------------------------------------------


def test_format_learning_report_empty() -> None:
    report = LearningReport(
        total_events=0,
        kept_count=0,
        removed_count=0,
        top_reason_codes=[],
        kept_vs_removed=[],
        recommendations=[],
    )
    text = format_learning_report(report)
    assert "Total events" in text
    assert "0" in text


def test_format_learning_report_with_recommendations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = tmp_path / "learning_log.jsonl"
    events = _project_claim_kept_events(_HEURISTIC_MIN_COUNT)
    _write_events(log, events)
    monkeypatch.setattr(ai, "LEARNING_LOG_PATH", log)

    report = build_learning_report()
    text = format_learning_report(report)
    assert "Recommendations" in text
    assert "domain_term" in text or "DOMAIN_TERMS" in text or "tech keywords" in text.lower()
