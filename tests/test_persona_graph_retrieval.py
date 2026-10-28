"""T6.6 — Integration tests for persona graph retrieval cutover.

These tests load the local data/avatar/persona_graph.json to verify:
- The graph loads every project present in the source file
- Graph-backed retrieval returns expected projects for known queries
- The app starts without PROFILE_CONTEXT set (migration regression gate R4)
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from services.avatar_intelligence import (
    AvatarState,
    load_avatar_state,
    normalize_evidence_facts,
    retrieve_evidence,
)
import services.avatar_intelligence as ai

# Paths to locally configured avatar data.
_REAL_PG = Path(__file__).parent.parent / "data" / "avatar" / "persona_graph.json"
_REAL_NM = Path(__file__).parent.parent / "data" / "avatar" / "narrative_memory.json"
_MAIN = str(Path(__file__).parent.parent / "main.py")


# ---------------------------------------------------------------------------
# Fixture: load the real avatar state once per module
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_state() -> AvatarState:
    """Load local avatar data, restoring path overrides even on load failure."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(ai, "PERSONA_GRAPH_PATH", _REAL_PG)
        patch.setattr(ai, "NARRATIVE_MEMORY_PATH", _REAL_NM)
        state = load_avatar_state()
    project_names = {p.name for p in state.persona_graph.projects} if state.persona_graph else set()
    required_private_projects = {"G7 GovAI Grand Challenge RIA", "Answer42"}
    if not required_private_projects.issubset(project_names):
        pytest.skip(
            "Maintainer-specific persona graph not configured; skipping private persona retrieval checks."
        )
    return state


# ---------------------------------------------------------------------------
# Graph load quality
# ---------------------------------------------------------------------------


def test_real_graph_loads_successfully(real_state) -> None:
    assert real_state.is_loaded is True
    assert real_state.load_errors == []


def test_real_graph_has_expected_project_count(real_state: AvatarState) -> None:
    assert real_state.persona_graph is not None
    source = json.loads(_REAL_PG.read_text(encoding="utf-8"))
    expected_ids = [project["id"] for project in source["projects"]]
    assert expected_ids
    assert [project.id for project in real_state.persona_graph.projects] == expected_ids


def test_real_graph_has_skills(real_state) -> None:
    assert len(real_state.persona_graph.skills) >= 20


def test_real_graph_has_companies(real_state) -> None:
    assert len(real_state.persona_graph.companies) >= 5


# ---------------------------------------------------------------------------
# Evidence fact normalization on real data
# ---------------------------------------------------------------------------


def test_normalize_evidence_facts_real(real_state: AvatarState) -> None:
    assert real_state.persona_graph is not None
    facts = normalize_evidence_facts(real_state)
    projects = real_state.persona_graph.projects
    assert len(facts) == len(projects)
    assert [fact.source_project_id for fact in facts] == [project.id for project in projects]
    for fact, project in zip(facts, projects, strict=True):
        assert fact.project == project.name
        assert fact.details == project.details
        assert fact.years == project.years
        assert fact.skills == project.skills


def test_evidence_ids_all_unique(real_state) -> None:
    facts = normalize_evidence_facts(real_state)
    ids = [f.evidence_id for f in facts]
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Retrieval quality — known query → expected top project
# ---------------------------------------------------------------------------


def test_retrieval_govai_tops_rag_query(real_state) -> None:
    """RAG + hybrid-search query should surface G7 GovAI project first."""
    facts = normalize_evidence_facts(real_state)
    results = retrieve_evidence("rag hybrid search elasticsearch government ai", facts, limit=3)
    top_names = [r.project for r in results]
    assert "G7 GovAI Grand Challenge RIA" in top_names[:2]


def test_retrieval_answer42_tops_spring_batch_query(real_state) -> None:
    """Spring Batch query should surface Answer42 project."""
    facts = normalize_evidence_facts(real_state)
    results = retrieve_evidence("spring batch java spring-boot batch processing", facts, limit=3)
    top_names = [r.project for r in results]
    assert "Answer42" in top_names[:2]


def test_retrieval_limit_respected(real_state) -> None:
    facts = normalize_evidence_facts(real_state)
    results = retrieve_evidence("python api ml", facts, limit=3)
    assert len(results) <= 3


def test_retrieval_unrelated_query_returns_fallback(real_state) -> None:
    """Even for an unrelated query, falls back to first N facts."""
    facts = normalize_evidence_facts(real_state)
    results = retrieve_evidence("underwater basket weaving origami", facts, limit=2)
    assert len(results) == 2  # fallback always returns `limit` items


# ---------------------------------------------------------------------------
# Migration regression gate R4 — app runs without PROFILE_CONTEXT
# ---------------------------------------------------------------------------


def test_app_starts_without_profile_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Running --help should succeed without PROFILE_CONTEXT in environment."""
    import os
    env = {k: v for k, v in os.environ.items() if k != "PROFILE_CONTEXT"}
    result = subprocess.run(
        [sys.executable, _MAIN, "--help"],
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
        cwd=str(Path(_MAIN).parent),
    )
    assert result.returncode == 0
    assert "PROFILE_CONTEXT" not in result.stderr


def test_no_profile_context_env_loading_in_retrieval_code() -> None:
    """Verify console_grounding no longer loads PROFILE_CONTEXT from env (T7.4).

    The function parse_profile_project_facts may still exist as a utility but
    must not call os.getenv('PROFILE_CONTEXT') so the env var is not required.
    Now checks the console_grounding package directory (refactored from single file).
    """
    cg_dir = Path(__file__).parent.parent / "services" / "console_grounding"
    sources: list[str] = []
    if cg_dir.is_dir():
        for py_file in sorted(cg_dir.glob("*.py")):
            sources.append(py_file.read_text(encoding="utf-8"))
    else:
        # Fallback: single-file layout (pre-refactor)
        cg_path = Path(__file__).parent.parent / "services" / "console_grounding.py"
        sources.append(cg_path.read_text(encoding="utf-8"))
    combined = "\n".join(sources)
    assert 'os.getenv("PROFILE_CONTEXT"' not in combined, (
        "console_grounding still loads PROFILE_CONTEXT from env — migration incomplete"
    )
    assert "os.getenv('PROFILE_CONTEXT'" not in combined, (
        "console_grounding still loads PROFILE_CONTEXT from env — migration incomplete"
    )
