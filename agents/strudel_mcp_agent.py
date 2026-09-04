"""
Strudel MCP Agent - Fixed for Retry Safety

This agent provides Strudel pattern generation via MCP stdio JSON-RPC with proper:
- Health checks before attempting to connect
- Exponential backoff on connection failures
- No GPU hammering on repeated failures
- Graceful degradation when services are unavailable

Author: Shawn Jackson Dyck
Version: alpha-v0.0.3.5
"""

import asyncio
import argparse
import json
import os
import logging
import sys
import shlex
import select
import subprocess
import time
import re
from typing import Optional, Dict, Any
from ollama import AsyncClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Environment Variables pointing to your local container endpoints
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL_NAME = os.getenv("OLLAMA_MODEL", "gemma4:e4b")
STRUDEL_MCP_COMMAND = os.getenv(
    "STRUDEL_MCP_COMMAND",
    "npx -y @williamzujkowski/live-coding-music-mcp"
)

# Retry configuration
MAX_HEALTH_CHECK_RETRIES = 5
HEALTH_CHECK_TIMEOUT = 5.0
INITIAL_BACKOFF = 2.0  # seconds
MAX_BACKOFF = 30.0  # seconds
MCP_PROTOCOL_VERSION = "2024-11-05"
REQUIRED_MCP_TOOLS = {"init", "edit_pattern", "playback"}
PLAYBACK_HOLD_SECONDS = float(os.getenv("STRUDEL_PLAYBACK_HOLD_SECONDS", "8"))
SHOW_BROWSER_WINDOW = os.getenv("STRUDEL_SHOW_BROWSER_WINDOW", "true").strip().lower() in {"1", "true", "yes", "on"}
WRITE_AUTO_PLAY = os.getenv("STRUDEL_WRITE_AUTO_PLAY", "true").strip().lower() in {"1", "true", "yes", "on"}
CALL_PLAYBACK_AFTER_WRITE = os.getenv("STRUDEL_CALL_PLAYBACK_AFTER_WRITE", "false").strip().lower() in {"1", "true", "yes", "on"}


async def check_ollama_health(retries: int = MAX_HEALTH_CHECK_RETRIES) -> bool:
    """
    Check if Ollama is ready by attempting a simple health check.
    Uses exponential backoff to avoid hammering the GPU.
    
    Args:
        retries: Number of retry attempts before giving up
        
    Returns:
        bool: True if Ollama is healthy, False otherwise
    """
    backoff = INITIAL_BACKOFF
    
    for attempt in range(retries):
        try:
            logger.info(f"Checking Ollama health (attempt {attempt + 1}/{retries})...")
            
            # Try a minimal health check by pulling model info
            client = AsyncClient(host=OLLAMA_HOST, timeout=HEALTH_CHECK_TIMEOUT)
            # Minimal operation to check connection
            response = await asyncio.wait_for(
                client.list(),
                timeout=HEALTH_CHECK_TIMEOUT
            )
            
            logger.info(f"✅ Ollama is healthy and ready")
            return True
            
        except asyncio.TimeoutError:
            logger.warning(f"Ollama health check timed out (attempt {attempt + 1}/{retries})")
            
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e} (attempt {attempt + 1}/{retries})")
        
        # Don't backoff on the last attempt
        if attempt < retries - 1:
            logger.info(f"Waiting {backoff:.1f}s before retry...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF)  # Exponential backoff with cap
    
    logger.error("❌ Ollama is not responding after all retries - giving up")
    return False


async def generate_strudel_code(user_prompt: str) -> Optional[str]:
    """
    Leverages Gemma 4's native system prompt support to guarantee a 
    clean, executable Strudel code snippet without conversational fluff.
    
    Args:
        user_prompt: The music generation prompt
        
    Returns:
        Optional[str]: Generated Strudel code, or None if generation failed
    """
    system_instruction = (
        "You are an expert live-coding music generator that writes 'strudel.js' code. "
        "Respond ONLY with valid, raw executable Strudel code. "
        "Do NOT include markdown code blocks. "
        "Example output: sound('bd sd hh sd')"
    )

    # Note: Adding the Gemma 4 '<|think|>' token at the start of the system prompt
    # will trigger its reasoning phase automatically if using a thinking-enabled variant.
    full_system_prompt = f"<|think|>\n{system_instruction}"

    try:
        logger.info(f"🎵 Prompting {MODEL_NAME} for music structure...")
        
        client = AsyncClient(host=OLLAMA_HOST, timeout=30.0)
        
        response = await asyncio.wait_for(
            client.chat(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": full_system_prompt},
                    {"role": "user", "content": f"Create a short loop based on this vibe: {user_prompt}"}
                ],
                options={
                    "temperature": 1.0,  # Standard recommended configuration for Gemma 4
                    "top_p": 0.95,
                    "top_k": 64
                }
            ),
            timeout=30.0
        )
        
        # Strip any accidental leading/trailing whitespace or lingering markdown
        raw_code = response['message']['content'].strip()
        clean_code = raw_code.replace("javascript", "").replace("```", "").strip()
        
        logger.info(f"✅ Generated Strudel code ({len(clean_code)} chars)")
        return clean_code
        
    except asyncio.TimeoutError:
        logger.error("❌ Strudel code generation timed out (30s)")
        return None
    except Exception as e:
        logger.error(f"❌ Failed to generate Strudel code: {e}")
        return None


def _mcp_send(proc: subprocess.Popen, payload: Dict[str, Any], timeout: float = 20.0) -> Optional[Dict[str, Any]]:
    """Send one JSON-RPC request line and read one JSON-RPC response line."""
    if proc.stdin is None or proc.stdout is None:
        return None

    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()

    ready, _, _ = select.select([proc.stdout], [], [], timeout)
    if not ready:
        return None

    line = proc.stdout.readline()
    if not line:
        return None

    try:
        return json.loads(line.strip())
    except json.JSONDecodeError:
        logger.error("❌ MCP server returned non-JSON response: %s", line[:200])
        return None


def _extract_tool_envelope(response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract wrapped envelope JSON from MCP tools/call response content text."""
    try:
        content = response.get("result", {}).get("content", [])
        if not content:
            return None
        text = content[0].get("text", "")
        if not text:
            return None
        return json.loads(text)
    except Exception:
        return None


def _contains_legacy_alias_syntax(strudel_code: str) -> bool:
    """Return True when deprecated legacy aliases are present."""
    return bool(re.search(r"(^|\n)\s*s\(", strudel_code) or ".s(" in strudel_code)


def run_strudel_mcp_health_check() -> bool:
    """Run a fast MCP diagnostic: initialize -> tools/list -> required tools check."""
    logger.info("🏥 Running Strudel MCP health check (initialize + tools/list)...")

    cmd = shlex.split(STRUDEL_MCP_COMMAND)
    if not cmd:
        logger.error("❌ STRUDEL_MCP_COMMAND is empty")
        return False

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=None,
        text=True,
        bufsize=1,
    )

    try:
        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "linkedin-ssi-booster-strudel-health", "version": "0.0.2.7"},
            },
        }
        init_resp = _mcp_send(proc, init_payload, timeout=10.0)
        if not init_resp or "error" in init_resp:
            logger.error("❌ MCP initialize failed during health check: %s", init_resp)
            return False

        list_payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        list_resp = _mcp_send(proc, list_payload, timeout=10.0)
        if not list_resp or "error" in list_resp:
            logger.error("❌ MCP tools/list failed during health check: %s", list_resp)
            return False

        tools = list_resp.get("result", {}).get("tools", [])
        tool_names = {tool.get("name", "") for tool in tools if isinstance(tool, dict)}
        missing = sorted(REQUIRED_MCP_TOOLS - tool_names)
        if missing:
            logger.error("❌ MCP health check failed, missing required tools: %s", ", ".join(missing))
            return False

        logger.info("✅ MCP health check passed (%d tools discovered)", len(tool_names))
        return True
    except Exception as e:
        logger.error("❌ MCP health check failed with exception: %s", e)
        return False
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


def send_to_strudel_mcp(strudel_code: str) -> bool:
    """Launch Strudel MCP server via stdio and call tools over JSON-RPC."""
    code = strudel_code.strip()
    if _contains_legacy_alias_syntax(code):
        logger.error("❌ Legacy Strudel aliases are not supported. Use sound(...) and .sound(...), not s(...) or .s(...)")
        return False

    logger.info("🚀 Sending code to Strudel MCP via JSON-RPC stdio (%d chars)...", len(code))

    cmd = shlex.split(STRUDEL_MCP_COMMAND)
    if not cmd:
        logger.error("❌ STRUDEL_MCP_COMMAND is empty")
        return False

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=None,
        text=True,
        bufsize=1,
    )

    try:
        # 1) MCP initialize handshake
        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "linkedin-ssi-booster-strudel-agent", "version": "0.0.2.7"},
            },
        }
        init_resp = _mcp_send(proc, init_payload)
        if not init_resp or "error" in init_resp:
            logger.error("❌ MCP initialize failed: %s", init_resp)
            return False

        # 2) Initialize browser/session in Strudel toolchain
        init_tool_payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "init", "arguments": {}},
        }
        tool_init_resp = _mcp_send(proc, init_tool_payload, timeout=60.0)
        if not tool_init_resp or "error" in tool_init_resp:
            logger.error("❌ tools/call init failed: %s", tool_init_resp)
            return False

        init_envelope = _extract_tool_envelope(tool_init_resp)
        if init_envelope and init_envelope.get("isError"):
            logger.error("❌ init returned tool error: %s", init_envelope)
            return False

        # Some Linux/Playwright environments need the browser window foregrounded
        # once so the first audio context gesture is established reliably.
        if SHOW_BROWSER_WINDOW:
            show_payload = {
                "jsonrpc": "2.0",
                "id": 21,
                "method": "tools/call",
                "params": {
                    "name": "browser_window",
                    "arguments": {"action": "show"},
                },
            }
            show_resp = _mcp_send(proc, show_payload, timeout=20.0)
            if not show_resp or "error" in show_resp:
                logger.warning("⚠️ browser_window show unavailable or failed: %s", show_resp)

        # 3) Write generated pattern into editor
        write_payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "edit_pattern",
                "arguments": {"mode": "write", "pattern": code},
            },
        }
        write_payload["params"]["arguments"]["auto_play"] = WRITE_AUTO_PLAY
        write_resp = _mcp_send(proc, write_payload, timeout=60.0)
        if not write_resp or "error" in write_resp:
            logger.error("❌ tools/call edit_pattern failed: %s", write_resp)
            return False

        envelope = _extract_tool_envelope(write_resp)
        if envelope and envelope.get("isError"):
            logger.error("❌ edit_pattern returned tool error: %s", envelope)
            return False

        # 4) Optionally call transport play after write.
        # Some Strudel sessions can toggle/interrupt when both auto_play and explicit play are used.
        if CALL_PLAYBACK_AFTER_WRITE:
            play_payload = {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "playback", "arguments": {"action": "play"}},
            }
            play_resp = _mcp_send(proc, play_payload, timeout=60.0)
            if not play_resp or "error" in play_resp:
                logger.error("❌ tools/call playback failed: %s", play_resp)
                return False

            play_envelope = _extract_tool_envelope(play_resp)
            if play_envelope and play_envelope.get("isError"):
                logger.error("❌ playback returned tool error: %s", play_envelope)
                return False
        else:
            logger.info("▶️ Skipping explicit playback call; relying on edit_pattern(auto_play=%s)", WRITE_AUTO_PLAY)

        # Keep process alive briefly so container audio output is actually audible.
        if PLAYBACK_HOLD_SECONDS > 0:
            logger.info("🔊 Holding playback for %.1fs before teardown", PLAYBACK_HOLD_SECONDS)
            time.sleep(PLAYBACK_HOLD_SECONDS)

        logger.info("✨ Code sent successfully to Strudel MCP")
        return True
    except Exception as e:
        logger.error("❌ Failed to execute Strudel MCP flow: %s", e)
        return False
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


async def main(health_check_only: bool = False):
    """
    Main entry point with health checks and proper error handling.
    """
    logger.info("Starting Strudel MCP Agent...")
    logger.info(f"Ollama host: {OLLAMA_HOST}")
    logger.info(f"Strudel MCP command: {STRUDEL_MCP_COMMAND}")
    logger.info(f"Model: {MODEL_NAME}")

    if health_check_only:
        success = await asyncio.to_thread(run_strudel_mcp_health_check)
        sys.exit(0 if success else 1)
    
    # Step 1: Check if Ollama is ready (with backoff)
    if not await check_ollama_health():
        logger.error("Cannot start: Ollama is not available")
        sys.exit(1)
    
    # Step 2: Generate pattern locally using Gemma 4
    user_request = os.getenv("STRUDEL_PROMPT", "a moody, low-fi jazz-hop loop with soft chords")
    
    strudel_code = await generate_strudel_code(user_request)
    if not strudel_code:
        logger.error("Cannot start: Failed to generate Strudel code")
        sys.exit(1)
    
    logger.info(f"\n[Generated Code]:\n{strudel_code}\n")
    
    # Step 3: Push code to Strudel MCP (JSON-RPC over stdio)
    success = await asyncio.to_thread(send_to_strudel_mcp, strudel_code)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Strudel MCP agent")
    parser.add_argument(
        "--health-check",
        action="store_true",
        help="Run MCP initialize + tools/list diagnostics and exit"
    )
    args = parser.parse_args()

    try:
        asyncio.run(main(health_check_only=args.health_check))
    except KeyboardInterrupt:
        logger.info("Agent interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)