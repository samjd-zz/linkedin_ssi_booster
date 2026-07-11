"""Strudel WebSocket bridge for containerized execution.

This bridge accepts WebSocket messages in the format:
  {"type": "eval", "code": "...", "metadata": {...}}

It forwards Strudel code to the MCP stdio flow and returns an acknowledgment.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict

import websockets

# Make absolute project imports work when launched as a file path.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.strudel_mcp_agent import send_to_strudel_mcp


logger = logging.getLogger(__name__)


def _json_response(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True)


async def _handle_message(raw_message: str) -> str:
    started = time.time()

    try:
        payload = json.loads(raw_message)
    except json.JSONDecodeError as exc:
        return _json_response({"status": "error", "error": f"invalid_json: {exc}"})

    msg_type = str(payload.get("type", "")).strip().lower()
    if msg_type == "ping":
        return _json_response({"status": "ok", "type": "pong"})

    if msg_type != "eval":
        return _json_response({"status": "error", "error": f"unsupported_type: {msg_type or 'missing'}"})

    code = payload.get("code")
    if not isinstance(code, str) or not code.strip():
        return _json_response({"status": "error", "error": "missing_code"})

    ok = await asyncio.to_thread(send_to_strudel_mcp, code)
    elapsed_ms = int((time.time() - started) * 1000)

    if not ok:
        return _json_response(
            {
                "status": "error",
                "error": "mcp_execution_failed",
                "elapsed_ms": elapsed_ms,
            }
        )

    return _json_response(
        {
            "status": "ok",
            "transport": "mcp-stdio",
            "elapsed_ms": elapsed_ms,
            "metadata": payload.get("metadata", {}),
        }
    )


async def _connection_handler(websocket: Any) -> None:
    peer = getattr(websocket, "remote_address", None)
    logger.info("Strudel WS bridge client connected: %s", peer)

    try:
        async for message in websocket:
            response = await _handle_message(message)
            await websocket.send(response)
    except websockets.ConnectionClosed:
        logger.info("Strudel WS bridge client disconnected: %s", peer)
    except Exception as exc:  # pragma: no cover
        logger.exception("Unhandled WS bridge error for client %s: %s", peer, exc)


async def main() -> None:
    host = os.getenv("STRUDEL_WS_BRIDGE_HOST", "0.0.0.0")
    port = int(os.getenv("STRUDEL_WS_BRIDGE_PORT", "4321"))

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    logger.info("Starting Strudel WS bridge on ws://%s:%s", host, port)
    logger.info("MCP command: %s", os.getenv("STRUDEL_MCP_COMMAND", "npx -y @williamzujkowski/live-coding-music-mcp"))

    async with websockets.serve(_connection_handler, host, port):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
