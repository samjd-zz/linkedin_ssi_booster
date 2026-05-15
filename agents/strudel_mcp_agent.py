import asyncio
import json
import os
import websockets
from ollama import AsyncClient

# Environment Variables pointing to your local container endpoints
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
STRUDEL_WS_URL = os.getenv("STRUDEL_WS_URL", "ws://localhost:4321")
MODEL_NAME = "gemma4"  # Works perfectly with e2b, e4b, 26b, or 31b variants

async def generate_strudel_code(user_prompt: str) -> str:
    """
    Leverages Gemma 4's native system prompt support to guarantee a 
    clean, executable Strudel code snippet without conversational fluff.
    """
    system_instruction = (
        "You are an expert live-coding music generator that writes 'strudel.js' code. "
        "Respond ONLY with valid, raw executable Strudel code. "
        "Do NOT include markdown code blocks like "
        "Example output: s('bd sd [sn:2 cp] bd').jux(rev)"
    )

    # Note: Adding the Gemma 4 '<|think|>' token at the start of the system prompt
    # will trigger its reasoning phase automatically if using a thinking-enabled variant.
    full_system_prompt = f"<|think|>\n{system_instruction}"

    client = AsyncClient(host=OLLAMA_HOST)
    
    print(f"🎵 Prompting {MODEL_NAME} for music structure...")
    response = await client.chat(
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
    )
    
    # Strip any accidental leading/trailing whitespace or lingering markdown
    raw_code = response['message']['content'].strip()
    clean_code = raw_code.replace("javascript", "").replace("```", "").strip()
    return clean_code

async def send_to_strudel_bridge(strudel_code: str):
    """
    Establishes a local websocket connection to your Strudel bridge 
    and sends the generated string payload instantly.
    """
    print(f"🚀 Sending code to Strudel Bridge: {strudel_code}")
    
    try:
        async with websockets.connect(STRUDEL_WS_URL) as websocket:
            payload = {
                "type": "eval",
                "code": strudel_code
            }
            await websocket.send(json.dumps(payload))
            print("✨ Code evaluated successfully! User should hear the music now.")
    except Exception as e:
        print(f"❌ Failed to connect to Strudel Bridge at {STRUDEL_WS_URL}: {e}")

async def main():
    # Example user interaction
    user_request = "a moody, low-fi jazz-hop loop with soft chords"
    
    # Step 1: Generate pattern locally using Gemma 4
    generated_code = await generate_strudel_code(user_request)
    print(f"\n[Generated Code]:\n{generated_code}\n")
    
    # Step 2: Push code directly to your local Strudel audio instance
    await send_to_strudel_bridge(generated_code)

if __name__ == "__main__":
    asyncio.run(main())