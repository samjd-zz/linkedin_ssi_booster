"""Tests for SSI score persistence, reporting, and Bluesky statistics."""

import json
import logging
import sys
from datetime import date
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

import services.ssi_tracker as ssi_tracker
from services.ssi_tracker import SSITracker, fetch_bluesky_stats


def _install_atproto(monkeypatch: pytest.MonkeyPatch, client_class: type) -> None:
    module = ModuleType("atproto")
    module.Client = client_class
    monkeypatch.setitem(sys.modules, "atproto", module)


def test_tracker_loads_existing_history_and_saves_new_scores(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "ssi-history.json"
    previous = [{"date": "2026-01-01", "total": 42.0}]
    path.write_text(json.dumps(previous), encoding="utf-8")
    monkeypatch.setattr(ssi_tracker, "date", SimpleNamespace(today=lambda: date(2026, 2, 3)))

    tracker = SSITracker(str(path))
    tracker.save_scores(10.0, 20.0, 30.0, 15.0)

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved == previous + [{
        "date": "2026-02-03",
        "establish_brand": 10.0,
        "find_right_people": 20.0,
        "engage_with_insights": 30.0,
        "build_relationships": 15.0,
        "total": 75.0,
    }]
    assert tracker.history == saved


def test_tracker_starts_with_empty_history_when_file_does_not_exist(tmp_path: Path) -> None:
    tracker = SSITracker(str(tmp_path / "missing.json"))

    assert tracker.history == []


def test_tracker_propagates_invalid_history_json(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text("{invalid", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        SSITracker(str(path))


def test_report_without_history_prompts_for_initial_score(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    SSITracker(str(tmp_path / "missing.json")).print_report()

    output = capsys.readouterr().out
    assert "LINKEDIN SSI WEEKLY REPORT" in output
    assert "No SSI data saved yet" in output
    assert "--save-ssi <brand> <find> <engage> <build>" in output
    assert "OVERALL:" not in output


def test_report_shows_latest_scores_actions_and_quick_wins(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "history.json"
    path.write_text(json.dumps([{
        "date": "2026-02-03",
        "establish_brand": 25.0,
        "find_right_people": 15.0,
        "engage_with_insights": 10.0,
        "build_relationships": 20.0,
    }]), encoding="utf-8")

    SSITracker(str(path)).print_report()

    output = capsys.readouterr().out
    assert "OVERALL: 70.00 / 100" in output
    assert "Gap to close:" in output
    assert "Establish professional brand" in output
    assert "Find the right people" in output
    assert "Post 3x this week (Buffer handles scheduling)" in output
    assert "QUICK WINS (do these daily, 15 mins)" in output
    assert "SCORE HISTORY" not in output


def test_report_includes_all_trend_directions_and_limits_history_to_five(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "history.json"
    entries = []
    for day in range(1, 8):
        entries.append({
            "date": f"2026-02-{day:02d}",
            "establish_brand": float(day),
            "find_right_people": 10.0,
            "engage_with_insights": 12.0,
            "build_relationships": 25.0 - day,
            "total": float(47 + day),
        })
    path.write_text(json.dumps(entries), encoding="utf-8")

    SSITracker(str(path)).print_report()

    output = capsys.readouterr().out
    assert "↑ +1.00 since last entry" in output
    assert "↔ no change since last entry" in output
    assert "↓ -1.00 since last entry" in output
    assert "SCORE HISTORY (last 5 entries)" in output
    assert "2026-02-02" not in output
    assert "2026-02-03" in output
    assert "2026-02-07" in output


@pytest.mark.parametrize(
    ("score", "expected_bar"),
    [(22.0, "GREEN"), (16.0, "YELLOW"), (10.0, "RED")],
)
def test_report_selects_progress_color_from_target_percentage(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    score: float,
    expected_bar: str,
) -> None:
    path = tmp_path / "history.json"
    path.write_text(json.dumps([{
        "establish_brand": score,
        "find_right_people": 0.0,
        "engage_with_insights": 0.0,
        "build_relationships": 0.0,
    }]), encoding="utf-8")

    SSITracker(str(path)).print_report()

    output = capsys.readouterr().out
    color = getattr(ssi_tracker.Fore, expected_bar)
    assert f"{color}{score:.2f}" in output


def test_bluesky_stats_uses_environment_credentials_and_aggregates_engagement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict = {}

    class FakeClient:
        def login(self, handle: str, password: str) -> None:
            calls["login"] = (handle, password)

        def get_profile(self, handle: str) -> SimpleNamespace:
            calls["profile_handle"] = handle
            return SimpleNamespace(
                handle=handle, followers_count=12, follows_count=34, posts_count=56,
            )

        def get_author_feed(self, **kwargs: object) -> SimpleNamespace:
            calls["feed"] = kwargs
            post = SimpleNamespace(
                like_count=4,
                reply_count=2,
                repost_count=3,
                quote_count=1,
                record=SimpleNamespace(text="A useful post"),
                uri="at://did:plc:abc/app.bsky.feed.post/post-key",
            )
            return SimpleNamespace(feed=[SimpleNamespace(post=post)])

    monkeypatch.setenv("BLUESKY_HANDLE", "writer.example")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-password")
    _install_atproto(monkeypatch, FakeClient)

    stats = fetch_bluesky_stats(feed_limit=7)

    assert stats == {
        "handle": "writer.example",
        "followers": 12,
        "following": 34,
        "posts": 56,
        "analysed": 1,
        "total_likes": 4,
        "total_replies": 2,
        "total_reposts": 3,
        "total_quotes": 1,
        "avg_engagement": 10.0,
        "top_post": {
            "text": "A useful post",
            "likes": 4,
            "replies": 2,
            "reposts": 3,
            "url": "https://bsky.app/profile/writer.example/post/post-key",
        },
    }
    assert calls["login"] == ("writer.example", "app-password")
    assert calls["feed"] == {
        "actor": "writer.example",
        "limit": 7,
        "filter": "posts_no_replies",
    }


def test_bluesky_stats_prefers_explicit_credentials_and_truncates_top_post(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeClient:
        def login(self, handle: str, password: str) -> None:
            assert (handle, password) == ("explicit.example", "explicit-password")

        def get_profile(self, handle: str) -> SimpleNamespace:
            return SimpleNamespace(
                handle=handle, followers_count=None, follows_count=None, posts_count=None,
            )

        def get_author_feed(self, **kwargs: object) -> SimpleNamespace:
            post = SimpleNamespace(
                like_count=1,
                reply_count=0,
                repost_count=0,
                quote_count=0,
                record=SimpleNamespace(text="x" * 101),
                uri="https://example.test/not-an-at-uri",
            )
            return SimpleNamespace(feed=[SimpleNamespace(post=post)])

    monkeypatch.setenv("BLUESKY_HANDLE", "environment.example")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "environment-password")
    _install_atproto(monkeypatch, FakeClient)

    stats = fetch_bluesky_stats("explicit.example", "explicit-password")

    assert stats is not None
    assert (stats["followers"], stats["following"], stats["posts"]) == (0, 0, 0)
    assert stats["top_post"]["text"] == ("x" * 100) + "…"
    assert stats["top_post"]["url"] == ""


def test_bluesky_stats_handles_empty_and_malformed_feed_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeClient:
        def login(self, handle: str, password: str) -> None:
            pass

        def get_profile(self, handle: str) -> SimpleNamespace:
            return SimpleNamespace(handle=handle, followers_count=0, follows_count=0, posts_count=0)

        def get_author_feed(self, **kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(feed=[
                SimpleNamespace(post=None),
                SimpleNamespace(post=SimpleNamespace(uri="at://incomplete")),
            ])

    _install_atproto(monkeypatch, FakeClient)

    stats = fetch_bluesky_stats("writer.example", "secret")

    assert stats is not None
    assert stats["analysed"] == 2
    assert stats["avg_engagement"] == 0.0
    assert stats["top_post"] == {
        "text": "",
        "likes": 0,
        "replies": 0,
        "reposts": 0,
        "url": "",
    }


def test_bluesky_stats_returns_none_when_credentials_are_missing(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.delenv("BLUESKY_HANDLE", raising=False)
    monkeypatch.delenv("BLUESKY_IDENTIFIER", raising=False)
    monkeypatch.delenv("BLUESKY_APP_PASSWORD", raising=False)
    _install_atproto(monkeypatch, object)

    with caplog.at_level(logging.WARNING):
        stats = fetch_bluesky_stats()

    assert stats is None
    assert "BLUESKY_HANDLE and BLUESKY_APP_PASSWORD are required" in caplog.text


def test_bluesky_stats_logs_and_returns_none_when_api_call_fails(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    class BrokenClient:
        def login(self, handle: str, password: str) -> None:
            raise RuntimeError("service unavailable")

    _install_atproto(monkeypatch, BrokenClient)

    with caplog.at_level(logging.WARNING):
        stats = fetch_bluesky_stats("writer.example", "app-password")

    assert stats is None
    assert "Could not fetch Bluesky stats: service unavailable" in caplog.text


def test_bluesky_stats_returns_none_when_optional_dependency_is_missing(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setitem(sys.modules, "atproto", None)

    with caplog.at_level(logging.WARNING):
        stats = fetch_bluesky_stats()

    assert stats is None
    assert "atproto package not installed" in caplog.text
