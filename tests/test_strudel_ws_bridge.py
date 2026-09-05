import json

import pytest

from services.rei_toei import strudel_ws_bridge


@pytest.mark.asyncio
async def test_handle_message_rejects_invalid_json() -> None:
    response = json.loads(await strudel_ws_bridge._handle_message("not-json"))

    assert response["status"] == "error"
    assert response["error"].startswith("invalid_json:")


@pytest.mark.asyncio
async def test_handle_message_ping_returns_pong() -> None:
    response = json.loads(await strudel_ws_bridge._handle_message('{"type":"ping"}'))

    assert response == {"status": "ok", "type": "pong"}


@pytest.mark.asyncio
async def test_handle_message_rejects_missing_or_unsupported_type() -> None:
    missing = json.loads(await strudel_ws_bridge._handle_message("{}"))
    unsupported = json.loads(await strudel_ws_bridge._handle_message('{"type":"play"}'))

    assert missing == {"status": "error", "error": "unsupported_type: missing"}
    assert unsupported == {"status": "error", "error": "unsupported_type: play"}


@pytest.mark.asyncio
async def test_handle_message_rejects_blank_eval_code() -> None:
    response = json.loads(await strudel_ws_bridge._handle_message('{"type":"eval","code":"   "}'))

    assert response == {"status": "error", "error": "missing_code"}


@pytest.mark.asyncio
async def test_handle_message_eval_success(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_codes: list[str] = []

    def fake_send_to_strudel_mcp(code: str) -> bool:
        seen_codes.append(code)
        return True

    monkeypatch.setattr(strudel_ws_bridge, "send_to_strudel_mcp", fake_send_to_strudel_mcp)

    response = json.loads(
        await strudel_ws_bridge._handle_message(
            json.dumps(
                {
                    "type": "eval",
                    "code": "sound('bd*2')",
                    "metadata": {"song_id": "rei-1"},
                }
            )
        )
    )

    assert response["status"] == "ok"
    assert response["transport"] == "mcp-stdio"
    assert response["metadata"] == {"song_id": "rei-1"}
    assert isinstance(response["elapsed_ms"], int)
    assert seen_codes == ["sound('bd*2')"]


@pytest.mark.asyncio
async def test_handle_message_eval_reports_mcp_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(strudel_ws_bridge, "send_to_strudel_mcp", lambda code: False)

    response = json.loads(
        await strudel_ws_bridge._handle_message(
            json.dumps({"type": "eval", "code": "sound('bad')"})
        )
    )

    assert response["status"] == "error"
    assert response["error"] == "mcp_execution_failed"
    assert isinstance(response["elapsed_ms"], int)
