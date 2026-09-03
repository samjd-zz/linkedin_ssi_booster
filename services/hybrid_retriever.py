"""Hybrid Retriever — BM25 + Knowledge Graph reranking layer.

Implements persona-aware hybrid scoring:
  final = 0.7 × bm25 + 0.2 × graph_proximity + 0.1 × claim_support

BM25 (rank_bm25) remains the primary candidate selector; the knowledge graph
adds graph proximity and claim-support signals on top.

Integrates with:
- avatar_intelligence.retrieve_evidence (BM25 path)
- knowledge_graph.KnowledgeGraphManager (graph path)
- derivative_of_truth (truth gradient scoring in score_breakdown)

Falls back gracefully to pure BM25 when networkx / KnowledgeGraphManager
is unavailable.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional, Sequence, Union

logger = logging.getLogger(__name__)

# Weights for hybrid scoring
_W_BM25 = 0.7
_W_GRAPH_PROXIMITY = 0.2
_W_CLAIM_SUPPORT = 0.1

try:
    from rank_bm25 import BM25Okapi as _BM25Okapi
    _BM25_AVAILABLE = True
except ImportError:  # pragma: no cover
    _BM25_AVAILABLE = False

try:
    from services.knowledge_graph import KnowledgeGraphManager
    _KG_AVAILABLE = True
except ImportError:  # pragma: no cover
    _KG_AVAILABLE = False


def _tokenize(text: str) -> list[str]:
    """Lemmatized, language-aware tokens shared with the truth gate."""
    from services.spacy_nlp import tokenize_for_search

    return tokenize_for_search(text)


def _fact_text(fact: Any) -> str:
    """Extract a single searchable text string from any evidence fact type."""
    parts: list[str] = []
    # EvidenceFact fields
    for attr in ("project", "company", "years", "details"):
        v = getattr(fact, attr, None)
        if v:
            parts.append(str(v))
    skills = getattr(fact, "skills", None) or getattr(fact, "tags", None) or []
    if skills:
        parts.extend(skills)
    # DomainEvidenceFact fields
    for attr in ("domain", "statement"):
        v = getattr(fact, attr, None)
        if v and v not in parts:
            parts.append(str(v))
    # ExtractedEvidenceFact
    for attr in ("source_title",):
        v = getattr(fact, attr, None)
        if v:
            parts.append(str(v))
    return " ".join(parts)


def _fact_graph_id(fact: Any) -> Optional[str]:
    """Derive the KG node ID for an evidence fact (best-effort)."""
    src_id = getattr(fact, "source_project_id", None)
    if src_id:
        return f"project:{src_id}"
    src_fact_id = getattr(fact, "source_fact_id", None)
    if src_fact_id:
        # Could be domain or extracted
        domain_attr = getattr(fact, "domain", None)
        if domain_attr:
            return f"fact:{src_fact_id}"
        return f"extracted:{src_fact_id}"
    return None


class HybridRetriever:
    """Reranks BM25 candidates with graph proximity and claim support.

    Parameters
    ----------
    kg:
        A bootstrapped KnowledgeGraphManager.  When None, the retriever
        falls back to pure BM25 scoring.
    persona_id:
        The persona node ID in the knowledge graph (e.g. ``person:Shawn Dyck``).
        Inferred from the KG manager when not supplied.
    bm25_weight:
        Weight for BM25 score (default 0.7).
    graph_weight:
        Weight for graph proximity (default 0.2).
    claim_weight:
        Weight for claim support (default 0.1).
    """

    def __init__(
        self,
        kg: Optional["KnowledgeGraphManager"] = None,
        persona_id: Optional[str] = None,
        bm25_weight: float = _W_BM25,
        graph_weight: float = _W_GRAPH_PROXIMITY,
        claim_weight: float = _W_CLAIM_SUPPORT,
    ) -> None:
        self._kg = kg
        self._persona_id: Optional[str] = (
            persona_id
            or (kg._persona_id if kg is not None else None)
        )
        self._w_bm25 = bm25_weight
        self._w_graph = graph_weight
        self._w_claim = claim_weight

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def find_facts(
        self,
        query: str,
        candidates: Sequence[Any],
        limit: int = 5,
    ) -> list[Any]:
        """Return up to *limit* candidates reranked by hybrid score.

        Parameters
        ----------
        query:
            The generation / grounding query string.
        candidates:
            Evidence facts to rank — any mix of EvidenceFact,
            DomainEvidenceFact, ExtractedEvidenceFact.
        limit:
            Maximum number of results to return.

        Returns
        -------
        list
            Sorted facts, highest hybrid score first.
        """
        if not candidates:
            return []

        bm25_scores = self._bm25_scores(query, candidates)
        scored = self._hybrid_score(bm25_scores, candidates, query)
        scored.sort(key=lambda x: x[0], reverse=True)
        return [fact for _, fact in scored[:limit]]

    def explain_fact_usage(self, fact: Any) -> list[list[str]]:
        """Return explanation paths for *fact* in the knowledge graph.

        Returns an empty list when no KG is attached or no paths exist.
        """
        if self._kg is None:
            return []
        gid = _fact_graph_id(fact)
        if gid is None:
            return []
        return self._kg.explain_fact_usage(gid)

    # ------------------------------------------------------------------
    # Internal scoring
    # ------------------------------------------------------------------

    def _bm25_scores(self, query: str, candidates: Sequence[Any]) -> list[float]:
        """Return normalised BM25 scores in candidate order."""
        texts = [_fact_text(f) for f in candidates]
        q_tokens = _tokenize(query)

        if _BM25_AVAILABLE and q_tokens:
            corpus = [_tokenize(t) for t in texts]
            bm25 = _BM25Okapi(corpus)
            raw: list[float] = bm25.get_scores(q_tokens).tolist()
        else:
            # Keyword fallback
            q_words = set(q_tokens)
            raw = []
            for t in texts:
                words = set(_tokenize(t))
                raw.append(float(len(q_words & words)))

        # Normalise to [0, 1]
        max_score = max(raw) if raw else 1.0
        if max_score == 0.0:
            return [0.0] * len(raw)
        return [s / max_score for s in raw]

    def _graph_scores(self, candidates: Sequence[Any]) -> list[float]:
        """Return graph-proximity scores in candidate order."""
        if self._kg is None or self._persona_id is None:
            return [0.0] * len(candidates)
        scores = []
        for fact in candidates:
            gid = _fact_graph_id(fact)
            if gid:
                scores.append(self._kg.graph_proximity(self._persona_id, gid))
            else:
                scores.append(0.0)
        return scores

    def _claim_scores(self, candidates: Sequence[Any]) -> list[float]:
        """Return claim-support scores in candidate order."""
        if self._kg is None:
            return [0.0] * len(candidates)
        scores = []
        for fact in candidates:
            gid = _fact_graph_id(fact)
            if gid:
                scores.append(self._kg.claim_support(gid))
            else:
                scores.append(0.0)
        return scores

    def _hybrid_score(
        self,
        bm25_scores: list[float],
        candidates: Sequence[Any],
        query: str,
    ) -> list[tuple[float, Any]]:
        """Compute hybrid score for each candidate."""
        graph_scores = self._graph_scores(candidates)
        claim_scores = self._claim_scores(candidates)

        result = []
        for i, fact in enumerate(candidates):
            hybrid = (
                self._w_bm25 * bm25_scores[i]
                + self._w_graph * graph_scores[i]
                + self._w_claim * claim_scores[i]
            )
            result.append((hybrid, fact))
        return result

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def score_breakdown(
        self,
        query: str,
        candidates: Sequence[Any],
    ) -> list[dict[str, Any]]:
        """Return per-candidate score breakdown for debugging.

        Returns a list of dicts with keys: fact_id, bm25, graph_proximity,
        claim_support, hybrid, and (when KG is available) truth_gradient,
        uncertainty, confidence_penalty, flagged from the Derivative of Truth
        subsystem.
        """
        bm25_scores = self._bm25_scores(query, candidates)
        graph_scores = self._graph_scores(candidates)
        claim_scores = self._claim_scores(candidates)

        # Attempt to compute truth gradient for each candidate using KG facts
        dot_results: list[Optional[dict[str, Any]]] = [None] * len(candidates)
        try:
            from services.derivative_of_truth import (
                build_evidence_paths_from_kg_facts,
                score_claim_with_truth_gradient,
                report_truth_gradient,
            )
            for i, fact in enumerate(candidates):
                gid = _fact_graph_id(fact)
                if gid and self._kg is not None and self._kg._graph.has_node(gid):
                    node_data = dict(self._kg._graph.nodes[gid])
                    kg_node = {"id": gid, **node_data}
                    evidence_paths = build_evidence_paths_from_kg_facts([kg_node])
                    dot_result = score_claim_with_truth_gradient(
                        claim=_fact_text(fact),
                        evidence_paths=evidence_paths,
                        raw_confidence=bm25_scores[i],
                    )
                    dot_results[i] = report_truth_gradient(
                        _fact_text(fact), dot_result, verbose=False
                    )
        except Exception as _dot_exc:
            logger.debug("DoT score_breakdown skipped: %s", _dot_exc)

        breakdown = []
        for i, fact in enumerate(candidates):
            hybrid = (
                self._w_bm25 * bm25_scores[i]
                + self._w_graph * graph_scores[i]
                + self._w_claim * claim_scores[i]
            )
            entry: dict[str, Any] = {
                "fact_id": getattr(fact, "evidence_id", str(i)),
                "bm25": round(bm25_scores[i], 4),
                "graph_proximity": round(graph_scores[i], 4),
                "claim_support": round(claim_scores[i], 4),
                "hybrid": round(hybrid, 4),
            }
            dr = dot_results[i]
            if dr is not None:
                entry["truth_gradient"] = dr.get("truth_gradient", 0.0)
                entry["uncertainty"] = dr.get("uncertainty", 1.0)
                entry["confidence_penalty"] = dr.get("confidence_penalty", 0.0)
                entry["flagged"] = dr.get("flagged", False)
                entry["uncertainty_sources"] = dr.get("uncertainty_sources", [])
            breakdown.append(entry)
        return breakdown
