"""Intel runtime compatibility without losing JSON response contracts."""

from typing import Any, Literal
from unittest.mock import Mock

import pytest
from ollama import ChatResponse, Message, ResponseError

from services.ollama_service import OllamaService


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Mock:
    mock = Mock()
    mock.chat.return_value = ChatResponse(message=Message(
        role="assistant", content='{"post_1": "First post", "post_2": "Second post"}',
    ))
    monkeypatch.setattr("services.ollama_service.ollama.Client", Mock(return_value=mock))
    monkeypatch.delenv("OLLAMA_MODEL_FALLBACK", raising=False)
    monkeypatch.delenv("OLLAMA_STRUCTURED_OUTPUT", raising=False)
    return mock


@pytest.mark.parametrize("enabled", [None, "true", "false"])
@pytest.mark.parametrize("requested", ["json", {"type": "object"}, None])
def test_chat_respects_structured_output_policy(
    client: Mock, monkeypatch: pytest.MonkeyPatch, enabled: str | None,
    requested: Literal["json"] | dict[str, Any] | None,
) -> None:
    if enabled is not None:
        monkeypatch.setenv("OLLAMA_STRUCTURED_OUTPUT", enabled)
    ai = OllamaService(model="test-model")
    reply = ai._chat("Return JSON.", "Translate.", format=requested)
    assert reply.startswith("{")
    assert client.chat.call_args.kwargs["format"] == (
        None if enabled == "false" else requested
    )


def test_invalid_structured_output_setting_fails_fast(
    client: Mock, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OLLAMA_STRUCTURED_OUTPUT", "maybe")
    with pytest.raises(ValueError, match="OLLAMA_STRUCTURED_OUTPUT"):
        OllamaService(model="test-model")


@pytest.mark.parametrize("enabled", ["true", "false"])
def test_thread_preserves_json_contract_without_native_grammar(
    client: Mock, monkeypatch: pytest.MonkeyPatch, enabled: str,
) -> None:
    monkeypatch.setenv("OLLAMA_STRUCTURED_OUTPUT", enabled)
    ai = OllamaService(model="test-model")
    assert ai.generate_thread_posts("An article about retrieval. " * 10, "https://example.com") == [
        "First post", "Second post",
    ]
    kwargs = client.chat.call_args.kwargs
    assert (kwargs["format"] is None) == (enabled == "false")
    assert "JSON" in kwargs["messages"][1]["content"]


def test_fallback_model_also_avoids_native_grammar(
    client: Mock, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OLLAMA_STRUCTURED_OUTPUT", "false")
    monkeypatch.setenv("OLLAMA_MODEL_FALLBACK", "fallback-model")
    response = client.chat.return_value
    client.chat.side_effect = [ResponseError("runner stopped", status_code=500), response]
    ai = OllamaService(model="test-model")
    assert ai._chat("Return JSON.", "Translate.", format="json").startswith("{")
    assert [call.kwargs["model"] for call in client.chat.call_args_list] == [
        "test-model", "fallback-model",
    ]
    assert all(call.kwargs["format"] is None for call in client.chat.call_args_list)
