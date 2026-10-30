"""Tests for the single-source project version constant in services.shared.

__version__ is the canonical version string. These tests enforce its format
and keep the human-maintained docs (README badge, .clinerules, Copilot
instructions) in sync with it.
"""

import re
from pathlib import Path

import pytest

from services.shared import __version__

PROJECT_ROOT = Path(__file__).resolve().parent.parent

VERSION_PATTERN = r"(alpha|beta|rc)-v\d+\.\d+\.\d+(\.\d+)?"


def test_version_format() -> None:
    """__version__ must follow the <stage>-v<major>.<minor>.<patch>[.<build>] scheme."""
    assert re.fullmatch(VERSION_PATTERN, __version__), (
        f"__version__ {__version__!r} does not match {VERSION_PATTERN!r}"
    )


@pytest.mark.parametrize(
    "doc_path",
    [
        "README.md",
        ".clinerules",
        ".github/copilot-instructions.md",
    ],
)
def test_docs_reference_current_version(doc_path: str) -> None:
    """Version-bearing docs must mention the current __version__ verbatim."""
    text = (PROJECT_ROOT / doc_path).read_text(encoding="utf-8")
    assert __version__ in text, (
        f"{doc_path} does not mention {__version__}; update it when bumping the version"
    )


def test_no_stale_version_stamps_in_source() -> None:
    """Module docstrings must not carry their own Version: stamps (they drift)."""
    offenders: list[str] = []
    for folder in ("services", "agents", "tests"):
        for py_file in (PROJECT_ROOT / folder).rglob("*.py"):
            if py_file.name == Path(__file__).name:
                continue
            if re.search(r"^Version: (alpha|beta|rc)-v", py_file.read_text(encoding="utf-8"), re.M):
                offenders.append(str(py_file.relative_to(PROJECT_ROOT)))
    assert not offenders, (
        f"Per-file version stamps found (use services.shared.__version__ instead): {offenders}"
    )
