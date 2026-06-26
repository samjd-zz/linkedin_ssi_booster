"""T6.5 — Integration tests for CLI flags and generate/curate flow regressions."""
import subprocess
import sys
from pathlib import Path

import pytest


_MAIN = str(Path(__file__).parent.parent / "main.py")


# ---------------------------------------------------------------------------
# Import sanity
# ---------------------------------------------------------------------------


def test_main_imports_without_profile_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """main.py must import cleanly with no PROFILE_CONTEXT env var set."""
    monkeypatch.delenv("PROFILE_CONTEXT", raising=False)
    result = subprocess.run(
        [sys.executable, "-c", "import importlib.util; "
         "spec = importlib.util.spec_from_file_location('m', 'main.py'); "
         "mod = importlib.util.module_from_spec(spec); "
         "spec.loader.exec_module(mod)"],
        cwd=str(Path(_MAIN).parent),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# Flag recognition — run main.py --help and check flags appear
# ---------------------------------------------------------------------------


def test_avatar_explain_flag_in_help() -> None:
    result = subprocess.run(
        [sys.executable, _MAIN, "--help"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert "--avatar-explain" in result.stdout


def test_avatar_learn_report_flag_in_help() -> None:
    result = subprocess.run(
        [sys.executable, _MAIN, "--help"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert "--avatar-learn-report" in result.stdout


def test_confidence_policy_flag_in_help() -> None:
    result = subprocess.run(
        [sys.executable, _MAIN, "--help"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert "--confidence-policy" in result.stdout


def test_confidence_policy_valid_choices_in_help() -> None:
    result = subprocess.run(
        [sys.executable, _MAIN, "--help"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert "strict" in result.stdout
    assert "balanced" in result.stdout
    assert "draft-first" in result.stdout


# ---------------------------------------------------------------------------
# --confidence-policy invalid value rejected by argparse
# ---------------------------------------------------------------------------


def test_confidence_policy_invalid_rejected() -> None:
    result = subprocess.run(
        [sys.executable, _MAIN, "--generate", "--confidence-policy", "invalid-value"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    # argparse should exit with code 2 for invalid choice
    assert result.returncode == 2
    assert "invalid-value" in result.stderr or "invalid choice" in result.stderr


# ---------------------------------------------------------------------------
# --avatar-learn-report exits cleanly (no API calls required)
# ---------------------------------------------------------------------------


def test_avatar_learn_report_exits_cleanly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--avatar-learn-report should print report and exit 0 even with empty log."""
    env = {"AVATAR_DATA_DIR": str(tmp_path), "PATH": "/usr/bin:/bin"}
    result = subprocess.run(
        [sys.executable, _MAIN, "--avatar-learn-report"],
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
        cwd=str(Path(_MAIN).parent),
    )
    assert result.returncode == 0
    # Should print the report header
    assert "Avatar Learning Report" in result.stdout or "Learning Report" in result.stdout
