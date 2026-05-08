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


def append_url_and_hashtags(text: str, url: str) -> str:
    """Programmatically append source URL then hashtags to a LinkedIn post body.

    Hashtags are extracted from the AI output, stripped from the body, and
    re-appended after the URL so ordering is always: body → URL → hashtags.
    """
    body, hashtags = extract_hashtags(text)
    result = body.rstrip()
    if url and url not in result:
        result += f"\n\nStory: {url}"
    if hashtags:
        result += f"\n\n{hashtags}"
    return result
