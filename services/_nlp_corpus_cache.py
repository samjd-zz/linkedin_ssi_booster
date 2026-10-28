"""Bounded, model-aware caches for repeatedly parsed NLP corpora."""

from collections import OrderedDict
from threading import RLock
from typing import Callable, Generic, Hashable, TypeVar

T = TypeVar("T")


class CorpusCache(Generic[T]):
    """Keep a few complete corpora; text/model changes naturally miss the cache."""

    def __init__(self, max_entries: int = 4, max_texts: int = 4096) -> None:
        self._entries: OrderedDict[tuple[Hashable, tuple[str, ...]], list[T]] = OrderedDict()
        self._max_entries = max_entries
        self._max_texts = max_texts
        self._lock = RLock()

    def get_or_build(
        self,
        model_key: Hashable,
        texts: list[str],
        build: Callable[[], list[T]],
    ) -> list[T]:
        key = (model_key, tuple(texts))
        with self._lock:
            if key in self._entries:
                self._entries.move_to_end(key)
                return self._entries[key]
            values = build()
            if len(values) == len(texts) and len(texts) <= self._max_texts:
                self._entries[key] = values
                while len(self._entries) > self._max_entries:
                    self._entries.popitem(last=False)
            return values
