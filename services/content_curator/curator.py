"""
ContentCurator — main orchestration class.
Fetches articles, generates posts via the AI service, applies confidence
scoring and truth-gate checks, and pushes to Buffer.
"""

import json
import logging
import os
import re
import requests
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from colorama import Fore, Style

from services.ollama_service import OllamaService
from services.shared import X_CHAR_LIMIT, X_URL_CHARS, THREADS_CHAR_LIMIT
from services.buffer_service import BufferQueueFullError, BufferChannelNotConnectedError
from services.console_grounding import ProjectFact, truth_gate_result

from services.content_curator._config import (
    IDEAS_CACHE_PATH,
    KEYWORDS,
)
from services.content_curator._text_utils import (
    truncate_at_sentence,
    append_url_and_hashtags,
)
from services.content_curator._rss_fetcher import fetch_relevant_articles
from services.content_curator._evidence_paths import (
    fact_to_evidence_path,
    article_to_evidence_path,
    extracted_fact_to_evidence_path,
)
from services.content_curator._ssi_picker import build_topic_signal, pick_ssi_component
from services.content_curator._grounding import (
    load_curation_grounding_keywords,
    load_curation_grounding_tag_expansions,
)

logger = logging.getLogger(__name__)

# Stable run identifier — shared across all candidates logged in this process.
_CURATE_RUN_ID: str = str(uuid.uuid4())


class ContentCurator:

    def __init__(
        self,
        ai_service: OllamaService,
        buffer_service=None,
        confidence_policy: str = "balanced",
        enable_spacy_summarization: bool = True,
        github_context: str = "",
        classify: bool = False,
    ) -> None:
        self.ai = ai_service
        self.buffer = buffer_service
        self.confidence_policy = confidence_policy
        self.enable_spacy_summarization = enable_spacy_summarization
        self.github_context = github_context
        self._classify = classify
        self.curation_grounding_keywords = load_curation_grounding_keywords()
        self.curation_grounding_tag_expansions = load_curation_grounding_tag_expansions()
        self._avatar_facts: list = []
        self._domain_facts: list = []
        self._extracted_facts: list = []
        self._topic_signal: dict[str, int] = {}
        self._narrative_memory = None
        self._spacy_nlp = None
        self._kg = None
        self._hybrid_retriever = None

        if self.enable_spacy_summarization:
            try:
                from services.spacy_nlp import get_spacy_nlp
                self._spacy_nlp = get_spacy_nlp()
            except Exception as _nlp_exc:
                logger.debug("spaCy NLP unavailable for article summarization: %s", _nlp_exc)

        try:
            from services.shared import AVATAR_LEARNING_ENABLED
            from services.avatar_intelligence import (
                load_avatar_state,
                normalize_evidence_facts,
                normalize_domain_facts,
                normalize_extracted_facts,
            )
            _state = load_avatar_state()
            self._avatar_facts = normalize_evidence_facts(_state)
            self._domain_facts = normalize_domain_facts(_state)
            self._extracted_facts = normalize_extracted_facts(_state)
            _topic_window = int(os.getenv("TOPIC_SIGNAL_WINDOW", "50"))
            self._topic_signal = build_topic_signal(self._extracted_facts, window=_topic_window)
            if AVATAR_LEARNING_ENABLED and _state.narrative_memory is not None:
                self._narrative_memory = _state.narrative_memory
            try:
                from services.knowledge_graph import KnowledgeGraphManager
                from services.hybrid_retriever import HybridRetriever
                self._kg = KnowledgeGraphManager()
                self._kg.bootstrap_from_avatar_state(_state)
                self._hybrid_retriever = HybridRetriever(kg=self._kg)
                logger.debug("HybridRetriever initialised with KG")
            except Exception as _kg_exc:
                logger.debug("KG/HybridRetriever init skipped: %s", _kg_exc)
        except Exception as _exc:
            logger.warning("Avatar state init failed (continuing): %s", _exc)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _grounding_facts_for_article(
        self,
        article_title: str,
        article_summary: str,
        ssi_component: str,
    ) -> tuple[list[ProjectFact], list[Any]]:
        """Retrieve top-N persona and domain facts, reranked via HybridRetriever when available."""
        query = f"{article_title}. {article_summary[:600]}. {ssi_component}"
        if self._avatar_facts or self._domain_facts or self._extracted_facts:
            from services.avatar_intelligence import (
                retrieve_evidence,
                evidence_facts_to_project_facts,
                domain_facts_to_project_facts,
                EvidenceFact,
                DomainEvidenceFact,
                ExtractedEvidenceFact,
                _get_evidence_split,
            )
            n_persona, n_domain = _get_evidence_split()
            n_extracted = int(os.getenv("EXTRACTED_EVIDENCE_COUNT", "2"))

            if self._hybrid_retriever is not None:
                all_candidates = list(self._avatar_facts) + list(self._domain_facts) + list(self._extracted_facts)
                total = n_persona + n_domain + n_extracted
                # Use 3x buffer so each type has enough headroom to meet its quota even
                # when facts from other types rank higher in the joint pool.
                ranked = self._hybrid_retriever.find_facts(query, all_candidates, limit=total * 3)
                persona_hits_typed: list[EvidenceFact] = [f for f in ranked if isinstance(f, EvidenceFact)][:n_persona]
                domain_hits_typed: list[DomainEvidenceFact] = [f for f in ranked if isinstance(f, DomainEvidenceFact)][:n_domain]
                extracted_hits_typed: list[ExtractedEvidenceFact] = [f for f in ranked if isinstance(f, ExtractedEvidenceFact)][:n_extracted]
            else:
                persona_hits = retrieve_evidence(query, self._avatar_facts, limit=n_persona) if self._avatar_facts else []
                domain_hits = retrieve_evidence(query, self._domain_facts, limit=n_domain) if self._domain_facts else []
                persona_hits_typed = [f for f in persona_hits if isinstance(f, EvidenceFact)]
                domain_hits_typed = [f for f in domain_hits if isinstance(f, DomainEvidenceFact)]
                q_tokens = set(re.findall(r"[a-zA-Z0-9_+#.-]{2,}", query.lower()))
                scored_extracted = []
                for fact in self._extracted_facts:
                    text = " ".join([
                        getattr(fact, "statement", ""),
                        getattr(fact, "source_title", ""),
                        " ".join(getattr(fact, "tags", []) or []),
                        " ".join(getattr(fact, "entities", []) or []),
                    ])
                    tokens = set(re.findall(r"[a-zA-Z0-9_+#.-]{2,}", text.lower()))
                    score = len(q_tokens & tokens)
                    scored_extracted.append((score, fact))
                scored_extracted.sort(key=lambda x: x[0], reverse=True)
                extracted_hits_typed = [f for s, f in scored_extracted if s > 0][:n_extracted]
                if not extracted_hits_typed:
                    extracted_hits_typed = list(self._extracted_facts)[:n_extracted]

            persona_pf = evidence_facts_to_project_facts(persona_hits_typed)
            domain_pf = domain_facts_to_project_facts(domain_hits_typed)
            return persona_pf + domain_pf, extracted_hits_typed
        return [], []

    def _load_published_titles(self) -> set:
        if IDEAS_CACHE_PATH.exists():
            return set(json.loads(IDEAS_CACHE_PATH.read_text()))
        return set()

    def _save_published_title(self, title: str) -> None:
        titles = self._load_published_titles()
        titles.add(title)
        IDEAS_CACHE_PATH.write_text(json.dumps(sorted(titles), indent=2))

    def _fetch_article_text_with_summary(self, url: str, max_chars: int = 3000) -> str:
        """Fetch and optionally spaCy-summarize article text."""
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            html = resp.text
            html = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", " ", html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()
            if self._spacy_nlp and len(text) > 500:
                try:
                    summary = self._spacy_nlp.summarize_article(
                        article_text=text[:max_chars],
                        max_sentences=5,
                        focus_entities=True,
                    )
                    if summary:
                        logger.debug("spaCy summarized article from %d to %d chars", len(text[:max_chars]), len(summary))
                        return summary
                except Exception as _sum_exc:
                    logger.debug("spaCy summarization failed, using truncated text: %s", _sum_exc)
            return text[:max_chars]
        except Exception as exc:
            logger.debug("Could not fetch article text from %s: %s", url, exc)
            return ""

    def _score_and_route(
        self,
        post_text: str,
        article_summary: str,
        grounding_facts: list[ProjectFact],
        channel: str,
        article_ref: str,
        requested_mode: str,
    ) -> tuple[str, str]:
        """Score post with confidence engine; return (route, reason).

        route is 'post' | 'idea' | 'block'. Falls back to *requested_mode* on error.
        """
        try:
            from services.avatar_intelligence import (
                extract_confidence_signals,
                score_confidence,
                decide_publish_mode,
                record_confidence_decision,
                compute_repetition_score,
            )
            from services.shared import AVATAR_LEARNING_ENABLED

            rep_score = (
                compute_repetition_score(post_text, self._narrative_memory)
                if self._narrative_memory is not None
                else 0.0
            )
            _assessed_text, gate_meta = truth_gate_result(post_text, article_summary, grounding_facts)
            signals = extract_confidence_signals(
                removed_count=gate_meta.removed_count,
                total_sentences=gate_meta.total_sentences,
                reason_codes=gate_meta.reason_codes,
                grounding_facts_count=len(grounding_facts),
                max_grounding_facts=int(os.getenv("EVIDENCE_PROJECT_COUNT", "3")) + int(os.getenv("EVIDENCE_DOMAIN_COUNT", "2")),
                channel=channel,
                post_length=len(post_text),
                narrative_repetition_score=rep_score,
            )
            result = score_confidence(signals)
            cd = decide_publish_mode(self.confidence_policy, result, requested_mode)
            if AVATAR_LEARNING_ENABLED:
                record_confidence_decision(
                    decision=cd,
                    confidence=result,
                    channel=channel,
                    article_ref=article_ref,
                )
            return cd.route, cd.reason
        except Exception as exc:
            logger.warning(
                "Confidence scoring failed (falling back to requested mode '%s'): %s",
                requested_mode,
                exc,
            )
            return requested_mode, "confidence scoring unavailable — using requested mode"

    def _print_avatar_explain(
        self,
        post_text: str,
        article: dict[str, Any],
        grounding_facts: list[ProjectFact],
        channel: str,
        ssi_component: str,
        extracted_facts: list[Any] | None = None,
    ) -> None:
        """Print the avatar explain block (evidence IDs + DoT/spaCy scores).
        
        ⚠️  Avatar Explain retrieves evidence independently from console grounding,
        so it may show facts that are filtered out by truth-gate before DoT reporting.
        
        This is by design: Avatar Explain displays the *candidate* facts that were considered,
        while DoT Report shows only the facts that passed filtering (grounding_facts).
        To align them fully, Avatar Explain would need to apply truth-gate filtering to its
        independently retrieved facts, which would require a deeper refactor.
        """
        try:
            from services.avatar_intelligence import (
                retrieve_evidence,
                build_explain_output,
                format_explain_output,
            )
            from services.console_grounding import truth_gate_result as _tgr_exp

            grounding_query = f"{article['title']}. {article['summary'][:600]}. {ssi_component}"
            _exp_limit = int(os.getenv("EVIDENCE_PROJECT_COUNT", "3")) + int(os.getenv("EVIDENCE_DOMAIN_COUNT", "2"))
            _relevant = retrieve_evidence(grounding_query, self._avatar_facts + self._domain_facts, limit=_exp_limit)
            _, _gate_meta = _tgr_exp(post_text, article["summary"], grounding_facts)
            _extracted = extracted_facts or []
            _explain = build_explain_output(
                evidence_facts=_relevant,
                article_ref=article.get("title", ""),
                channel=channel,
                ssi_component=ssi_component,
                dot_per_sentence_scores=_gate_meta.dot_per_sentence_scores,
                spacy_sim_scores=_gate_meta.spacy_sim_scores,
                extracted_facts=_extracted,  # type: ignore[arg-type]
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

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def curate_and_create_ideas(
        self,
        dry_run: bool = False,
        max_ideas: int = 5,
        request_delay: float = 5.0,
        channel: str | list[str] = "linkedin",
        message_type: str = "idea",
        interactive: bool = False,
        avatar_explain: bool = False,
        dot_report: bool = False,
        learn: bool = False,
        classify: bool = False,
    ) -> list | None:
        """Fetch articles, generate posts, apply routing, push to Buffer.

        message_type='idea'  — creates Buffer Ideas for manual review.
        message_type='post'  — schedules posts directly to the queue.
        channel='all'        — LinkedIn + X + Bluesky + Threads + YouTube per article.
        channel can be a string or list of strings for multiple channels.
        """
        
        _do_classify = self._classify or classify
        articles = fetch_relevant_articles(spacy_nlp=self._spacy_nlp, classify=_do_classify)
        try:
            from services.selection_learning import compute_acceptance_priors, rank_articles as _rank_arts
            _priors = compute_acceptance_priors()
            articles = _rank_arts(articles, _priors, keywords=list(KEYWORDS))
        except Exception as _rank_exc:
            import random
            logger.warning("selection_learning: ranking failed, using random order: %s", _rank_exc)
            random.shuffle(articles)

        published = set() if dry_run else self._load_published_titles()
        created_ideas: list | None = []

        learn_only = learn
        if learn_only:
            logger.info("🧠 --learn mode: extracting knowledge only — skipping generation%s", " (dry run)" if dry_run else "")

        for article in articles:
            if created_ideas is not None and not learn and len(created_ideas) >= max_ideas:
                break
            if article["title"] in published:
                logger.info("Skipping already-published idea: %s", article["title"][:60])
                continue

            # Fast-path: --curate --learn without --dry-run → extract only, skip generation
            if learn_only:
                try:
                    from services.avatar_intelligence import extract_and_append_knowledge
                    _learn_text = article["summary"]
                    if len(_learn_text.strip()) < 800 and article["link"]:
                        _fetched = self._fetch_article_text_with_summary(article["link"])
                        if _fetched:
                            logger.debug("🧠 fetched full text for '%s' (%d chars)", article["title"][:60], len(_fetched))
                            _learn_text = _fetched
                    _new_facts = extract_and_append_knowledge(
                        article_text=_learn_text,
                        source_url=article["link"],
                        source_title=article["title"],
                    )
                    if _new_facts:
                        from services.avatar_intelligence import load_avatar_state, normalize_extracted_facts
                        _latest_state = load_avatar_state()
                        self._extracted_facts = normalize_extracted_facts(_latest_state)
                        _topic_window = int(os.getenv("TOPIC_SIGNAL_WINDOW", "50"))
                        self._topic_signal = build_topic_signal(self._extracted_facts, window=_topic_window)
                        logger.info(
                            "🧠 ✨ +%d fact(s) from '%s' (🗂️ pool=%d)",
                            len(_new_facts), article["title"][:60], len(self._extracted_facts),
                        )
                    else:
                        logger.info(
                            "🧠 0 new facts from '%s' (🗂️ pool=%d)",
                            article["title"][:60], len(self._extracted_facts),
                        )
                except Exception as _exc:
                    logger.debug("Knowledge extraction skipped (continuing): %s", _exc)
                continue  # skip generation entirely

            if created_ideas:
                time.sleep(request_delay)

            _candidate_id = str(uuid.uuid4())
            ssi_component = pick_ssi_component(self._topic_signal)
            grounding_facts, extracted_facts = self._grounding_facts_for_article(
                article_title=article["title"],
                article_summary=article["summary"],
                ssi_component=ssi_component,
            )

            # Continual learning — persist new knowledge from the article
            if not dry_run or learn:
                try:
                    from services.avatar_intelligence import extract_and_append_knowledge
                    _learn_text = article["summary"]
                    if len(_learn_text.strip()) < 800 and article["link"]:
                        _fetched = self._fetch_article_text_with_summary(article["link"])
                        if _fetched:
                            logger.debug("🧠 fetched full text for '%s' (%d chars)", article["title"][:60], len(_fetched))
                            _learn_text = _fetched
                    _new_facts = extract_and_append_knowledge(
                        article_text=_learn_text,
                        source_url=article["link"],
                        source_title=article["title"],
                    )
                    if _new_facts:
                        from services.avatar_intelligence import load_avatar_state, normalize_extracted_facts
                        _latest_state = load_avatar_state()
                        self._extracted_facts = normalize_extracted_facts(_latest_state)
                        _topic_window = int(os.getenv("TOPIC_SIGNAL_WINDOW", "50"))
                        self._topic_signal = build_topic_signal(self._extracted_facts, window=_topic_window)
                        logger.info(
                            "🧠 Knowledge extraction: ✨ +%d fact(s) from '%s' (🗂️ pool=%d)",
                            len(_new_facts), article["title"][:60], len(self._extracted_facts),
                        )
                    else:
                        logger.info(
                            "🧠 Knowledge extraction: ➕ 0 new facts from '%s' (🗂️ pool=%d)",
                            article["title"][:60], len(self._extracted_facts),
                        )
                except Exception as _exc:
                    logger.debug("Knowledge extraction skipped (continuing): %s", _exc)
            else:
                logger.info("Knowledge extraction skipped for '%s' (dry_run without --learn)", article["title"][:60])

            logger.info("Generating [%s|%s] for: %s...", message_type, ssi_component, article["title"][:60])

            # Normalize channel to list
            if isinstance(channel, str):
                if channel == "all":
                    channel_list = ["all"]
                elif "," in channel:
                    channel_list = [ch.strip() for ch in channel.split(",") if ch.strip()]
                else:
                    channel_list = [channel]
            else:  # list
                channel_list = channel

            if created_ideas is None:  # Already stopped due to buffer full
                break
            if channel_list == ["all"]:
                created_ideas = self._process_all_channels(
                    article=article,
                    ssi_component=ssi_component,
                    grounding_facts=grounding_facts,
                    extracted_facts=extracted_facts,
                    dry_run=dry_run,
                    request_delay=request_delay,
                    message_type=message_type,
                    interactive=interactive,
                    avatar_explain=avatar_explain,
                    dot_report=dot_report,
                    candidate_id=_candidate_id,
                    created_ideas=created_ideas,
                )
                if created_ideas is None:  # buffer full — stop
                    break
            elif len(channel_list) > 1:
                for ch in channel_list:
                    result = self._process_single_channel(
                        article=article,
                        ssi_component=ssi_component,
                        grounding_facts=grounding_facts,
                        extracted_facts=extracted_facts,
                        channel=ch,
                        message_type=message_type,
                        dry_run=dry_run,
                        interactive=interactive,
                        avatar_explain=avatar_explain,
                        dot_report=dot_report,
                        candidate_id=_candidate_id,
                        created_ideas=created_ideas,
                    )
                    if result is None:  # buffer full — stop
                        created_ideas = None
                        break
            else:
                result = self._process_single_channel(
                    article=article,
                    ssi_component=ssi_component,
                    grounding_facts=grounding_facts,
                    extracted_facts=extracted_facts,
                    channel=channel_list[0],
                    message_type=message_type,
                    dry_run=dry_run,
                    interactive=interactive,
                    avatar_explain=avatar_explain,
                    dot_report=dot_report,
                    candidate_id=_candidate_id,
                    created_ideas=created_ideas,
                )
                if result is None:  # buffer full — stop
                    created_ideas = None
                    break
        return created_ideas

    # ------------------------------------------------------------------
    # Channel dispatch helpers
    # ------------------------------------------------------------------

    def _process_all_channels(
        self,
        article: dict[str, Any],
        ssi_component: str,
        grounding_facts: list[ProjectFact],
        extracted_facts: list[Any],
        dry_run: bool,
        request_delay: float,
        message_type: str,
        interactive: bool,
        avatar_explain: bool,
        dot_report: bool,
        candidate_id: str,
        created_ideas: list,
    ) -> list | None:
        """Generate LinkedIn + X + Bluesky + Threads + YouTube posts for one article."""
        _conf_route = "n/a"
        _conf_reason = "not generated"

        li_text = self.ai.summarise_for_curation(
            article_text=article["summary"],
            source_url=article["link"],
            ssi_component=ssi_component,
            channel="linkedin",
            post_mode=True,
            grounding_facts=grounding_facts,
            extracted_facts=extracted_facts,
            interactive=interactive,
            github_context=self.github_context,
        )
        if not li_text:
            logger.info("Skipping article with no usable content: %s", article["title"][:60])
            return created_ideas

        _conf_route, _conf_reason = self._score_and_route(
            post_text=li_text,
            article_summary=article["summary"],
            grounding_facts=grounding_facts,
            channel="linkedin",
            article_ref=article.get("link", article["title"]),
            requested_mode=message_type,
        )
        li_text = append_url_and_hashtags(li_text, article["link"])

        time.sleep(request_delay)
        x_post = self.ai.summarise_for_curation(
            article["summary"], article["link"], ssi_component, "x",
            grounding_facts=grounding_facts, extracted_facts=extracted_facts,
            interactive=interactive, github_context=self.github_context,
        )
        if x_post:
            x_budget = X_CHAR_LIMIT - X_URL_CHARS
            x_post = truncate_at_sentence(x_post, x_budget)
            if article["link"] and article["link"] not in x_post:
                x_post = x_post.rstrip() + f"\n\n{article['link']}"

        time.sleep(request_delay)
        threads_post = self.ai.summarise_for_curation(
            article["summary"], article["link"], ssi_component, "threads",
            grounding_facts=grounding_facts, extracted_facts=extracted_facts,
            interactive=interactive, github_context=self.github_context,
        )
        if threads_post:
            url_overhead = (2 + len(article["link"])) if article.get("link") else 0
            threads_budget = max(80, THREADS_CHAR_LIMIT - url_overhead)
            threads_post = truncate_at_sentence(threads_post, threads_budget)
            if article["link"] and article["link"] not in threads_post:
                threads_post = threads_post.rstrip() + f"\n\n{article['link']}"

        time.sleep(request_delay)
        bsky_post = self.ai.summarise_for_curation(
            article["summary"], article["link"], ssi_component, "bluesky",
            grounding_facts=grounding_facts, extracted_facts=extracted_facts,
            interactive=interactive, github_context=self.github_context,
        )
        if bsky_post:
            url_overhead = (2 + len(article["link"])) if article.get("link") else 0
            bsky_budget = 300 - url_overhead
            bsky_post = truncate_at_sentence(bsky_post, bsky_budget)
            if article["link"] and article["link"] not in bsky_post:
                bsky_post = bsky_post.rstrip() + f"\n\n{article['link']}"

        time.sleep(request_delay)
        yt_script = self.ai.summarise_for_curation(
            article["summary"], article["link"], ssi_component, "youtube",
            post_mode=True, grounding_facts=grounding_facts, extracted_facts=extracted_facts,
            interactive=interactive, github_context=self.github_context,
        )
        if yt_script:
            yt_script = truncate_at_sentence(yt_script, 500)

        yt_script_path = None
        if yt_script and not dry_run:
            yt_dir = Path("yt-vid-data")
            yt_dir.mkdir(exist_ok=True)
            safe_title = re.sub(r"[^\w\-]", "_", article["title"][:60]).strip("_")
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            yt_script_path = yt_dir / f"{timestamp}_{safe_title}.txt"
            yt_script_path.write_text(
                f"TITLE: {article['title']}\nSSI COMPONENT: {ssi_component}\nSOURCE: {article['link']}\n\n{yt_script}\n",
                encoding="utf-8",
            )

        self._print_article_header(article, "all", ssi_component, _conf_route, _conf_reason)
        print(str(Fore.GREEN) + f"\n🔵 LINKEDIN POST:" + str(Style.RESET_ALL) + f"\n{li_text}")
        print(str(Fore.BLUE) + f"\n𝕏  X POST:" + str(Style.RESET_ALL) + f"\n{x_post}")
        print(str(Fore.WHITE) + f"\nTHREADS POST:" + str(Style.RESET_ALL) + f"\n{threads_post}")
        print(str(Fore.MAGENTA) + f"\n🦋 BLUESKY POST:" + str(Style.RESET_ALL) + f"\n{bsky_post}")
        if yt_script:
            print(str(Fore.RED) + str(Style.BRIGHT) + "\n🎬 YOUTUBE SHORT SCRIPT:" + str(Style.RESET_ALL) + f"\n{yt_script}\n")
            print("GitHub: https://buff.ly/tfajNLI")
            print("Sign up for Buffer with my partner link — join.buffer.com/samjd42  — to start scheduling, publishing, and analyzing your social posts in one place while supporting my work.")
        if avatar_explain:
            self._print_avatar_explain(li_text, article, grounding_facts, "all", ssi_component, extracted_facts=extracted_facts)
        if dot_report:
            self._print_dot_report(li_text, article, grounding_facts, extracted_facts)

        if dry_run:
            created_ideas.append({"dry_run": True, "title": article["title"], "ssi_component": ssi_component, "channel": "all"})
            return created_ideas

        # Live push
        try:
            from services.selection_learning import log_candidate as _log_cand_all
            _log_cand_all(
                candidate_id=candidate_id,
                article_url=article.get("link", ""),
                article_title=article.get("title", ""),
                article_source=article.get("source", ""),
                ssi_component=ssi_component,
                channel="all",
                post_text=li_text,
                buffer_id=None,
                route="post",
                run_id=_CURATE_RUN_ID,
            )
        except Exception as _cand_exc:
            logger.warning("selection_learning: candidate log failed (continuing): %s", _cand_exc)

        if not self.buffer:
            logger.warning("No buffer_service provided — skipping post creation")
            return created_ideas

        try:
            _li_post = self.buffer.create_scheduled_post(self.buffer.get_linkedin_channel_id(), li_text)
            try:
                from services.selection_learning import update_candidate_buffer_id as _upd_all
                _upd_all(candidate_id, _li_post.get("id", ""))
            except Exception as _upd_exc:
                logger.warning("selection_learning: buffer_id update failed (continuing): %s", _upd_exc)
            if x_post:
                try:
                    self.buffer.create_scheduled_post(self.buffer.get_x_channel_id(), x_post, channel="x")
                except BufferChannelNotConnectedError as exc:
                    logger.warning(str(Fore.YELLOW) + f"⚠️  X channel not configured — skipping. ({exc})" + str(Style.RESET_ALL))
            if threads_post:
                try:
                    self.buffer.create_scheduled_post(self.buffer.get_threads_channel_id(), threads_post, channel="threads")
                except BufferChannelNotConnectedError as exc:
                    logger.warning(str(Fore.YELLOW) + f"⚠️  Threads channel not configured — skipping. ({exc})" + str(Style.RESET_ALL))
            if bsky_post:
                try:
                    self.buffer.create_scheduled_post(self.buffer.get_bluesky_channel_id(), bsky_post, channel="bluesky")
                except BufferChannelNotConnectedError as exc:
                    logger.warning(str(Fore.YELLOW) + f"⚠️  Bluesky channel not configured — skipping. ({exc})" + str(Style.RESET_ALL))
            if yt_script:
                print(str(Fore.RED) + str(Style.BRIGHT) + "\n🎬 YOUTUBE SHORT SCRIPT (all-channel mode):" + str(Style.RESET_ALL))
                print(str(Fore.WHITE) + f"📄 TITLE:  {article['title']}" + str(Style.RESET_ALL))
                print(str(Fore.CYAN) + f"🎯 SSI:    {ssi_component}" + str(Style.RESET_ALL))
                print(f"\n{yt_script}\n")
                if yt_script_path:
                    print(str(Fore.GREEN) + f"💾 Saved to: {yt_script_path}" + str(Style.RESET_ALL))
                print(str(Fore.YELLOW) + "⚠️  YouTube requires a video upload — script not pushed to Buffer." + str(Style.RESET_ALL))
            self._save_published_title(article["title"])
            created_ideas.append({"title": article["title"], "channel": "all", "ssi_component": ssi_component})
        except BufferQueueFullError as exc:
            logger.warning(str(Fore.YELLOW) + f"⚠️  Buffer queue full — stopping early. ({exc})" + str(Style.RESET_ALL))
            return None  # signal caller to break

        return created_ideas

    def _process_single_channel(
        self,
        article: dict[str, Any],
        ssi_component: str,
        grounding_facts: list[ProjectFact],
        extracted_facts: list[Any],
        channel: str,
        message_type: str,
        dry_run: bool,
        interactive: bool,
        avatar_explain: bool,
        dot_report: bool,
        candidate_id: str,
        created_ideas: list,
    ) -> list | None:
        """Generate and route a post for a single channel / idea mode."""

        try:
            from services.avatar_intelligence import build_continuity_context
            _continuity = (
                build_continuity_context(self._narrative_memory)
                if self._narrative_memory is not None
                else ""
            )
        except Exception:
            _continuity = ""

        post_text = self.ai.summarise_for_curation(
            article_text=article["summary"],
            source_url=article["link"],
            ssi_component=ssi_component,
            channel=channel,
            post_mode=(message_type == "post"),
            grounding_facts=grounding_facts,
            extracted_facts=extracted_facts,
            interactive=interactive,
            continuity_context=_continuity,
            github_context=self.github_context,
        )
        if not post_text:
            logger.info("Skipping article with no usable content: %s", article["title"][:60])
            return created_ideas

        try:
            from services.shared import AVATAR_LEARNING_ENABLED
            from services.avatar_intelligence import (
                extract_narrative_updates,
                update_narrative_memory,
                save_narrative_memory,
            )
            if AVATAR_LEARNING_ENABLED and self._narrative_memory is not None:
                _updates = extract_narrative_updates(post_text, ssi_component, article["title"])
                self._narrative_memory = update_narrative_memory(
                    self._narrative_memory,
                    themes=_updates["themes"],
                    claims=_updates["claims"],
                    arcs=_updates["arcs"],
                )
                save_narrative_memory(self._narrative_memory)
        except Exception as _mem_exc:
            logger.warning("Narrative memory update failed (continuing): %s", _mem_exc)

        if channel == "linkedin":
            post_text = append_url_and_hashtags(post_text, article["link"])
        elif channel == "facebook":
            post_text = append_url_and_hashtags(post_text, article["link"])
        elif channel == "youtube":
            post_text = truncate_at_sentence(post_text, 500)
        elif channel == "x":
            x_budget = X_CHAR_LIMIT - X_URL_CHARS
            post_text = truncate_at_sentence(post_text, x_budget)
            if article["link"] and article["link"] not in post_text:
                post_text = post_text.rstrip() + f"\n\n{article['link']}"

        elif channel == "threads":
            url_overhead = (2 + len(article["link"])) if article.get("link") else 0
            threads_budget = max(80, THREADS_CHAR_LIMIT - url_overhead)
            post_text = truncate_at_sentence(post_text, threads_budget)
            if article["link"] and article["link"] not in post_text:
                post_text = post_text.rstrip() + f"\n\n{article['link']}"
        elif channel == "bluesky":
            url_overhead = (2 + len(article["link"])) if article.get("link") else 0
            bsky_budget = 300 - url_overhead
            post_text = truncate_at_sentence(post_text, bsky_budget)
            if article["link"] and article["link"] not in post_text:
                post_text = post_text.rstrip() + f"\n\n{article['link']}"

        _conf_route, _conf_reason = self._score_and_route(
            post_text=post_text,
            article_summary=article["summary"],
            grounding_facts=grounding_facts,
            channel=channel,
            article_ref=article.get("link", article["title"]),
            requested_mode=message_type,
        )

        if not dry_run:
            try:
                from services.selection_learning import log_candidate as _log_cand
                _log_cand(
                    candidate_id=candidate_id,
                    article_url=article.get("link", ""),
                    article_title=article.get("title", ""),
                    article_source=article.get("source", ""),
                    ssi_component=ssi_component,
                    channel=channel,
                    post_text=post_text,
                    buffer_id=None,
                    route=_conf_route,
                    run_id=_CURATE_RUN_ID,
                )
            except Exception as _cand_exc:
                logger.warning("selection_learning: candidate log failed (continuing): %s", _cand_exc)

        self._print_article_header(article, channel, ssi_component, _conf_route, _conf_reason)
        print(str(Fore.GREEN) + f"\n✍️  GENERATED POST:" + str(Style.RESET_ALL) + f"\n{post_text}")

        if avatar_explain:
            self._print_avatar_explain(post_text, article, grounding_facts, channel, ssi_component, extracted_facts=extracted_facts)
        if dot_report:
            self._print_dot_report(post_text, article, grounding_facts, extracted_facts)

        if dry_run:
            created_ideas.append({
                "dry_run": True,
                "title": article["title"],
                "generated_text": post_text,
                "grounding_facts": grounding_facts,
                "ssi_component": ssi_component,
                "channel": channel,
                "confidence_route": _conf_route,
            })
            return created_ideas

        if _conf_route == "block":
            logger.warning(
                str(Fore.YELLOW) + f"⚠️  Confidence policy blocked publish for: {article['title'][:60]}" + str(Style.RESET_ALL)
            )
            return created_ideas

        if not self.buffer:
            logger.warning("No buffer_service provided — skipping idea creation")
            return created_ideas

        effective_message_type = "idea" if _conf_route == "idea" else message_type
        if effective_message_type == "post":
            if channel == "youtube":
                yt_dir = Path("yt-vid-data")
                yt_dir.mkdir(exist_ok=True)
                safe_title = re.sub(r"[^\w\-]", "_", article["title"][:60]).strip("_")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                script_path = yt_dir / f"{timestamp}_{safe_title}.txt"
                script_path.write_text(
                    f"TITLE: {article['title']}\nSSI COMPONENT: {ssi_component}\nSOURCE: {article['link']}\n\n{post_text}\n",
                    encoding="utf-8",
                )
                print(str(Fore.GREEN) + f"💾 Saved to: {script_path}" + str(Style.RESET_ALL))
                print("GitHub: https://buff.ly/tfajNLI")
                print("Sign up for Buffer with my partner link — join.buffer.com/samjd42  — to start scheduling, publishing, and analyzing your social posts in one place while supporting my work.")
                print(str(Fore.YELLOW) + "⚠️  Buffer YouTube requires a video — script not pushed." + str(Style.RESET_ALL))
                self._save_published_title(article["title"])
                created_ideas.append({
                    "title": article["title"], "text": post_text,
                    "ssi_component": ssi_component, "channel": "youtube",
                    "script_path": str(script_path),
                })
                return created_ideas
            elif channel == "x":
                channel_id = self.buffer.get_x_channel_id()

            elif channel == "threads":
                channel_id = self.buffer.get_threads_channel_id()
            elif channel == "bluesky":
                channel_id = self.buffer.get_bluesky_channel_id()
            elif channel == "facebook":
                channel_id = self.buffer.get_facebook_channel_id()
            else:
                channel_id = self.buffer.get_linkedin_channel_id()
            try:
                post = self.buffer.create_scheduled_post(channel_id, post_text, channel=channel)
                self._save_published_title(article["title"])
                try:
                    from services.selection_learning import update_candidate_buffer_id as _upd
                    _upd(candidate_id, post.get("id", ""))
                except Exception as _upd_exc:
                    logger.warning("selection_learning: buffer_id update failed (continuing): %s", _upd_exc)
                created_ideas.append({**(post if isinstance(post, dict) else {}), "generated_text": post_text, "grounding_facts": grounding_facts})
            except BufferQueueFullError as exc:
                logger.warning(
                    str(Fore.YELLOW) + f"⚠️  Buffer queue full — stopping early. ({exc})" + str(Style.RESET_ALL)
                )
                return None  # signal caller to break
        else:
            idea = self.buffer.create_idea(
                text=post_text,
                title=f"[{channel}|{ssi_component}] {article['title'][:70]}",
            )
            self._save_published_title(article["title"])
            try:
                from services.selection_learning import update_candidate_buffer_id as _upd
                _upd(candidate_id, idea.get("id", ""))
            except Exception as _upd_exc:
                logger.warning("selection_learning: buffer_id update failed (continuing): %s", _upd_exc)
            created_ideas.append({**(idea if isinstance(idea, dict) else {}), "generated_text": post_text, "grounding_facts": grounding_facts})

        return created_ideas
