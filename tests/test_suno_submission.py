import pytest

from services.rei_toei._models import SunoPrompt, SunoTask
from services.rei_toei import _suno_submission


@pytest.fixture()
def suno_prompt() -> SunoPrompt:
    return SunoPrompt(
        song_id="song-1",
        title="Test Song",
        suno_prompt="140 bpm, cyberpop",
        lyrics="[Verse 1]\nSignal rising",
        metadata={"suno_description_prompt": "Create a cyberpop test song."},
        evidence_ids=["fact-1"],
        generated_at="2026-09-05T00:00:00",
    )


@pytest.mark.asyncio
async def test_submit_to_suno_returns_submitted_task_without_wait(
    monkeypatch: pytest.MonkeyPatch,
    suno_prompt: SunoPrompt,
) -> None:
    seen_payload: dict = {}

    async def fake_generate_music_api(**kwargs):
        seen_payload.update(kwargs)
        return {"data": [{"id": "task-1"}, {"id": "task-2"}]}

    monkeypatch.setattr(_suno_submission, "generate_music_api", fake_generate_music_api)

    task = await _suno_submission.submit_to_suno(suno_prompt, api_key="secret")

    assert task.id == "task-1"
    assert task.title == "Test Song"
    assert task.status == "submitted"
    assert task.tags == "140 bpm, cyberpop"
    assert seen_payload == {
        "title": "Test Song",
        "tags": "140 bpm, cyberpop",
        "prompt": "Create a cyberpop test song.",
        "lyrics": "[Verse 1]\nSignal rising",
        "api_key": "secret",
    }


@pytest.mark.asyncio
async def test_submit_to_suno_raises_when_api_returns_no_tasks(
    monkeypatch: pytest.MonkeyPatch,
    suno_prompt: SunoPrompt,
) -> None:
    async def fake_generate_music_api(**kwargs):
        return {"data": []}

    monkeypatch.setattr(_suno_submission, "generate_music_api", fake_generate_music_api)

    with pytest.raises(Exception, match="Suno API returned no task IDs"):
        await _suno_submission.submit_to_suno(suno_prompt)


@pytest.mark.asyncio
async def test_submit_to_suno_wait_returns_completed_task(
    monkeypatch: pytest.MonkeyPatch,
    suno_prompt: SunoPrompt,
) -> None:
    async def fake_generate_music_api(**kwargs):
        return {"data": [{"id": "task-1"}]}

    async def fake_query_status_api(task_ids, api_key=None):
        return [
            SunoTask(
                id=task_ids[0],
                title="Test Song",
                status="complete",
                audio_url="https://example.com/audio.mp3",
            )
        ]

    monkeypatch.setattr(_suno_submission, "generate_music_api", fake_generate_music_api)
    monkeypatch.setattr(_suno_submission, "query_status_api", fake_query_status_api)

    task = await _suno_submission.submit_to_suno(
        suno_prompt,
        wait_for_completion=True,
        poll_interval_seconds=0,
    )

    assert task.status == "complete"
    assert task.audio_url == "https://example.com/audio.mp3"


@pytest.mark.asyncio
async def test_submit_to_suno_wait_returns_error_task(
    monkeypatch: pytest.MonkeyPatch,
    suno_prompt: SunoPrompt,
) -> None:
    async def fake_generate_music_api(**kwargs):
        return {"data": [{"id": "task-err"}]}

    async def fake_query_status_api(task_ids, api_key=None):
        return [SunoTask(id=task_ids[0], title="Test Song", status="error")]

    monkeypatch.setattr(_suno_submission, "generate_music_api", fake_generate_music_api)
    monkeypatch.setattr(_suno_submission, "query_status_api", fake_query_status_api)

    task = await _suno_submission.submit_to_suno(
        suno_prompt,
        wait_for_completion=True,
        poll_interval_seconds=0,
    )

    assert task.id == "task-err"
    assert task.status == "error"
