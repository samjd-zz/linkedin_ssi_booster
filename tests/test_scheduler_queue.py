from scheduler import PostScheduler


class FakeBufferService:
    def __init__(self) -> None:
        self.created_posts: list[dict[str, str | None]] = []

    def get_linkedin_channel_id(self) -> str:
        return "linkedin-channel"

    def create_post(
        self,
        channel_id: str,
        text: str,
        scheduled_at: str | None = None,
        channel: str = "linkedin",
    ) -> dict[str, str | None]:
        post = {
            "channel_id": channel_id,
            "text": text,
            "scheduled_at": scheduled_at,
            "channel": channel,
        }
        self.created_posts.append(post)
        return post


def test_schedule_week_queues_all_posts_without_time_overrides(monkeypatch) -> None:
    monkeypatch.delenv("SCHEDULER_POSTING_SLOTS", raising=False)
    monkeypatch.setenv("SSI_FOCUS_ESTABLISH_BRAND", "25")
    monkeypatch.setenv("SSI_FOCUS_FIND_RIGHT_PEOPLE", "25")
    monkeypatch.setenv("SSI_FOCUS_ENGAGE_WITH_INSIGHTS", "25")
    monkeypatch.setenv("SSI_FOCUS_BUILD_RELATIONSHIPS", "25")
    monkeypatch.setenv("SCHEDULER_TIMEZONE", "America/Vancouver")

    buffer_service = FakeBufferService()
    scheduler = PostScheduler(buffer_service)
    posts = [
        {"generated_text": f"post {idx}", "ssi_component": "establish_brand"}
        for idx in range(5)
    ]

    scheduled = scheduler.schedule_week(posts, week_number=1, channel="linkedin")

    assert len(scheduled) == 5
    assert [post["text"] for post in buffer_service.created_posts] == [
        "post 0",
        "post 1",
        "post 2",
        "post 3",
        "post 4",
    ]
    assert all(post["scheduled_at"] is None for post in buffer_service.created_posts)


def test_schedule_week_respects_configured_slot_limit(monkeypatch) -> None:
    monkeypatch.setenv("SCHEDULER_POSTING_SLOTS", "monday@09:00,tuesday@16:00,wednesday@16:00")
    monkeypatch.setenv("SSI_FOCUS_ESTABLISH_BRAND", "25")
    monkeypatch.setenv("SSI_FOCUS_FIND_RIGHT_PEOPLE", "25")
    monkeypatch.setenv("SSI_FOCUS_ENGAGE_WITH_INSIGHTS", "25")
    monkeypatch.setenv("SSI_FOCUS_BUILD_RELATIONSHIPS", "25")
    monkeypatch.setenv("SCHEDULER_TIMEZONE", "America/Vancouver")

    buffer_service = FakeBufferService()
    scheduler = PostScheduler(buffer_service)
    posts = [
        {"generated_text": f"post {idx}", "ssi_component": "establish_brand"}
        for idx in range(5)
    ]

    scheduled = scheduler.schedule_week(posts, week_number=1, channel="linkedin")

    assert len(scheduled) == 3
    assert [post["text"] for post in buffer_service.created_posts] == [
        "post 0",
        "post 1",
        "post 2",
    ]