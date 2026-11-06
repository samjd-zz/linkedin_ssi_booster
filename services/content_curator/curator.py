"""
ContentCurator — main orchestration class.
Fetches articles, generates posts via the AI service, applies confidence
scoring and truth-gate checks, and pushes to Buffer.
"""

import logging
import os
import uuid
from typing import Any

from services.ollama_service import OllamaService
from services.performance import timed_stage
from services.shared import KATZILLA_ENABLED
from services.console_grounding import ProjectFact, TruthGateMeta, truth_gate_result

from services.content_curator._config import KEYWORDS
from services.content_curator._rss_fetcher import fetch_relevant_articles
from services.content_curator._articles import CuratorArticleMixin
from services.content_curator._channel_all import CuratorAllChannelsMixin
from services.content_curator._channel_single import CuratorSingleChannelMixin
from services.content_curator._ssi_picker import build_topic_signal, pick_ssi_component
from services.content_curator._grounding import (
    load_curation_grounding_keywords,
    load_curation_grounding_tag_expansions,
)

logger = logging.getLogger(__name__)


class ContentCurator(CuratorArticleMixin, CuratorAllChannelsMixin, CuratorSingleChannelMixin):

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
    ) -> tuple[list[ProjectFact], list[Any], list[Any]]:
        """Retrieve top-N persona and domain facts, reranked via HybridRetriever when available."""
        from services.evidence_relevance import rank_relevant_evidence

        query = f"{article_title}. {article_summary[:600]}"
        if self._avatar_facts or self._domain_facts or self._extracted_facts:
            from services.avatar_intelligence import (
                retrieve_evidence,
                evidence_facts_to_project_facts,
                domain_facts_to_project_facts,
                EvidenceFact,
                DomainEvidenceFact,
                ExtractedEvidenceFact,
                ExternalEvidenceFact,
                _get_evidence_split,
            )
            n_persona, n_domain = _get_evidence_split()
            n_extracted = int(os.getenv("EXTRACTED_EVIDENCE_COUNT", "2"))
            n_external = int(os.getenv("KATZILLA_MAX_EXTERNAL_RESULTS", "2"))

            eligible = rank_relevant_evidence(
                query, list(self._avatar_facts) + list(self._domain_facts) + list(self._extracted_facts)
            )
            if self._hybrid_retriever is not None:
                # Rank all eligible facts so one evidence type cannot crowd out another.
                ranked = self._hybrid_retriever.find_facts(query, eligible, limit=len(eligible))
                persona_hits_typed: list[EvidenceFact] = [f for f in ranked if isinstance(f, EvidenceFact)][:n_persona]
                domain_hits_typed: list[DomainEvidenceFact] = [f for f in ranked if isinstance(f, DomainEvidenceFact)][:n_domain]
                extracted_hits_typed: list[ExtractedEvidenceFact] = [f for f in ranked if isinstance(f, ExtractedEvidenceFact)][:n_extracted]
                if KATZILLA_ENABLED:
                    combined_hits = retrieve_evidence(
                        query,
                        list(self._avatar_facts) + list(self._domain_facts),
                        limit=n_persona + n_domain + n_external,
                        category_filter=ssi_component,
                    )
                    external_hits_typed: list[ExternalEvidenceFact] = rank_relevant_evidence(query, [
                        f for f in combined_hits if isinstance(f, ExternalEvidenceFact)
                    ])[:n_external]
                else:
                    external_hits_typed = []
            else:
                persona_hits_typed = [f for f in eligible if isinstance(f, EvidenceFact)][:n_persona]
                domain_hits_typed = [f for f in eligible if isinstance(f, DomainEvidenceFact)][:n_domain]
                extracted_hits_typed = [f for f in eligible if isinstance(f, ExtractedEvidenceFact)][:n_extracted]

                if KATZILLA_ENABLED:
                    combined_hits = retrieve_evidence(
                        query,
                        list(self._avatar_facts) + list(self._domain_facts),
                        limit=n_persona + n_domain + n_external,
                        category_filter=ssi_component,
                    )
                    external_hits_typed = rank_relevant_evidence(query, [
                        f for f in combined_hits if isinstance(f, ExternalEvidenceFact)
                    ])[:n_external]
                else:
                    external_hits_typed = []

            persona_pf = evidence_facts_to_project_facts(persona_hits_typed)
            domain_pf = domain_facts_to_project_facts(domain_hits_typed)
            external_pf: list[ProjectFact] = [
                ProjectFact(
                    project=f"Katzilla {ef.agent}/{ef.action}",
                    company=ef.source_name or "Katzilla",
                    years=(ef.retrieved_at or "")[:10],
                    details=ef.statement,
                    source=f"katzilla:{ef.agent}/{ef.action}",
                    tags=set(ef.tags),
                )
                for ef in external_hits_typed
            ]
            return persona_pf + domain_pf + external_pf, extracted_hits_typed, external_hits_typed
        return [], [], []

    @timed_stage(logger, "curation.confidence")
    def _score_and_route(
        self,
        post_text: str,
        article_summary: str,
        grounding_facts: list[ProjectFact],
        channel: str,
        article_ref: str,
        requested_mode: str,
        gate_meta: TruthGateMeta | None = None,
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
            if gate_meta is None:
                cached_meta = getattr(self.ai, "last_truth_gate_meta", None)
                if (
                    isinstance(cached_meta, TruthGateMeta)
                    and getattr(self.ai, "last_truth_gate_text", None) == post_text
                ):
                    gate_meta = cached_meta
                else:
                    _assessed_text, gate_meta = truth_gate_result(
                        post_text, article_summary, grounding_facts,
                        channel=channel, article_ref=article_ref,
                    )
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

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def curate_and_create_ideas(
        self,
        dry_run: bool = False,
        max_ideas: int = 3,
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
        
        def update_published_cache(title: str) -> None:
            """Update both disk cache and in-memory set."""
            if not dry_run:
                self._save_published_title(title)
                published.add(title)

        learn_only = learn
        if learn_only:
            logger.info("🧠 --learn mode: extracting knowledge only — skipping generation%s", " (dry run)" if dry_run else "")

        prefetched_article_text: dict[str, str] = {}
        if learn or not dry_run:
            prefetched_article_text = self._prefetch_article_texts(articles)

        articles_processed = 0
        for article in articles:
            if created_ideas is not None and not learn and articles_processed >= max_ideas:
                break
            if article["title"] in published:
                logger.info("Skipping already-published idea: %s", article["title"][:60])
                continue

            # Fast-path: --curate --learn without --dry-run → extract only, skip generation
            if learn_only:
                self._learn_from_article(article, prefetched_article_text, learn_only=True)
                continue  # skip generation entirely

            _candidate_id = str(uuid.uuid4())
            ssi_component = pick_ssi_component(self._topic_signal)
            # Continual learning — persist new knowledge from the article
            if not dry_run or learn:
                self._learn_from_article(article, prefetched_article_text, learn_only=False)
            else:
                logger.info("Knowledge extraction skipped for '%s' (dry_run without --learn)", article["title"][:60])

            grounding_facts, extracted_facts, external_facts = self._grounding_facts_for_article(
                article_title=article["title"],
                article_summary=article["summary"],
                ssi_component=ssi_component,
            )
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
                    external_facts=external_facts,
                    dry_run=dry_run,
                    message_type=message_type,
                    interactive=interactive,
                    avatar_explain=avatar_explain,
                    dot_report=dot_report,
                    candidate_id=_candidate_id,
                    created_ideas=created_ideas,
                    update_published_cache=update_published_cache,
                )
                if created_ideas is None:  # buffer full — stop
                    break
                articles_processed += 1
            elif len(channel_list) > 1:
                for ch in channel_list:
                    result = self._process_single_channel(
                        article=article,
                        ssi_component=ssi_component,
                        grounding_facts=grounding_facts,
                        extracted_facts=extracted_facts,
                        external_facts=external_facts,
                        channel=ch,
                        message_type=message_type,
                        dry_run=dry_run,
                        interactive=interactive,
                        avatar_explain=avatar_explain,
                        dot_report=dot_report,
                        candidate_id=_candidate_id,
                        created_ideas=created_ideas,
                        update_published_cache=update_published_cache,
                    )
                    if result is None:  # buffer full — stop
                        created_ideas = None
                        break
                if created_ideas is not None:
                    articles_processed += 1
            else:
                result = self._process_single_channel(
                    article=article,
                    ssi_component=ssi_component,
                    grounding_facts=grounding_facts,
                    extracted_facts=extracted_facts,
                    external_facts=external_facts,
                    channel=channel_list[0],
                    message_type=message_type,
                    dry_run=dry_run,
                    interactive=interactive,
                    avatar_explain=avatar_explain,
                    dot_report=dot_report,
                    candidate_id=_candidate_id,
                    created_ideas=created_ideas,
                    update_published_cache=update_published_cache,
                )
                if result is None:  # buffer full — stop
                    created_ideas = None
                    break
                articles_processed += 1
        return created_ideas
