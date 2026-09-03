"""Public truth gate API: truth_gate_result and truth_gate."""

from __future__ import annotations

import logging
import re

from colorama import Fore, Style

from services.console_grounding._config import (
    _normalize_phrase,
    get_console_grounding_keywords,
    get_truth_gate_bm25_threshold,
    get_truth_gate_fact_sim_floor,
    get_truth_gate_spacy_sim_floor,
    get_whitelisted_phrases,
)
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
    _extract_spacy_orgs,
    _score_sentence_bm25,
    build_bm25_index,
    get_all_persona_facts_from_avatar_state,
    get_domain_facts_from_avatar_state,
    get_project_names_from_avatar_state,
)
from services.console_grounding._models import ProjectFact, TruthGateMeta

logger = logging.getLogger(__name__)


def _is_project_like_org_mention(sentence: str, org_phrase: str) -> bool:
    """Return True when an ORG-like phrase is used as a project or event reference.

    This prevents false positives like "G7 RIA project" or "G7 GovAI Grand Challenge"
    where spaCy may label the phrase as ORG even though the sentence is explicitly
    discussing a project/event/challenge, not introducing an unsupported organization.
    """
    sent_lower = sentence.lower()
    org_lower = org_phrase.lower().strip()
    if not org_lower:
        return False
    # Detect explicit "project" keyword after the org phrase
    if "project" in sent_lower and re.search(rf"\b{re.escape(org_lower)}\s+project\b", sent_lower):
        return True
    # Detect event/competition keywords anywhere in the sentence
    _EVENT_KEYWORDS = {"challenge", "summit", "conference", "forum", "hackathon", "competition", "congress", "symposium"}
    if any(kw in sent_lower for kw in _EVENT_KEYWORDS):
        return True
    return False


def _is_likely_false_positive_org(org_phrase: str) -> bool:
    """Return True when an ORG phrase is likely a formatting artifact or tag.

    Skips:
      - Phrases containing newlines (e.g., 'Scale\nIf' from text wrapping)
      - Phrases containing slashes (e.g., 'AI/GovTech/Ottawa' community tags)
      - Short social CTA labels such as 'DM' / 'Direct Message' used in copy
        calls-to-action, not as company names
      - Social phrases like 'DM exchange' or 'direct message exchange' that are
        conversational CTA language, not organizations
    """
    if not org_phrase:
        return False
    norm = org_phrase.strip().lower()
    if "\n" in org_phrase or "/" in org_phrase:
        return True
    if re.fullmatch(r"dm(s)?", norm):
        return True
    if norm in {"direct message", "direct messages"}:
        return True
    if re.fullmatch(r"dm\s+exchange", norm):
        return True
    if re.fullmatch(r"direct message\s+exchange", norm):
        return True
    if re.search(r"\b(?:comment|reply|reach out|message|send|drop|leave)\s+(?:or\s+)?(?:a\s+)?dm\b", norm):
        return True
    if re.search(r"\b(?:comment|reply|reach out|message|send|drop|leave)\s+(?:or\s+)?(?:a\s+)?direct message\b", norm):
        return True
    if re.search(r"\b(?:earn|get|cause|prompt|start|spark|invite)\s+(?:a\s+)?dm\s+exchange\b", norm):
        return True
    if re.search(r"\b(?:earn|get|cause|prompt|start|spark|invite)\s+(?:a\s+)?direct message\s+exchange\b", norm):
        return True
    return False


def _is_valid_social_cta_sentence(sentence: str) -> bool:
    """Return True for standard social CTA wording like 'DM' or 'Send a DM'.

    These are valid LinkedIn CTA phrases used in outreach copy, not organization
    names or unsupported claims. Keep them through the truth gate even when they
    are short and lightweight.
    """
    text = sentence.lower()
    if "dm" not in text and "direct message" not in text:
        return False
    patterns = [
        r"\bcomment\s+or\s+(?:a\s+)?dm\b",
        r"\bcomment\s+or\s+(?:a\s+)?direct message\b",
        r"\bdm\s+['\"][^'\"]+['\"]",
        r"\bdm\s+exchange\b",
        r"\bdirect message\s+exchange\b",
        r"\b(?:causes?|creates?|starts?|sparks?|drives?|gets?|earns?)\s+(?:a\s+)?dm\s+exchange\b",
        r"\b(?:causes?|creates?|starts?|sparks?|drives?|gets?|earns?)\s+(?:a\s+)?direct message\s+exchange\b",
        r"\b(?:send|drop|leave|reply|message|reach out|reach out to|hit me up)\s+(?:me\s+)?(?:a\s+)?dm\b",
        r"\b(?:send|drop|leave|reply|message|reach out|reach out to|hit me up)\s+(?:me\s+)?(?:a\s+)?dm\s+['\"][^'\"]+['\"]",
        r"\b(?:send|drop|leave|reply|message|reach out|reach out to)\s+(?:a\s+)?direct message\b",
        r"\bdirect message\s+['\"][^'\"]+['\"]",
        r"\b(?:reply|message|reach out)\s+with\s+dm\b",
        r"\b(?:reply|response|conversation|lead)\s+(?:through|via|with)\s+(?:a\s+)?dm\b",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def truth_gate_result(
    text: str,
    article_text: str,
    facts: list[ProjectFact],
    interactive: bool = False,
    article_ref: str = "",
    channel: str = "linkedin",
    suggest_facts: bool = True,
) -> tuple[str, TruthGateMeta]:
    """Truth gate that returns both the filtered text and scoring metadata.

    Scans each sentence for unsupported numeric claims, year references, dollar
    amounts, org names, and project-technology misattributions.  Returns the
    cleaned text and a :class:`TruthGateMeta` with removed_count, reason_codes,
    DoT gradient scores, and spaCy similarity scores.

    When *interactive* is True, flagged sentences are presented for confirmation
    and decisions are recorded in the avatar learning log.
    When *suggest_facts* is True, spaCy is used to suggest supporting facts for
    dropped sentences (interactive mode only).
    """
    if not text:
        return text, TruthGateMeta(removed_count=0, total_sentences=0)

    logger.debug("Truth gate called for channel=%s", channel)

    domain_facts = get_domain_facts_from_avatar_state()
    all_facts = facts + domain_facts
    logger.debug(
        "Truth gate using %d project facts + %d domain facts", len(facts), len(domain_facts)
    )

    all_persona_facts = get_all_persona_facts_from_avatar_state()
    allowed = _build_allowed_tokens(article_text, all_facts + all_persona_facts)
    known_project_names = get_project_names_from_avatar_state()
    tech_keywords = get_console_grounding_keywords()
    project_map = _build_project_tech_map(all_facts, article_text)
    sentences = _SENTENCE_SPLIT_RE.split(text)
    kept: list[str] = []
    removed: list[tuple[str, str]] = []

    spacy_nlp = None
    try:
        from services.spacy_nlp import get_spacy_nlp
        spacy_nlp = get_spacy_nlp()
    except Exception as _nlp_exc:
        logger.debug("spaCy NLP unavailable: %s", _nlp_exc)

    bm25_threshold = get_truth_gate_bm25_threshold()
    spacy_sim_floor = get_truth_gate_spacy_sim_floor()
    fact_sim_floor = get_truth_gate_fact_sim_floor()

    dot_per_sentence_scores: list[float] = []
    spacy_sim_scores: dict[str, float] = {}
    fact_sim_scores: dict[str, float] = {}

    _dot_score_fn = None
    try:
        from services.derivative_of_truth import score_claim_with_truth_gradient as _dot_score_fn
    except ImportError:
        logger.debug("DoT unavailable — per-sentence and full-post scoring skipped")

    whitelisted_phrases = get_whitelisted_phrases()

    # Built once: the evidence corpus is identical for every sentence.
    _bm25_index = None
    if _BM25_AVAILABLE and (article_text or all_facts):
        _bm25_index = build_bm25_index(article_text, all_facts)

    _fact_texts = [
        f"{f.project} {f.details}".strip()
        for f in all_facts
        if (f.project or f.details)
    ]

    for sentence in sentences:
        stripped = sentence.strip()
        if not stripped:
            kept.append(sentence)
            continue
        if _normalize_phrase(stripped) in whitelisted_phrases:
            kept.append(sentence)
            continue
        if _is_valid_social_cta_sentence(stripped):
            kept.append(sentence)
            continue
        if all(word.startswith("#") for word in stripped.split()):
            kept.append(sentence)
            continue
        url_pattern = re.compile(r"^(https?://\S+)$")
        if all(url_pattern.match(word) for word in stripped.split()):
            kept.append(sentence)
            continue
        if re.search(r"https?://\S+", stripped):
            kept.append(sentence)
            continue
        if stripped.endswith("?"):
            kept.append(sentence)
            continue

        reason: str | None = None

        # BM25 evidence strength check
        if _BM25_AVAILABLE and (article_text or all_facts):
            bm25_score = _score_sentence_bm25(
                sentence, article_text, all_facts, index=_bm25_index
            )
            if bm25_score < bm25_threshold:
                reason = f"weak_evidence_bm25: score={bm25_score:.2f} < threshold={bm25_threshold}"

        # Part C: spaCy semantic similarity floor (numeric/org sentences only, vs article)
        if not reason and spacy_nlp and article_text:
            _has_specific_claim = (
                _NUMERIC_CLAIM_RE.search(stripped)
                or _YEAR_RE.search(stripped)
                or _DOLLAR_RE.search(stripped)
                or _ORG_NAME_RE.search(stripped)
            )
            if _has_specific_claim:
                _sim = spacy_nlp.compute_similarity(sentence, article_text)
                spacy_sim_scores[sentence] = _sim
                if 0.0 < _sim < spacy_sim_floor:
                    reason = f"low_semantic_similarity: sim={_sim:.3f} < floor={spacy_sim_floor:.2f}"

        # Part E: spaCy semantic similarity vs persona/domain fact pool (all contexts)
        # Computes best similarity across all facts individually; works in console mode too.
        if not reason and spacy_nlp and all_facts:
            if _fact_texts:
                try:
                    _sims = spacy_nlp.compute_similarity_batch(sentence, _fact_texts)
                    _best_fact_sim = max(_sims) if _sims else 0.0
                    fact_sim_scores[sentence] = _best_fact_sim
                    if 0.0 < _best_fact_sim < fact_sim_floor:
                        reason = f"low_fact_similarity: sim={_best_fact_sim:.3f} < floor={fact_sim_floor:.2f}"
                except Exception as _fsim_exc:
                    logger.debug("Fact-pool spaCy sim failed: %s", _fsim_exc)

        # Strict token-matching checks
        if not reason:
            for m in _NUMERIC_CLAIM_RE.finditer(sentence):
                full_token = m.group(0).lower().strip()
                num_token = re.match(r"[\d,.]+", m.group(0))
                if num_token and full_token not in allowed and num_token.group(0).lower().rstrip(".") not in allowed:
                    reason = f"unsupported_numeric: '{m.group(0)}'"
                    break

        if not reason:
            for m in _YEAR_RE.finditer(sentence):
                if m.group(0) not in allowed:
                    reason = f"unsupported_year: '{m.group(0)}'"
                    break

        if not reason:
            for m in _DOLLAR_RE.finditer(sentence):
                nearby = sentence[m.start():m.start() + 20]
                num = re.search(r"\d[\d,.]*", nearby)
                if num and num.group(0).lower().rstrip(".") not in allowed:
                    reason = f"unsupported_dollar: '{nearby.strip()}'"
                    break

        if not reason:
            # Part D: spaCy NER org-name check (falls back to _ORG_NAME_RE regex)
            _spacy_orgs = _extract_spacy_orgs(sentence, spacy_nlp) if spacy_nlp else []
            if _spacy_orgs:
                for _org in _spacy_orgs:
                    if _is_valid_social_cta_sentence(sentence):
                        continue
                    if _is_project_like_org_mention(sentence, _org):
                        continue
                    if _is_likely_false_positive_org(_org):
                        continue
                    _org_lower = _org.lower()
                    # Strip leading articles before project name matching
                    _org_normalised = re.sub(r"^(the|a|an)\s+", "", _org_lower)
                    # Skip if the ORG phrase is a full name or substring of a known project
                    if any(_org_lower in proj_name for proj_name in known_project_names):
                        continue
                    if any(_org_normalised in proj_name for proj_name in known_project_names):
                        continue
                    if _org_lower not in allowed:
                        _org_words = [w for w in re.findall(r"\w+", _org_lower) if len(w) > 1]
                        if not all(word in allowed for word in _org_words):
                            reason = f"unsupported_org: '{_org}'"
                            break
            else:
                for m in _ORG_NAME_RE.finditer(sentence):
                    if _is_valid_social_cta_sentence(sentence):
                        continue
                    if _is_project_like_org_mention(sentence, m.group(1)):
                        continue
                    if _is_likely_false_positive_org(m.group(1)):
                        continue
                    org_phrase = m.group(1).lower()
                    # Strip leading articles before project name matching
                    org_normalised = re.sub(r"^(the|a|an)\s+", "", org_phrase)
                    # Skip if the ORG phrase is a full name or substring of a known project
                    if any(org_phrase in proj_name for proj_name in known_project_names):
                        continue
                    if any(org_normalised in proj_name for proj_name in known_project_names):
                        continue
                    if org_phrase not in allowed:
                        org_words = [w for w in re.findall(r"\w+", org_phrase) if len(w) > 1]
                        if not all(word in allowed for word in org_words):
                            reason = f"unsupported_org: '{m.group(1)}'"
                            break

        if not reason:
            reason = _check_project_claim(sentence, project_map, tech_keywords)

        # Part B: per-sentence DoT scoring
        if not reason and all_facts and _dot_score_fn is not None:
            try:
                _sent_paths = _build_evidence_paths_for_sentence(sentence, all_facts)
                if _sent_paths:
                    _sent_dot = _dot_score_fn(sentence, _sent_paths)
                    dot_per_sentence_scores.append(_sent_dot.truth_gradient)
                    if _sent_dot.flagged:
                        reason = f"weak_dot_gradient: gradient={_sent_dot.truth_gradient:.3f}"
                        logger.debug(
                            "DoT per-sentence flagged: gradient=%.3f sentence='%s...'",
                            _sent_dot.truth_gradient,
                            sentence[:60],
                        )
            except Exception as _dot_sent_exc:
                logger.debug("Per-sentence DoT failed: %s", _dot_sent_exc)

        if reason:
            if interactive:
                print(f"\n⚠️  Truth gate flagged sentence:")
                print(f"    Reason : {reason}")
                print(f"    Sentence: {sentence}")
                if suggest_facts and spacy_nlp and all_facts:
                    try:
                        fact_texts = [f"{f.project} | {f.details}" for f in all_facts]
                        suggestions = spacy_nlp.suggest_matching_facts(
                            dropped_sentence=sentence,
                            available_facts=fact_texts,
                            top_n=3,
                        )
                        if suggestions:
                            print(f"\n    💡 Suggested facts to support this claim:")
                            for i, sugg in enumerate(suggestions, 1):
                                print(f"       {i}. [{sugg['similarity']:.2f}] {sugg['fact'][:80]}...")
                                print(f"          → {sugg['suggestion']}")
                    except Exception as _sugg_exc:
                        logger.debug("Fact suggestion failed: %s", _sugg_exc)
                try:
                    answer = input("    Remove this sentence? [y/N]: ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    answer = "n"
                user_removed = answer in ("y", "yes")
                if user_removed:
                    removed.append((sentence, reason))
                else:
                    kept.append(sentence)
                decision = "removed" if user_removed else "kept"
                try:
                    from services.avatar_intelligence import record_moderation_event
                    record_moderation_event(
                        sentence=sentence,
                        reason_code=reason.split(":")[0],
                        decision=decision,
                        channel=channel,
                        article_ref=article_ref,
                    )
                except Exception as _log_exc:
                    logger.warning("Failed to record moderation event: %s", _log_exc)
            else:
                removed.append((sentence, reason))
        else:
            kept.append(sentence)

    if removed:
        for full_sentence, reason in removed:
            logger.info(
                "%s🛑 Truth gate removed [channel=%s] [%s]: %s%s",
                str(Fore.RED),
                channel,
                reason,
                full_sentence,
                str(Style.RESET_ALL),
            )
        logger.info(
            "%s⚖️  Truth gate summary [channel=%s]: removed %d of %d sentences%s",
            str(Fore.YELLOW),
            channel,
            len(removed),
            len(sentences),
            str(Style.RESET_ALL),
        )
    else:
        logger.debug(
            "Truth gate [channel=%s]: no sentences removed (%d total sentences)",
            channel,
            len(sentences),
        )

    meta = TruthGateMeta(
        removed_count=len(removed),
        total_sentences=len(sentences),
        reason_codes=[r.split(":")[0] for _, r in removed],
        dot_per_sentence_scores=dot_per_sentence_scores,
        spacy_sim_scores=spacy_sim_scores,
        fact_sim_scores=fact_sim_scores,
    )

    # --- Derivative of Truth scoring on the kept post text (Part A) ---
    try:
        if _dot_score_fn is None:
            raise ImportError("DoT not imported")
        kept_text = " ".join(kept).strip()
        ev_paths = _build_evidence_paths_for_sentence(kept_text, all_facts) if all_facts else []
        _dot = _dot_score_fn(kept_text, ev_paths)
        meta.truth_gradient = _dot.truth_gradient
        meta.dot_uncertainty = _dot.uncertainty
        meta.dot_flagged = _dot.flagged
        meta.dot_uncertainty_sources = _dot.uncertainty_sources
        if _dot.flagged:
            logger.warning(
                "DoT: truth gradient %.3f below threshold — post flagged (channel=%s)",
                _dot.truth_gradient,
                channel,
            )
        else:
            logger.debug(
                "DoT: truth gradient=%.3f uncertainty=%.3f (channel=%s)",
                _dot.truth_gradient,
                _dot.uncertainty,
                channel,
            )
    except Exception as _dot_exc:
        logger.debug("DoT scoring unavailable: %s", _dot_exc)

    return " ".join(kept).strip(), meta


def truth_gate(
    text: str,
    article_text: str,
    facts: list[ProjectFact],
    interactive: bool = False,
    article_ref: str = "",
    channel: str = "linkedin",
    suggest_facts: bool = True,
) -> str:
    """Lightweight post-generation truth gate.

    Scans each sentence in *text* for unsupported numeric claims, year
    references, dollar amounts, company names, and project-technology
    misattributions.  Returns the filtered text (may be identical to input
    if nothing was stripped).

    When *interactive* is True each flagged sentence is presented to the user
    for confirmation; decisions are recorded in the avatar learning log.
    """
    filtered, _ = truth_gate_result(
        text=text,
        article_text=article_text,
        facts=facts,
        interactive=interactive,
        article_ref=article_ref,
        channel=channel,
        suggest_facts=suggest_facts,
    )
    return filtered
