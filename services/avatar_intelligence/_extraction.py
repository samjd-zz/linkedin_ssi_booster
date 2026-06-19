"""Continual learning — NLP extraction pipeline for avatar_intelligence."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.avatar_intelligence._loaders import _load_extracted_knowledge
from services.avatar_intelligence._models import (
    ExtractedFact,
    ExtractedKnowledgeGraph,
)
from services.avatar_intelligence._paths import EXTRACTED_KNOWLEDGE_PATH

logger = logging.getLogger(__name__)

_EXTRACTION_STOPWORDS: frozenset[str] = frozenset({
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of",
    "with", "that", "this", "it", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "will", "would", "can", "could",
    "should", "may", "might", "by", "from", "as", "about", "into", "through",
})


def _make_extracted_evidence_id(fact_id: str, run_index: int) -> str:
    """Return a stable, short evidence ID based on extracted fact ID and run index.

    IDs are stable per run for the same input order:
    X{index:03d}-{6-char fact hash}
    """
    fact_hash = hashlib.sha256(fact_id.encode()).hexdigest()[:6]
    return f"X{run_index:03d}-{fact_hash}"


def _make_extracted_fact_id(source_url: str, statement: str) -> str:
    """Return a stable 12-char SHA-256 hex ID from source_url + statement.

    Used as the deduplication key for extracted facts.
    """
    raw = f"{source_url}||{statement}"
    return "ext-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def save_extracted_knowledge(
    graph: ExtractedKnowledgeGraph,
    path: Path | None = None,
) -> None:
    """Persist *graph* to *path* (defaults to ``EXTRACTED_KNOWLEDGE_PATH``).

    Failures emit a warning so the caller is never interrupted.
    """
    target = path or EXTRACTED_KNOWLEDGE_PATH
    payload: dict[str, Any] = {
        "schemaVersion": graph.schema_version,
        "facts": [asdict(f) for f in graph.facts],
    }
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.debug(
            "Extracted knowledge saved to %s (%d facts)", target, len(graph.facts)
        )
    except OSError as exc:
        logger.warning("Extracted knowledge save failed (continuing): %s", exc)


def extract_and_append_knowledge(
    article_text: str,
    source_url: str,
    source_title: str,
    *,
    min_sentence_len: int = 40,
    confidence: str = "medium",
    path: Path | None = None,
    dry_run: bool = False,
    spacy_nlp: Any | None = None,
) -> list[ExtractedFact]:
    """Extract facts from *article_text* using SpacyNLP and append them to extracted_knowledge.json.

    Pipeline:
    1. Optionally pre-filter article_text through spaCy summarization for higher quality input.
    2. Split article_text into sentences (regex-based).
    3. For each sentence of sufficient length, attempt spaCy theme extraction.
    4. Deduplicate against existing facts using SHA-256 content hash.
    5. Append new facts to the on-disk extracted_knowledge.json.

    Args:
        article_text:          Full article text to extract from.
        source_url:            URL of the originating article.
        source_title:          Title of the originating article.
        min_sentence_len:      Minimum sentence character length to consider.
        confidence:            Confidence level to assign: 'high' | 'medium' | 'low'.
        path:                  Override path to extracted_knowledge.json (for testing).
        dry_run:               If True, extract but do not write to disk.
        spacy_nlp:             Optional SpacyNLP instance for pre-extraction summarization.
                               If provided and article_text > 800 chars, will summarize first.

    Returns:
        List of newly-appended ExtractedFact objects (empty if all were duplicates or dry_run).
    """
    target = path or EXTRACTED_KNOWLEDGE_PATH

    existing_graph, load_errors = _load_extracted_knowledge(target)
    if load_errors and "not found" in load_errors[0]:
        existing_graph = ExtractedKnowledgeGraph(schema_version="1.0", facts=[])
    elif existing_graph is None:
        logger.warning(
            "extract_and_append_knowledge: could not load existing graph — %s", load_errors
        )
        existing_graph = ExtractedKnowledgeGraph(schema_version="1.0", facts=[])

    # Classify the article text once using Model2Vec — stamp every extracted fact
    # with the article's primary category and SSI component.
    _article_category: str = ""
    _article_ssi_component: str = ""
    try:
        from services.model2vec_service import get_model2vec_service
        _m2v = get_model2vec_service()
        if _m2v.is_available():
            _classify_text = f"{source_title} {article_text[:1000]}".strip()
            _cls_result = _m2v.classify_text(_classify_text, top_k=1)
            if _cls_result.predictions:
                _article_category = _cls_result.primary_category
                _article_ssi_component = _cls_result.primary_ssi_component
                logger.debug(
                    "extract_and_append_knowledge: article classified as '%s' (SSI: %s)",
                    _article_category, _article_ssi_component,
                )
    except Exception as _cls_exc:
        logger.debug("extract_and_append_knowledge: category classification skipped: %s", _cls_exc)

    existing_ids: set[str] = {f.id for f in existing_graph.facts}
    # Cross-URL dedup: build a set of normalised statement hashes so the same boilerplate
    # text fetched from multiple URLs (e.g. Elastic sidebar, InfoQ consent form) is only
    # stored once regardless of which source_url it came from.
    _stmt_hash = lambda s: hashlib.sha256(s.strip().lower().encode()).hexdigest()[:16]
    existing_stmt_hashes: set[str] = {_stmt_hash(f.statement) for f in existing_graph.facts}

    # Pre-filter through spaCy summarization for higher quality extraction
    # Use more sentences (8-10) than post generation (5) to preserve fact coverage
    _preprocessing_text = article_text
    if spacy_nlp is not None and len(article_text.strip()) > 800:
        try:
            _summary = spacy_nlp.summarize_article(
                article_text=article_text[:5000],  # Wider window than post generation
                max_sentences=10,  # More sentences to preserve fact diversity
                focus_entities=True,
            )
            if _summary and len(_summary.strip()) >= 200:
                logger.debug(
                    "extract_and_append_knowledge: spaCy pre-filter %d → %d chars for '%s'",
                    len(article_text), len(_summary), source_title[:60]
                )
                _preprocessing_text = _summary
            else:
                logger.debug(
                    "extract_and_append_knowledge: spaCy summary too short, using full text"
                )
        except Exception as _sum_exc:
            logger.debug(
                "extract_and_append_knowledge: spaCy summarization failed, using full text: %s",
                _sum_exc,
            )

    # Strip HTML tags, entities, and common boilerplate before extracting facts
    from services.content_curator._text_utils import clean_article_text
    clean_text = clean_article_text(_preprocessing_text)

    if len(clean_text) < 40:
        logger.debug(
            "extract_and_append_knowledge: no usable text after HTML strip — skipping"
        )
        return []

    try:
        from services.spacy_nlp import get_spacy_nlp
        nlp_engine = get_spacy_nlp()
        spacy_available = True
    except Exception:
        nlp_engine = None
        spacy_available = False

    sentences = re.split(r"(?<=[.!?])\s+", clean_text)
    new_facts: list[ExtractedFact] = []
    extracted_at = datetime.now(timezone.utc).isoformat()

    for sentence in sentences:
        sentence = sentence.strip()
        # Normalize Unicode curly/smart quotes to ASCII so regex filters work consistently
        sentence = (
            sentence.replace("\u2018", "'").replace("\u2019", "'")
            .replace("\u201c", '"').replace("\u201d", '"')
            .replace("\u2013", "-").replace("\u2014", "--")
        )
        # Strip changelog/announcement preamble prefixes before filtering
        # e.g. "#5725 The Vertex AI..." → "The Vertex AI..."
        # e.g. "📢 Noteworthy: The Pixtral..." → "The Pixtral..."
        sentence = re.sub(r"^#\d+\s+", "", sentence)
        sentence = re.sub(r"^[\U00010000-\U0010ffff\U00002000-\U00002BFF\U00002600-\U000027BF]+\s*", "", sentence)  # strip leading emoji
        sentence = re.sub(r"^Noteworthy:\s*", "", sentence, flags=re.IGNORECASE)
        sentence = sentence.strip()
        if len(sentence) < min_sentence_len:
            logger.debug("extraction [too-short]: %.100s", sentence)
            continue
        if re.search(r"[<>]|&[a-zA-Z#]", sentence):
            logger.debug("extraction [html-residue]: %.100s", sentence)
            continue
        if re.search(
            r"appeared first on|^The post\b|^From this\b", sentence, re.IGNORECASE
        ):
            logger.debug("extraction [rss-boilerplate]: %.100s", sentence)
            continue
        # Filter email-capture / consent form fragments scraped from page footers/sidebars
        # e.g. InfoQ "View an example Enter your e-mail address Select your country..."
        if re.search(
            r"(Enter your e-mail address|Select your country|I consent to \w+\.\w+ handling"
            r"|e-mail address Select|Select a country)",
            sentence, re.IGNORECASE,
        ):
            logger.debug("extraction [email-consent-form]: %.100s", sentence)
            continue
        # Filter author byline and changelog fragments that start with punctuation
        # e.g. ", Bharathan Balaji , and Daniel Suarez on 30 APR 2026 in Advanced..."
        if re.match(r"^\s*[,;:]", sentence):
            logger.debug("extraction [punct-start-fragment]: %.100s", sentence)
            continue
        # Filter sentences truncated mid-word (scraper cut off the page in the middle of a word).
        # Catches both 3+ char truncations ("...code-generati") and very short 1-2 char trailing
        # fragments after a space ("...and re", "...triage, i") — both are clear mid-word cuts.
        # \s[a-z]{1,2}$ is safe: only matches when the final whitespace-delimited token is
        # exactly 1-2 lowercase chars (e.g. " re", " i"), not product names or valid endings.
        if (
            re.search(r"[a-z]{3,}$", sentence)
            or re.search(r"\s[a-z]{1,2}$", sentence)
        ) and not re.search(r"[.!?\"'\u2019]\s*$", sentence):
            logger.debug("extraction [truncated-mid-word]: %.100s", sentence)
            continue
        # Filter long product-feature list blobs masquerading as a single sentence.
        # e.g. Elastic sidebar: "Context engineering Get the most relevant context... Vector
        # database... Search powered applications... Threat protection..."
        # These are 400+ char strings with at most one trailing period and 4+ capitalized
        # section-header words in sequence with no sentence separators.
        if len(sentence) > 400:
            _period_count = sentence.count(". ")  # internal sentence separators
            _header_seqs = re.findall(
                r"\b(?:Context|Vector|Search|Threat|Workflow|Endpoint|Security|Logging|Analytics"
                r"|Discover|Dashboard|Components|Deployment|Developer)\b",
                sentence,
            )
            if _period_count == 0 and len(_header_seqs) >= 3:
                logger.debug("extraction [product-feature-list-blob]: %.100s", sentence)
                continue
        if re.match(r"^[\w\s,\-]+,\s+and\s+more\.?$", sentence, re.IGNORECASE):
            logger.debug("extraction [and-more-blob]: %.100s", sentence)
            continue
        if re.match(
            r"^(Have you ever|Did you know|Are you |Do you |What if |Ever wonder)",
            sentence,
            re.IGNORECASE,
        ):
            logger.debug("extraction [rhetorical-question]: %.100s", sentence)
            continue
        if re.match(
            r"^(It|They|This|That|These|Those)\s+(was|were|is|are|has|have|had|added|changed|became)\b",
            sentence,
            re.IGNORECASE,
        ) or re.match(
            # Future-tense preamble / teaser: "It will also cover/discuss/walk/show..."
            r"^It will (also\s+)?(cover|discuss|explore|walk|show|demonstrate|explain"
            r"|highlight|present|outline|introduce|address|describe)\b",
            sentence,
            re.IGNORECASE,
        ):
            logger.debug("extraction [pronoun-opener]: %.100s", sentence)
            continue
        # Filter heading+pronoun concatenations: "Velero It operates..." / "Redis They support..."
        # Pattern: one or two capitalized words immediately followed by bare pronoun as next word
        if re.match(r"^[A-Z]\w+(\s+[A-Z]\w+)? (It|They|This|He|She)\s+", sentence):
            logger.debug("extraction [heading-pronoun-concat]: %.100s", sentence)
            continue
        # Filter dangling-pronoun quantity references (require prior context to be meaningful)
        # e.g. "V4-Flash drops these numbers even further: 10%..."
        if re.search(
            r"\b(this|these|those|the above|the following) (number|metric|value|figure|result|finding|stat|percentage)s?\b",
            sentence,
            re.IGNORECASE,
        ) and not re.search(r"\b(show|indicate|suggest|reveal|confirm|mean|represent)\b", sentence, re.IGNORECASE):
            logger.debug("extraction [dangling-quantity-ref]: %.100s", sentence)
            continue
        # Filter generic-dismissal advisory sentences with no concrete claim
        # e.g. "Optimizing CSS is rarely something you need to worry about..."
        if re.search(
            r"(?i)\brarely (something|a concern|necessary|needed|required|an issue|worth)\b",
            sentence,
        ):
            logger.debug("extraction [generic-dismissal]: %.100s", sentence)
            continue
        # Filter first-person author narration (personal commentary, not domain knowledge)
        if re.match(
            r"^(I |I'm |I've |I couldn't|I sat |I talked |As I |We've |We've )",
            sentence,
        ):
            logger.debug("extraction [first-person-narration]: %.100s", sentence)
            continue
        # Filter adversative conjunction openers followed by a pronoun or demonstrative —
        # these depend on the prior sentence for meaning (the referent is missing).
        # e.g. "However, this also means...", "But it was designed to handle..."
        # Named-subject continuations are NOT filtered:
        # e.g. "However, IBM Bob has now reached 80,000 developers..." is a valid fact.
        if re.match(
            r"^(But |However,\s|Yet,\s|Although |Though |Nevertheless,\s|Nonetheless,\s)"
            r"(it|they|this|that|these|those|he|she|its|their|the same|such)\b",
            sentence,
            re.IGNORECASE,
        ):
            logger.debug("extraction [adversative-pronoun]: %.100s", sentence)
            continue
        # Filter "… Read more" truncated fragments from RSS feed previews
        if re.search(r"[…\.]{1,3}\s*Read more\s*$", sentence, re.IGNORECASE):
            logger.debug("extraction [read-more-truncated]: %.100s", sentence)
            continue
        # Filter newsletter/podcast preamble openers (no extractable domain knowledge)
        if re.match(
            r"^(Welcome to |For this episode |In last week'?s |This week'?s |Last week'?s |This latest one\b)",
            sentence,
            re.IGNORECASE,
        ):
            logger.debug("extraction [newsletter-preamble]: %.100s", sentence)
            continue
        # Filter boilerplate article openers — "In this post/article/release, we/you..." style
        # Also catches "This post demonstrates/covers/explores..." and "This section covers..." variants
        if re.match(
            r"^(In this (post|article|tutorial|guide|blog|video|talk|walkthrough|demo|notebook|session|installment),?\s|"
            r"In this (post|article|tutorial|guide|blog|video|talk|walkthrough|demo|notebook|session|installment) we\b|"
            r"This (post|article|release|update|guide|tutorial|video) (demonstrates?|covers?|explores?|addresses?|"
            r"introduces?|examines?|focuses? on|walks? through|provides?|presents?|shows?)|" 
            r"This section (covers?|discusses?|explains?|walks? through|introduces?|presents?|outlines?)\b)",
            sentence,
            re.IGNORECASE,
        ):
            logger.debug("extraction [boilerplate-opener]: %.100s", sentence)
            continue
        # Filter bullet-list run-ons: scraped blob with 2+ "Be <Adj>" imperatives glued together
        if len(re.findall(r'\bBe [A-Z]', sentence)) >= 2:
            logger.debug("extraction [bullet-list-run-on]: %.100s", sentence)
            continue
        # Filter code classname blobs: sentences containing a CamelCase identifier ≥25 chars
        if re.search(r'\b[A-Z][a-zA-Z]{24,}\b', sentence):
            logger.debug("extraction [code-classname-blob]: %.100s", sentence)
            continue
        # Filter newsletter promo banners ("Software Architects' Newsletter", "things you need to know...")
        if re.search(
            r"things you need to know as an architect|Software Architects'?\s+Newsletter",
            sentence,
            re.IGNORECASE,
        ):
            logger.debug("extraction [newsletter-promo-banner]: %.100s", sentence)
            continue
        # Filter comparative heading questions ("Why X compared to Y?") — section headers, not facts
        if re.match(r'^Why .{5,} compared to ', sentence, re.IGNORECASE):
            logger.debug("extraction [heading-comparison-question]: %.100s", sentence)
            continue
        # Filter disclaimer / AI-generated disclosure sentences
        if re.search(
            r"(this article was (created|written|generated|produced) using|"
            r"disclaimer:?\s|ai-based writing|ai writing companion)",
            sentence,
            re.IGNORECASE,
        ):
            logger.debug("extraction [ai-disclaimer]: %.100s", sentence)
            continue
        # Filter CTA / feedback / community boilerplate
        if re.match(
            r"^(Learn more\b|Learn [A-Z]|We encourage\b|You can find\b|Many thanks\b|Feedback\b|"
            r"Try it\b|Get started\b|Sign up\b|Click here\b|Read more\b|"
            r"Check out\b|Find out\b|Visit\b|Download\b|Subscribe\b)",
            sentence,
            re.IGNORECASE,
        ):
            logger.debug("extraction [cta-boilerplate]: %.100s", sentence)
            continue
        # Filter event marketing announcements — "event for X developers", "conference for Y engineers"
        if re.search(
            r"(?i)\b(?:event|conference|summit|meetup|workshop|hackathon)\s+for\s+\w+\s+(?:developer|engineer|professional|practitioner)s?\b",
            sentence,
        ):
            logger.debug("extraction [event-marketing]: %.100s", sentence)
            continue
        # Filter concatenated section headers separated by double-dash (ToC / bullet-list blobs)
        # e.g. "Model architecture ... Conv3D temporal compression -- Efficient Video Sampling"
        if " -- " in sentence and len(sentence.split()) >= 15:
            logger.debug("extraction [double-dash-blob]: %.100s", sentence)
            continue
        # Filter generic marketing/upgrade CTAs and platform-pitch claims
        if re.search(
            r"(?i)(?:"
            r"explore your options|plan ahead|take advantage of the latest|choose your path"
            r"|\bis (?:now )?available and (?:makes for|offers?|provides?|delivers?)"
            r"|\b(?:requires?|provides?|offers?|delivers?) (?:this |a |the )?(?:holistic|unified|comprehensive|end-to-end|forward-looking) (?:solution|platform|approach|upgrade)"
            r")",
            sentence,
        ):
            logger.debug("extraction [marketing-cta]: %.100s", sentence)
            continue
        # Filter event marketing openers — "This year / Next year / Last year, we're..."
        if re.match(
            r"^(This|Next|Last) (year|quarter|month|week),? (we'?re|we are|we'?ve|I'?m|I am)\b",
            sentence,
            re.IGNORECASE,
        ):
            logger.debug("extraction [event-year-opener]: %.100s", sentence)
            continue
        # Filter passive advisory sentences — "Users are encouraged / Users must migrate..."
        if re.match(
            r"^(Users|Developers|Teams|Customers|Everyone|You) (are (encouraged|advised|asked|required|expected|invited|recommended)|must|should|need to|have to|will need to)\b",
            sentence,
            re.IGNORECASE,
        ):
            logger.debug("extraction [passive-advisory]: %.100s", sentence)
            continue
        # Filter section header blobs — "Version-Specific Highlights", "Getting Started", etc.
        if re.match(
            r"^(Version-Specific\b|Release Notes\b|Key Highlights\b|What'?s New\b|"
            r"Overview:\s|Summary:\s|Background:\s|Context:\s|Motivation:\s|"
            r"How It (Started|Works|Began):|Why (Async|Sync|This|It|We)|TL;DR[:\s])",
            sentence,
            re.IGNORECASE,
        ):
            logger.debug("extraction [section-header]: %.100s", sentence)
            continue
        # Filter narrative heading+body concatenations (uppercase word run followed by prose)
        # e.g. "How It Started: Hitting the GIL Wall at Scale We ve been running..."
        # Pattern: word(s) starting with uppercase, colon, then another sentence fragment
        if re.match(
            r"^[A-Z][\w\s]+(:\s|:\s*[A-Z])[\w\s,]+(\s[A-Z][a-z]|\sWe |\sI |\sThe |\sThis )",
            sentence,
        ):
            # Only discard if it lacks a numeric claim (might be a genuine heading+stat)
            if not re.search(r"\d+\s*%|\d+[xX]|\$\d|\d+\s*(ms|s|min|hour|sec)", sentence):
                logger.debug("extraction [narrative-heading-concat]: %.100s", sentence)
                continue
        # Filter marketing superlative taglines — "Our most X" / "Product: Our most X"
        if re.match(
            r"^(Our|The world'?s?|Industry'?s?|Your) (most|best|only|first|largest|fastest|smartest)\b",
            sentence,
            re.IGNORECASE,
        ):
            logger.debug("extraction [marketing-superlative]: %.100s", sentence)
            continue
        # Also catch "ProductName: Our most / The best / Its most..." prefix form
        if re.match(
            r"^[A-Z][\w\s\d\.\-]+:\s+(Our|The|Its|A) (most|best|only|first|largest|fastest|smartest)\b",
            sentence,
        ):
            logger.debug("extraction [product-superlative]: %.100s", sentence)
            continue
        # Filter "In this installment/episode, I talk/interview/chat/speak" (podcast preambles)
        if re.match(
            r"^In (this|our|my) (installment|episode|talk|conversation|discussion|podcast|livestream|interview),?\s",
            sentence,
            re.IGNORECASE,
        ):
            logger.debug("extraction [podcast-preamble]: %.100s", sentence)
            continue
        # Filter pure URL sentences (no prose content)
        if re.match(r"^https?://\S+$", sentence.strip()):
            logger.debug("extraction [bare-url]: %.100s", sentence)
            continue
        # Filter sentences that are mostly URLs embedded in prose (URL is > 40% of char length)
        _urls_in_sent = re.findall(r"https?://\S+", sentence)
        if _urls_in_sent and sum(len(u) for u in _urls_in_sent) / len(sentence) > 0.40:
            logger.debug("extraction [url-heavy]: %.100s", sentence)
            continue
        # Filter truncated sentences — end without terminal punctuation and have ellipsis/dash
        if re.search(r"(…|\.{3}|--)$", sentence.strip()):
            logger.debug("extraction [truncated-sentence]: %.100s", sentence)
            continue
        # Filter sentences dangling on a bare preposition, conjunction, or article at end
        # e.g. "...all the way back to the foundational techniques of"
        if re.search(r"\s(of|for|to|in|on|at|by|with|from|and|or|but|the|a|an)$", sentence.strip()):
            logger.debug("extraction [dangling-preposition]: %.100s", sentence)
            continue
        # Filter "we show / we walk through / we introduce / we take a look" preambles
        if re.match(
            r"^(In this (post|article|section),? )?(we|you('ll| will))?\s?"
            r"(show|walk through|walk you through|introduce|take a (deeper )?look|explore|demonstrate|describe)\b",
            sentence,
            re.IGNORECASE,
        ):
            logger.debug("extraction [we-show-preamble]: %.100s", sentence)
            continue
        # Filter conditional tutorial/advisory fragments — "When you are developing X..."
        # "While you're building...", "Whenever you need to..."
        # These are instructional prose, not extractable domain facts.
        if re.match(
            r"^(When|While|Whenever) (you|we) (are|were|'re|re )\s*(building|developing|creating|writing|working|deploying|running|using|handling|dealing|testing|debugging|setting up)",
            sentence,
            re.IGNORECASE,
        ):
            logger.debug("extraction [conditional-tutorial]: %.100s", sentence)
            continue
        # Filter background/setup sentences with colloquial anthropomorphism and no concrete metric
        # e.g. "...overlays that the user never thinks about, but that a printer happily reproduces"
        if re.search(
            r"\b(user|developer|engineer)s? never (thinks?|notices?|sees?|considers?|cares?|worries?|realizes?) about\b",
            sentence,
            re.IGNORECASE,
        ) and not re.search(r"\d+\s*%|\d+[xX]|\$\d|\d+\s*(ms|MB|GB|sec|min)", sentence):
            logger.debug("extraction [anthropomorphism]: %.100s", sentence)
            continue
        # Filter HuggingFace/GitHub navigation blobs — long run-on sentences with UI chrome keywords
        if re.search(
            r"\b(Log In|Sign Up|Back to Articles|Models\s+Datasets\s+Spaces|Upvote\s+\d+)\b",
            sentence,
        ):
            logger.debug("extraction [ui-nav-blob]: %.100s", sentence)
            continue
        # Filter pipe-delimited navigation links — catches both multi-pipe nav
        # (e.g. "Home | Source on GitHub | Reference documentation") and single-pipe
        # page-title chrome (e.g. "Article Title | Site Name")
        if re.search(r"\w[^|]+\|[^|]+\|", sentence) or re.search(
            r"\w[^|]{5,}\|\s*[A-Z][\w\s]{2,20}$", sentence
        ):
            logger.debug("extraction [pipe-nav]: %.100s", sentence)
            continue
        # Filter "In our/my recent <event>" livestream/podcast preambles not caught by the earlier pattern
        if re.match(
            r"^In (our|my) recent\s+(JetBrains|episode|livestream|webinar|meetup|talk|session|interview|podcast)",
            sentence,
            re.IGNORECASE,
        ):
            logger.debug("extraction [recent-event-preamble]: %.100s", sentence)
            continue
        # Filter colourful/anecdotal scene-setters with no factual claim
        if re.match(
            r"^(Somewhere out there|Here's what we|Did you ever|Imagine if|Picture this|"
            r"Once upon a|It used to be|Not long ago|Back in the day|True story)",
            sentence,
            re.IGNORECASE,
        ):
            logger.debug("extraction [scene-setter]: %.100s", sentence)
            continue
        # Filter vague rhetorical survey openers ("Here's what we learned from the 2026 survey...")
        if re.match(
            r"^Here'?s (what|how|why|where|when|who) (we|you|I|they|it)",
            sentence,
            re.IGNORECASE,
        ):
            logger.debug("extraction [rhetorical-survey]: %.100s", sentence)
            continue
        # Filter "Starting from square one / First things first / Step X:" heading fragments
        if re.match(
            r"^(Starting from square one|First things first|Step \d+[\.:]\s|At its core,?\s|"
            r"At a high level,?\s|Let's (take|start|begin|look|walk))",
            sentence,
            re.IGNORECASE,
        ):
            logger.debug("extraction [step-heading]: %.100s", sentence)
            continue
        # Filter "You'll learn / You will see / You will discover" educational preambles
        if re.match(
            r"^You'?(?:ll| will) (learn|see|discover|find out|understand|notice|explore|get)\b",
            sentence,
            re.IGNORECASE,
        ):
            logger.debug("extraction [educational-preamble]: %.100s", sentence)
            continue
        # Filter "On behalf of...", "Did you see...", "Have you seen..." openers
        if re.match(
            r"^(On behalf of\b|Did you (see|hear|notice|watch)\b|Have you (seen|heard|noticed|watched)\b)",
            sentence,
            re.IGNORECASE,
        ):
            logger.debug("extraction [on-behalf-opener]: %.100s", sentence)
            continue
        # Filter future-tense article preambles — "We'll focus on / We'll look at / We'll dive into"
        if re.match(
            r"^We'?(?:ll| will) (focus|look|cover|dive|dig|discuss|walk|explore|go through|talk)\b",
            sentence,
            re.IGNORECASE,
        ):
            logger.debug("extraction [future-tense-preamble]: %.100s", sentence)
            continue
        # Filter award/recognition self-promotion sentences
        if re.match(
            r"^(This award\b|This recognition\b|This honor\b|This prize\b|We('re| are) (honored|proud|excited|thrilled|delighted))",
            sentence,
            re.IGNORECASE,
        ):
            logger.debug("extraction [award-promo]: %.100s", sentence)
            continue
        # Filter mangled heading+sentence concatenations — heading word runs directly into
        # sentence text with no space, e.g. "InterconnectedThe phone rang", "HyperscaleThis works"
        # Specifically look for 3+ lowercase chars immediately followed by a common sentence-start
        # word (article, pronoun, preposition) — this avoids matching product names like SageMaker,
        # QuickSight, GitHub which contain camelCase but NOT sentence-word transitions.
        if re.search(
            r"[a-z]{3,}(?:The|This|That|These|Those|Here|Now|With|From|When|Where|Why|How|Who|What|After|Before|During|If|But|And|Or|We|They|You|He|She|It|I )",
            sentence,
        ):
            if not re.search(r"\d+\s*%|\d+[xX]|\b\d{4}\b", sentence):
                logger.debug("extraction [camelcase-concat]: %.100s", sentence)
                continue
        # Filter table/architecture blobs: many repeated short tokens, digit-heavy, no prose verb
        # e.g. "Dense 8B Dense 30B Dense Embedding size 2560 4096 4096 Number of layers 40 40 64..."
        _words = sentence.split()
        if len(_words) >= 12:
            _digit_tokens = sum(1 for w in _words if re.match(r"^\d+$", w))
            _repeated_words = len(_words) - len(set(w.lower() for w in _words))
            if _digit_tokens >= 4 and _repeated_words >= 4:
                logger.debug("extraction [table-blob]: %.100s", sentence)
                continue
        # Filter release-list blobs and ToC navigation: 3+ version numbers where at least one repeats
        # e.g. Spring Boot/Modulith dump, Granite "4.1 ... 4.1" ToC
        _version_nums = re.findall(r"\d+\.\d+", sentence)
        if len(_version_nums) >= 3 and len(set(_version_nums)) < len(_version_nums):
            logger.debug("extraction [version-list-blob]: %.100s", sentence)
            continue
        # Filter generic filler takes with no concrete claim (no number, no named entity pair)
        _generic_filler = bool(re.match(
            r"^(Countless|Many|Most|Some|Several|Various|A (number|lot|few|wide variety)) "
            r"(companies|teams|organizations|developers|engineers|users|people)\b",
            sentence,
            re.IGNORECASE,
        ))
        if _generic_filler and not re.search(r"\d+\s*%|\d+[xX\s]|[€$£¥]\d|\d+\s*(million|billion|thousand)", sentence):
            logger.debug("extraction [generic-filler]: %.100s", sentence)
            continue
        # Filter weak entity sentences: all multi-word entities are stopword-only phrases
        # e.g. "this gap", "the model", "the full journey", "the goal"
        _entity_candidates = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b|\b[A-Z]{2,}\b", sentence)
        _meaningful_entities = [
            e for e in _entity_candidates
            if not all(w.lower() in _EXTRACTION_STOPWORDS for w in e.split())
            and len(e) > 3
        ]
        # Also check for numeric facts (always useful) or named single-word proper nouns
        _has_number = bool(re.search(r"\d", sentence))
        _has_proper_noun = bool(re.search(r"\b[A-Z][a-z]{2,}\b", sentence))
        if not _meaningful_entities and not _has_number and not _has_proper_noun:
            logger.debug("extraction [no-entities]: %.100s", sentence)
            continue
        # Filter navigation/listing blobs: sentences of 12+ words where >45% start with uppercase
        # (catches concatenated HuggingFace/GitHub menus, contributor lists, etc.)
        _blob_words = sentence.split()
        if len(_blob_words) >= 12:
            _cap_ratio = sum(1 for w in _blob_words if re.match(r"^[A-Z]", w)) / len(_blob_words)
            if _cap_ratio > 0.45:
                logger.debug("extraction [nav-blob-cap-ratio=%.2f]: %.100s", _cap_ratio, sentence)
                continue
        # Filter bare product availability announcements with no technical substance
        # e.g. "Vaadin 25.1 is now available and makes for a strong upgrade."
        # Exempt if sentence contains a concrete metric or named platform target
        if re.search(r"(?i)\bis (?:now )?available\b", sentence):
            if not re.search(r"\d+\s*%|\d+[xX]|\bon [A-Z][a-z]+|\benabling\b", sentence):
                logger.debug("extraction [bare-availability]: %.100s", sentence)
                continue
        # Require at least one informative signal: a digit, a 2+ char acronym, or two consecutive
        # title-case words (named entity / product name). Filters generic filler sentences.
        _has_signal = (
            bool(re.search(r"\d", sentence))
            or bool(re.search(r"\b[A-Z]{2,}\b", sentence))
            or bool(re.search(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b", sentence))
        )
        if not _has_signal:
            logger.debug("extraction [no-informative-signal]: %.100s", sentence)
            continue
        # spaCy structural filters — fragment detection + multi-sentence blob detection
        if spacy_available and nlp_engine is not None:
            try:
                _raw_nlp = nlp_engine._ensure_model()
                if _raw_nlp is not None:
                    _sdoc = _raw_nlp(sentence)
                    # Filter name-drop fragments: sentence starts with a PERSON entity and
                    # has no VERB/AUX in the first 10 tokens (no main predicate).
                    _first_10 = list(_sdoc)[:10]
                    _first_has_verb = any(t.pos_ in {"VERB", "AUX"} for t in _first_10)
                    _starts_propn = bool(_sdoc) and _sdoc[0].pos_ in {"PROPN", "NOUN"}
                    _has_person_ent = any(ent.label_ == "PERSON" for ent in _sdoc.ents)
                    if _starts_propn and _has_person_ent and not _first_has_verb:
                        logger.debug("extraction [spacy-name-drop-fragment]: %.100s", sentence)
                        continue
                    # Filter concatenated release/changelog blobs: spaCy detects 5+ sentences
                    # packed into what was split as a single sentence by our regex splitter.
                    if sum(1 for _ in _sdoc.sents) >= 5:
                        logger.debug("extraction [spacy-multi-sentence-blob]: %.100s", sentence)
                        continue
                    # Filter verbless noun-phrase blobs: section headers, ToC lists, nav menus
                    # e.g. "General multimodal reasoning Model architecture Conv3D temporal..."
                    if len(_sdoc) >= 10:
                        _has_any_verb = any(t.pos_ == "VERB" for t in _sdoc)
                        if not _has_any_verb:
                            logger.debug("extraction [spacy-verbless-blob]: %.100s", sentence)
                            continue
            except Exception:
                pass  # spaCy errors are non-fatal — continue without this filter
        fact_id = _make_extracted_fact_id(source_url, sentence)
        if fact_id in existing_ids:
            logger.debug(
                "extract_and_append_knowledge: skipping duplicate fact %s", fact_id
            )
            continue
        # Cross-URL duplicate check: skip if the same statement text was already stored
        # from a different URL (e.g. Elastic sidebar / InfoQ consent form appearing in
        # multiple articles).
        _this_stmt_hash = _stmt_hash(sentence)
        if _this_stmt_hash in existing_stmt_hashes:
            logger.debug(
                "extract_and_append_knowledge: skipping cross-url duplicate statement %.60s", sentence
            )
            continue

        # Within-article semantic dedup: skip if this sentence is near-paraphrase of a
        # fact already collected from the same source URL in this run (spaCy similarity >= 0.93).
        # Catches tense/wording variants that produce different hashes but identical meaning.
        if spacy_available and nlp_engine is not None and new_facts:
            try:
                _raw_nlp = nlp_engine._ensure_model()
                if _raw_nlp is not None:
                    _this_doc = _raw_nlp(sentence)
                    _is_near_dup = False
                    for _prev in new_facts:
                        if _prev.source_url == source_url:
                            _prev_doc = _raw_nlp(_prev.statement)
                            if _this_doc.similarity(_prev_doc) >= 0.93:
                                _is_near_dup = True
                                break
                    if _is_near_dup:
                        logger.debug(
                            "extract_and_append_knowledge: semantic near-dup skipped for %s",
                            fact_id,
                        )
                        continue
            except Exception:
                pass  # spaCy errors are non-fatal

        entities: list[str] = []
        tags: list[str] = []
        if spacy_available and nlp_engine is not None:
            try:
                raw_themes = nlp_engine.extract_themes(sentence)
                tags = [t for t in raw_themes if len(t.split()) == 1][:8]
                entities = [t for t in raw_themes if len(t.split()) > 1][:5]
            except Exception as exc:
                logger.debug(
                    "extract_and_append_knowledge: spaCy extraction error — %s", exc
                )
        else:
            entities = list(dict.fromkeys(
                w for w in re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", sentence)
                if w.lower() not in _EXTRACTION_STOPWORDS
            ))[:5]
            tags = list(dict.fromkeys(
                w.lower()
                for w in re.findall(r"\b[a-zA-Z]{4,}\b", sentence.lower())
                if w.lower() not in _EXTRACTION_STOPWORDS
            ))[:8]

        fact = ExtractedFact(
            id=fact_id,
            statement=sentence,
            source_url=source_url,
            source_title=source_title,
            extracted_at=extracted_at,
            entities=entities,
            tags=tags,
            confidence=confidence,
            extraction_method="spacy_nlp" if spacy_available else "regex_fallback",
            primary_category=_article_category,
            primary_ssi_component=_article_ssi_component,
        )
        new_facts.append(fact)
        existing_ids.add(fact_id)
        existing_stmt_hashes.add(_this_stmt_hash)

    if new_facts and not dry_run:
        updated_facts = existing_graph.facts + new_facts
        updated_graph = ExtractedKnowledgeGraph(
            schema_version=existing_graph.schema_version,
            facts=updated_facts,
        )
        save_extracted_knowledge(updated_graph, path=target)
        logger.debug(
            "extract_and_append_knowledge: appended %d new fact(s) to %s (total: %d)",
            len(new_facts),
            target,
            len(updated_facts),
        )
    elif not new_facts:
        logger.debug(
            "extract_and_append_knowledge: no new facts extracted from '%s'", source_title
        )

    return new_facts if not dry_run else []


def _extracted_fact_tokens(fact: "Any") -> list[str]:
    """Build the BM25 document token list for one extracted evidence fact.

    Concatenates statement, source title, tags, and entities.
    Tags and entities are repeated three times to weight them above plain
    statement words without hard-coded per-field multipliers.
    """
    base = f"{fact.statement} {fact.source_title}"
    tag_boost = " ".join(fact.tags * 3)
    entity_boost = " ".join(fact.entities * 3)
    return re.findall(
        r"[a-zA-Z0-9_+#.-]{2,}",
        (base + " " + tag_boost + " " + entity_boost).lower(),
    )
