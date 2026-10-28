"""Content-free wall-clock and Ollama server timing logs."""

import logging
from contextlib import contextmanager
from time import perf_counter
from typing import Iterator

from ollama import ChatResponse


@contextmanager
def timed_stage(logger: logging.Logger, stage: str) -> Iterator[None]:
    """Measure a stage without swallowing errors or logging user content."""
    started = perf_counter()
    status = "error"
    logger.info("Stage start stage=%s", stage)
    try:
        yield
        status = "ok"
    finally:
        logger.info(
            "Stage end stage=%s elapsed_s=%.3f status=%s",
            stage, perf_counter() - started, status,
        )


def _seconds(duration_ns: int | None) -> float | None:
    return round(duration_ns / 1_000_000_000, 3) if duration_ns is not None else None


def log_ollama_timings(logger: logging.Logger, model: str, response: ChatResponse) -> None:
    """Report server timings separately from client wall time; missing values stay None."""
    logger.info(
        "Ollama timing model=%s load_s=%s prompt_eval_s=%s generation_s=%s "
        "total_s=%s prompt_tokens=%s generated_tokens=%s",
        model, _seconds(response.load_duration), _seconds(response.prompt_eval_duration),
        _seconds(response.eval_duration), _seconds(response.total_duration),
        response.prompt_eval_count, response.eval_count,
    )
