"""
Text utility helpers for the content curator.
No external service dependencies — pure string manipulation.
"""

import re


def truncate_at_sentence(text: str, budget: int) -> str:
    """Ensure *text* fits within *budget* chars AND ends on a complete sentence.

    If the text is already within budget, only cuts at a sentence boundary if
    one exists — never removes words from within-budget text.
    If the text was over budget and had to be hard-cut, finds the last sentence
    boundary; if none, removes the partial word at the cut point.
    """
    was_over_budget = len(text) > budget
    if was_over_budget:
        text = text[:budget]
    stripped = text.rstrip()
    if stripped[-1:] in ".!?":
        return stripped
    last_match = None
    for m in re.finditer(r"[.!?](?=\s|$)", stripped):
        last_match = m
    if last_match and last_match.end() > len(stripped) // 4:
        return stripped[:last_match.end()]
    if was_over_budget:
        return stripped.rsplit(" ", 1)[0]
    return stripped


def extract_hashtags(text: str) -> tuple[str, str]:
    """Split the AI-generated post body from the trailing hashtag line.

    Returns (body, hashtags) where hashtags may be an empty string.
    The last non-empty line is treated as hashtags if every word starts with '#'.
    """
    lines = text.rstrip().splitlines()
    if lines and all(w.startswith("#") for w in lines[-1].split()):
        return "\n".join(lines[:-1]).rstrip(), lines[-1]
    return text, ""


def clean_article_text(text: str) -> str:
    """Clean article text by removing HTML tags, entities, and common boilerplate.

    Consolidates all text cleaning operations for knowledge extraction:
    - Strips HTML tags and entities
    - Removes short bracket annotations [1], [a], etc.
    - Removes WordPress/blog footers ("The post X appeared first on Y")
    - Collapses multiple whitespace into single spaces

    Args:
        text: Raw article text (may contain HTML, entities, boilerplate).

    Returns:
        Cleaned text with HTML/boilerplate removed and whitespace normalized.
    """
    # Strip HTML tags
    clean = re.sub(r"<[^>]+>", " ", text)
    # Remove HTML entities (both named and numeric)
    clean = re.sub(r"&[a-zA-Z]+;", " ", clean)
    clean = re.sub(r"&#\d+;", " ", clean)
    # Remove short bracket content (citations, annotations)
    clean = re.sub(r"\[\s*[^\]]{0,20}\s*\]", " ", clean)
    # Remove WordPress/blog post footers
    clean = re.sub(
        r"The post .+? appeared first on .+?\s*\.",
        " ",
        clean,
        flags=re.IGNORECASE,
    )
    # Collapse multiple whitespace and trim
    clean = re.sub(r"\s{2,}", " ", clean).strip()
    return clean


def append_url_and_hashtags(text: str, url: str) -> str:
    """Programmatically append source URL then hashtags to a LinkedIn post body.

    Hashtags are extracted from the AI output, stripped from the body, and
    re-appended after the URL so ordering is always: body → URL → hashtags.
    """
    body, hashtags = extract_hashtags(text)
    result = body.rstrip()
    if url and url not in result:
        result += f"\n\n{url}" 
    if hashtags:
        result += f"\n\n{hashtags} #BufferAPI"
    return result
