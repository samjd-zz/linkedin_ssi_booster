"""Tests for category analytics and explicit selection feedback."""

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.selection_learning._category_analytics import (
    CategoryAnalyticsReport,
    CategoryPerformance,
    compute_category_analytics,
    format_category_analytics_report,
)
from services.selection_learning._feedback import FeedbackService


def _candidate(
    category: str | None,
    ssi: str | None,
    status: str = "pending",
    rank_score: float = 0.0,
) -> SimpleNamespace:
    return SimpleNamespace(
        primary_category=category,
        primary_ssi_component=ssi,
        status=status,
        rank_score=rank_score,
    )


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_category_performance_rate_is_zero_without_labeled_candidates() -> None:
    performance = CategoryPerformance(category="AI", ssi_component="establish_brand")

    performance.update_acceptance_rate()

    assert performance.acceptance_rate == 0.0


def test_compute_category_analytics_groups_counts_and_average_rank_scores() -> None:
    report = compute_category_analytics([
        _candidate("AI", "establish_brand", "accepted", 0.8),
        _candidate("AI", "establish_brand", "rejected", 0.4),
        _candidate("AI", "establish_brand", "pending", 0.6),
        _candidate("Community", "find_right_people", "accepted", 0.9),
        _candidate(None, "find_right_people", "accepted", 1.0),
        _candidate("Missing SSI", None, "rejected", 0.2),
    ])

    assert report.total_candidates_analyzed == 4
    assert report.total_categories_tracked == 2
    ai = report.category_performance["AI:establish_brand"]
    assert (ai.total_candidates, ai.accepted_count, ai.rejected_count) == (3, 1, 1)
    assert ai.avg_rank_score == pytest.approx(0.6)
    assert ai.acceptance_rate == pytest.approx(0.5)
    assert report.ssi_component_breakdown["find_right_people"][0].category == "Community"


def test_category_analytics_orders_results_and_honors_limits() -> None:
    report = compute_category_analytics([
        _candidate("Low", "establish_brand", "rejected", 0.2),
        _candidate("Mid", "establish_brand", "accepted", 0.5),
        _candidate("Mid", "establish_brand", "rejected", 0.7),
        _candidate("High", "establish_brand", "accepted", 0.9),
        _candidate("Other SSI", "find_right_people", "accepted", 0.8),
    ])

    assert [item.category for item in report.top_categories_by_acceptance(2)] == [
        "High", "Other SSI",
    ]
    assert [item.category for item in report.top_categories_by_ssi(
        "establish_brand", limit=1,
    )] == ["High"]
    assert report.top_categories_by_ssi("unknown_ssi") == []
    assert report.top_categories_by_acceptance(0) == []


@pytest.mark.parametrize(
    ("accepted", "rejected", "expected_rate"),
    [(0, 0, 0.0), (1, 0, 1.0), (0, 2, 0.0), (1, 3, 0.25)],
)
def test_acceptance_rate_handles_labeled_count_edges(
    accepted: int, rejected: int, expected_rate: float,
) -> None:
    performance = CategoryPerformance(
        category="AI",
        ssi_component="establish_brand",
        accepted_count=accepted,
        rejected_count=rejected,
    )

    performance.update_acceptance_rate()

    assert performance.acceptance_rate == expected_rate


def test_format_category_analytics_report_includes_rankings_and_ssi_breakdown() -> None:
    report = compute_category_analytics([
        _candidate("Popular", "establish_brand", "accepted", 0.8765),
        _candidate("Popular", "establish_brand", "rejected", 0.1235),
        _candidate("Emerging", "build_relationships", "rejected", 0.2),
    ])

    formatted = format_category_analytics_report(report)

    assert "Total candidates analyzed: 3" in formatted
    assert "Categories tracked: 2" in formatted
    assert "Popular (establish_brand)" in formatted
    assert "50.0% acceptance (1/2)" in formatted
    assert "Avg rank score: 0.500" in formatted
    assert "Establish Brand" in formatted
    assert "Build Relationships" in formatted
    assert "Emerging: 0.0% acceptance (0/1)" in formatted


@pytest.mark.parametrize(
    ("rate", "expected_color"),
    [(0.5, "GREEN"), (0.25, "YELLOW"), (0.0, "RED")],
)
def test_format_category_analytics_uses_acceptance_color_thresholds(
    monkeypatch: pytest.MonkeyPatch, rate: float, expected_color: str,
) -> None:
    from colorama import Fore

    report = CategoryAnalyticsReport(
        total_categories_tracked=1,
        category_performance={
            "Example:establish_brand": CategoryPerformance(
                category="Example",
                ssi_component="establish_brand",
                total_candidates=1,
                accepted_count=int(rate > 0),
                rejected_count=int(rate == 0),
                acceptance_rate=rate,
            ),
        },
    )
    monkeypatch.setattr(Fore, expected_color, f"<{expected_color}>")

    formatted = format_category_analytics_report(report)

    assert f"<{expected_color}>{rate * 100:.1f}% acceptance" in formatted


def test_format_empty_category_report_has_totals_and_no_ranking_sections() -> None:
    formatted = format_category_analytics_report(CategoryAnalyticsReport())

    assert "Total candidates analyzed: 0" in formatted
    assert "Categories tracked: 0" in formatted
    assert "Top Categories by Acceptance Rate" not in formatted


def test_record_user_feedback_updates_only_matching_candidate(tmp_path: Path) -> None:
    path = tmp_path / "candidates.jsonl"
    _write_jsonl(path, [
        {"candidate_id": "first", "user_feedback": {"rating": 3}},
        {"candidate_id": "second", "selected": None},
    ])

    assert FeedbackService.record_user_feedback("second", "upvote", True, path=path)

    rows = _read_jsonl(path)
    assert rows[0]["user_feedback"] == {"rating": 3}
    assert rows[1]["user_feedback"]["upvote"] is True
    datetime.fromisoformat(rows[1]["user_feedback"]["last_updated"])


def test_record_user_feedback_returns_false_without_rewriting_missing_candidate(
    tmp_path: Path,
) -> None:
    path = tmp_path / "candidates.jsonl"
    original = '{"candidate_id": "present"}\n'
    path.write_text(original, encoding="utf-8")

    assert not FeedbackService.record_user_feedback("missing", "rating", 5, path=path)

    assert path.read_text(encoding="utf-8") == original


def test_record_user_feedback_creates_feedback_mapping_for_existing_record(
    tmp_path: Path,
) -> None:
    path = tmp_path / "candidates.jsonl"
    _write_jsonl(path, [{"candidate_id": "first"}])

    assert FeedbackService.record_user_feedback("first", "rating", 5, path=path)

    feedback = _read_jsonl(path)[0]["user_feedback"]
    assert feedback["rating"] == 5
    assert "last_updated" in feedback


def test_apply_user_feedback_respects_flags_and_existing_selection(tmp_path: Path) -> None:
    path = tmp_path / "candidates.jsonl"
    _write_jsonl(path, [
        {"candidate_id": "upvote", "selected": None, "user_feedback": {"upvote": True}},
        {"candidate_id": "downvote", "selected": None, "user_feedback": {"downvote": True}},
        {"candidate_id": "already-selected", "selected": True, "user_feedback": {"override": False}},
        {"candidate_id": "no-feedback", "selected": None},
    ])

    updated = FeedbackService.apply_user_feedback_to_selection(
        path=path, downvote_as_rejected=True,
    )

    rows = {record["candidate_id"]: record for record in _read_jsonl(path)}
    assert updated == 2
    assert rows["upvote"]["selected"] is True
    assert rows["downvote"]["selected"] is False
    assert "selected_at" in rows["upvote"]
    assert "selected_at" in rows["downvote"]
    assert rows["already-selected"]["selected"] is True
    assert rows["no-feedback"]["selected"] is None


@pytest.mark.parametrize(
    ("feedback", "upvote_as_selected", "downvote_as_rejected", "expected"),
    [
        ({"upvote": True}, False, True, None),
        ({"downvote": True}, True, False, None),
        ({"override": False}, True, False, False),
        ({"upvote": True, "override": False}, True, False, False),
        ({"downvote": True, "override": True}, True, True, True),
    ],
)
def test_apply_user_feedback_handles_disabled_votes_and_overrides(
    tmp_path: Path,
    feedback: dict,
    upvote_as_selected: bool,
    downvote_as_rejected: bool,
    expected: bool | None,
) -> None:
    path = tmp_path / "candidates.jsonl"
    _write_jsonl(path, [
        {"candidate_id": "candidate", "selected": None, "user_feedback": feedback},
    ])

    updated = FeedbackService.apply_user_feedback_to_selection(
        path=path,
        upvote_as_selected=upvote_as_selected,
        downvote_as_rejected=downvote_as_rejected,
    )

    record = _read_jsonl(path)[0]
    assert updated == (1 if expected is not None else 0)
    assert record["selected"] is expected
    if expected is not None:
        datetime.fromisoformat(record["selected_at"])
    else:
        assert "selected_at" not in record


def test_apply_user_feedback_does_not_rewrite_when_nothing_changes(tmp_path: Path) -> None:
    path = tmp_path / "candidates.jsonl"
    original = '{"candidate_id": "candidate", "selected": null, "user_feedback": {}}\n'
    path.write_text(original, encoding="utf-8")

    assert FeedbackService.apply_user_feedback_to_selection(path=path) == 0

    assert path.read_text(encoding="utf-8") == original
