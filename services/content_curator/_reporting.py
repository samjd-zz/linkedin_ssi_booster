"""Curator console reports: avatar explanations, DoT, and article headers."""

import logging
from typing import Any

from colorama import Fore, Style

from services.console_grounding import ProjectFact
from services.content_curator._curator_base import CuratorHost
from services.content_curator._evidence_paths import (
    fact_to_evidence_path,
    article_to_evidence_path,
    extracted_fact_to_evidence_path,
    external_fact_to_evidence_path,
)

logger = logging.getLogger(__name__)


class CuratorReportingMixin(CuratorHost):
    """Console report helpers shared by curator channel pipelines."""

    def _print_avatar_explain(
        self,
        post_text: str,
        article: dict[str, Any],
        grounding_facts: list[ProjectFact],
        channel: str,
        ssi_component: str,
        extracted_facts: list[Any] | None = None,
        external_facts: list[Any] | None = None,
    ) -> None:
        """Print the actual selected grounding evidence and DoT/spaCy scores."""
        try:
            from services.avatar_intelligence import (
                build_explain_output,
                format_explain_output,
            )
            from services.console_grounding import truth_gate_result as _tgr_exp

            sources = {fact.source for fact in grounding_facts}
            _relevant = [
                fact for fact in self._avatar_facts
                if f"avatar:{fact.source_project_id}" in sources
            ] + [
                fact for fact in self._domain_facts
                if f"domain:{fact.source_fact_id}" in sources
            ]
            _, _gate_meta = _tgr_exp(post_text, article["summary"], grounding_facts)
            _extracted = extracted_facts or []
            _external = external_facts or []
            _explain = build_explain_output(
                evidence_facts=_relevant,
                article_ref=article.get("title", ""),
                channel=channel,
                ssi_component=ssi_component,
                dot_per_sentence_scores=_gate_meta.dot_per_sentence_scores,
                spacy_sim_scores=_gate_meta.spacy_sim_scores,
                extracted_facts=_extracted,  # type: ignore[arg-type]
                external_facts=_external,  # type: ignore[arg-type]
                article_title=article.get("title", ""),
                article_url=article.get("link", ""),
            )
            print(format_explain_output(_explain))
        except Exception as _exp_exc:
            logger.warning("Avatar explanation failed (continuing): %s", _exp_exc)

    def _print_dot_report(
        self,
        post_text: str,
        article: dict[str, Any],
        grounding_facts: list[ProjectFact],
        extracted_facts: list[Any],
        external_facts: list[Any],
    ) -> None:
        """Print the Derivative of Truth report for *post_text*."""
        try:
            from services.derivative_of_truth import (
                score_claim_with_truth_gradient,
                report_truth_gradient,
                format_truth_gradient_report,
            )
            _dot_paths = (
                [fact_to_evidence_path(f, post_text) for f in (grounding_facts or [])]
                + [extracted_fact_to_evidence_path(f, post_text) for f in (extracted_facts or [])]
                + [external_fact_to_evidence_path(f, post_text) for f in (external_facts or [])]
                + [article_to_evidence_path(article, post_text)]
            )
            _dot_result = score_claim_with_truth_gradient(post_text, _dot_paths)
            _dot_report_dict = report_truth_gradient(
                post_text,
                _dot_result,
                verbose=True,
                primary_category=article.get("primary_category"),
                primary_ssi_component=article.get("primary_ssi_component"),
            )
            _dot_colour = str(Fore.RED) if _dot_result.flagged else str(Fore.CYAN)
            from services.derivative_of_truth._reporting import format_dot_report_header
            print(format_dot_report_header("Derivative of Truth Report (curate)"))
            print(format_truth_gradient_report(_dot_report_dict))
        except Exception as _dot_err:
            logger.debug("DoT report unavailable (curate): %s", _dot_err)
    

        # Category alignment validation — only when classify is active
        if self._classify:
            try:
                from services.model2vec_service import validate_category_alignment
                article_text = f"{article.get('title', '')} {article.get('summary', '')}".strip()
                _align = validate_category_alignment(
                    post_text=post_text,
                    article_text=article_text,
                    article_category=article.get("primary_category", ""),
                    article_ssi_component=article.get("primary_ssi_component", ""),
                )
                if _align.post_category:
                    _c = str(Fore.CYAN)
                    _r = str(Style.RESET_ALL)
                    _dim = str(Style.DIM)
                    if _align.flagged:
                        _align_col = str(Fore.RED)
                        _align_sym = "⚠️ "
                    elif _align.alignment_score >= 0.7:
                        _align_col = str(Fore.GREEN)
                        _align_sym = "✅"
                    else:
                        _align_col = str(Fore.YELLOW)
                        _align_sym = "◑ "
                    print(
                        f"  {_c}Category Alignment:{_r} "
                        f"{_align_sym} {_align_col}{_align.alignment_score:.2f}{_r}"
                        f"  {_dim}post={_align.post_category} / article={_align.article_category}{_r}"
                    )
                    if _align.flagged:
                        print(f"  {str(Fore.RED)}⚠️  {_align.flag_reason}{_r}")
            except Exception as _align_err:
                logger.debug("Category alignment check unavailable: %s", _align_err)

    def _print_article_header(self, article: dict[str, Any], channel: str, ssi_component: str, conf_route: str, conf_reason: str) -> None:
        print(str(Fore.CYAN) + f"\n{'='*60}" + str(Style.RESET_ALL))
        print(str(Fore.WHITE) + str(Style.BRIGHT) + f"📰 SOURCE: {article['source']}" + str(Style.RESET_ALL))
        print(str(Fore.WHITE) + str(Style.BRIGHT) + f"📄 ARTICLE: {article['title']}" + str(Style.RESET_ALL))
        print(str(Fore.CYAN) + f"📡 CHANNEL: {channel}" + str(Style.RESET_ALL))
        print(str(Fore.CYAN) + f"🎯 SSI COMPONENT: {ssi_component}" + str(Style.RESET_ALL))
        print(str(Fore.YELLOW) + f"🔒 CONFIDENCE ROUTE: {conf_route} — {conf_reason}" + str(Style.RESET_ALL))
        print(
            str(Fore.WHITE)
            + str(Style.DIM)
            + "   confidence score = publish safety (truth gate + grounding + repetition), not DoT evidence quality"
            + str(Style.RESET_ALL)
        )
        if "(1.00)" in conf_reason:
            print(
                str(Fore.WHITE)
                + str(Style.DIM)
                + "   1.00 means no confidence penalties fired for this generated post"
                + str(Style.RESET_ALL)
            )
