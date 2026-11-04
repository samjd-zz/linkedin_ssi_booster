"""Shared host contract for ContentCurator mixins."""

import uuid
from typing import TYPE_CHECKING, Any

from services.console_grounding import ProjectFact, TruthGateMeta
from services.ollama_service import OllamaService

# Stable run identifier — shared across all candidates logged in this process.
_CURATE_RUN_ID: str = str(uuid.uuid4())


class CuratorHost:
    """Attributes and hooks that ContentCurator provides to its mixins."""

    ai: OllamaService
    buffer: Any
    confidence_policy: str
    github_context: str
    _classify: bool
    _avatar_facts: list
    _domain_facts: list
    _extracted_facts: list
    _topic_signal: dict[str, int]
    _narrative_memory: Any
    _spacy_nlp: Any

    if TYPE_CHECKING:
        def _score_and_route(
            self,
            post_text: str,
            article_summary: str,
            grounding_facts: list[ProjectFact],
            channel: str,
            article_ref: str,
            requested_mode: str,
            gate_meta: TruthGateMeta | None = None,
        ) -> tuple[str, str]: ...
