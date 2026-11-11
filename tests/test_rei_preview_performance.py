"""Rei CLI preview avoids unrelated services and duplicate preparation."""

import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import cli._rei_strudel as rei_strudel
import cli._rei_suno as rei_suno
import main
import services.avatar_intelligence as avatar
import services.rei_toei_service as rei
from services.rei_toei import Theme
from services.rei_toei._models import LyricCompositionError
from services.rei_toei._suno_themes import load_recent_rei_themes


@pytest.fixture
def preview(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SimpleNamespace:
    ai = Mock()
    constructor = Mock(return_value=ai)
    github = Mock(return_value="unused GitHub context")
    theme = Theme(
        id="test", name="Async", technical_concepts=["async"], evidence_ids=[],
        frequency=1, recency_score=1.0,
    )
    concept = SimpleNamespace(
        title="Async Lights", mood="playful", bpm=142, genre_tags=["cyberpop"],
        narrative_arc="An async story",
    )
    prompt = SimpleNamespace(
        title="Async Lights", suno_prompt="cyberpop", lyrics="[Chorus]\nAsync lights",
        evidence_ids=[],
    )
    history = Mock(return_value=["Earlier song"])
    theme_history = Mock(return_value=["Earlier theme"])
    choose_theme = Mock(return_value=theme)
    load_state = Mock(return_value=object())
    normalize = Mock(return_value=[])
    generate = Mock(return_value=concept)
    compose = Mock(return_value=object())
    submit = Mock()
    validate = Mock(return_value=SimpleNamespace(overall_truth_score=1.0, flagged_claims=[]))
    monkeypatch.setattr(main, "print_startup_notice", Mock())
    monkeypatch.setattr(main, "build_github_profile_context", github)
    monkeypatch.setattr(main, "OllamaService", constructor)
    monkeypatch.setattr(rei_suno, "get_rei_toei_dir", lambda create=False: tmp_path)
    monkeypatch.setattr(rei_strudel, "get_rei_toei_dir", lambda create=False: tmp_path)
    monkeypatch.setattr(avatar, "load_avatar_state", load_state)
    monkeypatch.setattr(avatar, "normalize_extracted_facts", normalize)
    monkeypatch.setattr(rei, "load_rei_persona", Mock())
    monkeypatch.setattr(rei, "load_rei_domain_knowledge", Mock())
    monkeypatch.setattr(rei, "load_recent_rei_titles", history)
    monkeypatch.setattr(rei, "load_recent_rei_themes", theme_history)
    monkeypatch.setattr(rei, "extract_themes", Mock(return_value=[theme]))
    monkeypatch.setattr(rei, "choose_diverse_theme", choose_theme)
    monkeypatch.setattr(rei, "generate_song_concept", generate)
    monkeypatch.setattr(rei, "compose_lyrics", compose)
    monkeypatch.setattr(rei, "assemble_suno_prompt", Mock(return_value=prompt))
    monkeypatch.setattr(rei, "submit_to_suno", submit)
    monkeypatch.setattr(rei, "validate_lyrics_with_dot", validate)
    return SimpleNamespace(
        ai=ai, constructor=constructor, github=github, history=history,
        theme_history=theme_history, choose_theme=choose_theme,
        load_state=load_state, normalize=normalize, generate=generate,
        compose=compose, submit=submit, validate=validate, output_dir=tmp_path,
    )


def test_theme_requires_a_value(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["main.py", "--rei-generate", "--rei-preview", "--rei-theme"])
    with pytest.raises(SystemExit) as exc:
        main.main()
    assert exc.value.code == 2
    assert "--rei-theme: expected one argument" in capsys.readouterr().err


def test_explicit_preview_skips_unused_preparation(
    preview: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        sys, "argv", ["main.py", "--rei-generate", "--rei-preview", "--rei-theme", "async"],
    )
    with caplog.at_level(logging.INFO):
        main.main()
    assert "Preview mode" in capsys.readouterr().out
    preview.github.assert_not_called()
    preview.load_state.assert_not_called()
    preview.normalize.assert_not_called()
    preview.constructor.assert_called_once()
    assert preview.generate.call_args.args[4] is preview.ai
    assert preview.compose.call_args.args[4] is preview.ai
    preview.history.assert_called_once()
    preview.theme_history.assert_called_once()
    preview.submit.assert_not_called()
    preview.validate.assert_not_called()
    assert not list(preview.output_dir.glob("*_suno.json"))
    assert (preview.output_dir / "title_history.jsonl").exists()
    for stage in ("rei.concept", "rei.lyrics", "rei.suno_formatting"):
        assert f"Stage end stage={stage}" in caplog.text


def test_automatic_preview_loads_knowledge_and_history_once(
    preview: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["main.py", "--rei-generate", "--rei-preview"])
    main.main()
    assert "Preview mode" in capsys.readouterr().out
    preview.github.assert_not_called()
    preview.load_state.assert_called_once()
    preview.normalize.assert_called_once()
    preview.history.assert_called_once()
    preview.theme_history.assert_called_once()
    assert preview.choose_theme.call_args.kwargs["recent_theme_names"] == ["Earlier theme"]
    preview.submit.assert_not_called()
    assert preview.generate.call_args.args[5] == ["Earlier song"]


def test_automatic_preview_theme_is_avoided_by_the_next_preview(
    preview: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["main.py", "--rei-generate", "--rei-preview"])

    main.main()
    capsys.readouterr()

    assert load_recent_rei_themes(preview.output_dir) == ["Async"]

    preview.theme_history.reset_mock()
    preview.theme_history.side_effect = lambda *_args, **_kwargs: load_recent_rei_themes(
        preview.output_dir
    )
    preview.choose_theme.reset_mock()
    main.main()
    capsys.readouterr()

    assert preview.choose_theme.call_args.kwargs["recent_theme_names"] == ["Async"]
    assert not list(preview.output_dir.glob("*_suno.json"))


@pytest.mark.parametrize("preview_mode", [True, False])
def test_failed_lyrics_stop_before_formatting_saving_or_submission(
    preview: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str],
    preview_mode: bool,
) -> None:
    preview.compose.side_effect = LyricCompositionError(
        "Lyric composition failed after 5 attempts. No song was generated; please try again."
    )
    arguments = ["main.py", "--rei-generate", "--rei-theme", "async"]
    if preview_mode:
        arguments.append("--rei-preview")
    monkeypatch.setattr(sys, "argv", arguments)

    with caplog.at_level(logging.INFO), pytest.raises(SystemExit) as exc:
        main.main()

    assert exc.value.code == 1
    output = capsys.readouterr().out
    assert "No song was generated" in output
    assert "SUNO SONG" not in output
    rei.assemble_suno_prompt.assert_not_called()
    preview.submit.assert_not_called()
    preview.validate.assert_not_called()
    assert not list(preview.output_dir.glob("*_suno.json"))
    assert (preview.output_dir / "title_history.jsonl").exists()
    assert "status=error" in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


def test_explicit_explain_keeps_evidence_validation(
    preview: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", [
        "main.py", "--rei-generate", "--rei-preview", "--rei-theme", "async", "--rei-explain",
    ])
    main.main()
    assert "DoT score" in capsys.readouterr().out
    preview.load_state.assert_called_once()
    preview.normalize.assert_called_once()
    preview.validate.assert_called_once()
    preview.submit.assert_not_called()


def test_rei_default_model_is_preserved(
    preview: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.setattr(
        sys, "argv", ["main.py", "--rei-generate", "--rei-preview", "--rei-theme", "async"],
    )
    main.main()
    assert preview.constructor.call_args.kwargs["model"] == "gemma4:e4b"


def test_strudel_explicit_preview_reuses_client_without_loading_avatar(
    preview: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    template = SimpleNamespace(name="Async pattern")
    generate = Mock(return_value=SimpleNamespace(strudel_code='sound("bd")'))
    execute = Mock()
    monkeypatch.setattr(rei, "load_strudel_patterns", Mock())
    monkeypatch.setattr(rei, "map_concept_to_pattern", Mock(return_value=template))
    monkeypatch.setattr(rei, "generate_strudel_code", generate)
    monkeypatch.setattr(
        rei, "validate_strudel_syntax", Mock(return_value=SimpleNamespace(valid=True)),
    )
    monkeypatch.setattr(rei, "execute_strudel_pattern", execute)
    monkeypatch.setattr(sys, "argv", [
        "main.py", "--rei-generate-strudel", "--rei-preview", "--rei-theme", "async",
    ])
    main.main()
    assert "Preview mode" in capsys.readouterr().out
    preview.github.assert_not_called()
    preview.load_state.assert_not_called()
    assert generate.call_args.args[5] is preview.ai
    execute.assert_not_called()


def test_console_still_loads_github_context(
    preview: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    console = Mock()
    monkeypatch.setattr(main, "run_console", console)
    monkeypatch.setattr(sys, "argv", ["main.py", "--console"])
    main.main()
    preview.github.assert_called_once()
    assert console.call_args.kwargs["github_context"] == "unused GitHub context"
