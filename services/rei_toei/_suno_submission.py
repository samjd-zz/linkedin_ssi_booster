"""Suno API submission orchestration for Rei Toei songs."""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from ._models import SunoPrompt, SunoTask
from ._suno_client import generate_music_api, query_status_api

logger = logging.getLogger(__name__)


async def submit_to_suno(
    suno_prompt: SunoPrompt,
    wait_for_completion: bool = False,
    api_key: Optional[str] = None,
    poll_interval_seconds: int = 5,
    max_wait_seconds: int = 300
) -> SunoTask:
    """
    Submit song to Suno API and optionally wait for completion.

    This orchestration function calls generate_music_api() to submit the song,
    then optionally polls query_status_api() until completion or timeout.
    """
    logger.info(f"Submitting song to Suno: '{suno_prompt.title}'")

    response = await generate_music_api(
        title=suno_prompt.title,
        tags=suno_prompt.suno_prompt,
        prompt=suno_prompt.metadata.get("suno_description_prompt", suno_prompt.metadata.get("narrative_arc", "")),
        lyrics=suno_prompt.lyrics,
        api_key=api_key
    )

    task_ids = [task["id"] for task in response.get("data", [])]

    if not task_ids:
        raise Exception("Suno API returned no task IDs")

    logger.info(f"Suno API returned {len(task_ids)} task IDs: {task_ids}")

    if not wait_for_completion:
        return SunoTask(
            id=task_ids[0],
            title=suno_prompt.title,
            status="submitted",
            tags=suno_prompt.suno_prompt,
            created_at=datetime.now().isoformat()
        )

    logger.info(f"Polling for completion (max wait: {max_wait_seconds}s, interval: {poll_interval_seconds}s)")

    start_time = datetime.now()
    elapsed = 0
    poll_count = 0

    while elapsed < max_wait_seconds:
        tasks = await query_status_api(task_ids, api_key=api_key)

        if not tasks:
            raise Exception("Suno API query returned no tasks")

        primary_task = tasks[0]
        poll_count += 1

        logger.info(
            f"[Poll #{poll_count}] Task {primary_task.id}: status={primary_task.status!r}"
            f" (elapsed {int(elapsed)}s / {max_wait_seconds}s)"
        )

        if primary_task.status == "complete":
            logger.info(f"Song complete! Audio URL: {primary_task.audio_url}")
            return primary_task

        if primary_task.status == "error":
            logger.error(f"Suno generation failed for task {primary_task.id}")
            return primary_task

        await asyncio.sleep(poll_interval_seconds)

        elapsed = (datetime.now() - start_time).total_seconds()

    logger.warning(f"Suno generation timed out after {elapsed}s")

    final_tasks = await query_status_api(task_ids, api_key=api_key)
    final_task = final_tasks[0] if final_tasks else SunoTask(
        id=task_ids[0],
        title=suno_prompt.title,
        status="timeout",
        tags=suno_prompt.suno_prompt,
        created_at=datetime.now().isoformat()
    )

    raise TimeoutError(
        f"Suno generation did not complete within {max_wait_seconds}s. "
        f"Final status: {final_task.status}. "
        f"You can check status later using task ID: {final_task.id}"
    )
