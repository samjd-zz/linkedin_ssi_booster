import asyncio

import pytest

from agents import buffer_mcp_agent


class _FakeOllamaClient:
    def __init__(self, host: str, timeout: float):
        self.host = host
        self.timeout = timeout

    async def list(self):
        return {"models": []}


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class _FakeAsyncHttpClient:
    def __init__(self, responses: list[_FakeResponse], sink: list[dict]):
        self._responses = responses
        self._sink = sink

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, headers, json):
        self._sink.append({"url": url, "headers": headers, "json": json})
        return self._responses.pop(0)


def test_check_ollama_health_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(buffer_mcp_agent, "AsyncClient", _FakeOllamaClient)

    ok = asyncio.run(buffer_mcp_agent.check_ollama_health(retries=1))
    assert ok is True


def test_check_ollama_health_retries_and_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FailingClient:
        def __init__(self, host: str, timeout: float):
            self.host = host
            self.timeout = timeout

        async def list(self):
            raise RuntimeError("down")

    sleeps: list[float] = []

    async def _fake_sleep(seconds: float):
        sleeps.append(seconds)

    monkeypatch.setattr(buffer_mcp_agent, "AsyncClient", _FailingClient)
    monkeypatch.setattr(buffer_mcp_agent.asyncio, "sleep", _fake_sleep)

    ok = asyncio.run(buffer_mcp_agent.check_ollama_health(retries=3))
    assert ok is False
    assert sleeps == [2.0, 4.0]


def test_generate_buffer_request_parses_clean_json(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Client:
        def __init__(self, host: str, timeout: float):
            self.host = host
            self.timeout = timeout

        async def chat(self, model, messages, options):
            return {
                "message": {
                    "content": "```json\n{\"method\":\"list_channels\",\"params\":{}}\n```"
                }
            }

    monkeypatch.setattr(buffer_mcp_agent, "AsyncClient", _Client)

    payload = asyncio.run(buffer_mcp_agent.generate_buffer_request("list channels"))
    assert payload == {"method": "list_channels", "params": {}}


def test_generate_buffer_request_invalid_json_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Client:
        def __init__(self, host: str, timeout: float):
            self.host = host
            self.timeout = timeout

        async def chat(self, model, messages, options):
            return {"message": {"content": "not json"}}

    monkeypatch.setattr(buffer_mcp_agent, "AsyncClient", _Client)

    payload = asyncio.run(buffer_mcp_agent.generate_buffer_request("invalid"))
    assert payload is None


def test_send_to_buffer_mcp_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(buffer_mcp_agent, "BUFFER_API_KEY", "")

    result = asyncio.run(buffer_mcp_agent.send_to_buffer_mcp({"method": "list_channels", "params": {}}))
    assert result is None


def test_send_to_buffer_mcp_initializes_and_wraps_tool_call(monkeypatch: pytest.MonkeyPatch) -> None:
    requests_seen: list[dict] = []
    responses = [
        _FakeResponse(200, {"result": {"ok": True}}),
        _FakeResponse(200, {"result": {"ok": True, "type": "tool_result"}}),
    ]

    def _client_factory(timeout: float):
        return _FakeAsyncHttpClient(responses, requests_seen)

    monkeypatch.setattr(buffer_mcp_agent, "BUFFER_API_KEY", "token")
    monkeypatch.setattr(buffer_mcp_agent.httpx, "AsyncClient", _client_factory)

    result = asyncio.run(
        buffer_mcp_agent.send_to_buffer_mcp({"method": "create_post", "params": {"text": "hello"}})
    )

    assert result == {"result": {"ok": True, "type": "tool_result"}}
    assert len(requests_seen) == 2
    assert requests_seen[0]["json"]["method"] == "initialize"
    assert requests_seen[1]["json"]["method"] == "tools/call"
    assert requests_seen[1]["json"]["params"]["name"] == "create_post"
    assert requests_seen[1]["json"]["params"]["arguments"] == {"text": "hello"}


def test_send_to_buffer_mcp_passes_through_jsonrpc_request(monkeypatch: pytest.MonkeyPatch) -> None:
    requests_seen: list[dict] = []
    responses = [
        _FakeResponse(200, {"result": {"ok": True}}),
        _FakeResponse(200, {"result": {"ok": True, "passthrough": True}}),
    ]

    def _client_factory(timeout: float):
        return _FakeAsyncHttpClient(responses, requests_seen)

    monkeypatch.setattr(buffer_mcp_agent, "BUFFER_API_KEY", "token")
    monkeypatch.setattr(buffer_mcp_agent.httpx, "AsyncClient", _client_factory)

    direct_payload = {"jsonrpc": "2.0", "id": 77, "method": "tools/call", "params": {"name": "list_channels"}}
    result = asyncio.run(buffer_mcp_agent.send_to_buffer_mcp(direct_payload))

    assert result == {"result": {"ok": True, "passthrough": True}}
    assert requests_seen[1]["json"] == direct_payload


def test_send_to_buffer_mcp_init_failure_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    requests_seen: list[dict] = []
    responses = [_FakeResponse(500, {}, text="fail")]

    def _client_factory(timeout: float):
        return _FakeAsyncHttpClient(responses, requests_seen)

    monkeypatch.setattr(buffer_mcp_agent, "BUFFER_API_KEY", "token")
    monkeypatch.setattr(buffer_mcp_agent.httpx, "AsyncClient", _client_factory)

    result = asyncio.run(buffer_mcp_agent.send_to_buffer_mcp({"method": "list_channels", "params": {}}))
    assert result is None
    assert len(requests_seen) == 1
