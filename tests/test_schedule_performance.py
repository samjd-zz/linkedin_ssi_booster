"""Schedule operation counts without model, hardware, or publishing access."""

import sys
import logging
from types import SimpleNamespace
from unittest.mock import Mock
from pathlib import Path

import pytest

import main
import services.avatar_intelligence as avatar
import services.derivative_of_truth as dot
from scheduler import PostScheduler


@pytest.fixture
def schedule(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    topics = [
        dict(title=f"Topic {i}", angle="Software lesson", ssi_component="establish_brand", hashtags=["Software"])
        for i in range(5)
    ]
    ai = Mock()
    result = SimpleNamespace(flagged=False)

    def generate(**kwargs: object) -> str:
        ai.last_truth_gate_text = "A grounded software lesson."
        ai.last_truth_gate_meta = SimpleNamespace(
            dot_result=result, dot_per_sentence_scores={}, spacy_sim_scores={},
        )
        return "A grounded software lesson."

    ai.generate_linkedin_post.side_effect = generate
    ai.generate_youtube_short_script.side_effect = generate
    github = Mock(return_value="unused")
    load = Mock(return_value=object())
    normalizers = [Mock(return_value=[]) for _ in range(3)]
    retrieve = Mock(return_value=[])
    render = Mock(return_value={})
    report = Mock()
    flux = SimpleNamespace(
        config=SimpleNamespace(enabled=False, minimal_mode=False),
        notify_ollama_start=Mock(), notify_ollama_done=Mock(),
    )
    buffer = Mock()
    buffer.get_linkedin_channel_id.return_value = "linkedin"
    buffer.get_x_channel_id.return_value = "x"
    buffer_factory = Mock(return_value=buffer)
    cleanup = Mock()
    score = Mock(return_value=result)
    monkeypatch.setenv("BUFFER_API_KEY", "test-only")
    for component in ("ESTABLISH_BRAND", "FIND_RIGHT_PEOPLE", "ENGAGE_WITH_INSIGHTS", "BUILD_RELATIONSHIPS"):
        monkeypatch.setenv(f"SSI_FOCUS_{component}", "25")
    monkeypatch.delenv("SCHEDULER_POSTING_SLOTS", raising=False)
    monkeypatch.setattr(main, "load_content_calendar", lambda: {"week_1": topics})
    monkeypatch.setattr(main, "print_startup_notice", Mock())
    monkeypatch.setattr(main, "build_github_profile_context", github)
    monkeypatch.setattr(main, "OllamaService", Mock(return_value=ai))
    monkeypatch.setattr(main, "BufferService", buffer_factory)
    monkeypatch.setattr(main, "get_flux_service", Mock(return_value=flux))
    monkeypatch.setattr(main, "_optimize_flux_story_for_render", lambda ai, text, **kwargs: text)
    monkeypatch.setattr(main, "_render_schedule_art_avatar", render)
    monkeypatch.setattr(main, "_run_post_generation_cleanup", cleanup)
    monkeypatch.setattr(avatar, "load_avatar_state", load)
    for name, normalizer in zip(
        ("normalize_evidence_facts", "normalize_domain_facts", "normalize_extracted_facts"), normalizers,
    ):
        monkeypatch.setattr(avatar, name, normalizer)
    monkeypatch.setattr(avatar, "retrieve_evidence", retrieve)
    monkeypatch.setattr(avatar, "build_explain_output", Mock())
    monkeypatch.setattr(avatar, "format_explain_output", Mock(return_value="explain"))
    monkeypatch.setattr(dot, "score_claim_with_truth_gradient", score)
    monkeypatch.setattr(dot, "report_truth_gradient", report)
    monkeypatch.setattr(dot, "format_truth_gradient_report", Mock(return_value="report"))
    return SimpleNamespace(
        ai=ai, topics=topics, github=github, load=load, normalizers=normalizers,
        retrieve=retrieve, render=render, buffer=buffer, buffer_factory=buffer_factory,
        cleanup=cleanup, score=score, report=report, flux=flux,
    )


def test_schedule_reuses_preparation_and_original_generation_report(
    schedule: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "argv", [
        "main.py", "--schedule", "--channel", "linkedin,x", "--dot-report", "--avatar-explain",
    ])
    main.main()
    schedule.github.assert_not_called()
    schedule.load.assert_called_once()
    for normalizer in schedule.normalizers:
        normalizer.assert_called_once()
    assert schedule.retrieve.call_count == 5
    assert schedule.ai.generate_linkedin_post.call_count == 10
    schedule.score.assert_not_called()
    assert schedule.buffer.create_post.call_count == 10
    assert all(call.args[0] == "A grounded software lesson." for call in schedule.report.call_args_list)


@pytest.mark.parametrize("dry_run", [False, True])
def test_live_cap_precedes_generation_but_preview_retains_full_calendar(
    schedule: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, dry_run: bool,
) -> None:
    monkeypatch.setenv("SCHEDULER_POSTING_SLOTS", "monday@09:00")
    monkeypatch.setattr(sys, "argv", [
        "main.py", "--schedule", "--channel", "linkedin,x", *(["--dry-run"] if dry_run else []),
    ])
    main.main()
    assert schedule.ai.generate_linkedin_post.call_count == (10 if dry_run else 2)
    assert schedule.render.call_count == (10 if dry_run else 2)
    assert schedule.buffer.create_post.call_count == (0 if dry_run else 2)


def test_schedule_without_explain_skips_extracted_preparation(
    schedule: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "argv", ["main.py", "--schedule", "--dry-run"])
    main.main()
    schedule.normalizers[2].assert_not_called()
    schedule.buffer_factory.assert_not_called()


@pytest.mark.parametrize("cap", [None, "invalid", "monday@09:00,tuesday@10:00"])
def test_ssi_selection_before_generation_matches_queue_selection(
    schedule: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, cap: str | None,
) -> None:
    components = ["build_relationships", "establish_brand", "find_right_people",
                  "engage_with_insights", "establish_brand"]
    for topic, component in zip(schedule.topics, components):
        topic["ssi_component"] = component
    for component in set(components):
        monkeypatch.setenv(f"SSI_FOCUS_{component.upper()}", "25")
    if cap is not None:
        monkeypatch.setenv("SCHEDULER_POSTING_SLOTS", cap)
    expected = PostScheduler.select_posts(schedule.topics)
    assert [topic["title"] for topic in expected] == (
        ["Topic 1", "Topic 4"] if cap and cap != "invalid"
        else ["Topic 1", "Topic 4", "Topic 2", "Topic 3", "Topic 0"]
    )
    scheduled_topics = []

    def queue(posts: list[dict], *, preselected: bool, **kwargs: object) -> list:
        selected = posts if preselected else PostScheduler.select_posts(posts)
        scheduled_topics.extend(post["title"] for post in selected)
        return []

    scheduler = Mock()
    scheduler.schedule_week.side_effect = queue
    monkeypatch.setattr(main, "PostScheduler", Mock(
        select_posts=PostScheduler.select_posts,
        _get_posting_slot_limit=PostScheduler._get_posting_slot_limit,
        return_value=scheduler,
    ))
    monkeypatch.setattr(sys, "argv", ["main.py", "--schedule"])
    main.main()
    assert scheduled_topics == [topic["title"] for topic in expected]
    assert schedule.ai.generate_linkedin_post.call_count == (2 if cap and cap != "invalid" else 5)


def test_capped_linkedin_does_not_limit_youtube_or_confuse_grounding_cache(
    schedule: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("SCHEDULER_POSTING_SLOTS", "monday@09:00")
    # SSI grouping selects topic 1, not topic 0.
    schedule.topics[0]["ssi_component"] = "build_relationships"
    monkeypatch.setattr(main, "get_youtube_scripts_dir", lambda: tmp_path)
    monkeypatch.setattr(sys, "argv", ["main.py", "--schedule", "--channel", "linkedin,youtube"])
    main.main()
    assert schedule.ai.generate_linkedin_post.call_count == 1
    assert schedule.ai.generate_youtube_short_script.call_count == 5
    assert schedule.retrieve.call_count == 5
    assert len(list(tmp_path.glob("*.txt"))) == 5
    assert schedule.buffer.create_post.call_count == 1
    schedule.render.assert_called_once()


@pytest.mark.parametrize("metadata", ["missing", "stale", "formatting"])
def test_reports_reuse_only_matching_generated_content(
    schedule: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, metadata: str,
) -> None:
    schedule.topics[:] = schedule.topics[:1]
    schedule.ai.generate_linkedin_post.side_effect = None
    schedule.ai.generate_linkedin_post.return_value = "A grounded software lesson."
    schedule.ai.last_truth_gate_meta = SimpleNamespace(dot_result=SimpleNamespace(flagged=False))
    schedule.ai.last_truth_gate_text = (
        "A grounded\n\nsoftware lesson." if metadata == "formatting" else "Stale content."
    )
    if metadata == "missing":
        schedule.ai.last_truth_gate_meta = None
    monkeypatch.setattr(sys, "argv", ["main.py", "--schedule", "--dry-run", "--dot-report"])
    main.main()
    assert schedule.score.call_count == (0 if metadata == "formatting" else 1)
    assert schedule.report.call_args.args[0] == "A grounded software lesson."


def test_generation_report_does_not_include_hashtags_or_footer(
    schedule: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("services.shared.LINKEDIN_POST_FOOTER", "Configured footer")
    monkeypatch.setattr(sys, "argv", ["main.py", "--schedule", "--dot-report"])
    main.main()
    for call in schedule.buffer.create_post.call_args_list:
        assert "#Software" in call.kwargs["text"]
        assert call.kwargs["text"].endswith("Configured footer")
    schedule.score.assert_not_called()
    assert "excludes appended hashtags and footer" in capsys.readouterr().out


def test_schedule_cleanup_and_ollama_notification_on_generation_error(
    schedule: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    schedule.ai.generate_linkedin_post.side_effect = RuntimeError("Generation failed")
    monkeypatch.setattr(sys, "argv", ["main.py", "--schedule", "--dry-run"])
    with pytest.raises(RuntimeError, match="Generation failed"):
        main.main()
    schedule.flux.notify_ollama_done.assert_called_once()
    schedule.cleanup.assert_called_once_with(schedule.ai, "schedule")
    schedule.buffer_factory.assert_not_called()


def test_missing_week_skips_preparation_but_runs_cleanup(
    schedule: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "argv", ["main.py", "--schedule", "--week", "99"])
    main.main()
    schedule.load.assert_not_called()
    schedule.ai.generate_linkedin_post.assert_not_called()
    schedule.cleanup.assert_called_once_with(schedule.ai, "schedule")


def test_grounding_is_reused_per_topic_not_shared_between_different_topics(
    schedule: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def retrieve(query: str, facts: list, limit: int) -> list:
        return [avatar.DomainEvidenceFact(
            evidence_id=query, domain="Software", statement=query, tags=[],
            confidence="high", source_fact_id=query,
        )]

    schedule.retrieve.side_effect = retrieve
    monkeypatch.setattr(sys, "argv", ["main.py", "--schedule", "--channel", "linkedin,x", "--dry-run"])
    main.main()
    calls = schedule.ai.generate_linkedin_post.call_args_list
    for index in range(5):
        first = calls[index].kwargs
        second = calls[index + 5].kwargs
        assert first["grounding_facts"] is second["grounding_facts"]
        assert first["title"] in first["grounding_facts"][0].details
    assert len({id(call.kwargs["grounding_facts"]) for call in calls}) == 5


def test_schedule_logs_preparation_retrieval_and_queue_timings(
    schedule: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(sys, "argv", ["main.py", "--schedule", "--dot-report"])
    with caplog.at_level(logging.INFO):
        main.main()
    for stage in (
        "schedule.preparation", "schedule.retrieval", "schedule.generation",
        "schedule.dot_report", "schedule.queue", "schedule.gc",
    ):
        assert f"Stage end stage={stage}" in caplog.text


def test_early_cap_preserves_order_when_ssi_allocation_has_overflow(
    schedule: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    schedule.topics[:] = [
        dict(
            title=f"Topic {i}", angle="Software lesson", hashtags=[],
            ssi_component="establish_brand" if i < 8 else "build_relationships",
        )
        for i in range(10)
    ]
    monkeypatch.setenv("SCHEDULER_POSTING_SLOTS", ",".join(["monday@09:00"] * 6))
    expected = [topic["title"] for topic in PostScheduler.select_posts(schedule.topics)]
    assert expected == ["Topic 0", "Topic 1", "Topic 2", "Topic 8", "Topic 9", "Topic 3"]
    schedule.ai.generate_linkedin_post.side_effect = lambda **kwargs: kwargs["title"]
    schedule.ai.last_truth_gate_text = ""
    schedule.ai.last_truth_gate_meta = None
    monkeypatch.setattr(sys, "argv", ["main.py", "--schedule"])
    main.main()
    assert [call.kwargs["text"].split("\n")[0] for call in schedule.buffer.create_post.call_args_list] == expected
