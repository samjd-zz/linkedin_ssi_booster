import asyncio
import json
import os
from typing import Optional, Dict
import httpx  # Switched to httpx for non-blocking async calls
from ollama import AsyncClient

# Environment Variables pointing to your local container endpoints
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
BUFFER_MCP_URL = os.getenv("BUFFER_MCP_URL", "https://mcp.buffer.com/mcp")
BUFFER_API_KEY = os.getenv("BUFFER_API_KEY", "")
MODEL_NAME = "gemma4"  # Optimized for thinking-enabled variants

async def generate_buffer_request(user_prompt: str) -> dict:
    """
    Leverages Gemma 4's native system prompt support to generate a 
    clean, structured Buffer MCP request without conversational fluff.
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

    client = AsyncClient(host=OLLAMA_HOST)
    
    print(f"🎯 Prompting {MODEL_NAME} for Buffer MCP request...")
    response = await client.chat(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": full_system_prompt},
            {"role": "user", "content": f"Create a Buffer MCP request for this action: {user_prompt}"}
        ],
        options={
            "temperature": 1.0,
            "top_p": 0.95,
            "top_k": 64
        }
    )
    
    raw_content = response['message']['content'].strip()
    # Clean up any potential markdown formatting from the LLM
    clean_json = raw_content.replace("```json", "").replace("```", "").strip()
    
    try:
        return json.loads(clean_json)
    except json.JSONDecodeError as e:
        print(f"⚠️ Failed to parse JSON response: {e}")
        print(f"Raw response: {raw_content}")
        return {}

async def send_to_buffer_mcp(request: dict) -> Optional[dict]:
    """
    Sends the generated request payload to the Buffer MCP server
    using httpx to maintain an asynchronous workflow.
    """
    if not BUFFER_API_KEY:
        print("❌ BUFFER_API_KEY is not set. Please set it in your .env file.")
        return None
    
    print(f"🚀 Sending request to Buffer MCP: {json.dumps(request, indent=2)}")
    
    # Explicitly type-hinting headers to satisfy Pylance/Type Checkers
    headers: Dict[str, str] = {
        "Authorization": f"Bearer {BUFFER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                BUFFER_MCP_URL,
                headers=headers,
                json=request,
                timeout=30.0
            )
        
        if response.status_code == 200:
            result = response.json()
            print("✨ Request successful!")
            return result
        else:
            print(f"❌ Request failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except httpx.RequestError as e:
        print(f"❌ Failed to connect to Buffer MCP at {BUFFER_MCP_URL}: {e}")
        return None

async def main():
    # Example user interaction
    user_request = "List all my connected Buffer channels"
    
    # Step 1: Generate MCP request locally using Gemma 4
    generated_request = await generate_buffer_request(user_request)
    
    if not generated_request:
        print("❌ Failed to generate a valid Buffer MCP request")
        return
    
    print(f"\n[Generated Request]:\n{json.dumps(generated_request, indent=2)}\n")
    
    # Step 2: Send request to Buffer MCP server
    response = await send_to_buffer_mcp(generated_request)
    
    if response:
        print(f"\n[Final Response]:\n{json.dumps(response, indent=2)}\n")

if __name__ == "__main__":
    asyncio.run(main())