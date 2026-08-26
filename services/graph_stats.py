"""Helpers for graph diagnostics and domain-knowledge reporting."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _safe_read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Read a JSON object from disk and return a structured error when invalid."""
    if not path.exists():
        return None, f"missing: {path}"
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return None, f"invalid_json: {path} ({exc})"
    if not isinstance(parsed, dict):
        return None, f"invalid_shape: {path} (expected object)"
    return parsed, None


def _count_array_field(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    return len(value) if isinstance(value, list) else 0


def collect_sam_domain_knowledge_stats(data_dir: Path) -> dict[str, Any]:
    """Collect aggregate stats for Sam domain knowledge packs.

    Sam uses a canonical shape with top-level arrays: domains, facts,
    relationships. This loader includes:
    - domain_knowledge.json
    - any sibling domain_knowledge_*.json packs
    """
    base_path = data_dir / "domain_knowledge.json"
    extra_paths = sorted(data_dir.glob("domain_knowledge_*.json"))
    all_paths = [base_path, *extra_paths]

    files: list[dict[str, Any]] = []
    errors: list[str] = []
    totals = {"domains": 0, "facts": 0, "relationships": 0}

    for path in all_paths:
        data, error = _safe_read_json(path)
        if error is not None:
            errors.append(error)
            continue
        if data is None:
            continue

        domains = _count_array_field(data, "domains")
        facts = _count_array_field(data, "facts")
        relationships = _count_array_field(data, "relationships")

        totals["domains"] += domains
        totals["facts"] += facts
        totals["relationships"] += relationships

        files.append(
            {
                "file": path.name,
                "domains": domains,
                "facts": facts,
                "relationships": relationships,
            }
        )

    return {
        "profile": "sam",
        "base_file": base_path.name,
        "files_loaded": len(files),
        "files": files,
        "totals": totals,
        "errors": errors,
    }


def _count_nested_shape(value: Any) -> dict[str, int]:
    """Return recursive shape counts for dict/list-heavy documents."""
    counts = {
        "dict_nodes": 0,
        "dict_keys": 0,
        "list_nodes": 0,
        "list_items": 0,
        "scalar_nodes": 0,
    }

    def _visit(node: Any) -> None:
        if isinstance(node, dict):
            counts["dict_nodes"] += 1
            counts["dict_keys"] += len(node)
            for child in node.values():
                _visit(child)
            return
        if isinstance(node, list):
            counts["list_nodes"] += 1
            counts["list_items"] += len(node)
            for child in node:
                _visit(child)
            return
        counts["scalar_nodes"] += 1

    _visit(value)
    return counts


def collect_rei_domain_knowledge_stats(data_dir: Path) -> dict[str, Any]:
    """Collect structural stats for Rei domain knowledge.

    Rei uses a rich nested schema (music_theory, tidal_cycles_syntax, etc.)
    instead of the Sam domains/facts/relationships arrays, so we report
    shape-level counts and section-level sizes.
    """
    rei_path = data_dir / "rei_toei_domain_knowledge.json"
    data, error = _safe_read_json(rei_path)
    if error is not None or data is None:
        return {
            "profile": "rei",
            "file": rei_path.name,
            "exists": False,
            "sections": [],
            "section_count": 0,
            "shape": {
                "dict_nodes": 0,
                "dict_keys": 0,
                "list_nodes": 0,
                "list_items": 0,
                "scalar_nodes": 0,
            },
            "errors": [error] if error else [],
        }

    sections: list[dict[str, Any]] = []
    for key, value in data.items():
        if key in {"schemaVersion", "description"}:
            continue
        if isinstance(value, dict):
            size = len(value)
            value_type = "dict"
        elif isinstance(value, list):
            size = len(value)
            value_type = "list"
        else:
            size = 1
            value_type = "scalar"
        sections.append({"name": key, "type": value_type, "size": size})

    sections.sort(key=lambda row: int(row["size"]), reverse=True)
    shape = _count_nested_shape(data)

    return {
        "profile": "rei",
        "file": rei_path.name,
        "exists": True,
        "sections": sections,
        "section_count": len(sections),
        "shape": shape,
        "errors": [],
    }


def collect_domain_knowledge_profiles(data_dir: Path) -> dict[str, Any]:
    """Collect both Sam and Rei domain-knowledge profile summaries."""
    return {
        "sam": collect_sam_domain_knowledge_stats(data_dir),
        "rei": collect_rei_domain_knowledge_stats(data_dir),
    }
