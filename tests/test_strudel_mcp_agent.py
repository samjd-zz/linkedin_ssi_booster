import asyncio
import json
import subprocess
from typing import Any, cast

import pytest

from agents import strudel_mcp_agent


class _FakeStdout:
    def __init__(self, lines: list[str]):
        self._lines = list(lines)

    def readline(self):
        if not self._lines:
            return ""
        return self._lines.pop(0)


class _FakeStdin:
    def __init__(self):
        self.lines: list[str] = []

    def write(self, data: str):
        self.lines.append(data)

    def flush(self):
        return None


class _FakeProc:
    def __init__(self):
        self.stdin = _FakeStdin()
        self.stdout = _FakeStdout([])
        self._terminated = False
        self.terminated = False
        self.killed = False

    def poll(self):
        return None if not self._terminated else 0

    def terminate(self):
        self.terminated = True
        self._terminated = True

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.killed = True
        self._terminated = True


def test_extract_tool_envelope_success() -> None:
    response = {
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({"isError": False, "result": {"ok": True}}),
                }
            ]
        }
    }
    envelope = strudel_mcp_agent._extract_tool_envelope(response)
    assert envelope == {"isError": False, "result": {"ok": True}}


def test_extract_tool_envelope_invalid_returns_none() -> None:
    response = {"result": {"content": [{"type": "text", "text": "not-json"}]}}
    assert strudel_mcp_agent._extract_tool_envelope(response) is None


def test_mcp_send_reads_response_line(monkeypatch: pytest.MonkeyPatch) -> None:
    proc = _FakeProc()
    proc.stdout = _FakeStdout(['{"jsonrpc":"2.0","id":1,"result":{"ok":true}}\n'])

    monkeypatch.setattr(strudel_mcp_agent.select, "select", lambda r, w, x, t: ([proc.stdout], [], []))

    payload = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    result = strudel_mcp_agent._mcp_send(cast(subprocess.Popen[Any], proc), payload)

    assert result == {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}
    assert proc.stdin.lines
    assert '"method": "initialize"' in proc.stdin.lines[0]


def test_run_strudel_mcp_health_check_success(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_proc = _FakeProc()

    monkeypatch.setattr(strudel_mcp_agent, "STRUDEL_MCP_COMMAND", "fake-mcp")
    monkeypatch.setattr(strudel_mcp_agent.subprocess, "Popen", lambda *a, **k: fake_proc)

    responses = [
        {"result": {"serverInfo": {"name": "ok"}}},
        {
            "result": {
                "tools": [
                    {"name": "init"},
                    {"name": "edit_pattern"},
                    {"name": "playback"},
                ]
            }
        },
    ]

    def _fake_send(proc, payload, timeout=20.0):
        return responses.pop(0)

    monkeypatch.setattr(strudel_mcp_agent, "_mcp_send", _fake_send)

    assert strudel_mcp_agent.run_strudel_mcp_health_check() is True
    assert fake_proc.terminated is True


def test_run_strudel_mcp_health_check_missing_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_proc = _FakeProc()

    monkeypatch.setattr(strudel_mcp_agent, "STRUDEL_MCP_COMMAND", "fake-mcp")
    monkeypatch.setattr(strudel_mcp_agent.subprocess, "Popen", lambda *a, **k: fake_proc)

    responses = [
        {"result": {"serverInfo": {"name": "ok"}}},
        {"result": {"tools": [{"name": "init"}, {"name": "playback"}]}}
    ]

    def _fake_send(proc, payload, timeout=20.0):
        return responses.pop(0)

    monkeypatch.setattr(strudel_mcp_agent, "_mcp_send", _fake_send)

    assert strudel_mcp_agent.run_strudel_mcp_health_check() is False
    assert fake_proc.terminated is True


def test_send_to_strudel_mcp_success(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_proc = _FakeProc()
    seen_payloads: list[dict] = []

    monkeypatch.setattr(strudel_mcp_agent, "STRUDEL_MCP_COMMAND", "fake-mcp")
    monkeypatch.setattr(strudel_mcp_agent.subprocess, "Popen", lambda *a, **k: fake_proc)

    responses = [
        {"result": {"serverInfo": {"name": "ok"}}},
        {"result": {"content": [{"type": "text", "text": json.dumps({"isError": False})}]}},
        {"result": {"content": [{"type": "text", "text": json.dumps({"isError": False})}]}},
        {"result": {"content": [{"type": "text", "text": json.dumps({"isError": False})}]}}
    ]

    def _fake_send(proc, payload, timeout=20.0):
        seen_payloads.append(payload)
        return responses.pop(0)

    monkeypatch.setattr(strudel_mcp_agent, "_mcp_send", _fake_send)

    ok = strudel_mcp_agent.send_to_strudel_mcp("s('bd sd').fast(2)")
    assert ok is True
    assert [p["id"] for p in seen_payloads] == [1, 2, 3, 4]
    assert seen_payloads[2]["params"]["name"] == "edit_pattern"
    assert fake_proc.terminated is True


def test_send_to_strudel_mcp_edit_pattern_tool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_proc = _FakeProc()

    monkeypatch.setattr(strudel_mcp_agent, "STRUDEL_MCP_COMMAND", "fake-mcp")
    monkeypatch.setattr(strudel_mcp_agent.subprocess, "Popen", lambda *a, **k: fake_proc)

    responses = [
        {"result": {"serverInfo": {"name": "ok"}}},
        {"result": {"content": [{"type": "text", "text": json.dumps({"isError": False})}]}},
        {"result": {"content": [{"type": "text", "text": json.dumps({"isError": True, "error": "bad pattern"})}]}}
    ]

    def _fake_send(proc, payload, timeout=20.0):
        return responses.pop(0)

    monkeypatch.setattr(strudel_mcp_agent, "_mcp_send", _fake_send)

    ok = strudel_mcp_agent.send_to_strudel_mcp("broken")
    assert ok is False
    assert fake_proc.terminated is True


def test_send_to_strudel_mcp_empty_command_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(strudel_mcp_agent, "STRUDEL_MCP_COMMAND", "")
    assert strudel_mcp_agent.send_to_strudel_mcp("s('bd')") is False


def test_generate_strudel_code_sanitizes_markdown(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Client:
        def __init__(self, host: str, timeout: float):
            self.host = host
            self.timeout = timeout

        async def chat(self, model, messages, options):
            return {"message": {"content": "```javascript\ns('bd sd')\n```"}}

    monkeypatch.setattr(strudel_mcp_agent, "AsyncClient", _Client)

    code = asyncio.run(strudel_mcp_agent.generate_strudel_code("beat"))
    assert code == "s('bd sd')"
