from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np

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
    """In-memory, NetworkX-backed knowledge graph with NumPy-accelerated scoring."""

    def __init__(self) -> None:
        if not _NX_AVAILABLE:
            raise ImportError(
                "networkx is required for KnowledgeGraphManager. "
                "Run: pip install 'networkx>=3.2'"
            )
        self._graph: nx.MultiDiGraph = nx.MultiDiGraph()
        self._persona_id: Optional[str] = None

        # --- NumPy Acceleration Cache ---
        self._dirty: bool = True
        self._node_ids: list[str] = []
        self._node_id_to_idx: dict[str, int] = {}
        self._claim_support_vec: Optional[np.ndarray] = None
        self._proximity_cache: dict[str, np.ndarray] = {}

    def _mark_dirty(self) -> None:
        """Flag the graph indices as needing a NumPy array sync."""
        self._dirty = True

    def _reindex_numpy(self) -> None:
        """Lazily build dense array structures and degree vectors for NumPy ops."""
        if not self._dirty:
            return

        self._node_ids = list(self._graph.nodes())
        self._node_id_to_idx = {nid: idx for idx, nid in enumerate(self._node_ids)}
        n = len(self._node_ids)

        if n == 0:
            self._claim_support_vec = np.zeros(0, dtype=np.float64)
            self._proximity_cache.clear()
            self._dirty = False
            return

        # Vectorized degree extraction across MultiDiGraph in/out edges
        in_counts = np.fromiter(
            (sum(len(ed) for ed in self._graph.pred[nid].values()) for nid in self._node_ids),
            dtype=np.float64,
            count=n,
        )
        out_counts = np.fromiter(
            (sum(len(ed) for ed in self._graph.succ[nid].values()) for nid in self._node_ids),
            dtype=np.float64,
            count=n,
        )
        total_degrees = in_counts + out_counts

        # Soft cap at 10 supporting links -> 1.0
        self._claim_support_vec = np.minimum(total_degrees / 10.0, 1.0)
        self._proximity_cache.clear()
        self._dirty = False

    def _get_proximity_vector(self, persona_id: str) -> np.ndarray:
        """Compute/retrieve a 1D NumPy vector of inverse-distance proximity from persona_id."""
        self._reindex_numpy()
        n = len(self._node_ids)
        if n == 0 or not self._graph.has_node(persona_id):
            return np.zeros(n, dtype=np.float64)

        if persona_id in self._proximity_cache:
            return self._proximity_cache[persona_id]

        # Compute Single-Source Shortest Path (SSSP) once for all reachable nodes
        undirected = self._graph.to_undirected()
        try:
            lengths = nx.single_source_shortest_path_length(undirected, persona_id)
        except (nx.NodeNotFound, nx.NetworkXNoPath):
            return np.zeros(n, dtype=np.float64)

        distances = np.full(n, -1.0, dtype=np.float64)
        for target_id, dist in lengths.items():
            idx = self._node_id_to_idx.get(target_id)
            if idx is not None:
                distances[idx] = float(dist)

        # Proximity score: 1 / (1 + distance) for reachable, 0.0 for disconnected
        proximity = np.zeros_like(distances, dtype=float)
        valid_mask = distances >= 0
        proximity[valid_mask] = 1.0 / (1.0 + distances[valid_mask])
        
        self._proximity_cache[persona_id] = proximity
        return proximity

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
            existing = self._graph.nodes[node_id]
            existing["label"] = attrs["label"]
            existing["metadata"].update(attrs["metadata"])
            logger.debug("KG: updated node %s (%s)", node_id, node_type)
        else:
            self._graph.add_node(node_id, **attrs)
            self._mark_dirty()
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
        """Add a typed directed edge from_id -> to_id."""
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
        self._mark_dirty()
        logger.debug("KG: linked %s -[%s]-> %s", from_id, edge_type, to_id)

    # ------------------------------------------------------------------
    # Fact ingestion
    # ------------------------------------------------------------------

    def add_fact(self, fact: dict[str, Any]) -> str:
        """Add a generic fact node to the graph."""
        node_id: str = fact.get("id", "")
        if not node_id:
            raise ValueError("fact dict must include non-empty 'id'")
        node_type: str = fact.get("type", NODE_FACT)
        label: str = fact.get("text", fact.get("statement", fact.get("label", node_id)))
        metadata: dict[str, Any] = {
            "source": fact.get("source", "system"),
            "confidence": fact.get("confidence", "medium"),
            "timestamp": fact.get("timestamp", datetime.now(timezone.utc).isoformat()),
        }
        if "tags" in fact:
            metadata["tags"] = fact["tags"]
        if "entities" in fact:
            metadata["entities"] = fact["entities"]

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
        """Return a proximity score in (0, 1] from persona_id to node_id."""
        if not self._graph.has_node(persona_id) or not self._graph.has_node(node_id):
            return 0.0
        self._reindex_numpy()
        idx = self._node_id_to_idx.get(node_id)
        if idx is None:
            return 0.0
        vec = self._get_proximity_vector(persona_id)
        return float(vec[idx])

    def claim_support(self, node_id: str) -> float:
        """Return a claim-support score in [0, 1] for a node."""
        if not self._graph.has_node(node_id):
            return 0.0
        self._reindex_numpy()
        idx = self._node_id_to_idx.get(node_id)
        if idx is None or self._claim_support_vec is None:
            return 0.0
        return float(self._claim_support_vec[idx])

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
        """Return fact-like nodes ranked via NumPy-accelerated scoring."""
        fact_types = {NODE_FACT, NODE_EXTRACTED_FACT, NODE_CLAIM, NODE_DOMAIN}
        self._reindex_numpy()

        candidate_indices: list[int] = []
        candidate_nodes: list[dict[str, Any]] = []
        labels: list[str] = []
        tags_list: list[list[str]] = []

        for nid, data in self._graph.nodes(data=True):
            if data is not None and data.get("type") in fact_types:
                idx = self._node_id_to_idx.get(nid)
                if idx is not None:
                    candidate_indices.append(idx)
                    candidate_nodes.append({"id": nid, **data})
                    labels.append((data.get("label") or "").lower())
                    raw_meta = data.get("metadata") or {}
                    meta_tags = (
                        raw_meta.get("tags", []) if isinstance(raw_meta, dict) else []
                    )
                    tags_list.append([t.lower() for t in meta_tags])

        if not candidate_indices:
            return []

        cand_idx_arr = np.array(candidate_indices, dtype=np.intp)
        q_lower = query_context.lower()
        q_words = set(q_lower.split())

        # Vectorized keyword & tag overlap scoring across candidates
        label_scores = np.fromiter(
            (sum(1.0 for w in q_words if w in lbl) for lbl in labels),
            dtype=np.float64,
            count=len(labels),
        )

        tag_scores = np.fromiter(
            (sum(2.0 for t in tags if t in q_lower) for tags in tags_list),
            dtype=np.float64,
            count=len(tags_list),
        )

        scores = label_scores + tag_scores

        # Vectorized addition of persona proximity vector
        if persona_id and self._graph.has_node(persona_id):
            prox_vec = self._get_proximity_vector(persona_id)
            scores += 3.0 * prox_vec[cand_idx_arr]

        # Vectorized addition of claim support vector
        if self._claim_support_vec is not None:
            scores += self._claim_support_vec[cand_idx_arr]

        # O(N) top-k selection via argpartition
        num_cands = len(scores)
        if num_cands <= limit:
            top_indices = np.argsort(-scores)
        else:
            top_indices = np.argpartition(-scores, limit)[:limit]
            top_indices = top_indices[np.argsort(-scores[top_indices])]

        return [candidate_nodes[i] for i in top_indices]

    def get_relevant_subgraph(
        self,
        query_context: str,
        persona_id: Optional[str] = None,
        max_nodes: int = 20,
    ) -> nx.MultiDiGraph:
        """Return a subgraph of the most relevant nodes for query_context."""
        top_facts = self.find_facts(query_context, persona_id=persona_id, limit=max_nodes)
        node_ids = [f["id"] for f in top_facts]
        if persona_id and self._graph.has_node(persona_id):
            node_ids.append(persona_id)
        return self._graph.subgraph(node_ids).copy()

    def explain_fact_usage(self, fact_id: str) -> list[list[str]]:
        """Return all simple paths from the persona node to fact_id."""
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
        """Populate graph from a fully-loaded AvatarState."""
        if state is None or not state.is_loaded or state.persona_graph is None:
            logger.info("KG bootstrap: avatar state not loaded — skipping")
            return

        pg = state.persona_graph

        persona_id = f"person:{pg.person.name}"
        self._persona_id = persona_id
        self.add_node(
            persona_id,
            NODE_PERSON,
            label=pg.person.name,
            metadata={
                "title": pg.person.title,
                "location": pg.person.location,
                "source": "persona_graph",
            },
        )

        for company in pg.companies:
            cid = f"company:{company.id}"
            self.add_node(
                cid,
                NODE_COMPANY,
                label=company.name,
                metadata={"aliases": company.aliases, "source": "persona_graph"},
            )

        for skill in pg.skills:
            sid = f"skill:{skill.id}"
            self.add_node(
                sid,
                NODE_SKILL,
                label=skill.name,
                metadata={
                    "aliases": skill.aliases,
                    "scope": skill.scope,
                    "source": "persona_graph",
                },
            )
            self.link_entities(
                persona_id, sid, EDGE_HAS_SKILL, {"source": "persona_graph", "confidence": "high"}
            )

        company_map = {c.id: f"company:{c.id}" for c in pg.companies}
        for project in pg.projects:
            pid_node = f"project:{project.id}"
            self.add_node(
                pid_node,
                NODE_PROJECT,
                label=project.name,
                metadata={
                    "years": project.years,
                    "details": project.details,
                    "source": "persona_graph",
                    "confidence": "high",
                },
            )
            self.link_entities(
                persona_id, pid_node, EDGE_WORKED_ON, {"source": "persona_graph", "confidence": "high"}
            )
            cid = company_map.get(project.company_id)
            if cid and self._graph.has_node(cid):
                self.link_entities(pid_node, cid, EDGE_EMPLOYED_BY, {"source": "persona_graph"})
            for skill_id in project.skills:
                sid = f"skill:{skill_id}"
                if self._graph.has_node(sid):
                    self.link_entities(pid_node, sid, EDGE_HAS_SKILL, {"source": "persona_graph"})

        for claim in pg.claims:
            clid = f"claim:{claim.id}"
            self.add_node(
                clid,
                NODE_CLAIM,
                label=claim.text,
                metadata={
                    "confidence": claim.confidence_hint,
                    "source": "persona_graph",
                },
            )
            self.link_entities(
                persona_id,
                clid,
                EDGE_SUPPORTS,
                {"source": "persona_graph", "confidence": claim.confidence_hint},
            )
            for proj_id in claim.project_ids:
                pid_node = f"project:{proj_id}"
                if self._graph.has_node(pid_node):
                    self.link_entities(
                        clid, pid_node, EDGE_DESCRIBED_BY, {"source": "persona_graph"}
                    )

        if state.domain_knowledge:
            dk = state.domain_knowledge
            domain_map = {d.id: f"domain:{d.id}" for d in dk.domains}
            for domain in dk.domains:
                did = f"domain:{domain.id}"
                self.add_node(
                    did,
                    NODE_DOMAIN,
                    label=domain.name,
                    metadata={"description": domain.description, "source": "domain_knowledge"},
                )
                self.link_entities(
                    persona_id, did, EDGE_RELATED_TO, {"source": "domain_knowledge"}
                )
            for fact in dk.facts:
                fid = f"fact:{fact.id}"
                self.add_node(
                    fid,
                    NODE_FACT,
                    label=fact.statement,
                    metadata={
                        "confidence": fact.confidence,
                        "tags": fact.tags,
                        "source": "domain_knowledge",
                        "scope": fact.scope,
                    },
                )
                did = domain_map.get(fact.domain_id)
                if did and self._graph.has_node(did):
                    self.link_entities(
                        did, fid, EDGE_DESCRIBED_BY, {"source": "domain_knowledge"}
                    )
            for rel in dk.relationships:
                from_fid = f"fact:{rel.from_fact_id}"
                to_fid = f"fact:{rel.to_fact_id}"
                if self._graph.has_node(from_fid) and self._graph.has_node(to_fid):
                    self.link_entities(
                        from_fid,
                        to_fid,
                        rel.relation_type,
                        {"source": "domain_knowledge", "description": rel.description},
                    )

        if state.extracted_knowledge and state.extracted_knowledge.facts:
            for xfact in state.extracted_knowledge.facts:
                xid = f"extracted:{xfact.id}"
                self.add_node(
                    xid,
                    NODE_EXTRACTED_FACT,
                    label=xfact.statement,
                    metadata={
                        "confidence": xfact.confidence,
                        "tags": xfact.tags,
                        "entities": xfact.entities,
                        "source_url": xfact.source_url,
                        "source_title": xfact.source_title,
                        "source": "extracted_knowledge",
                    },
                )
                for domain in pg.skills:
                    sid = f"skill:{domain.id}"
                    if self._graph.has_node(sid):
                        if any(
                            t.lower() in xfact.statement.lower()
                            for t in domain.aliases + [domain.name]
                        ):
                            self.link_entities(
                                xid,
                                sid,
                                EDGE_RELATED_TO,
                                {
                                    "source": "extracted_knowledge",
                                    "confidence": xfact.confidence,
                                },
                            )

        logger.debug(
            "KG bootstrap complete: %d nodes, %d edges",
            self._graph.number_of_nodes(),
            self._graph.number_of_edges(),
        )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def serialize_graph(self, path: str | Path) -> None:
        """Save the graph to a JSON file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = nx.node_link_data(self._graph)
        data["_persona_id"] = self._persona_id
        p.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        logger.info("KG serialized to %s (%d nodes)", p, self._graph.number_of_nodes())

    def load_graph(self, path: str | Path) -> None:
        """Load a serialized graph from a JSON file."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Knowledge graph file not found: {p}")
        data = json.loads(p.read_text(encoding="utf-8"))
        self._persona_id = data.pop("_persona_id", None)
        loaded = nx.node_link_graph(data, multigraph=True, directed=True)
        self._graph = nx.MultiDiGraph(loaded)
        self._mark_dirty()
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