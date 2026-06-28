"""
Suno HTTP Client Functions

This module provides async HTTP client functions for interacting with the Suno API.

Author: Shawn Jackson Dyck
Version: alpha-v0.0.2.7
"""

import logging
import os
from typing import Any, Dict, List, Optional

from ._models import SunoGenerateRequest, SunoTask

logger = logging.getLogger(__name__)


async def generate_music_api(
    title: str,
    tags: str,
    prompt: str,
    lyrics: Optional[str] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Call Suno /v2/ai-music/generate endpoint to create a new music generation task
    
    Args:
        title: Song title
        tags: Genre, BPM, vocal style (e.g., "industrial techno, 142 bpm, female ai vocaloid")
        prompt: Song description/theme
        lyrics: Optional custom lyrics (if not provided, Suno generates them)
        api_key: Suno API key (defaults to SUNO_API_KEY env var)
        
    Returns:
        Dict containing API response with task IDs and status
        
    Raises:
        ValueError: If API key is missing
        Exception: If API call fails
    """
    import aiohttp
    
    if api_key is None:
        api_key = os.getenv("SUNO_API_KEY")
    
    if not api_key:
        raise ValueError("SUNO_API_KEY environment variable is required for Suno API integration")
    
    # Build request payload
    request = SunoGenerateRequest(
        custom_mode=True,
        mv="chirp-v3-5",
        title=title,
        tags=tags,
        prompt=prompt
    )
    
    payload = {
        "custom_mode": request.custom_mode,
        "mv": request.mv,
        "title": request.title,
        "tags": request.tags,
        "prompt": request.prompt
    }
    
    # Add lyrics if provided
    if lyrics:
        payload["lyrics"] = lyrics
    
    logger.info(f"Calling Suno API: generate_music (title: {title})")
    
    # Call Suno API - use correct endpoint from tutorial
    api_url = "https://api.suno.ai/api/v2/ai-music/generate"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(api_url, json=payload, headers=headers) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Suno API error ({response.status}): {error_text}")
            
            result = await response.json()
            logger.info(f"Suno API returned {len(result.get('data', []))} tasks")
            return result


async def query_status_api(
    task_ids: List[str],
    api_key: Optional[str] = None
) -> List[SunoTask]:
    """
    Poll Suno /v2/ai-music/query endpoint for task status
    
    Args:
        task_ids: List of task IDs to query
        api_key: Suno API key (defaults to SUNO_API_KEY env var)
        
    Returns:
        List[SunoTask]: Task objects with current status and results
        
    Raises:
        ValueError: If API key is missing
        Exception: If API call fails
    """
    import aiohttp
    
    if api_key is None:
        api_key = os.getenv("SUNO_API_KEY")
    
    if not api_key:
        raise ValueError("SUNO_API_KEY environment variable is required for Suno API integration")
    
    logger.info(f"Querying Suno API status for {len(task_ids)} tasks")
    
    # Call Suno API - use correct endpoint from tutorial
    api_url = "https://api.suno.ai/api/v2/ai-music/query"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {"ids": ",".join(task_ids)}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url, params=payload, headers=headers) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Suno API query error ({response.status}): {error_text}")
            
            result = await response.json()
            
            # Parse response into SunoTask objects
            tasks = []
            for task_data in result.get("data", []):
                task = SunoTask(
                    id=task_data["id"],
                    title=task_data.get("title", ""),
                    status=task_data.get("status", "unknown"),
                    image_url=task_data.get("image_url"),
                    lyric=task_data.get("lyric"),
                    audio_url=task_data.get("audio_url"),
                    video_url=task_data.get("video_url"),
                    created_at=task_data.get("created_at", ""),
                    model_name=task_data.get("model_name", ""),
                    gpt_description_prompt=task_data.get("gpt_description_prompt"),
                    prompt=task_data.get("prompt"),
                    type=task_data.get("type", "gen"),
                    tags=task_data.get("tags", "")
                )
                tasks.append(task)
            
            logger.info(f"Retrieved status for {len(tasks)} tasks")
            return tasks
