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
    svc = BufferService(api_key)
    try:
        svc.get_channels()  # Verify key has channel-level access; skip if FORBIDDEN
    except RuntimeError as exc:
        pytest.skip(f"Buffer API not accessible: {exc}")
    return svc

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


def test_create_scheduled_post_x_preserves_full_url(monkeypatch):
    service = BufferService("test-token")
    captured: dict = {}

    def fake_query(_query, variables=None):
        captured["text"] = variables["input"]["text"]
        return {"createPost": {"post": {"id": "1", "text": captured["text"], "status": "scheduled"}}}

    monkeypatch.setattr(service, "_query", fake_query)

    url = "https://example.com/this/is/a/very/long/path/that/should/not/be/clipped"
    text = ("A" * 275) + "\n\n" + url

    service.create_scheduled_post("chan-1", text, channel="x")

    sent_text = captured["text"]
    assert url in sent_text
    assert BufferService._x_effective_length(sent_text) <= 280


def test_x_effective_length_counts_url_as_fixed_length():
    url = "https://example.com/some/very/long/url/that/would/otherwise/be/large"
    text = f"hello {url} world"
    expected = len("hello ") + 23 + len(" world")
    assert BufferService._x_effective_length(text) == expected
