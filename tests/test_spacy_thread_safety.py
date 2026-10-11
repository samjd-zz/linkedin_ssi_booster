"""Concurrency guard for shared spaCy pipelines (SudachiPy is not re-entrant)."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from services.spacy_nlp import _ThreadSafeNLP


class _NonReentrantNLP:
    """Mimics SudachiPy: raises if entered from two threads at once."""

    pipe_names = ["tok2vec"]

    def __init__(self) -> None:
        self._busy = threading.Lock()

    def _enter(self, text: str) -> str:
        if not self._busy.acquire(blocking=False):
            raise RuntimeError("Tokenizer is already in use")
        try:
            time.sleep(0.002)
            return text.upper()
        finally:
            self._busy.release()

    def __call__(self, text: str) -> str:
        return self._enter(text)

    def pipe(self, texts: Any, **_: Any) -> Any:
        for text in texts:
            yield self._enter(text)


def test_concurrent_calls_are_serialized() -> None:
    nlp = _ThreadSafeNLP(_NonReentrantNLP())
    texts = [f"t{i}" for i in range(40)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(nlp, texts))
    assert results == [t.upper() for t in texts]


def test_concurrent_pipe_is_serialized() -> None:
    nlp = _ThreadSafeNLP(_NonReentrantNLP())
    batches = [[f"b{i}-{j}" for j in range(5)] for i in range(10)]
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(nlp.pipe, batches))
    assert results == [[t.upper() for t in b] for b in batches]


def test_attribute_passthrough() -> None:
    assert _ThreadSafeNLP(_NonReentrantNLP()).pipe_names == ["tok2vec"]
