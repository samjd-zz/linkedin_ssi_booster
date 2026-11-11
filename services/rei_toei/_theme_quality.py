"""Theme-candidate quality rules: keep grounded named concepts, drop generic words."""

import re
from collections import Counter
from typing import Any, Iterable, Set

from services.content_curator._text_utils import looks_like_nav_chrome

THEME_MAX_WORDS = 4

# Tags/entities skipped during theme extraction. Articles and pronouns, plus
# generic discourse nouns that spaCy noun-chunking emits from learned facts
# (e.g. "For example, ..." → tag "example") — none of them make a song theme.
_THEME_STOP_WORDS = {
    "the", "a", "an", "which", "that", "this", "these", "those", "it", "its",
    "they", "their",
    "example", "examples", "instance", "instances", "case", "cases",
    "result", "results", "observation", "observations", "figure", "figures",
    "table", "tables", "pair", "pairs", "number", "numbers", "percent",
    "part", "parts", "thing", "things", "way", "ways", "item", "items",
    "step", "steps", "section", "sections", "list", "lists", "note", "notes",
    "term", "terms", "word", "words", "sentence", "sentences",
    "overview", "summary", "introduction", "conclusion", "people",
    "today", "today's", "today s", "yesterday", "tomorrow", "recently",
    "currently", "new", "album", "new album", "latest album", "debut album",
    "full album", "release", "released", "new release", "release information",
    "press release", "single", "new single", "album release",
    "本日", "今日", "昨日", "明日", "今週", "来週", "今月", "来月", "今年", "昨年",
    "新譜", "アルバム", "ニューアルバム", "リリース", "発売", "配信リリース",
    "improved configuration", "an improved configuration", "custom implementation",
    "custom implementations", "deep dive", "quality drop", "best practices",
    # Release/event metadata labels ("Label：", "OPEN 18:00 / START 19:00")
    "label", "open", "start", "tracklist", "release date",
    # Japanese discourse connectives (never a song theme)
    "その後", "今回", "一方", "さらに", "また", "そして",
}
# Bare temporal tags ("2024年", "10月", "October") — demoted in NER but they
# still slip through as noun-chunk tags; a date is not a music theme.
_TEMPORAL_TAG_RE = re.compile(
    r"^(?:\d{4}\s*年?|\d{1,2}\s*月|\d{1,2}月\d{1,2}日"
    r"|(?:january|february|march|april|may|june|july|august|september|october|november|december)"
    r"|(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))$",
    re.IGNORECASE,
)
_LOW_SIGNAL_THEME_RE = re.compile(
    r"\b(?:today(?:'s)?|yesterday|tomorrow|this week|last week|next week|"
    r"this month|next month|last month|this year|last year|this morning|tonight)\b"
    r"|\balbum\b"
    r"|(?:本日|今日|昨日|明日|今週|来週|今月|来月|今年|昨年)"
    r"|(?:ニューアルバム|アルバム|リリース|発売|新譜)",
    re.IGNORECASE,
)
# Decades and counters ("1990年代", "1組", "第1弾", "1990s", "2nd").
_COUNTER_TOKEN_RE = re.compile(
    r"^第?\d+(?:\s*[\u3040-\u30ff\u3400-\u9fff]{1,2}|s|st|nd|rd|th)?$"
)
_LEADING_DETERMINER_RE = re.compile(
    r"^(?:the|a|an|this|that|these|those|its|their|our|my|your|his|her)\s+"
)
_EDGE_PUNCTUATION = "＜＞〈〉『』「」【】《》（）()<>[]{}\"'“”‘’:：,，、。・!！?？ "
_UNCLOSED_PAREN_TAIL_RE = re.compile(r"\s*[（(][^）)]*$")
_INNER_BRACKET_RE = re.compile(r"[〈〉『』「」【】《》＜＞]")
_LIST_SEPARATOR_RE = re.compile(r"[、，,;|]")
# Site navigation words; a phrase built from several of them is a scraped menu.
_SITE_MENU_WORDS = {
    "menu", "search", "close", "products", "solutions", "industries",
    "partners", "customers", "pricing", "resources", "docs", "login", "signup",
}
_JAPANESE_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
_HIRAGANA_ONLY_RE = re.compile(r"^[\u3040-\u309fー]+$")
_LATIN_LETTER_RE = re.compile(r"[A-Za-z]")
# \w also matches Japanese, so "TOKYOで" needs an explicit Latin word boundary.
_LATIN_WORD_CHARS = r"0-9A-Za-z\u00C0-\u024F"
_SENTENCE_OPENERS = ".!?:;\"“'(（「『【"


def _theme_key(value: str) -> str:
    return re.sub(r"\W+", " ", value.lower()).strip()


def is_theme_candidate(value: Any) -> bool:
    """Reject metadata, timing, promotional and generic phrase fragments."""
    if not isinstance(value, str):
        return False
    normalized = " ".join(value.casefold().split()).strip()
    key = _theme_key(normalized)
    words = normalized.split()
    return bool(
        len(normalized) > 2
        and key
        and len(words) <= THEME_MAX_WORDS
        and normalized not in _THEME_STOP_WORDS
        and key not in _THEME_STOP_WORDS
        and not normalized.endswith(".")
        and not _COUNTER_TOKEN_RE.match(normalized)
        and not _TEMPORAL_TAG_RE.match(normalized)
        and not _LOW_SIGNAL_THEME_RE.search(normalized)
        and not _INNER_BRACKET_RE.search(normalized)
        and not _LIST_SEPARATOR_RE.search(normalized)
        and sum(word in _SITE_MENU_WORDS for word in words) < 2
        and not looks_like_nav_chrome(normalized)
    )


def normalize_theme_candidate(value: Any) -> str:
    """Return the canonical theme key for a tag/entity, or "" when it is not a theme.

    Strips wrapping brackets/quotes, unclosed parenthetical tails and leading
    determiners so "The Agent", "an agent" and "〈GAP（ギャップ" collapse to one key.
    """
    if not isinstance(value, str):
        return ""
    normalized = " ".join(value.casefold().split()).strip(_EDGE_PUNCTUATION)
    normalized = _UNCLOSED_PAREN_TAIL_RE.sub("", normalized).strip(_EDGE_PUNCTUATION)
    # "the-art" is a fragment of "state-of-the-art", never a concept.
    if normalized.startswith("the-"):
        return ""
    normalized = _LEADING_DETERMINER_RE.sub("", normalized).strip(_EDGE_PUNCTUATION)
    return normalized if is_theme_candidate(normalized) else ""


def _is_sentence_initial(statement: str, start: int) -> bool:
    prefix = statement[:start].rstrip()
    return not prefix or prefix[-1] in _SENTENCE_OPENERS


def _concept_pattern(concept: str) -> re.Pattern[str]:
    body = r"\s+".join(re.escape(word) for word in concept.split())
    return re.compile(
        rf"(?<![{_LATIN_WORD_CHARS}-]){body}(?![{_LATIN_WORD_CHARS}-])", re.IGNORECASE
    )


def display_theme_name(concept: str, statements: Iterable[str]) -> str:
    """Prefer the casing the sources use ("OpenAI", "NeRF") over ``str.title()``."""
    pattern = _concept_pattern(concept)
    forms: Counter[str] = Counter()
    for statement in statements:
        if not isinstance(statement, str):
            continue
        for match in pattern.finditer(statement):
            surface = " ".join(match.group(0).split())
            if surface != surface.lower():
                forms[surface] += 1
    return forms.most_common(1)[0][0] if forms else concept.title()


def has_named_evidence(concept: str, statements: Iterable[str], entity_terms: Set[str]) -> bool:
    """Return whether the concept is used as a named thing rather than a common word.

    Single Latin words must be written as names in their own source statements
    ("Java", "LSTM", "NeRF" mid-sentence), not mostly lowercase ("scale",
    "training"). Japanese terms need NER entity support unless they mix in Latin
    ("生成AI"). Multi-word phrases do not need name casing. Every candidate must
    occur in at least one supporting statement.
    """
    pattern = _concept_pattern(concept)
    lowercase = named = sentence_initial = 0
    for statement in statements:
        if not isinstance(statement, str):
            continue
        for match in pattern.finditer(statement):
            surface = match.group(0)
            if surface == surface.lower():
                lowercase += 1
            elif any(char.isupper() for char in surface[1:]) or not _is_sentence_initial(
                statement, match.start()
            ):
                named += 1
            else:
                sentence_initial += 1

    if not (lowercase or named or sentence_initial):
        return False
    if _JAPANESE_RE.search(concept):
        if _HIRAGANA_ONLY_RE.match(concept):
            return False
        return concept in entity_terms or bool(_LATIN_LETTER_RE.search(concept))
    if " " in concept:
        return True
    if named:
        return named > lowercase
    if lowercase:
        return False
    return concept in entity_terms
