import asyncio
import json
import os
from typing import Optional
import requests
from ollama import AsyncClient

# Environment Variables pointing to your local container endpoints
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
BUFFER_MCP_URL = os.getenv("BUFFER_MCP_URL", "https://mcp.buffer.com/mcp")
BUFFER_API_KEY = os.getenv("BUFFER_API_KEY", "")
MODEL_NAME = "gemma4"  # Works perfectly with e2b, e4b, 26b, or 31b variants

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

    # Note: Adding the Gemma 4 '<|think|>' token at the start of the system prompt
    # will trigger its reasoning phase automatically if using a thinking-enabled variant.
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
            "temperature": 1.0,  # Standard recommended configuration for Gemma 4
            "top_p": 0.95,
            "top_k": 64
        }
    )
    
    # Strip any accidental leading/trailing whitespace or lingering markdown
    raw_json = response['message']['content'].strip()
    clean_json = raw_json.replace("json", "").replace("```", "").strip()
    
    try:
        return json.loads(clean_json)
    except json.JSONDecodeError as e:
        print(f"⚠️  Failed to parse JSON response: {e}")
        print(f"Raw response: {raw_json}")
        return {}

async def send_to_buffer_mcp(request: dict) -> Optional[dict]:
    """
    Sends the generated request payload to the Buffer MCP server
    and returns the response.
    """
    if not BUFFER_API_KEY:
        print("❌ BUFFER_API_KEY is not set. Please set it in your .env file.")
        return None
    
    print(f"🚀 Sending request to Buffer MCP: {json.dumps(request, indent=2)}")
    
    try:
        headers = {
            "Authorization": f"Bearer {BUFFER_API_KEY}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            BUFFER_MCP_URL,
            headers=headers,
            json=request,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✨ Request successful!")
            print(f"Response: {json.dumps(result, indent=2)}")
            return result
        else:
            print(f"❌ Request failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to connect to Buffer MCP at {BUFFER_MCP_URL}: {e}")
        return None

async def main():
    # Example user interactions
    examples = [
        "List all my connected Buffer channels",
        "Add a post to my Buffer queue that says 'Testing the Buffer MCP agent!' for tomorrow at 2pm",
        "Show me all my draft posts in Buffer"
    ]
    
    # Use the first example
    user_request = examples[0]
    
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
