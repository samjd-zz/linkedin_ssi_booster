def get_ssi_focus_weights() -> dict:
    """Return SSI focus weights from environment as a normalized dict."""
    weights = {
        "establish_brand": int(os.getenv("SSI_FOCUS_ESTABLISH_BRAND", 0)),
        "find_right_people": int(os.getenv("SSI_FOCUS_FIND_RIGHT_PEOPLE", 0)),
        "engage_with_insights": int(os.getenv("SSI_FOCUS_ENGAGE_WITH_INSIGHTS", 0)),
        "build_relationships": int(os.getenv("SSI_FOCUS_BUILD_RELATIONSHIPS", 0)),
    }
    total = sum(weights.values())
    if total == 0:
        raise ValueError("SSI focus weights sum to zero; check your .env config.")
    # Normalize to proportions (0-1)
    return {k: v / total for k, v in weights.items()}
"""
Shared constants and utilities for all LLM service backends.

Import platform limits, persona, SSI instructions, and text helpers from here.
The ollama_service module owns API logic — nothing in here should import from it.
"""

import os
import re
import logging
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Platform limits
# ---------------------------------------------------------------------------

X_CHAR_LIMIT = 280  # Standard X character limit
X_URL_CHARS  = 23   # Every URL on X counts as exactly 23 characters
THREADS_CHAR_LIMIT = 500  # Standard Threads post limit

# ---------------------------------------------------------------------------
# Persona — configurable via .env
# ---------------------------------------------------------------------------

YOUTUBE_SHORT_SYSTEM_PROMPT: str = os.getenv(
    "YOUTUBE_SHORT_SYSTEM_PROMPT",
    """IMPORTANT — this is a YouTube Short spoken script for a lipsync.video avatar:
- Write entirely in the avatar's voice, first-person.
- Target: 100-150 words maximum (60-second Short) — do NOT exceed 150 words
- Spoken word only — natural contractions, conversational cadence, no jargon walls
- No hashtags, no markdown, no bullet points, no stage directions
- Structure: hook (1-2 sentences) → insight or story (3-4 sentences) → subscribe CTA
- Every sentence must be speakable aloud naturally
Set YOUTUBE_SHORT_SYSTEM_PROMPT in your .env to customise this for your avatar persona."""
)

PERSONA_SYSTEM_PROMPT: str = os.getenv(
    "PERSONA_SYSTEM_PROMPT",
    """You are a LinkedIn content strategist and ghostwriter for a senior technical professional.
Your voice is technical but human: concise, direct, and occasionally contrarian. Posts feel written by someone who has actually shipped the thing.
Never use: 'In the age of AI', 'Game changer', 'Exciting to share', 'Thrilled to announce', 'Delighted to', 'I am pleased to'.
Never start a post with 'I'. Never use bullet points for the main body — write in short, punchy paragraphs.
Avoid corporate jargon, passive voice, and hollow hype. Favour specifics over generalities.
Set PERSONA_SYSTEM_PROMPT in your .env to customise this for a specific person and domain.
IMPORTANT: Output plain text only — no Markdown. Do not use **, ##, __, `, or any other Markdown syntax. LinkedIn does not render Markdown."""
)

# ---------------------------------------------------------------------------
# SSI component instructions — configurable via .env
# ---------------------------------------------------------------------------

SSI_COMPONENT_INSTRUCTIONS: dict[str, str] = {
    "establish_brand": os.getenv(
        "SSI_ESTABLISH_BRAND",
        """This post should ESTABLISH PROFESSIONAL BRAND.
- Share something you built, learned, or solved
- Demonstrate deep expertise in AI/RAG/search
- Use specific technical details — not vague claims
- End with a clear point of view or lesson learned
- LinkedIn algorithm rewards posts that get saves and shares"""
    ),
    "find_right_people": os.getenv(
        "SSI_FIND_RIGHT_PEOPLE",
        """This post should help FIND THE RIGHT PEOPLE.
- Mention specific tools, communities, or events relevant to your industry
- Ask a question that invites replies from your target audience
- Tag relevant communities or technologies (not people)
- This drives profile visits from the right professionals"""
    ),
    "engage_with_insights": os.getenv(
        "SSI_ENGAGE_WITH_INSIGHTS",
        """This post should ENGAGE WITH INSIGHTS.
- Reference or summarize a recent AI paper, article, or trend
- Give YOUR take on it — don't just summarize
- Make a bold or counterintuitive claim based on your experience
- Invite discussion: 'What's your experience with this?'
- This component rewards thoughtful engagement on others' content too"""
    ),
    "build_relationships": os.getenv(
        "SSI_BUILD_RELATIONSHIPS",
        """This post should BUILD RELATIONSHIPS.
- Share a behind-the-scenes story or honest lesson from a project
- Be specific about challenges you faced and how you solved them
- Show personality — not just technical facts
- Make it feel like a conversation, not a press release
- End with something that invites comments and connection"""
    ),
}

# ---------------------------------------------------------------------------
# Shared text utilities
# ---------------------------------------------------------------------------

def clean_llm_text(s: str) -> str:
    """Strip markdown formatting that LLMs sneak in despite instructions."""
    s = re.sub(r'\*\*(.*?)\*\*', r'\1', s)                    # **bold**
    s = re.sub(r'__(.*?)__', r'\1', s)                         # __bold__
    s = re.sub(r'\*(.*?)\*', r'\1', s)                         # *italic*
    s = re.sub(r'_(.*?)_', r'\1', s)                           # _italic_
    s = re.sub(r'`(.*?)`', r'\1', s)                           # `code`
    s = re.sub(r'^#{1,6}\s+', '', s, flags=re.MULTILINE)       # ## headings
    s = re.sub(r'^"+', '', s)                                   # leading " LLMs wrap output in
    return s.strip()


_HASHTAG_TAIL_RE = re.compile(r'((?:\s*#\w+)+)\s*$')
_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')


def format_post_paragraphs(text: str, sentences_per_para: int = 3) -> str:
    """Break a wall-of-text post into paragraphs and put hashtags on their own line.

    - If the body already contains paragraph breaks (\\n\\n), only ensures
      hashtags are separated onto their own line.
    - Otherwise, splits sentences and groups them into paragraphs of
      *sentences_per_para* sentences each.
    """
    if not text or not text.strip():
        return text

    # --- extract trailing hashtags -----------------------------------
    match = _HASHTAG_TAIL_RE.search(text)
    hashtags = ""
    body = text
    if match:
        hashtags = match.group(1).strip()
        body = text[: match.start()].rstrip()

    # --- already paragraphed? just fix hashtag placement -------------
    if "\n\n" in body:
        return (body + f"\n\n{hashtags}") if hashtags else body

    # --- split into sentences ----------------------------------------
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(body) if s.strip()]
    if len(sentences) <= sentences_per_para:
        result = body
    else:
        paragraphs: list[str] = []
        for i in range(0, len(sentences), sentences_per_para):
            paragraphs.append(" ".join(sentences[i : i + sentences_per_para]))
        # avoid a lonely 1-sentence final paragraph — merge with previous
        if len(paragraphs) > 1 and len(sentences) % sentences_per_para == 1:
            last = paragraphs.pop()
            paragraphs[-1] += " " + last
        result = "\n\n".join(paragraphs)

    if hashtags:
        result += f"\n\n{hashtags}"
    return result


def parse_xml_thread(raw: str, source_url: str) -> Optional[list[str]]:
    """Extract a 2-post thread from <post_1>…</post_1> tagged LLM output.

    Returns exactly 2 clean strings, or None if the tags are missing/malformed.
    """
    parts = re.findall(r'<post_[12]>(.*?)</post_[12]>', raw, re.DOTALL | re.IGNORECASE)
    parts = [clean_llm_text(p) for p in parts if p.strip()]
    if len(parts) >= 2:
        return parts[:2]
    logger.warning(
        f"XML thread parse failed — expected 2 <post_N> tags, got {len(parts)} for: {source_url}"
    )
    return None


# ---------------------------------------------------------------------------
# Avatar intelligence configuration defaults (Phase 1C — T3.7)
# ---------------------------------------------------------------------------

_VALID_CONFIDENCE_POLICIES = {"strict", "balanced", "draft-first"}

AVATAR_CONFIDENCE_POLICY: str = os.getenv("AVATAR_CONFIDENCE_POLICY", "balanced")
if AVATAR_CONFIDENCE_POLICY not in _VALID_CONFIDENCE_POLICIES:
    logger.warning(
        "Invalid AVATAR_CONFIDENCE_POLICY '%s'; falling back to 'balanced'. "
        "Valid values: strict, balanced, draft-first",
        AVATAR_CONFIDENCE_POLICY,
    )
    AVATAR_CONFIDENCE_POLICY = "balanced"

AVATAR_LEARNING_ENABLED: bool = os.getenv("AVATAR_LEARNING_ENABLED", "true").lower() == "true"
AVATAR_MAX_MEMORY_ITEMS: int = int(os.getenv("AVATAR_MAX_MEMORY_ITEMS", "200"))

