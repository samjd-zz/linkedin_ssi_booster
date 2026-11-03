"""English-first bilingual lyrics: pick hook lines and translate them in one batch.

A small local model cannot reliably write a song, hit a Japanese-line ratio and
write correct Japanese in one pass. Instead the song is written in English,
code picks which lines become Japanese (so the ratio holds by construction),
and those lines are translated together in a single short Ollama call. Lines
the model gets wrong fall back to the offline Argos en→ja model; anything
still untranslated stays English. Each Japanese line is inserted above its
English line, which remains as the sung echo.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Tuple

from services.rei_toei._argos_fallback import get_argos_translator
from services.rei_toei._lyric_romaji import _JAPANESE_CHAR_RE
from services.rei_toei._suno_cleanup import has_chinese_grammar, replace_chinese_phrasing

if TYPE_CHECKING:
    from services.ollama_service import OllamaService

logger = logging.getLogger(__name__)

# Sections in the order they receive Japanese lines; the chorus hook comes first.
HOOK_SECTION_PRIORITY: Tuple[str, ...] = (
    "chorus", "verse_1", "verse_2", "bridge", "pre_chorus", "outro", "drop", "intro",
)
MIN_HOOK_WORDS = 2
MAX_HOOK_WORDS = 12
MAX_TRANSLATION_CHARS = 48
TOKENS_PER_TRANSLATED_LINE = 64
# Lines per Ollama translation call; smaller batches keep a 7B model aligned.
TRANSLATION_BATCH_SIZE = 10

_LATIN_RE = re.compile(r"[A-Za-z]")
_KANA_RE = re.compile(r"[\u3040-\u30ff\uff66-\uff9f]")
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_CHINESE_MARKER_RE = re.compile(r"[，的]")
# Untranslated English words inside Japanese ("周波数のswell"); acronyms like SQL are fine.
_LOWERCASE_WORD_RE = re.compile(r"[a-z]{2,}")
_NUMBER_PREFIX_RE = re.compile(r"^\s*\d+\s*[.):、]\s*")
_TRAILING_ANNOTATION_RE = re.compile(r"\s*(?:\[[^\[\]]*\]|[(（][^()（）]*[)）])\s*$")
_WRAPPING_QUOTES = "\"'“”‘’「」『』"
# Translators often answer in polite (-masu) form, which sounds stiff in lyrics.
_PLAIN_FORM_ENDINGS = (
    ("しています", "している"),
    ("ています", "ている"),
    ("しました", "した"),
    ("します", "する"),
    ("できます", "できる"),
    ("なります", "なる"),
    ("あります", "ある"),
    ("です", ""),
)
# e-row + ます is always an ichidan/potential verb (消えます → 消える); 死にます → 死ぬ.
_ICHIDAN_MASU_RE = re.compile(r"([えけげせぜてでねへべぺめれ])ます$")
_GODAN_MASU_ENDINGS = (("にます", "ぬ"), ("みます", "む"))

TRANSLATION_SYSTEM_PROMPT = (
    "You translate English song lyrics into natural, singable contemporary Japanese "
    "for a cyberpop vocalist. Translate the meaning and feeling, not word for word, "
    "and keep each line about as short as the English. Use standard Japanese kanji and "
    "kana with Japanese grammar and particles (が, を, に, の, へ). Never use Chinese "
    "characters, Chinese grammar (在, 了, 们), pinyin, Romaji, or explanations. "
    "Use plain (dictionary) verb forms such as 消える, not polite forms like 消えます, "
    "and translate every English word; do not leave English inside a Japanese line."
)


@dataclass(frozen=True)
class HookLine:
    """An English lyric line chosen to receive a Japanese translation above it."""

    field: str
    index: int
    text: str


def _is_candidate(line: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped[0] in "[(（":
        return False
    if _JAPANESE_CHAR_RE.search(stripped) or not _LATIN_RE.search(stripped):
        return False
    return MIN_HOOK_WORDS <= len(stripped.split()) <= MAX_HOOK_WORDS


def _sung_line_count(payload: Dict[str, Any]) -> int:
    count = 0
    for value in payload.values():
        if isinstance(value, str):
            count += sum(
                1 for line in value.splitlines()
                if line.strip() and line.strip()[0] not in "[(（"
            )
    return count


def japanese_line_target(sung_lines: int, ratio: float, max_lines: int) -> int:
    """Lines to translate so Japanese makes up ``ratio`` of sung lines after insertion."""
    if sung_lines <= 0 or ratio <= 0.0:
        return 0
    if ratio >= 1.0:
        return max_lines
    target = round(ratio * sung_lines / (1.0 - ratio))
    floor = 2 if sung_lines >= 8 else 1
    return max(floor, min(max_lines, target))


def _ordered_candidates(field: str, text: str) -> List[HookLine]:
    """Stanza openers first (alternating lines for the bridge), then the rest."""
    lines = text.splitlines()
    first: List[HookLine] = []
    rest: List[HookLine] = []
    previous_blank = True
    position = 0
    for index, line in enumerate(lines):
        if not line.strip():
            previous_blank = True
            continue
        if _is_candidate(line):
            hook = HookLine(field, index, line.strip())
            if field == "chorus":
                first.append(hook)
            elif field == "bridge":
                (first if position % 2 == 0 else rest).append(hook)
            else:
                (first if previous_blank else rest).append(hook)
            position += 1
        previous_blank = line.strip().startswith("[")
    return first + rest


def select_hook_lines(
    payload: Dict[str, Any], target_ratio: float, max_lines: int
) -> List[HookLine]:
    """Choose English lines to translate, spread across sections round-robin."""
    target = japanese_line_target(_sung_line_count(payload), target_ratio, max_lines)
    queues = [
        _ordered_candidates(field, payload[field])
        for field in HOOK_SECTION_PRIORITY
        if isinstance(payload.get(field), str)
    ]
    selected: List[HookLine] = []
    seen: set[str] = set()
    while len(selected) < target and any(queues):
        for queue in queues:
            while queue:
                hook = queue.pop(0)
                key = hook.text.casefold()
                if key not in seen:
                    seen.add(key)
                    selected.append(hook)
                    break
            if len(selected) >= target:
                break
    return selected


def _translation_source(text: str) -> str:
    """De-shout ALL-CAPS chorus lines so translators read them as normal text."""
    return text.capitalize() if text.isupper() else text


def to_plain_form(line: str) -> str:
    """Turn a common polite sentence ending into lyric-friendly plain form."""
    for polite, plain in _PLAIN_FORM_ENDINGS + _GODAN_MASU_ENDINGS:
        if line.endswith(polite) and len(line) > len(polite):
            return line[: -len(polite)] + plain
    if len(line) > 3:
        return _ICHIDAN_MASU_RE.sub(r"\1る", line)
    return line


def clean_translation(text: Any) -> Optional[str]:
    """Normalize one translated line; ``None`` if it is not usable Japanese."""
    if not isinstance(text, str) or not text.strip():
        return None
    line = text.strip().splitlines()[0]
    line = _NUMBER_PREFIX_RE.sub("", line)
    line = _TRAILING_ANNOTATION_RE.sub("", line).strip().rstrip("。.、，, ")
    line = line.strip(_WRAPPING_QUOTES).strip()
    line = to_plain_form(replace_chinese_phrasing(line).rstrip("。.、，, "))
    if not line or not _JAPANESE_CHAR_RE.search(line) or len(line) > MAX_TRANSLATION_CHARS:
        return None
    if _CHINESE_MARKER_RE.search(line) or has_chinese_grammar(line):
        return None
    if not _KANA_RE.search(line) and len(_CJK_RE.findall(line)) > 8:
        return None
    if _LOWERCASE_WORD_RE.search(line):
        return None
    return line


def build_translation_prompt(lines: Sequence[str], context: str = "") -> str:
    numbered = "\n".join(f"{i}. {_translation_source(line)}" for i, line in enumerate(lines, 1))
    about = f"Song context: {context}\n\n" if context else ""
    return (
        f"{about}Translate each numbered English lyric line into Japanese.\n"
        'Return only a JSON object mapping each line number to its Japanese line, '
        f'e.g. {{"1": "...", "2": "..."}}, with all {len(lines)} numbers.\n\n'
        f"{numbered}"
    )


def _extract_items(data: Any, expected: int) -> Optional[List[Any]]:
    """Return items aligned to line numbers; numbered keys allow partial replies."""
    if isinstance(data, dict):
        for key in ("translations", "lines", "japanese"):
            if isinstance(data.get(key), (list, dict)):
                return _extract_items(data[key], expected)
        numbered = {
            int(str(key).strip().rstrip(".")): value
            for key, value in data.items()
            if str(key).strip().rstrip(".").isdigit()
        }
        if numbered:
            return [numbered.get(number) for number in range(1, expected + 1)]
        return None
    if isinstance(data, list) and len(data) == expected:
        return data
    return None


def parse_batched_translations(text: str, expected: int) -> List[Optional[str]]:
    """Parse the batch reply; an unnumbered list with the wrong count is rejected."""
    empty: List[Optional[str]] = [None] * expected
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        match = re.search(r"\{.*\}|\[.*\]", text or "", re.DOTALL)
        if not match:
            return empty
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return empty
    items = _extract_items(data, expected)
    if items is None:
        return empty
    results: List[Optional[str]] = []
    for item in items:
        if isinstance(item, dict):
            item = item.get("ja") or item.get("japanese") or item.get("translation")
        results.append(clean_translation(item))
    return results


def translate_hook_texts(
    lines: Sequence[str],
    ollama: "OllamaService",
    argos_model_dir: Optional[Path] = None,
    context: str = "",
) -> Tuple[List[Optional[str]], Dict[str, int]]:
    """Translate lines in batched Ollama calls, then Argos for any that failed."""
    counts = {"ollama": 0, "argos": 0, "failed": 0}
    if not lines:
        return [], counts
    translations: List[Optional[str]] = []
    for start in range(0, len(lines), TRANSLATION_BATCH_SIZE):
        batch = list(lines[start:start + TRANSLATION_BATCH_SIZE])
        try:
            reply = ollama._chat(
                TRANSLATION_SYSTEM_PROMPT,
                build_translation_prompt(batch, context),
                max_tokens=TOKENS_PER_TRANSLATED_LINE * (len(batch) + 1),
                format="json",
            )
            translations.extend(parse_batched_translations(reply, len(batch)))
        except RuntimeError as exc:
            logger.warning(
                "Batched hook translation failed; skipping remaining Ollama batches "
                "and using Argos where available: %s", exc,
            )
            translations.extend([None] * (len(lines) - start))
            break
    counts["ollama"] = sum(1 for item in translations if item)

    missing = [i for i, item in enumerate(translations) if not item]
    if missing and argos_model_dir is not None:
        argos = get_argos_translator(argos_model_dir)
        if argos is not None:
            fallback = argos.translate([_translation_source(lines[i]) for i in missing])
            for i, raw in zip(missing, fallback):
                cleaned = clean_translation(raw)
                if cleaned:
                    translations[i] = cleaned
                    counts["argos"] += 1
    counts["failed"] = sum(1 for item in translations if not item)
    return translations, counts


def insert_hook_translations(
    payload: Dict[str, Any],
    hooks: Sequence[HookLine],
    translations: Sequence[Optional[str]],
) -> int:
    """Insert each Japanese line above its English line; returns lines inserted."""
    by_field: Dict[str, List[Tuple[int, str]]] = {}
    for hook, japanese in zip(hooks, translations):
        if japanese:
            by_field.setdefault(hook.field, []).append((hook.index, japanese))
    inserted = 0
    for field, items in by_field.items():
        lines = payload[field].splitlines()
        for index, japanese in sorted(items, reverse=True):
            indent = lines[index][: len(lines[index]) - len(lines[index].lstrip())]
            lines.insert(index, f"{indent}{japanese}")
            inserted += 1
        payload[field] = "\n".join(lines)
    return inserted


def apply_bilingual_hooks(
    payload: Dict[str, Any],
    target_ratio: float,
    ollama: "OllamaService",
    max_lines: int,
    argos_model_dir: Optional[Path] = None,
    context: str = "",
) -> Dict[str, int]:
    """Translate selected English lines in place and return a summary of sources."""
    hooks = select_hook_lines(payload, target_ratio, max_lines)
    translations, counts = translate_hook_texts(
        [hook.text for hook in hooks], ollama, argos_model_dir, context
    )
    inserted = insert_hook_translations(payload, hooks, translations)
    summary = {"selected": len(hooks), "inserted": inserted, **counts}
    logger.info(
        "Bilingual hooks: %d selected, %d inserted (ollama=%d, argos=%d, failed=%d).",
        summary["selected"], inserted, counts["ollama"], counts["argos"], counts["failed"],
    )
    return summary
