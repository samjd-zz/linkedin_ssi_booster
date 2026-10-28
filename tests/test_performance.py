"""Timing telemetry reports elapsed time and errors without disclosing prompts."""

import logging
from unittest.mock import Mock, patch

import pytest
from ollama import ChatResponse

from services.ollama_service import OllamaService
from services.performance import log_ollama_timings, timed_stage

LOGGER = logging.getLogger(__name__)


def test_stage_reports_measured_elapsed_time(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO), \
            patch("services.performance.perf_counter", side_effect=[10.0, 12.25]):
        with timed_stage(LOGGER, "test"):
            pass
    assert "stage=test elapsed_s=2.250 status=ok" in caplog.text
    assert [record.getMessage() for record in caplog.records] == [
        "▶️  Stage start stage=test",
        "✅ Stage end stage=test elapsed_s=2.250 status=ok",
    ]


def test_stage_propagates_errors(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO), \
            patch("services.performance.perf_counter", side_effect=[10.0, 10.5]):
        with pytest.raises(ValueError, match="bad config"):
            with timed_stage(LOGGER, "test"):
                raise ValueError("bad config")
    assert "stage=test elapsed_s=0.500 status=error" in caplog.text
    assert caplog.records[-1].getMessage() == "❌ Stage end stage=test elapsed_s=0.500 status=error"


def test_decorated_stages_measure_each_call(caplog: pytest.LogCaptureFixture) -> None:
    @timed_stage(LOGGER, "decorated")
    def identity(value: int) -> int:
        return value

    with caplog.at_level(logging.INFO), \
            patch("services.performance.perf_counter", side_effect=[1.0, 2.0, 3.0, 5.0]):
        assert identity(1) == 1
        assert identity(2) == 2
    assert "elapsed_s=1.000 status=ok" in caplog.text
    assert "elapsed_s=2.000 status=ok" in caplog.text


def test_ollama_nanosecond_metrics_are_seconds(caplog: pytest.LogCaptureFixture) -> None:
    response = ChatResponse(
        message={"role": "assistant", "content": "private output"},
        load_duration=2_000_000_000, prompt_eval_duration=3_000_000_000,
        eval_duration=7_000_000_000, total_duration=12_000_000_000,
        prompt_eval_count=100, eval_count=50,
    )
    for reason in ("stop", "length", "other"):
        response.done_reason = reason
        with caplog.at_level(logging.INFO):
            log_ollama_timings(LOGGER, "local-model", response)
        assert caplog.records[-1].getMessage().endswith(f"done_reason={reason}")
    assert "load_s=2.0 prompt_eval_s=3.0 generation_s=7.0 total_s=12.0" in caplog.text
    assert "prompt_tokens=100 generated_tokens=50" in caplog.text
    assert caplog.records[-1].getMessage().startswith("⏱️  Ollama timing model=local-model")
    assert "private output" not in caplog.text


def test_missing_ollama_metrics_are_explicit(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        log_ollama_timings(
            LOGGER, "local-model", ChatResponse(message={"role": "assistant", "content": ""}),
        )
    assert "load_s=None" in caplog.text
    assert "generated_tokens=None" in caplog.text
    assert "done_reason=None" in caplog.text


def test_chat_emits_wall_and_server_timings_without_content(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.delenv("OLLAMA_MODEL_FALLBACK", raising=False)
    ai = OllamaService.__new__(OllamaService)
    ai.model = "local-model"
    ai.think = False
    ai.num_ctx = 1024
    ai.base_url = "http://localhost:11434"
    ai.client = Mock()
    ai.client.chat.return_value = ChatResponse(
        message={"role": "assistant", "content": "private output"}, load_duration=0,
        done_reason="length",
    )
    with caplog.at_level(logging.INFO):
        assert ai._chat("private system", "private prompt") == "private output"
    assert "stage=ollama.chat" in caplog.text
    assert "Ollama timing model=local-model load_s=0.0" in caplog.text
    assert "done_reason=length" in caplog.text
    assert any(
        record.getMessage() == "🤖 Ollama request model=local-model max_tokens=1024"
        for record in caplog.records
    )
    assert "private" not in caplog.text
