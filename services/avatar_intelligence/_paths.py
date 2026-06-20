"""
Path configuration for the avatar_intelligence package.

Resolution hierarchy (first match wins for each path):
  1. Individual env var (e.g. PERSONA_GRAPH_PATH)
  2. AVATAR_DATA_DIR + default filename
  3. Repo-relative default (data/avatar/<filename>)

This lets you:
  - Point the whole suite at a different directory: set AVATAR_DATA_DIR
  - Override one specific file:  set e.g. DOMAIN_KNOWLEDGE_PATH
  - Merge multiple domain knowledge sources: set DOMAIN_KNOWLEDGE_EXTRA_PATHS
    (semicolon-separated list of additional .json paths; merged at load time)

Example configurations
----------------------
Simple fork with data elsewhere:
  AVATAR_DATA_DIR=/path/to/my-repo/data/corpus

Separate persona from domain knowledge (e.g. personal persona + org domain pack):
  PERSONA_GRAPH_PATH=/home/user/my-persona/persona_graph.json
  DOMAIN_KNOWLEDGE_EXTRA_PATHS=/org/shared/domain_knowledge.json

Multiple domain knowledge sources merged at runtime:
  DOMAIN_KNOWLEDGE_EXTRA_PATHS=/org/domain.json;/project/domain.json
"""

from __future__ import annotations

import os
from pathlib import Path

# ── Base directory ──────────────────────────────────────────────────────────
# All paths default to this directory + their standard filename.
# Override individual paths below to break files out of the base dir.
_BASE_DIR = Path(os.getenv("AVATAR_DATA_DIR", "data/avatar"))


def _path(env_var: str, filename: str) -> Path:
    """Resolve a path: individual env var > base dir > repo-relative default."""
    raw = os.getenv(env_var)
    if raw:
        return Path(raw)
    return _BASE_DIR / filename


# ── Primary data paths ──────────────────────────────────────────────────────
PERSONA_GRAPH_PATH       = _path("PERSONA_GRAPH_PATH",       "persona_graph.json")
NARRATIVE_MEMORY_PATH    = _path("NARRATIVE_MEMORY_PATH",    "narrative_memory.json")
DOMAIN_KNOWLEDGE_PATH    = _path("DOMAIN_KNOWLEDGE_PATH",    "domain_knowledge.json")
LEARNING_LOG_PATH        = _path("LEARNING_LOG_PATH",        "learning_log.jsonl")
EXTRACTED_KNOWLEDGE_PATH = _path("EXTRACTED_KNOWLEDGE_PATH", "extracted_knowledge.json")

# ── Additional domain knowledge sources (merged at load time) ───────────────
# Semicolon-separated list of extra domain knowledge JSON files to merge
# with DOMAIN_KNOWLEDGE_PATH. Useful for combining a personal domain pack
# with an org-wide or project-specific one without editing either.
_dk_extra_raw = os.getenv("DOMAIN_KNOWLEDGE_EXTRA_PATHS", "")
DOMAIN_KNOWLEDGE_EXTRA_PATHS: list[Path] = [
    Path(p.strip()) for p in _dk_extra_raw.split(";") if p.strip()
]
