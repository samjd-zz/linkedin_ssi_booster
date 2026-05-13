"""Knowledge Graph Manager — AtomSpace/MeTTa-inspired incremental learning subsystem.

Provides:
- KnowledgeGraphManager: in-memory NetworkX-backed knowledge graph.
- Node/link schema with typed edges and metadata (source, confidence, timestamp).
- add_fact, link_entities, query, serialize_graph, load_graph API.
- Integration helpers to bootstrap graph from an AvatarState.

This subsystem is additive: the BM25 retriever remains the primary candidate
selector; the graph adds persona-aware reranking and claim-support scoring.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    import networkx as nx
    _NX_AVAILABLE = True
except ImportError:  # pragma: no cover
    _NX_AVAILABLE = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Node types
# ---------------------------------------------------------------------------

NODE_PERSON = "Person"
NODE_PROJECT = "Project"
NODE_SKILL = "Skill"
NODE_COMPANY = "Company"
NODE_CLAIM = "Claim"
NODE_DOMAIN = "Domain"
NODE_FACT = "Fact"
NODE_EXTRACTED_FACT = "ExtractedFact"
NODE_EVENT = "Event"
NODE_SOURCE = "Source"

# ---------------------------------------------------------------------------
# Edge (link) types
# ---------------------------------------------------------------------------

EDGE_WORKED_ON = "WorkedOn"
EDGE_HAS_SKILL = "HasSkill"
EDGE_EMPLOYED_BY = "EmployedBy"
EDGE_SUPPORTS = "Supports"
EDGE_DESCRIBED_BY = "DescribedBy"
EDGE_DERIVED_FROM = "DerivedFrom"
EDGE_RELATED_TO = "RelatedTo"
EDGE_BELONGS_TO = "BelongsTo"


class KnowledgeGraphManager:
    """In-memory, NetworkX-backed knowledge graph for incremental learning.

    The graph stores nodes (Person, Project, Skill, Fact, …) and typed directed
    edges.  All nodes/edges carry a ``metadata`` dict with at least:
    - ``source`` (str): where this knowledge came from
    - ``confidence`` (str): 'high' | 'medium' | 'low'
    - ``timestamp`` (str): ISO-8601 UTC creation time

    Usage::

        kg = KnowledgeGraphManager()
        kg.bootstrap_from_avatar_state(state)
        # … later …
        kg.add_fact({"id": "f1", "type": "Fact", "text": "Python 3.12 …",
                     "confidence": "high", "source": "article"})
        kg.link_entities("persona", "f1", EDGE_SUPPORTS,
                         {"source": "article", "confidence": "high"})
        results = kg.find_facts("python async performance", persona_id="persona")
    """

    def __init__(self) -> None:
        if not _NX_AVAILABLE:
            raise ImportError(
                "networkx is required for KnowledgeGraphManager. "
                "Run: pip install 'networkx>=3.2'"
            )
        self._graph: nx.MultiDiGraph = nx.MultiDiGraph()
        self._persona_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Node operations
    # ------------------------------------------------------------------

    def add_node(
        self,
        node_id: str,
        node_type: str,
        label: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Add or update a node; returns node_id."""
        ts = datetime.now(timezone.utc).isoformat()
        attrs: dict[str, Any] = {
            "type": node_type,
            "label": label or node_id,
            "metadata": {
                "source": "system",
                "confidence": "medium",
                "timestamp": ts,
                **(metadata or {}),
            },
        }
        if self._graph.has_node(node_id):
            # Merge — update label/metadata but keep existing edges
            existing = self._graph.nodes[node_id]
            existing["label"] = attrs["label"]
            existing["metadata"].update(attrs["metadata"])
            logger.debug("KG: updated node %s (%s)", node_id, node_type)
        else:
            self._graph.add_node(node_id, **attrs)
            logger.debug("KG: added node %s (%s)", node_id, node_type)
        return node_id

    # ------------------------------------------------------------------
    # Edge operations
    # ------------------------------------------------------------------

    def link_entities(
        self,
        from_id: str,
        to_id: str,
        edge_type: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Add a typed directed edge from_id → to_id.

        Both nodes must already exist; raises ValueError otherwise.
        """
        if not self._graph.has_node(from_id):
            raise ValueError(f"Source node '{from_id}' not in graph")
        if not self._graph.has_node(to_id):
            raise ValueError(f"Target node '{to_id}' not in graph")
        ts = datetime.now(timezone.utc).isoformat()
        edge_attrs: dict[str, Any] = {
            "type": edge_type,
            "metadata": {
                "source": "system",
                "confidence": "medium",
                "timestamp": ts,
                **(metadata or {}),
            },
        }
        self._graph.add_edge(from_id, to_id, **edge_attrs)
        logger.debug("KG: linked %s -[%s]-> %s", from_id, edge_type, to_id)

    # ------------------------------------------------------------------
    # Fact ingestion
    # ------------------------------------------------------------------

    def add_fact(self, fact: dict[str, Any]) -> str:
        """Add a generic fact node to the graph.

        ``fact`` must include at minimum ``id`` and ``type``.  Optional keys:
        ``text``, ``confidence``, ``source``, ``tags``, ``timestamp``.

        Derivative of Truth (DoT) annotations are auto-derived and stored
        under ``metadata["dot"]`` when not already present in the fact dict.
        Callers may supply pre-computed annotations via ``fact["dot"]``.

        Returns the node_id.
        """
        node_id: str = fact.get("id", "")
        if not node_id:
            raise ValueError("fact dict must include non-empty 'id'")
        node_type: str = fact.get("type", NODE_FACT)
        label: str = fact.get("text", fact.get("statement", fact.get("label", node_id)))
        metadata: dict[str, Any] = {
            "source": fact.get("source", "system"),
            "confidence": fact.get("confidence", "medium"),
            "timestamp": fact.get(
                "timestamp", datetime.now(timezone.utc).isoformat()
            ),
        }
        if "tags" in fact:
            metadata["tags"] = fact["tags"]
        if "entities" in fact:
            metadata["entities"] = fact["entities"]

        # --- Derivative of Truth annotations ---
        # Use caller-supplied dot dict if present; otherwise auto-derive.
        if "dot" in fact:
            metadata["dot"] = fact["dot"]
        else:
            try:
                from services.derivative_of_truth import annotate_evidence_and_reasoning
                node_dict_for_annotation: dict[str, Any] = {
                    "id": node_id,
                    "type": node_type,
                    "metadata": {
                        "source": metadata["source"],
                        "confidence": metadata["confidence"],
                        "tags": metadata.get("tags", []),
                    },
                }
                annotation = annotate_evidence_and_reasoning(node_dict_for_annotation)
                metadata["dot"] = {
                    "evidence_type": annotation.evidence_type,
                    "reasoning_type": annotation.reasoning_type,
                    "source_credibility": annotation.source_credibility,
                    "uncertainty": annotation.uncertainty,
                }
            except Exception as _dot_exc:  # pragma: no cover
                logger.debug("DoT annotation skipped for %s: %s", node_id, _dot_exc)

        return self.add_node(node_id, node_type, label=label, metadata=metadata)

    # ------------------------------------------------------------------
    # Graph proximity helpers
    # ------------------------------------------------------------------

    def graph_proximity(self, persona_id: str, node_id: str) -> float:
        """Return a proximity score ∈ (0, 1] from persona_id to node_id.

        Uses inverse shortest-path distance in the *undirected* view of the
        graph so direction of edges does not block reachability.

        Returns 0.0 if no path exists or either node is absent.
        """
        if not self._graph.has_node(persona_id) or not self._graph.has_node(node_id):
            return 0.0
        try:
            undirected = self._graph.to_undirected()
            # shortest_path_length with both source+target always returns int;
            # cast explicitly so static checkers are satisfied.
            raw_len = nx.shortest_path_length(undirected, source=persona_id, target=node_id)
            length: int = int(raw_len)  # type: ignore[arg-type]
            return 1.0 / (1.0 + length)
        except nx.NetworkXNoPath:
            return 0.0
        except nx.NodeNotFound:
            return 0.0

    def claim_support(self, node_id: str) -> float:
        """Return a claim-support score ∈ [0, 1] for a node.

        Counts all incoming + outgoing edges (across all edge keys in the
        MultiDiGraph) and normalises with a soft cap at 10 supporting links.
        """
        if not self._graph.has_node(node_id):
            return 0.0
        # sum edge counts via dict-of-dict adjacency — works for MultiDiGraph
        in_count = sum(
            len(edge_dict)
            for _, edge_dict in self._graph.pred[node_id].items()
        )
        out_count = sum(
            len(edge_dict)
            for _, edge_dict in self._graph.succ[node_id].items()
        )
        total = in_count + out_count
        # soft cap: 10 links → 1.0
        return min(total / 10.0, 1.0)

    # ------------------------------------------------------------------
    # Query / retrieval
    # ------------------------------------------------------------------

    def query(self, node_type: Optional[str] = None) -> list[dict[str, Any]]:
        """Return all nodes (optionally filtered by type) as dicts."""
        results = []
        for node_id, data in self._graph.nodes(data=True):
            if data is None:
                continue
            if node_type is None or data.get("type") == node_type:
                results.append({"id": node_id, **data})
        return results

    def find_facts(
        self,
        query_context: str,
        persona_id: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Return fact-like nodes ranked by keyword overlap with query_context.

        This is a lightweight in-graph filter — the full hybrid score that
        combines BM25 + graph proximity is computed by HybridRetriever.
        """
        fact_types = {NODE_FACT, NODE_EXTRACTED_FACT, NODE_CLAIM, NODE_DOMAIN}
        candidates = [
            {"id": nid, **data}
            for nid, data in self._graph.nodes(data=True)
            if data is not None and data.get("type") in fact_types
        ]
        if not candidates:
            return []

        q_lower = query_context.lower()
        q_words = set(q_lower.split())

        def _score(node: dict[str, Any]) -> float:
            label = (node.get("label") or "").lower()
            raw_meta = node.get("metadata") or {}
            meta_tags: list[str] = raw_meta.get("tags", []) if isinstance(raw_meta, dict) else []
            sc: float = float(sum(1 for w in q_words if w in label))
            sc += float(sum(2 for t in meta_tags if t.lower() in q_lower))
            if persona_id:
                sc += 3.0 * self.graph_proximity(persona_id, node["id"])
            sc += self.claim_support(node["id"])
            return sc

        ranked = sorted(candidates, key=_score, reverse=True)
        return ranked[:limit]

    def get_relevant_subgraph(
        self,
        query_context: str,
        persona_id: Optional[str] = None,
        max_nodes: int = 20,
    ) -> "nx.MultiDiGraph":
        """Return a subgraph of the most relevant nodes for query_context."""
        top_facts = self.find_facts(query_context, persona_id=persona_id, limit=max_nodes)
        node_ids = [f["id"] for f in top_facts]
        if persona_id and self._graph.has_node(persona_id):
            node_ids.append(persona_id)
        return self._graph.subgraph(node_ids).copy()

    def explain_fact_usage(self, fact_id: str) -> list[list[str]]:
        """Return all simple paths from the persona node to fact_id.

        Returns an empty list if persona is not set, fact not found, or no
        paths exist.
        """
        pid = self._persona_id
        if pid is None or not self._graph.has_node(pid) or not self._graph.has_node(fact_id):
            return []
        try:
            undirected = self._graph.to_undirected()
            return list(
                nx.all_simple_paths(undirected, source=pid, target=fact_id, cutoff=5)
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    # ------------------------------------------------------------------
    # Bootstrap from AvatarState
    # ------------------------------------------------------------------

    def bootstrap_from_avatar_state(self, state: Any) -> None:
        """Populate graph from a fully-loaded AvatarState.

        Idempotent: calling multiple times will merge/update nodes.
        """
        if state is None or not state.is_loaded or state.persona_graph is None:
            logger.info("KG bootstrap: avatar state not loaded — skipping")
            return

        pg = state.persona_graph

        # --- Person node ---
        persona_id = f"person:{pg.person.name}"
        self._persona_id = persona_id
        self.add_node(
            persona_id,
            NODE_PERSON,
            label=pg.person.name,
            metadata={"title": pg.person.title, "location": pg.person.location, "source": "persona_graph"},
        )

        # --- Company nodes ---
        for company in pg.companies:
            cid = f"company:{company.id}"
            self.add_node(cid, NODE_COMPANY, label=company.name,
                          metadata={"aliases": company.aliases, "source": "persona_graph"})

        # --- Skill nodes ---
        for skill in pg.skills:
            sid = f"skill:{skill.id}"
            self.add_node(sid, NODE_SKILL, label=skill.name,
                          metadata={"aliases": skill.aliases, "scope": skill.scope,
                                    "source": "persona_graph"})
            self.link_entities(persona_id, sid, EDGE_HAS_SKILL,
                               {"source": "persona_graph", "confidence": "high"})

        # --- Project nodes ---
        company_map = {c.id: f"company:{c.id}" for c in pg.companies}
        for project in pg.projects:
            pid_node = f"project:{project.id}"
            self.add_node(pid_node, NODE_PROJECT, label=project.name,
                          metadata={"years": project.years, "details": project.details,
                                    "source": "persona_graph", "confidence": "high"})
            self.link_entities(persona_id, pid_node, EDGE_WORKED_ON,
                               {"source": "persona_graph", "confidence": "high"})
            cid = company_map.get(project.company_id)
            if cid and self._graph.has_node(cid):
                self.link_entities(pid_node, cid, EDGE_EMPLOYED_BY,
                                   {"source": "persona_graph"})
            for skill_id in project.skills:
                sid = f"skill:{skill_id}"
                if self._graph.has_node(sid):
                    self.link_entities(pid_node, sid, EDGE_HAS_SKILL,
                                       {"source": "persona_graph"})

        # --- Claim nodes ---
        for claim in pg.claims:
            clid = f"claim:{claim.id}"
            self.add_node(clid, NODE_CLAIM, label=claim.text,
                          metadata={"confidence": claim.confidence_hint,
                                    "source": "persona_graph"})
            self.link_entities(persona_id, clid, EDGE_SUPPORTS,
                               {"source": "persona_graph",
                                "confidence": claim.confidence_hint})
            for proj_id in claim.project_ids:
                pid_node = f"project:{proj_id}"
                if self._graph.has_node(pid_node):
                    self.link_entities(clid, pid_node, EDGE_DESCRIBED_BY,
                                       {"source": "persona_graph"})

        # --- Domain Knowledge ---
        if state.domain_knowledge:
            dk = state.domain_knowledge
            domain_map = {d.id: f"domain:{d.id}" for d in dk.domains}
            for domain in dk.domains:
                did = f"domain:{domain.id}"
                self.add_node(did, NODE_DOMAIN, label=domain.name,
                              metadata={"description": domain.description,
                                        "source": "domain_knowledge"})
                self.link_entities(persona_id, did, EDGE_RELATED_TO,
                                   {"source": "domain_knowledge"})
            for fact in dk.facts:
                fid = f"fact:{fact.id}"
                self.add_node(fid, NODE_FACT, label=fact.statement,
                              metadata={"confidence": fact.confidence, "tags": fact.tags,
                                        "source": "domain_knowledge", "scope": fact.scope})
                did = domain_map.get(fact.domain_id)
                if did and self._graph.has_node(did):
                    self.link_entities(did, fid, EDGE_DESCRIBED_BY,
                                       {"source": "domain_knowledge"})
            for rel in dk.relationships:
                from_fid = f"fact:{rel.from_fact_id}"
                to_fid = f"fact:{rel.to_fact_id}"
                if self._graph.has_node(from_fid) and self._graph.has_node(to_fid):
                    self.link_entities(from_fid, to_fid, rel.relation_type,
                                       {"source": "domain_knowledge",
                                        "description": rel.description})

        # --- Extracted Knowledge ---
        if state.extracted_knowledge and state.extracted_knowledge.facts:
            for xfact in state.extracted_knowledge.facts:
                xid = f"extracted:{xfact.id}"
                self.add_node(xid, NODE_EXTRACTED_FACT, label=xfact.statement,
                              metadata={"confidence": xfact.confidence,
                                        "tags": xfact.tags, "entities": xfact.entities,
                                        "source_url": xfact.source_url,
                                        "source_title": xfact.source_title,
                                        "source": "extracted_knowledge"})
                # Link to domain nodes with matching tags
                for domain in pg.skills:  # best-effort tag matching
                    sid = f"skill:{domain.id}"
                    if self._graph.has_node(sid):
                        if any(t.lower() in xfact.statement.lower() for t in domain.aliases + [domain.name]):
                            self.link_entities(xid, sid, EDGE_RELATED_TO,
                                               {"source": "extracted_knowledge",
                                                "confidence": xfact.confidence})

        logger.debug(
            "KG bootstrap complete: %d nodes, %d edges",
            self._graph.number_of_nodes(),
            self._graph.number_of_edges(),
        )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def serialize_graph(self, path: str | Path) -> None:
        """Save the graph to a JSON file (node-link format)."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = nx.node_link_data(self._graph)
        # Include persona_id in the payload for round-trip fidelity
        data["_persona_id"] = self._persona_id
        p.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        logger.info("KG serialized to %s (%d nodes)", p, self._graph.number_of_nodes())

    def load_graph(self, path: str | Path) -> None:
        """Load a previously serialized graph from a JSON file."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Knowledge graph file not found: {p}")
        data = json.loads(p.read_text(encoding="utf-8"))
        self._persona_id = data.pop("_persona_id", None)
        loaded = nx.node_link_graph(data, multigraph=True, directed=True)
        # node_link_graph returns Graph | DiGraph | MultiGraph | MultiDiGraph
        # We always save as MultiDiGraph so cast accordingly.
        self._graph = nx.MultiDiGraph(loaded)
        logger.info("KG loaded from %s (%d nodes)", p, self._graph.number_of_nodes())

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    @property
    def node_count(self) -> int:
        return int(self._graph.number_of_nodes())

    @property
    def edge_count(self) -> int:
        return int(self._graph.number_of_edges())

    def summary(self) -> dict[str, Any]:
        """Return a concise graph summary."""
        type_counts: dict[str, int] = {}
        for _, data in self._graph.nodes(data=True):
            if data is None:
                continue
            t = str(data.get("type", "Unknown"))
            type_counts[t] = type_counts.get(t, 0) + 1
        return {
            "nodes": self._graph.number_of_nodes(),
            "edges": self._graph.number_of_edges(),
            "node_types": type_counts,
            "persona_id": self._persona_id,
        }
