"""Public API re-exports for the console_grounding package."""

from __future__ import annotations

# Config / constants
from services.console_grounding._config import (
    DEFAULT_TAG_EXPANSIONS,
    DEFAULT_TECH_KEYWORDS,
    DOMAIN_KNOWLEDGE_PHRASES,
    _normalize_phrase,
    get_console_grounding_keywords,
    get_console_grounding_tag_expansions_from_graph,
    get_truth_gate_bm25_threshold,
    get_truth_gate_spacy_sim_floor,
    get_whitelisted_phrases,
)

# Models
from services.console_grounding._models import (
    ProjectFact,
    QueryConstraints,
    TruthGateMeta,
)

# Profile parsing
from services.console_grounding._profile_parser import (
    _extract_company,
    _extract_tags,
    parse_profile_project_facts,
)

# Retrieval / grounded-reply builders
from services.console_grounding._retrieval import (
    build_deterministic_grounded_reply,
    build_grounding_facts_block,
    build_learned_knowledge_context,
    get_latest_extracted_knowledge,
    parse_query_constraints,
    retrieve_relevant_facts,
    search_learned_knowledge,
)

# Gate helpers (private — exported for tests)
from services.console_grounding._gate_helpers import (
    _BM25_AVAILABLE,
    _DOLLAR_RE,
    _NUMERIC_CLAIM_RE,
    _ORG_NAME_RE,
    _SENTENCE_SPLIT_RE,
    _YEAR_RE,
    _build_allowed_tokens,
    _build_evidence_paths_for_sentence,
    _build_project_tech_map,
    _check_project_claim,
    _compute_fact_overlap,
    _extract_spacy_orgs,
    _score_sentence_bm25,
    _tokenize_for_bm25,
    get_all_persona_facts_from_avatar_state,
    get_domain_facts_from_avatar_state,
)

# Truth gate public API
from services.console_grounding._truth_gate import (
    truth_gate,
    truth_gate_result,
)

__all__ = [
    # config
    "DEFAULT_TAG_EXPANSIONS",
    "DEFAULT_TECH_KEYWORDS",
    "DOMAIN_KNOWLEDGE_PHRASES",
    "_normalize_phrase",
    "get_console_grounding_keywords",
    "get_console_grounding_tag_expansions_from_graph",
    "get_truth_gate_bm25_threshold",
    "get_truth_gate_spacy_sim_floor",
    "get_whitelisted_phrases",
    # models
    "ProjectFact",
    "QueryConstraints",
    "TruthGateMeta",
    # profile parsing
    "_extract_company",
    "_extract_tags",
    "parse_profile_project_facts",
    # retrieval
    "build_deterministic_grounded_reply",
    "build_grounding_facts_block",
    "build_learned_knowledge_context",
    "get_latest_extracted_knowledge",
    "parse_query_constraints",
    "retrieve_relevant_facts",
    "search_learned_knowledge",
    # gate helpers
    "_BM25_AVAILABLE",
    "_DOLLAR_RE",
    "_NUMERIC_CLAIM_RE",
    "_ORG_NAME_RE",
    "_SENTENCE_SPLIT_RE",
    "_YEAR_RE",
    "_build_allowed_tokens",
    "_build_evidence_paths_for_sentence",
    "_build_project_tech_map",
    "_check_project_claim",
    "_compute_fact_overlap",
    "_extract_spacy_orgs",
    "_score_sentence_bm25",
    "_tokenize_for_bm25",
    "get_all_persona_facts_from_avatar_state",
    "get_domain_facts_from_avatar_state",
    # truth gate
    "truth_gate",
    "truth_gate_result",
]
