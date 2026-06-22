"""
Strudel MCP Agent - Fixed for Retry Safety

This agent provides Strudel pattern generation via websocket with proper:
- Health checks before attempting to connect
- Exponential backoff on connection failures
- No GPU hammering on repeated failures
- Graceful degradation when services are unavailable

Author: Shawn Jackson Dyck
Version: alpha-v0.0.2.7
"""

import asyncio
import json
import os
import logging
import sys
from typing import Optional
import websockets
from ollama import AsyncClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Environment Variables pointing to your local container endpoints
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
STRUDEL_WS_URL = os.getenv("STRUDEL_WS_URL", "ws://localhost:4321")
MODEL_NAME = os.getenv("OLLAMA_MODEL", "gemma4:e4b")

# Retry configuration
MAX_HEALTH_CHECK_RETRIES = 5
HEALTH_CHECK_TIMEOUT = 5.0
INITIAL_BACKOFF = 2.0  # seconds
MAX_BACKOFF = 30.0  # seconds


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
        "Example output: s('bd sd [sn:2 cp] bd').jux(rev)"
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


async def send_to_strudel_bridge(strudel_code: str) -> bool:
    """
    Establishes a websocket connection to the Strudel bridge 
    and sends the generated pattern code instantly.
    
    Args:
        strudel_code: The Strudel/Tidal Cycles pattern code to execute
        
    Returns:
        bool: True if send was successful, False otherwise
    """
    logger.info(f"🚀 Sending code to Strudel Bridge ({len(strudel_code)} chars)...")
    
    try:
        async with websockets.connect(STRUDEL_WS_URL, timeout=10) as websocket:
            payload = {
                "type": "eval",
                "code": strudel_code
            }
            await websocket.send(json.dumps(payload))
            logger.info("✨ Code sent successfully to Strudel Bridge")
            return True
            
    except Exception as e:
        logger.error(f"❌ Failed to connect to Strudel Bridge at {STRUDEL_WS_URL}: {e}")
        return False


async def main():
    """
    Main entry point with health checks and proper error handling.
    """
    logger.info("Starting Strudel MCP Agent...")
    logger.info(f"Ollama host: {OLLAMA_HOST}")
    logger.info(f"Strudel WebSocket: {STRUDEL_WS_URL}")
    logger.info(f"Model: {MODEL_NAME}")
    
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
    
    # Step 3: Push code directly to your local Strudel audio instance
    success = await send_to_strudel_bridge(strudel_code)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Agent interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)