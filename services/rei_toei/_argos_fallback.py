"""Offline English→Japanese fallback using the Argos Translate en→ja model.

The ``argostranslate`` package pulls in stanza and torch (several GB), so the
model is run directly with CTranslate2 + SentencePiece, which is all Argos
uses for inference. Download the model with ``scripts/download-argos-en-ja.sh``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

ARGOS_BEAM_SIZE = 4
ARGOS_MAX_DECODING_LENGTH = 64

_CACHE: dict[Path, Optional["ArgosTranslator"]] = {}


class ArgosTranslator:
    """Lazy CTranslate2 wrapper around an unpacked Argos ``translate-en_ja`` package."""

    def __init__(self, model_dir: Path) -> None:
        import ctranslate2
        import sentencepiece

        self.model_dir = model_dir
        self._tokenizer: Any = sentencepiece.SentencePieceProcessor(
            model_file=str(model_dir / "sentencepiece.model")
        )
        self._translator: Any = ctranslate2.Translator(
            str(model_dir / "model"), device="cpu", compute_type="int8"
        )

    def translate(self, lines: List[str]) -> List[Optional[str]]:
        """Translate each line; a failed batch yields ``None`` for every line."""
        if not lines:
            return []
        try:
            tokens = [self._tokenizer.encode(line, out_type=str) for line in lines]
            results = self._translator.translate_batch(
                tokens,
                beam_size=ARGOS_BEAM_SIZE,
                max_decoding_length=ARGOS_MAX_DECODING_LENGTH,
            )
            return [
                self._tokenizer.decode(result.hypotheses[0]).strip() or None
                for result in results
            ]
        except (RuntimeError, ValueError, IndexError) as exc:
            logger.warning("Argos translation failed: %s", exc)
            return [None] * len(lines)


def get_argos_translator(model_dir: Path) -> Optional[ArgosTranslator]:
    """Return a cached translator, or ``None`` when the model or runtime is missing."""
    model_dir = Path(model_dir)
    if model_dir in _CACHE:
        return _CACHE[model_dir]
    translator: Optional[ArgosTranslator] = None
    if not (model_dir / "model" / "model.bin").is_file():
        logger.info(
            "Argos en→ja model not found at %s; run scripts/download-argos-en-ja.sh "
            "to enable the offline translation fallback.",
            model_dir,
        )
    else:
        try:
            translator = ArgosTranslator(model_dir)
        except ImportError as exc:
            logger.info("Argos fallback unavailable (%s); install ctranslate2 and sentencepiece.", exc)
        except (RuntimeError, OSError, ValueError) as exc:
            logger.warning("Could not load Argos model from %s: %s", model_dir, exc)
    _CACHE[model_dir] = translator
    return translator
