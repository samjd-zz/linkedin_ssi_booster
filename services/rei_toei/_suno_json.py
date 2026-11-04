"""Parse LLM JSON payloads and normalise serialized lyric sections."""

import json
import re
from typing import Any, cast, Dict, List, Optional

def _strip_markdown_fences(value: str) -> str:
    """Strip markdown fences and return inner content when present."""
    text = value.strip()
    if "```" not in text:
        return str(text)

    fenced_blocks: List[str] = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
    if fenced_blocks:
        merged = "\n".join(str(block).strip() for block in fenced_blocks if str(block).strip())
        if merged:
            return str(merged).strip()

    return str(text.replace("```json", "").replace("```", "").strip())


def _extract_balanced_json_fragment(value: str) -> Optional[str]:
    """Extract the first balanced JSON object/array fragment from free text."""
    start_index = -1
    opening_char = ""
    for i, ch in enumerate(value):
        if ch in "[{":
            start_index = i
            opening_char = ch
            break
    if start_index < 0:
        return None

    closing_char = "}" if opening_char == "{" else "]"
    depth = 0
    in_string = False
    escaped = False

    for i in range(start_index, len(value)):
        ch = value[i]

        if in_string:
            if escaped:
                escaped = False
                continue
            if ch == "\\":
                escaped = True
                continue
            if ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue

        if ch == opening_char:
            depth += 1
            continue

        if ch == closing_char:
            depth -= 1
            if depth == 0:
                return value[start_index : i + 1]

    return None


def _json_normalization_variants(value: str) -> List[str]:
    """Build progressively relaxed JSON candidates for robust parsing."""
    cleaned = value.strip()
    variants: List[str] = [cleaned]

    normalized_quotes = (
        cleaned.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )
    if normalized_quotes != cleaned:
        variants.append(normalized_quotes)

    no_comment_lines = re.sub(r"(?m)^\s*//.*$", "", normalized_quotes)
    if no_comment_lines != normalized_quotes:
        variants.append(no_comment_lines.strip())

    no_trailing_commas = re.sub(r",(\s*[}\]])", r"\1", no_comment_lines)
    if no_trailing_commas != no_comment_lines:
        variants.append(no_trailing_commas.strip())

    # Auto-repair missing commas between JSON properties across newlines
    missing_commas_fixed = re.sub(
        r'("(?:[^"\\]|\\.)*"|[0-9]+|true|false|null|\]|\})\s*\n\s*(")',
        r"\1,\n\2",
        no_trailing_commas,
        flags=re.IGNORECASE,
    )
    if missing_commas_fixed != no_trailing_commas:
        variants.append(missing_commas_fixed.strip())

    deduped: List[str] = []
    seen: set[str] = set()
    for item in variants:
        candidate = item.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        deduped.append(candidate)
    return deduped


def _parse_llm_json_payload(response_text: str) -> Dict[str, Any]:
    """Parse LLM JSON output with fence stripping and lightweight repair attempts."""
    stripped = _strip_markdown_fences(response_text)
    candidates: List[str] = [stripped]

    fragment = _extract_balanced_json_fragment(stripped)
    if fragment and fragment != stripped:
        candidates.append(fragment)

    last_error: Optional[Exception] = None
    for candidate in candidates:
        for variant in _json_normalization_variants(candidate):
            try:
                parsed = json.loads(variant, strict=False)
            except json.JSONDecodeError as exc:
                last_error = exc
                continue

            if not isinstance(parsed, dict):
                raise ValueError("Expected JSON object payload from LLM response")
            return cast(Dict[str, Any], parsed)

    if last_error is not None:
        raise last_error
    raise ValueError("Unable to parse JSON payload from LLM response")


def _normalize_serialized_lyric_text(value: str) -> str:
    """Convert JSON-like escape leakage into clean multiline lyric text."""
    normalized = value.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", " ")
    normalized = re.sub(r"\\([.,!?…])", r"\1", normalized)

    cleaned_lines: List[str] = []
    for line in normalized.splitlines():
        cleaned = re.sub(r'^\s*"', "", line)
        cleaned = re.sub(r'",?\s*$', "", cleaned)
        cleaned_lines.append(cleaned.rstrip())
    return "\n".join(cleaned_lines).strip()


def _normalize_lyric_payload(section_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize string fields and dictionary keys (lowercasing and key aliases)."""
    key_aliases = {
        "chorus_1": "chorus",
        "refrain": "chorus",
        "main_chorus": "chorus",
        "verse1": "verse_1",
        "verse2": "verse_2",
        "prechorus": "pre_chorus",
        "instrumental_build": "intro",
    }
    
    normalized: Dict[str, Any] = {}
    for key, value in section_payload.items():
        clean_key = str(key).strip().lower().replace(" ", "_")
        clean_key = key_aliases.get(clean_key, clean_key)
        normalized[clean_key] = (
            _normalize_serialized_lyric_text(value) if isinstance(value, str) else value
        )
    return normalized


def _has_prompt_schema_leakage(section_payload: Dict[str, Any]) -> bool:
    """Detect prompt instructions returned as lyric content by a small model."""
    leakage_markers = (
        r"\bCharacter Cap\s*:",
        r"\bon its own line\b",
        r"\bfollowed by\s+\d+",
        r"\btotal\)\s*\(Character Cap",
        r"\bTwo stanzas of\b",
        r"\b4-8 lines of\b",
    )
    combined = re.compile("|".join(leakage_markers), re.IGNORECASE)
    return any(
        isinstance(value, str) and combined.search(value)
        for value in section_payload.values()
    )
