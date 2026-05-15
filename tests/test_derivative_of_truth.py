"""Unit tests for services/derivative_of_truth.py — Derivative of Truth framework.

Tests cover:
  - EvidencePath dataclass validation/clamping
  - score_claim_with_truth_gradient: no evidence, single path, multiple paths,
    conflict penalty, long-chain penalty, sparse penalty, low-credibility penalty
  - annotate_evidence_and_reasoning: evidence type inference, reasoning type
    inference, credibility mapping, uncertainty mapping
  - build_evidence_paths_from_kg_facts: stored dot annotations, fresh derivation
  - report_truth_gradient: output structure, verbose mode
  - format_truth_gradient_report: string output
  - apply_truth_gradient_to_kg_node: non-mutating, annotation stored in metadata
"""

from __future__ import annotations

import pytest

from services.derivative_of_truth import (
    EVIDENCE_TYPE_DERIVED,
    EVIDENCE_TYPE_PATTERN,
    EVIDENCE_TYPE_PRIMARY,
    EVIDENCE_TYPE_SECONDARY,
    REASONING_TYPE_ANALOGY,
    REASONING_TYPE_LOGICAL,
    REASONING_TYPE_PATTERN,
    REASONING_TYPE_STATISTICAL,
    TRUTH_GRADIENT_FLAG_THRESHOLD,
    UNCERTAINTY_CONFLICT,
    UNCERTAINTY_LONG_CHAIN,
    UNCERTAINTY_LOW_CREDIBILITY,
    UNCERTAINTY_SPARSE,
    AnnotatedFact,
    EvidencePath,
    TruthGradientResult,
    annotate_evidence_and_reasoning,
    apply_truth_gradient_to_kg_node,
    build_evidence_paths_from_kg_facts,
    format_truth_gradient_report,
    report_truth_gradient,
    score_claim_with_truth_gradient,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_path(
    source: str = "test_src",
    evidence_type: str = EVIDENCE_TYPE_SECONDARY,
    reasoning_type: str = REASONING_TYPE_LOGICAL,
    credibility: float = 0.7,
    uncertainty: float = 0.0,
    chain_length: int = 1,
    conflicts_with: list[str] | None = None,
) -> EvidencePath:
    return EvidencePath(
        source=source,
        evidence_type=evidence_type,
        reasoning_type=reasoning_type,
        credibility=credibility,
        uncertainty=uncertainty,
        chain_length=chain_length,
        conflicts_with=conflicts_with or [],
    )


def make_kg_fact(
    fact_id: str = "fact:001",
    node_type: str = "Fact",
    source: str = "domain_knowledge",
    confidence: str = "high",
    tags: list[str] | None = None,
    dot: dict | None = None,
) -> dict:
    meta: dict = {
        "source": source,
        "confidence": confidence,
        "tags": tags or [],
    }
    if dot:
        meta["dot"] = dot
    return {
        "id": fact_id,
        "type": node_type,
        "label": "Test fact",
        "metadata": meta,
    }


# ---------------------------------------------------------------------------
# EvidencePath tests
# ---------------------------------------------------------------------------


class TestEvidencePath:
    def test_credibility_clamped_high(self):
        p = EvidencePath(source="s", credibility=1.5)
        assert p.credibility == 1.0

    def test_credibility_clamped_low(self):
        p = EvidencePath(source="s", credibility=-0.5)
        assert p.credibility == 0.0

    def test_uncertainty_clamped(self):
        p = EvidencePath(source="s", uncertainty=2.0)
        assert p.uncertainty == 1.0

    def test_chain_length_minimum(self):
        p = EvidencePath(source="s", chain_length=0)
        assert p.chain_length == 1

    def test_defaults(self):
        p = EvidencePath(source="s")
        assert p.evidence_type == EVIDENCE_TYPE_SECONDARY
        assert p.reasoning_type == REASONING_TYPE_LOGICAL
        assert p.credibility == 0.5
        assert p.uncertainty == 0.0
        assert p.chain_length == 1
        assert p.conflicts_with == []


# ---------------------------------------------------------------------------
# score_claim_with_truth_gradient tests
# ---------------------------------------------------------------------------


class TestScoreClaimWithTruthGradient:
    def test_no_evidence_returns_zero_gradient(self):
        result = score_claim_with_truth_gradient("Some claim.", [], raw_confidence=0.8)
        assert result.truth_gradient == 0.0
        assert result.uncertainty == 1.0
        assert result.flagged is True
        assert UNCERTAINTY_SPARSE in result.uncertainty_sources
        assert result.confidence_penalty == pytest.approx(0.8, abs=1e-6)

    def test_single_primary_logical_path_high_credibility(self):
        path = make_path(
            evidence_type=EVIDENCE_TYPE_PRIMARY,
            reasoning_type=REASONING_TYPE_LOGICAL,
            credibility=0.9,
        )
        result = score_claim_with_truth_gradient("A fact.", [path], raw_confidence=0.5)
        # PLN-enhanced scoring produces slightly different results than legacy
        # Base gradient ≈ 0.948, sparse penalty 0.15 → gradient ≈ 0.806
        assert result.truth_gradient == pytest.approx(0.806, abs=0.01)
        assert UNCERTAINTY_SPARSE in result.uncertainty_sources
        assert result.flagged is False  # > 0.35 threshold

    def test_two_paths_no_conflicts_no_penalty(self):
        paths = [
            make_path(source="a", evidence_type=EVIDENCE_TYPE_PRIMARY, credibility=0.9),
            make_path(source="b", evidence_type=EVIDENCE_TYPE_SECONDARY, credibility=0.8),
        ]
        result = score_claim_with_truth_gradient("A claim.", paths)
        # PLN aggregation produces ≈ 0.926 for these two paths
        assert result.truth_gradient == pytest.approx(0.926, abs=0.01)
        assert result.uncertainty_sources == []
        assert result.flagged is False

    def test_conflict_penalty_applied(self):
        paths = [
            make_path(source="a", conflicts_with=["b"]),
            make_path(source="b"),
        ]
        result = score_claim_with_truth_gradient("Conflicting claim.", paths)
        assert UNCERTAINTY_CONFLICT in result.uncertainty_sources
        # Penalty should include 0.20 conflict penalty
        assert result.uncertainty >= 0.20

    def test_long_chain_penalty(self):
        path = make_path(source="a", chain_length=5)
        # chain_length=5, extra hops = 5-3 = 2, penalty += 0.10 * 2 = 0.20
        # also sparse penalty 0.15; total = 0.35 (but capped at 0.5)
        result = score_claim_with_truth_gradient("Derived claim.", [path])
        assert UNCERTAINTY_LONG_CHAIN in result.uncertainty_sources
        assert result.uncertainty >= 0.20

    def test_low_credibility_penalty(self):
        path = make_path(source="a", credibility=0.1)
        result = score_claim_with_truth_gradient("Weak claim.", [path])
        assert UNCERTAINTY_LOW_CREDIBILITY in result.uncertainty_sources

    def test_pattern_evidence_gives_low_gradient(self):
        path = make_path(
            evidence_type=EVIDENCE_TYPE_PATTERN,
            reasoning_type=REASONING_TYPE_PATTERN,
            credibility=0.3,
        )
        result = score_claim_with_truth_gradient("Pattern claim.", [path])
        # Should be much lower than primary/logical
        assert result.truth_gradient < 0.5

    def test_flagged_when_gradient_below_threshold(self):
        path = make_path(
            evidence_type=EVIDENCE_TYPE_PATTERN,
            reasoning_type=REASONING_TYPE_PATTERN,
            credibility=0.1,
        )
        result = score_claim_with_truth_gradient("Weak pattern.", [path])
        if result.truth_gradient < TRUTH_GRADIENT_FLAG_THRESHOLD:
            assert result.flagged is True

    def test_truth_gradient_clamped_to_unit_interval(self):
        paths = [make_path(credibility=1.0) for _ in range(5)]
        result = score_claim_with_truth_gradient("Claim.", paths)
        assert 0.0 <= result.truth_gradient <= 1.0

    def test_confidence_penalty_non_negative(self):
        path = make_path(credibility=0.9)
        result = score_claim_with_truth_gradient("Claim.", [path], raw_confidence=0.1)
        assert result.confidence_penalty >= 0.0

    def test_explanation_not_empty(self):
        path = make_path()
        result = score_claim_with_truth_gradient("Claim.", [path])
        assert result.explanation != ""

    def test_per_path_uncertainty_carried_forward(self):
        path = make_path(source="a", uncertainty=0.30)
        result = score_claim_with_truth_gradient("Claim.", [path])
        # avg_path_uncertainty = 0.30, sparse = 0.15, total = 0.45 (capped at 0.5)
        # actual penalty = min(0.30 + 0.15, 0.5) = 0.45
        assert result.uncertainty == pytest.approx(0.45, abs=1e-3)

    def test_penalty_capped_at_max(self):
        # Construct a scenario that would exceed _MAX_UNCERTAINTY_PENALTY
        path = make_path(source="a", uncertainty=0.40, chain_length=6, conflicts_with=[])
        path2 = make_path(source="b", credibility=0.1, conflicts_with=["a"])
        result = score_claim_with_truth_gradient("Claim.", [path, path2])
        assert result.uncertainty <= 0.5


# ---------------------------------------------------------------------------
# annotate_evidence_and_reasoning tests
# ---------------------------------------------------------------------------


class TestAnnotateEvidenceAndReasoning:
    def test_persona_graph_source_gives_primary(self):
        fact = make_kg_fact(node_type="Project", source="persona_graph", confidence="high")
        ann = annotate_evidence_and_reasoning(fact)
        assert ann.evidence_type == EVIDENCE_TYPE_PRIMARY
        assert ann.source_credibility == pytest.approx(0.90, abs=1e-6)

    def test_domain_knowledge_source_gives_secondary(self):
        fact = make_kg_fact(node_type="Fact", source="domain_knowledge", confidence="medium")
        ann = annotate_evidence_and_reasoning(fact)
        assert ann.evidence_type == EVIDENCE_TYPE_SECONDARY
        assert ann.source_credibility == pytest.approx(0.60, abs=1e-6)

    def test_extracted_knowledge_source_gives_derived(self):
        fact = make_kg_fact(node_type="ExtractedFact", source="extracted_knowledge", confidence="low")
        ann = annotate_evidence_and_reasoning(fact)
        assert ann.evidence_type == EVIDENCE_TYPE_DERIVED
        assert ann.source_credibility == pytest.approx(0.30, abs=1e-6)

    def test_statistical_tag_gives_statistical_reasoning(self):
        fact = make_kg_fact(tags=["benchmark", "performance"], source="domain_knowledge")
        ann = annotate_evidence_and_reasoning(fact)
        assert ann.reasoning_type == REASONING_TYPE_STATISTICAL

    def test_pattern_tag_gives_pattern_reasoning(self):
        fact = make_kg_fact(tags=["pattern", "trend"], source="domain_knowledge")
        ann = annotate_evidence_and_reasoning(fact)
        assert ann.reasoning_type == REASONING_TYPE_PATTERN

    def test_analogy_tag_gives_analogy_reasoning(self):
        fact = make_kg_fact(tags=["analogy", "similar"], source="domain_knowledge")
        ann = annotate_evidence_and_reasoning(fact)
        assert ann.reasoning_type == REASONING_TYPE_ANALOGY

    def test_no_tags_defaults_to_logical(self):
        fact = make_kg_fact(source="domain_knowledge")
        ann = annotate_evidence_and_reasoning(fact)
        assert ann.reasoning_type == REASONING_TYPE_LOGICAL

    def test_primary_evidence_has_low_base_uncertainty(self):
        fact = make_kg_fact(node_type="Project", source="persona_graph")
        ann = annotate_evidence_and_reasoning(fact)
        assert ann.uncertainty == pytest.approx(0.05, abs=1e-6)

    def test_pattern_evidence_has_high_base_uncertainty(self):
        # Use an unmapped node_type so default_evidence_type=PATTERN is applied
        fact = {
            "id": "fact:pattern_test",
            "type": "UnknownNodeType",
            "label": "Pattern test",
            "metadata": {
                "source": "unknown_source",
                "confidence": "medium",
                "tags": [],
            },
        }
        ann = annotate_evidence_and_reasoning(
            fact, default_evidence_type=EVIDENCE_TYPE_PATTERN
        )
        assert ann.uncertainty == pytest.approx(0.45, abs=1e-6)

    def test_unknown_confidence_defaults_to_medium_credibility(self):
        fact = make_kg_fact(confidence="unknown_value")
        ann = annotate_evidence_and_reasoning(fact)
        assert ann.source_credibility == pytest.approx(0.50, abs=1e-6)

    def test_returns_annotated_fact_with_correct_id(self):
        fact = make_kg_fact(fact_id="fact:xyz")
        ann = annotate_evidence_and_reasoning(fact)
        assert ann.fact_id == "fact:xyz"


# ---------------------------------------------------------------------------
# build_evidence_paths_from_kg_facts tests
# ---------------------------------------------------------------------------


class TestBuildEvidencePathsFromKgFacts:
    def test_empty_list_returns_empty(self):
        assert build_evidence_paths_from_kg_facts([]) == []

    def test_uses_stored_dot_annotations_when_present(self):
        fact = make_kg_fact(
            dot={
                "evidence_type": EVIDENCE_TYPE_PRIMARY,
                "reasoning_type": REASONING_TYPE_STATISTICAL,
                "source_credibility": 0.95,
                "uncertainty": 0.02,
            }
        )
        paths = build_evidence_paths_from_kg_facts([fact])
        assert len(paths) == 1
        p = paths[0]
        assert p.evidence_type == EVIDENCE_TYPE_PRIMARY
        assert p.reasoning_type == REASONING_TYPE_STATISTICAL
        assert p.credibility == pytest.approx(0.95, abs=1e-6)
        assert p.uncertainty == pytest.approx(0.02, abs=1e-6)

    def test_derives_annotation_when_dot_absent(self):
        fact = make_kg_fact(source="persona_graph", confidence="high")
        paths = build_evidence_paths_from_kg_facts([fact])
        assert len(paths) == 1
        assert paths[0].evidence_type == EVIDENCE_TYPE_PRIMARY

    def test_source_is_fact_id(self):
        fact = make_kg_fact(fact_id="fact:abc")
        paths = build_evidence_paths_from_kg_facts([fact])
        assert paths[0].source == "fact:abc"

    def test_multiple_facts_returns_multiple_paths(self):
        facts = [make_kg_fact(fact_id=f"fact:{i}") for i in range(5)]
        paths = build_evidence_paths_from_kg_facts(facts)
        assert len(paths) == 5


# ---------------------------------------------------------------------------
# report_truth_gradient tests
# ---------------------------------------------------------------------------


class TestReportTruthGradient:
    def _make_result(self) -> TruthGradientResult:
        paths = [make_path(source="s1"), make_path(source="s2")]
        return score_claim_with_truth_gradient("Some claim.", paths, raw_confidence=0.6)

    def test_basic_keys_present(self):
        result = self._make_result()
        report = report_truth_gradient("Some claim.", result)
        for key in ("claim_snippet", "truth_gradient", "uncertainty", "confidence_penalty",
                    "flagged", "uncertainty_sources", "explanation"):
            assert key in report

    def test_truth_gradient_rounded(self):
        result = self._make_result()
        report = report_truth_gradient("Some claim.", result)
        assert isinstance(report["truth_gradient"], float)
        # Should be rounded to 4 decimal places
        assert report["truth_gradient"] == round(result.truth_gradient, 4)

    def test_claim_snippet_truncated(self):
        long_claim = "x" * 200
        paths = [make_path()]
        result = score_claim_with_truth_gradient(long_claim, paths)
        report = report_truth_gradient(long_claim, result)
        assert len(report["claim_snippet"]) <= 125  # 120 + "…"

    def test_verbose_includes_evidence_paths(self):
        paths = [make_path(source="s1")]
        result = score_claim_with_truth_gradient("Claim.", paths)
        report = report_truth_gradient("Claim.", result, verbose=True)
        assert "evidence_paths" in report
        assert len(report["evidence_paths"]) == 1

    def test_non_verbose_excludes_evidence_paths(self):
        paths = [make_path(source="s1")]
        result = score_claim_with_truth_gradient("Claim.", paths)
        report = report_truth_gradient("Claim.", result, verbose=False)
        assert "evidence_paths" not in report

    def test_verbose_evidence_path_structure(self):
        paths = [make_path(source="src_a", credibility=0.7, uncertainty=0.1)]
        result = score_claim_with_truth_gradient("Claim.", paths)
        report = report_truth_gradient("Claim.", result, verbose=True)
        ep = report["evidence_paths"][0]
        for key in ("source", "evidence_type", "reasoning_type", "credibility",
                    "uncertainty", "chain_length", "conflicts_with"):
            assert key in ep


# ---------------------------------------------------------------------------
# format_truth_gradient_report tests
# ---------------------------------------------------------------------------


class TestFormatTruthGradientReport:
    def test_returns_string(self):
        paths = [make_path()]
        result = score_claim_with_truth_gradient("A claim.", paths)
        report = report_truth_gradient("A claim.", result)
        formatted = format_truth_gradient_report(report)
        assert isinstance(formatted, str)
        assert len(formatted) > 0

    def test_flagged_shows_warning_indicator(self):
        # No evidence → flagged
        result = score_claim_with_truth_gradient("Claim.", [])
        report = report_truth_gradient("Claim.", result)
        formatted = format_truth_gradient_report(report)
        assert "FLAGGED" in formatted

    def test_ok_shows_ok_indicator(self):
        paths = [
            make_path(evidence_type=EVIDENCE_TYPE_PRIMARY, credibility=0.9),
            make_path(evidence_type=EVIDENCE_TYPE_SECONDARY, credibility=0.8),
        ]
        result = score_claim_with_truth_gradient("Strong claim.", paths)
        report = report_truth_gradient("Strong claim.", result)
        if not report["flagged"]:
            formatted = format_truth_gradient_report(report)
            assert "OK" in formatted

    def test_verbose_report_includes_path_details(self):
        paths = [make_path(source="test_source")]
        result = score_claim_with_truth_gradient("Claim.", paths)
        report = report_truth_gradient("Claim.", result, verbose=True)
        formatted = format_truth_gradient_report(report)
        assert "test_source" in formatted


# ---------------------------------------------------------------------------
# apply_truth_gradient_to_kg_node tests
# ---------------------------------------------------------------------------


class TestApplyTruthGradientToKgNode:
    def test_does_not_mutate_input(self):
        node = make_kg_fact()
        original_meta = dict(node["metadata"])
        apply_truth_gradient_to_kg_node(node)
        assert node["metadata"] == original_meta

    def test_adds_dot_key_to_metadata(self):
        node = make_kg_fact()
        updated = apply_truth_gradient_to_kg_node(node)
        assert "dot" in updated["metadata"]

    def test_dot_has_required_fields(self):
        node = make_kg_fact()
        updated = apply_truth_gradient_to_kg_node(node)
        dot = updated["metadata"]["dot"]
        for key in ("evidence_type", "reasoning_type", "source_credibility", "uncertainty"):
            assert key in dot

    def test_pre_computed_annotation_stored(self):
        node = make_kg_fact()
        ann = AnnotatedFact(
            fact_id="f1",
            evidence_type=EVIDENCE_TYPE_PRIMARY,
            reasoning_type=REASONING_TYPE_STATISTICAL,
            source_credibility=0.95,
            uncertainty=0.01,
        )
        updated = apply_truth_gradient_to_kg_node(node, annotation=ann)
        dot = updated["metadata"]["dot"]
        assert dot["evidence_type"] == EVIDENCE_TYPE_PRIMARY
        assert dot["reasoning_type"] == REASONING_TYPE_STATISTICAL
        assert dot["source_credibility"] == pytest.approx(0.95)
        assert dot["uncertainty"] == pytest.approx(0.01)


# ---------------------------------------------------------------------------
# Integration: KG add_fact auto-annotates with DoT
# ---------------------------------------------------------------------------


class TestKgIntegration:
    """Verify that KnowledgeGraphManager.add_fact() stores DoT annotations."""

    def test_add_fact_includes_dot_metadata(self):
        try:
            from services.knowledge_graph import KnowledgeGraphManager
        except ImportError:
            pytest.skip("networkx not available")

        kg = KnowledgeGraphManager()
        kg.add_fact({
            "id": "f_dot_test",
            "type": "Fact",
            "text": "Python 3.12 improves performance",
            "confidence": "high",
            "source": "domain_knowledge",
            "tags": ["python", "performance"],
        })
        nodes = kg.query(node_type="Fact")
        assert len(nodes) == 1
        meta = nodes[0].get("metadata", {})
        assert "dot" in meta, "DoT annotation should be stored in metadata"
        dot = meta["dot"]
        assert "evidence_type" in dot
        assert "reasoning_type" in dot
        assert "source_credibility" in dot
        assert "uncertainty" in dot

    def test_add_fact_respects_caller_supplied_dot(self):
        try:
            from services.knowledge_graph import KnowledgeGraphManager
        except ImportError:
            pytest.skip("networkx not available")

        kg = KnowledgeGraphManager()
        custom_dot = {
            "evidence_type": EVIDENCE_TYPE_PRIMARY,
            "reasoning_type": REASONING_TYPE_STATISTICAL,
            "source_credibility": 0.99,
            "uncertainty": 0.01,
        }
        kg.add_fact({
            "id": "f_custom_dot",
            "type": "Fact",
            "text": "Custom fact",
            "confidence": "high",
            "source": "domain_knowledge",
            "dot": custom_dot,
        })
        nodes = kg.query(node_type="Fact")
        assert len(nodes) == 1
        dot = nodes[0]["metadata"]["dot"]
        assert dot["evidence_type"] == EVIDENCE_TYPE_PRIMARY
        assert dot["source_credibility"] == pytest.approx(0.99)
