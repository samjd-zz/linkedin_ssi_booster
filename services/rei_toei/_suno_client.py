"""
Suno HTTP Client Functions

This module provides async HTTP client functions for interacting with the Suno API
via sunoapi.org (third-party proxy with stable v1 REST interface).

API docs: https://docs.sunoapi.org/suno-api/generate-music

Author: Shawn Jackson Dyck
Version: alpha-v0.0.3.3
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from ._models import SunoTask

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "https://api.sunoapi.org"
_DEFAULT_MODEL = "V4_5"
# Required by sunoapi.org schema; we poll instead of using callbacks, so a
# placeholder URL is fine here.
_CALLBACK_PLACEHOLDER = "https://example.com/suno-callback"


def _request_json(
    method: str,
    url: str,
    headers: Dict[str, str],
    payload: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout_seconds: int = 30,
) -> tuple[int, Dict[str, Any]]:
    """Make a JSON HTTP request using the standard library."""
    final_url = url
    if params:
        final_url = f"{url}?{urllib_parse.urlencode(params)}"

    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    request = urllib_request.Request(final_url, data=body, headers=headers, method=method)

    try:
        with urllib_request.urlopen(request, timeout=timeout_seconds) as response:
            status = int(response.getcode() or 0)
            raw_text = response.read().decode("utf-8")
    except urllib_error.HTTPError as exc:
        status = int(exc.code or 0)
        raw_text = exc.read().decode("utf-8", errors="replace")
    except urllib_error.URLError as exc:
        raise Exception(f"Suno API request failed: {exc.reason}") from exc

    try:
        parsed = json.loads(raw_text or "{}")
    except json.JSONDecodeError as exc:
        raise Exception(f"Suno API returned invalid JSON: {raw_text[:200]}") from exc

    if not isinstance(parsed, dict):
        raise Exception("Suno API returned a non-object JSON payload")

    return status, parsed


async def generate_music_api(
    title: str,
    tags: str,
    prompt: str,
    lyrics: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Submit a music generation task via sunoapi.org POST /api/v1/generate.

    In custom mode (customMode=True, instrumental=False) the `lyrics` argument
    is sent as the `prompt` field — that is how sunoapi.org handles exact lyrics.
    The `tags` argument maps to the `style` field (genre, BPM, vocal style).

    Args:
        title:   Song title (max 100 chars for V4_5+).
        tags:    Style/genre string sent as the `style` field.
        prompt:  Narrative description — used only when no lyrics are provided.
        lyrics:  Full formatted lyrics sent as the `prompt` field in custom mode.
        api_key: Suno API key (defaults to SUNO_API_KEY env var).

    Returns:
        Dict wrapping the task ID for compatibility with submit_to_suno:
        ``{"data": [{"id": "<taskId>"}]}``

    Raises:
        ValueError: If API key is missing.
        Exception:  If the HTTP call fails or the API returns a non-200 code.
    """
    if api_key is None:
        api_key = os.getenv("SUNO_API_KEY")

    if not api_key:
        raise ValueError("SUNO_API_KEY environment variable is required for Suno API integration")

    base_url = os.getenv("SUNO_API_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")
    model = os.getenv("SUNO_MODEL", _DEFAULT_MODEL)

    payload: Dict[str, Any] = {
        "customMode": True,
        "instrumental": False,
        "model": model,
        "style": tags,
        "title": title[:100],
        "callBackUrl": _CALLBACK_PLACEHOLDER,
        # In custom mode, `prompt` is used as the exact lyrics.
        "prompt": lyrics if lyrics else prompt,
    }

    logger.info(f"Calling sunoapi.org: generate_music title={title!r} model={model}")
    logger.debug(f"Style tags ({len(tags)} chars): {tags[:120]}")

    api_url = f"{base_url}/api/v1/generate"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    status, result = await asyncio.to_thread(
        _request_json,
        "POST",
        api_url,
        headers,
        payload,
        None,
    )
    if status != 200:
        raise Exception(f"Suno API error ({status}): {result}")

    code = result.get("code", 0)
    if code != 200:
        raise Exception(
            f"Suno API returned code {code}: {result.get('msg', 'unknown error')}"
        )

    task_id: str = result["data"]["taskId"]
    logger.info(f"Suno task submitted: {task_id}")
    # Wrap in list form so submit_to_suno's existing extraction works unchanged.
    return {"data": [{"id": task_id}]}


async def query_status_api(
    task_ids: List[str],
    api_key: Optional[str] = None,
) -> List[SunoTask]:
    """
    Poll sunoapi.org GET /api/v1/generate/record-info for task status.

    sunoapi.org issues one task ID per generate call, so only the first entry
    in `task_ids` is queried.

    Status mapping from sunoapi.org → internal:
        SUCCESS                                    → "complete"
        CREATE_TASK_FAILED / GENERATE_AUDIO_FAILED
        / CALLBACK_EXCEPTION / SENSITIVE_WORD_ERROR → "error"
        PENDING / TEXT_SUCCESS / FIRST_SUCCESS     → "pending"

    Args:
        task_ids: List of task IDs (only the first is used).
        api_key:  Suno API key (defaults to SUNO_API_KEY env var).

    Returns:
        List containing a single SunoTask with current status and audio URL.

    Raises:
        ValueError: If API key is missing.
        Exception:  If the HTTP call fails or the API returns a non-200 code.
    """
    if api_key is None:
        api_key = os.getenv("SUNO_API_KEY")

    if not api_key:
        raise ValueError("SUNO_API_KEY environment variable is required for Suno API integration")

    if not task_ids:
        return []

    base_url = os.getenv("SUNO_API_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")
    task_id = task_ids[0]

    logger.info(f"Querying sunoapi.org status for task {task_id}")

    api_url = f"{base_url}/api/v1/generate/record-info"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    status, result = await asyncio.to_thread(
        _request_json,
        "GET",
        api_url,
        headers,
        None,
        {"taskId": task_id},
    )
    if status != 200:
        raise Exception(f"Suno API query error ({status}): {result}")

    code = result.get("code", 0)
    if code != 200:
        raise Exception(
            f"Suno API query returned code {code}: {result.get('msg', 'unknown error')}"
        )

    data = result.get("data", {})
    raw_status: str = data.get("status", "PENDING")

    _ERROR_STATUSES = {
        "CREATE_TASK_FAILED",
        "GENERATE_AUDIO_FAILED",
        "CALLBACK_EXCEPTION",
        "SENSITIVE_WORD_ERROR",
    }
    if raw_status == "SUCCESS":
        mapped_status = "complete"
    elif raw_status in _ERROR_STATUSES:
        mapped_status = "error"
    else:
        mapped_status = "pending"

    suno_data: list = data.get("response", {}).get("sunoData", [])
    first_track: dict = suno_data[0] if suno_data else {}

    task = SunoTask(
        id=task_id,
        title=first_track.get("title", ""),
        status=mapped_status,
        image_url=first_track.get("imageUrl"),
        lyric=first_track.get("prompt"),
        audio_url=first_track.get("audioUrl"),
        video_url=first_track.get("videoUrl"),
        created_at=first_track.get("createTime", ""),
        model_name=first_track.get("modelName", ""),
        tags=first_track.get("tags", ""),
    )
    logger.info(f"Task {task_id}: raw_status={raw_status!r} → {mapped_status!r}")
    return [task]

