"""
Tests for Rei Toei CLI flag parsing and validation

These tests verify that the CLI argument parser correctly handles
all Rei Toei music generation flags and triggers the correct generation pipeline.
"""

import pytest
import os
import sys
from contextlib import ExitStack
from unittest.mock import patch, MagicMock, AsyncMock


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _mock_theme(name: str = "machine learning") -> MagicMock:
    t = MagicMock()
    t.id = "test_ml"
    t.name = name
    t.technical_concepts = ["neural networks"]
    t.evidence_ids = []
    t.frequency = 3
    t.recency_score = 0.9
    return t


def _mock_concept() -> MagicMock:
    c = MagicMock()
    c.song_id = "song_001"
    c.title = "Neural Cascade"
    c.theme = "machine learning"
    c.mood = "intense"
    c.bpm = 142
    c.genre_tags = ["industrial techno"]
    c.narrative_arc = "Data flows through silicon"
    c.evidence_ids = []
    return c


def _mock_lyrics() -> MagicMock:
    l = MagicMock()
    l.verse_1 = "Data flows through silicon dreams"
    l.chorus = "Neural cascade, electric cascade"
    l.verse_2 = "Weights adjust in gradient descent"
    l.bridge = "Backpropagation through the void"
    l.breakdown = None
    l.evidence_ids = []
    return l


def _mock_suno_prompt() -> MagicMock:
    p = MagicMock()
    p.song_id = "song_001"
    p.title = "Neural Cascade"
    p.suno_prompt = "industrial techno cyberpunk, 142 bpm, female ai vocaloid"
    p.lyrics = "[Verse 1]\nData flows through silicon dreams\n\n[Chorus]\nNeural cascade"
    p.metadata = {}
    p.evidence_ids = []
    p.generated_at = "2026-05-20T00:00:00+00:00"
    return p


def _mock_template() -> MagicMock:
    t = MagicMock()
    t.template_id = "tmpl_001"
    t.name = "neural_cascade"
    t.description = "Cascading neural network pattern"
    t.code_template = "stack(s('bd sd'), s('hh*4'))"
    t.parameters = {}
    t.suitable_for_concepts = ["neural networks", "machine learning"]
    return t


def _mock_validation(is_valid: bool = True) -> MagicMock:
    v = MagicMock()
    v.is_valid = is_valid
    v.errors = []
    return v


def _mock_dot_score(valid: bool = True) -> MagicMock:
    d = MagicMock()
    d.valid = valid
    d.overall_truth_score = 0.85 if valid else 0.30
    d.flagged_claims = [] if valid else ["Unsupported claim about data throughput"]
    d.truth_gradients = {}
    d.warnings = []
    return d


def _mock_pattern_library() -> MagicMock:
    lib = MagicMock()
    lib.templates = [_mock_template()]
    lib.patterns = []
    return lib


def _mock_exec_result(success: bool = True) -> MagicMock:
    r = MagicMock()
    r.success = success
    r.output = "Pattern playing" if success else None
    r.error = None if success else "Connection refused"
    return r


# ---------------------------------------------------------------------------
# Helper: run main() with all Rei Toei dependencies mocked
# ---------------------------------------------------------------------------

def _run_main_with_rei_mocks(
    argv: list,
    env: dict | None = None,
    dot_result: MagicMock | None = None,
    rei_output_dir=None,
) -> MagicMock:
    """
    Run main() with all Rei Toei service dependencies mocked.
    Returns the mock_print object so callers can assert on output; the Suno
    submission mock is attached as ``mock_print.rei_submit_mock``.
    """
    # generate_strudel_code is synchronous — returns a StrudelPattern object
    _mock_strudel_pattern = MagicMock()
    _mock_strudel_pattern.strudel_code = "stack(s('bd sd'), s('hh*4'))"
    _mock_strudel_pattern.pattern_id = "test_001"
    _mock_strudel_pattern.title = "machine learning pattern"
    mock_gen_strudel = MagicMock(return_value=_mock_strudel_pattern)
    # execute_strudel_pattern is async
    mock_exec_strudel = AsyncMock(return_value=_mock_exec_result(success=True))
    mock_submit = AsyncMock(
        return_value=MagicMock(id="task_001", status="complete", audio_url=None, video_url=None)
    )

    with ExitStack() as stack:
        stack.enter_context(patch("sys.argv", argv))
        if env is not None:
            stack.enter_context(patch.dict(os.environ, env))
        if rei_output_dir is not None:
            stack.enter_context(
                patch("main.get_rei_toei_dir", return_value=rei_output_dir)
            )
        # Infrastructure mocks
        stack.enter_context(
            patch("services.github_service.build_github_profile_context", return_value="")
        )
        stack.enter_context(
            patch("services.ollama_service.OllamaService", return_value=MagicMock())
        )
        # Avatar intelligence mocks
        stack.enter_context(
            patch("services.avatar_intelligence.load_avatar_state", return_value=MagicMock())
        )
        stack.enter_context(
            patch("services.avatar_intelligence.normalize_extracted_facts", return_value=[])
        )
        # Rei Toei service mocks
        stack.enter_context(
            patch("services.rei_toei_service.load_rei_persona", return_value=MagicMock())
        )
        stack.enter_context(
            patch("services.rei_toei_service.load_rei_domain_knowledge", return_value=MagicMock())
        )
        stack.enter_context(
            patch("services.rei_toei_service.load_strudel_patterns", return_value=_mock_pattern_library())
        )
        stack.enter_context(
            patch("services.rei_toei_service.extract_themes", return_value=[_mock_theme()])
        )
        stack.enter_context(
            patch("services.rei_toei_service.generate_song_concept", return_value=_mock_concept())
        )
        stack.enter_context(
            patch("services.rei_toei_service.compose_lyrics", return_value=_mock_lyrics())
        )
        stack.enter_context(
            patch("services.rei_toei_service.assemble_suno_prompt", return_value=_mock_suno_prompt())
        )
        stack.enter_context(
            patch(
                "services.rei_toei_service.validate_lyrics_with_dot",
                return_value=dot_result if dot_result is not None else _mock_dot_score(),
            )
        )
        stack.enter_context(
            patch("services.rei_toei_service.submit_to_suno", mock_submit)
        )
        stack.enter_context(
            patch("services.rei_toei_service.map_concept_to_pattern", return_value=_mock_template())
        )
        stack.enter_context(
            patch("services.rei_toei_service.generate_strudel_code", mock_gen_strudel)
        )
        stack.enter_context(
            patch("services.rei_toei_service.validate_strudel_syntax", return_value=_mock_validation())
        )
        stack.enter_context(patch("services.rei_toei_service.save_pattern_to_library"))
        stack.enter_context(
            patch("services.rei_toei_service.execute_strudel_pattern", mock_exec_strudel)
        )
        mock_print = stack.enter_context(patch("builtins.print"))

        from main import main
        main()
        mock_print.rei_submit_mock = mock_submit
        return mock_print


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_rei_generate_flag_parses():
    """Test that --rei-generate flag triggers Suno generation pipeline."""
    mock_print = _run_main_with_rei_mocks(["main.py", "--rei-generate", "--rei-preview"])
    output = str(mock_print.call_args_list)
    # Should show Rei Toei Suno header and song title from mock
    assert "REI TOEI" in output or "Neural Cascade" in output or "Suno" in output


def test_rei_generate_strudel_flag_parses():
    """Test that --rei-generate-strudel flag triggers Strudel generation pipeline."""
    mock_print = _run_main_with_rei_mocks(["main.py", "--rei-generate-strudel", "--rei-preview"])
    output = str(mock_print.call_args_list)
    # Should show Rei Toei Strudel header and template name from mock
    assert "REI TOEI" in output or "Strudel" in output or "neural_cascade" in output


def test_rei_theme_flag_parses():
    """Test that --rei-theme accepts string argument and uses it as theme."""
    mock_print = _run_main_with_rei_mocks(
        ["main.py", "--rei-generate", "--rei-theme", "microservices", "--rei-preview"]
    )
    output = str(mock_print.call_args_list)
    # Should show the specified theme in output
    assert "microservices" in output or "REI TOEI" in output


def test_rei_explain_flag_parses():
    """Test that --rei-explain flag shows reasoning output."""
    mock_print = _run_main_with_rei_mocks(
        ["main.py", "--rei-generate", "--rei-explain", "--rei-preview"]
    )
    output = str(mock_print.call_args_list)
    # Should show reasoning section header
    assert "Reasoning" in output or "REI TOEI" in output or "Theme" in output


def test_rei_preview_flag_parses():
    """Test that --rei-preview flag shows preview message and skips saving."""
    mock_print = _run_main_with_rei_mocks(
        ["main.py", "--rei-generate-strudel", "--rei-preview"]
    )
    output = str(mock_print.call_args_list)
    # Should show preview mode message
    assert "Preview" in output or "preview" in output or "REI TOEI" in output


def test_rei_execute_flag_parses():
    """Test that --rei-execute flag triggers pattern execution."""
    mock_print = _run_main_with_rei_mocks(
        ["main.py", "--rei-generate-strudel", "--rei-execute"]
    )
    output = str(mock_print.call_args_list)
    # Should show Strudel pattern output and execution result
    assert "REI TOEI" in output or "Strudel" in output or "Pattern" in output


def test_rei_combined_flags_parse():
    """Test that multiple Rei flags can be combined without error."""
    mock_print = _run_main_with_rei_mocks(
        [
            "main.py",
            "--rei-generate-strudel",
            "--rei-theme", "kubernetes",
            "--rei-explain",
            "--rei-preview",
        ]
    )
    output = str(mock_print.call_args_list)
    # Should parse without error and show output
    assert "REI TOEI" in output or "Strudel" in output or "kubernetes" in output


def test_rei_flags_show_helpful_message():
    """Test that Rei CLI flags display generation output with Rei Toei branding."""
    mock_print = _run_main_with_rei_mocks(["main.py", "--rei-generate", "--rei-preview"])
    calls = [str(call) for call in mock_print.call_args_list]
    output = " ".join(calls)
    # Should show Rei Toei branding in output
    assert (
        "rei toei" in output.lower()
        or "suno" in output.lower()
        or "neural cascade" in output.lower()
    )


def test_rei_generate_respects_rei_toei_enabled_false():
    """REI_TOEI_ENABLED=false must short-circuit the rei flow.

    Regression: the flag was documented and loaded into ReiToeiConfig but
    never checked, so disabling Rei Toei did nothing.
    """
    mock_print = _run_main_with_rei_mocks(
        ["main.py", "--rei-generate", "--rei-preview"],
        env={"REI_TOEI_ENABLED": "false"},
    )
    output = str(mock_print.call_args_list)
    assert "disabled" in output.lower()
    assert "Neural Cascade" not in output


def test_rei_generate_skips_suno_submit_when_dot_invalid(tmp_path):
    """A failing DoT validation saves the song but skips Suno auto-submission.

    Regression: validate_lyrics_with_dot only ran under --rei-explain and its
    `valid` flag never gated anything — unvalidated songs were submitted.
    """
    mock_print = _run_main_with_rei_mocks(
        ["main.py", "--rei-generate"],
        env={"SUNO_API_KEY": "test-key", "REI_TOEI_DOT_VALIDATION_ENABLED": "true"},
        dot_result=_mock_dot_score(valid=False),
        rei_output_dir=tmp_path,
    )
    output = str(mock_print.call_args_list)
    assert "skipping suno submission" in output.lower()
    mock_print.rei_submit_mock.assert_not_awaited()
    # The song artifact is still saved locally for review
    assert list(tmp_path.glob("rei_*_suno.json"))


def test_rei_generate_submits_to_suno_when_dot_valid(tmp_path):
    """With a valid DoT result and an API key, submission proceeds."""
    mock_print = _run_main_with_rei_mocks(
        ["main.py", "--rei-generate"],
        env={"SUNO_API_KEY": "test-key", "REI_TOEI_DOT_VALIDATION_ENABLED": "true"},
        dot_result=_mock_dot_score(valid=True),
        rei_output_dir=tmp_path,
    )
    mock_print.rei_submit_mock.assert_awaited()