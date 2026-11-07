"""Tests for Rei title history used to avoid repeating concept titles."""

import json
from pathlib import Path

from services.rei_toei import load_recent_rei_titles, record_rei_title
from services.rei_toei import _suno_themes


def test_preview_titles_are_recorded_and_loaded_newest_first(tmp_path: Path) -> None:
    record_rei_title(tmp_path, "Neural Net Nexus", "neural nets", preview=True)
    record_rei_title(tmp_path, "  Shinjuku   Flux ", "tokyo", preview=True)

    assert load_recent_rei_titles(tmp_path) == ["Shinjuku Flux", "Neural Net Nexus"]
    entry = json.loads((tmp_path / _suno_themes.REI_TITLE_HISTORY_FILE).read_text().splitlines()[0])
    assert entry["preview"] is True
    assert entry["theme"] == "neural nets"


def test_history_merges_with_saved_songs_without_duplicates(tmp_path: Path) -> None:
    (tmp_path / "rei_1_saved_suno.json").write_text(json.dumps({"title": "Saved Song"}))
    (tmp_path / "rei_2_dupe_suno.json").write_text(json.dumps({"title": "neural net NEXUS"}))
    record_rei_title(tmp_path, "Neural Net Nexus")

    titles = load_recent_rei_titles(tmp_path)

    assert titles[0] == "Neural Net Nexus"
    assert set(titles) == {"Neural Net Nexus", "Saved Song"}


def test_limit_and_malformed_lines_are_handled(tmp_path: Path) -> None:
    for index in range(5):
        record_rei_title(tmp_path, f"Title {index}")
    with (tmp_path / _suno_themes.REI_TITLE_HISTORY_FILE).open("a", encoding="utf-8") as handle:
        handle.write("not json\n")

    assert load_recent_rei_titles(tmp_path, limit=2) == ["Title 4", "Title 3"]


def test_history_file_is_capped(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(_suno_themes, "REI_TITLE_HISTORY_MAX", 3)
    for index in range(6):
        record_rei_title(tmp_path, f"Title {index}")

    lines = (tmp_path / _suno_themes.REI_TITLE_HISTORY_FILE).read_text().splitlines()
    assert [json.loads(line)["title"] for line in lines] == ["Title 3", "Title 4", "Title 5"]


def test_blank_title_is_ignored(tmp_path: Path) -> None:
    record_rei_title(tmp_path, "   ")
    assert not (tmp_path / _suno_themes.REI_TITLE_HISTORY_FILE).exists()
