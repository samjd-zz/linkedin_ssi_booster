"""Rei lyric JSON repair for common small-model formatting mistakes."""

import pytest

from services.rei_toei._suno_json import _parse_llm_json_payload


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            '{\n "title": "Java Loop",\n "verse_1": "Line one",\n "Line two",\n "Line three",\n "chorus": "Hook"\n}',
            {"title": "Java Loop", "verse_1": "Line one\nLine two\nLine three", "chorus": "Hook"},
        ),
        (
            '{\n "verse_1": "She said "run" now",\n "chorus": "Hook"\n}',
            {"verse_1": 'She said "run" now', "chorus": "Hook"},
        ),
        (
            '{"verse_1": "Say "go"",\n"Then run",\n"chorus": "Hook"}',
            {"verse_1": 'Say "go"\nThen run', "chorus": "Hook"},
        ),
    ],
    ids=["orphan-lines", "inner-quotes", "both"],
)
def test_parse_repairs_orphan_lines_and_inner_quotes(raw: str, expected: dict) -> None:
    assert _parse_llm_json_payload(raw) == expected


def test_parse_leaves_valid_json_unchanged() -> None:
    raw = '{"verse_1": "A\\nB", "tags": ["x", "y"], "meta": {"bpm": 142}}'
    assert _parse_llm_json_payload(raw) == {
        "verse_1": "A\nB", "tags": ["x", "y"], "meta": {"bpm": 142},
    }


def test_parse_still_raises_for_truncated_json() -> None:
    import json

    with pytest.raises(json.JSONDecodeError):
        _parse_llm_json_payload('{"verse_1": "broken')
