import os
import pytest
from services.buffer_service import (
    BufferService,
    BufferQueueFullError,
    BufferChannelNotConnectedError,
)

import logging
logging.basicConfig(level=logging.INFO)

@pytest.fixture
def buffer_service():
    api_key = os.getenv("BUFFER_API_KEY")
    if not api_key:
        pytest.skip("BUFFER_API_KEY not set in environment")
    return BufferService(api_key)

def test_get_scheduled_posts(buffer_service):
    linkedin_id = buffer_service.get_linkedin_channel_id()
    posts = buffer_service.get_scheduled_posts(linkedin_id, limit=5)
    assert isinstance(posts, list)
    for post in posts:
        assert "id" in post
        assert "text" in post
        assert "status" in post
        assert post["status"].lower() == "scheduled"

def test_get_published_posts(buffer_service):
    linkedin_id = buffer_service.get_linkedin_channel_id()
    posts = buffer_service.get_published_posts(linkedin_id, limit=5)
    assert isinstance(posts, list)
    for post in posts:
        assert "id" in post
        assert "text" in post
        assert "status" in post
        assert post["status"].lower() == "sent" or post["status"].lower() == "published"


def test_get_threads_channel_id_from_connected_channels(monkeypatch):
    service = BufferService("test-token")
    monkeypatch.setattr(
        service,
        "get_channels",
        lambda: [
            {"service": "linkedin", "name": "eden-redman", "id": "li-1"},
            {"service": "threads", "name": "edenredman", "id": "threads-1"},
        ],
    )

    assert service.get_threads_channel_id() == "threads-1"


def test_get_threads_channel_id_raises_when_missing(monkeypatch):
    service = BufferService("test-token")
    monkeypatch.setattr(
        service,
        "get_channels",
        lambda: [{"service": "linkedin", "name": "eden-redman", "id": "li-1"}],
    )

    with pytest.raises(BufferChannelNotConnectedError):
        service.get_threads_channel_id()
