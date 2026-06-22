"""
Buffer MCP Agent - Fixed for Retry Safety

This agent provides Buffer API request generation via Ollama with proper:
- Health checks before attempting to connect to Ollama
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
from typing import Optional, Dict
import httpx  # Async HTTP client for Buffer MCP server calls
from ollama import AsyncClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Environment Variables pointing to your local/remote endpoints
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
BUFFER_MCP_URL = os.getenv("BUFFER_MCP_URL", "https://mcp.buffer.com/mcp")
BUFFER_API_KEY = os.getenv("BUFFER_API_KEY", "")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e4b")

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
            
            # Try a minimal health check by listing available models
            client = AsyncClient(host=OLLAMA_HOST, timeout=HEALTH_CHECK_TIMEOUT)
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


async def generate_buffer_request(user_prompt: str) -> Optional[Dict]:
    """
    Leverages Gemma 4's native system prompt support to generate a 
    clean, structured Buffer MCP request without conversational fluff.
    
    Args:
        user_prompt: The Buffer API action to perform
        
    Returns:
        Optional[Dict]: Generated request dict, or None if generation failed
    """
    system_instruction = (
        "You are an expert at creating Buffer API requests via the MCP protocol. "
        "Respond ONLY with valid JSON that can be sent to the Buffer MCP server. "
        "The JSON should have a 'method' field (e.g., 'list_channels', 'create_post', 'list_drafts') "
        "and a 'params' field with the necessary parameters. "
        "Do NOT include markdown code blocks or explanatory text. "
        "Example output: {\"method\": \"create_post\", \"params\": {\"text\": \"Hello world\", \"channel_id\": \"123\"}}"
    )

    # Triggering the reasoning phase for Gemma 4
    full_system_prompt = f"<|think|>\n{system_instruction}"

    try:
        logger.info(f"🎯 Prompting {OLLAMA_MODEL} for Buffer MCP request...")
        
        client = AsyncClient(host=OLLAMA_HOST, timeout=30.0)
        
        response = await asyncio.wait_for(
            client.chat(
                model=OLLAMA_MODEL,
                messages=[
                    {"role": "system", "content": full_system_prompt},
                    {"role": "user", "content": f"Create a Buffer MCP request for this action: {user_prompt}"}
                ],
                options={
                    "temperature": 1.0,
                    "top_p": 0.95,
                    "top_k": 64
                }
            ),
            timeout=30.0
        )
        
        raw_content = response['message']['content'].strip()
        # Clean up any potential markdown formatting from the LLM
        clean_json = raw_content.replace("```json", "").replace("```", "").strip()
        
        try:
            result = json.loads(clean_json)
            logger.info(f"✅ Generated Buffer request ({len(json.dumps(result))} chars)")
            return result
        except json.JSONDecodeError as e:
            logger.error(f"⚠️ Failed to parse JSON response: {e}")
            logger.debug(f"Raw response: {raw_content}")
            return None
            
    except asyncio.TimeoutError:
        logger.error("❌ Buffer request generation timed out (30s)")
        return None
    except Exception as e:
        logger.error(f"❌ Failed to generate Buffer request: {e}")
        return None


async def send_to_buffer_mcp(request: Dict) -> Optional[Dict]:
    """
    Sends the generated request payload to the Buffer MCP server
    using httpx to maintain an asynchronous workflow.
    
    Args:
        request: The Buffer API request dict to send
        
    Returns:
        Optional[Dict]: Response from Buffer MCP, or None if send failed
    """
    if not BUFFER_API_KEY:
        logger.error("❌ BUFFER_API_KEY is not set. Please set it in your .env file.")
        return None
    
    logger.info(f"🚀 Sending request to Buffer MCP: {json.dumps(request, indent=2)}")
    
    # Explicitly type-hinting headers to satisfy type checkers
    headers: Dict[str, str] = {
        "Authorization": f"Bearer {BUFFER_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                BUFFER_MCP_URL,
                headers=headers,
                json=request
            )
        
        if response.status_code == 200:
            result = response.json()
            logger.info("✨ Request successful!")
            return result
        else:
            logger.error(f"❌ Request failed with status {response.status_code}")
            logger.debug(f"Response: {response.text}")
            return None
            
    except httpx.TimeoutException:
        logger.error(f"❌ Buffer MCP request timed out (15s) at {BUFFER_MCP_URL}")
        return None
    except httpx.RequestError as e:
        logger.error(f"❌ Failed to connect to Buffer MCP at {BUFFER_MCP_URL}: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected error sending to Buffer MCP: {e}")
        return None


async def main():
    """
    Main entry point with health checks and proper error handling.
    """
    logger.info("Starting Buffer MCP Agent...")
    logger.info(f"Ollama host: {OLLAMA_HOST}")
    logger.info(f"Buffer MCP URL: {BUFFER_MCP_URL}")
    logger.info(f"Model: {OLLAMA_MODEL}")
    
    # Step 1: Check if Ollama is ready (with backoff)
    if not await check_ollama_health():
        logger.error("Cannot start: Ollama is not available")
        sys.exit(1)
    
    # Step 2: Generate request locally using Gemma 4
    user_request = os.getenv("BUFFER_PROMPT", "List all my connected Buffer channels")
    
    generated_request = await generate_buffer_request(user_request)
    if not generated_request:
        logger.error("Cannot start: Failed to generate Buffer request")
        sys.exit(1)
    
    logger.info(f"\n[Generated Request]:\n{json.dumps(generated_request, indent=2)}\n")
    
    # Step 3: Send request to Buffer MCP server
    response = await send_to_buffer_mcp(generated_request)
    
    if response:
        logger.info(f"\n[Final Response]:\n{json.dumps(response, indent=2)}\n")
        sys.exit(0)
    else:
        logger.error("Failed to send request to Buffer MCP")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Agent interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)