"""Tests for graph/domain knowledge stats helpers."""

from __future__ import annotations

import json
from pathlib import Path

from services.graph_stats import (
    collect_domain_knowledge_profiles,
    collect_rei_domain_knowledge_stats,
    collect_sam_domain_knowledge_stats,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_collect_sam_domain_knowledge_stats_aggregates_base_and_packs(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "domain_knowledge.json",
        {
            "domains": [{"id": "d1"}],
            "facts": [{"id": "f1"}, {"id": "f2"}],
            "relationships": [{"id": "r1"}],
        },
    )
    _write_json(
        tmp_path / "domain_knowledge_python.json",
        {
            "domains": [{"id": "d2"}, {"id": "d3"}],
            "facts": [{"id": "f3"}],
            "relationships": [],
        },
    )

    stats = collect_sam_domain_knowledge_stats(tmp_path)

    assert stats["files_loaded"] == 2
    assert stats["totals"]["domains"] == 3
    assert stats["totals"]["facts"] == 3
    assert stats["totals"]["relationships"] == 1
    assert stats["errors"] == []


def test_collect_rei_domain_knowledge_stats_reports_structure(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "rei_toei_domain_knowledge.json",
        {
            "schemaVersion": "1.0",
            "music_theory": {
                "scales": {"minor": ["a", "b", "c"]},
                "rhythm": {"signatures": ["4/4"]},
            },
            "genre_production_techniques": {
                "techno": ["compression", "distortion"],
            },
            "production_notes": ["note-a", "note-b"],
        },
    )

    stats = collect_rei_domain_knowledge_stats(tmp_path)

    assert stats["exists"] is True
    assert stats["section_count"] == 3
    assert stats["shape"]["dict_keys"] > 0
    assert stats["shape"]["list_items"] >= 6
    top_names = [s["name"] for s in stats["sections"]]
    assert "music_theory" in top_names


def test_collect_domain_knowledge_profiles_includes_sam_and_rei(tmp_path: Path) -> None:
    _write_json(tmp_path / "domain_knowledge.json", {"domains": [], "facts": [], "relationships": []})
    _write_json(tmp_path / "rei_toei_domain_knowledge.json", {"schemaVersion": "1.0", "music_theory": {}})

    profiles = collect_domain_knowledge_profiles(tmp_path)

    assert set(profiles.keys()) == {"sam", "rei"}
    assert profiles["sam"]["files_loaded"] == 1
    assert profiles["rei"]["exists"] is True
