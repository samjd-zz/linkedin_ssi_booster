"""Content-based eligibility for article grounding, independent of graph popularity."""

from __future__ import annotations

from collections.abc import Sequence
import re
from typing import TypeVar

from spacy.lang.en.stop_words import STOP_WORDS

from services.avatar_intelligence._models import (
    DomainEvidenceFact,
    EvidenceFact,
    ExternalEvidenceFact,
    ExtractedEvidenceFact,
)
from services.spacy_nlp import regex_tokens, tokenize_many_for_search

Evidence = EvidenceFact | DomainEvidenceFact | ExtractedEvidenceFact | ExternalEvidenceFact
_FactT = TypeVar("_FactT", bound=Evidence)
_JAPANESE_TERMS = re.compile(r"[\u4e00-\u9fff]{2,}|[\u30a1-\u30fa\u30fc]{2,}")


def _content(fact: Evidence) -> str:
    if isinstance(fact, EvidenceFact):
        return f"{fact.project} {fact.details}"
    return fact.statement


def _informative_tokens(tokens: Sequence[str]) -> set[str]:
    return {
        token.lower().strip(".-") for token in tokens
        if len(token.strip(".-")) >= 2 and token.lower().strip(".-") not in STOP_WORDS
        and any(char.isalpha() for char in token)
    }


def rank_relevant_evidence(query: str, facts: Sequence[_FactT]) -> list[_FactT]:
    """Rank facts with at least two shared content lemmas (one for a one-term query).

    Raw words also match names whose lemmas differ with capitalization. Japanese
    script terms preserve basic matching without the optional Japanese model.
    Metadata and graph connectivity cannot make a fact eligible.
    """
    if not facts:
        return []
    texts = [query, *(_content(fact) for fact in facts)]
    rows = tokenize_many_for_search(texts)
    tokens = [
        (
            _informative_tokens(row) | set(_JAPANESE_TERMS.findall(text)),
            _informative_tokens(regex_tokens(text)) | set(_JAPANESE_TERMS.findall(text)),
        )
        for text, row in zip(texts, rows)
    ]
    scored = []
    for fact, representations in zip(facts, tokens[1:]):
        scores = []
        # Keep raw and lemmatized matches separate: agent/agents is one topic, not two.
        for query_tokens, fact_tokens in zip(tokens[0], representations):
            shared = len(query_tokens & fact_tokens)
            if query_tokens and shared >= min(2, len(query_tokens)):
                scores.append(shared / len(query_tokens | fact_tokens))
        if scores:
            scored.append((max(scores), fact))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [fact for _, fact in scored]
