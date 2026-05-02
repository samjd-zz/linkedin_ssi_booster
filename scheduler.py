from services.shared import get_ssi_focus_weights
from services.buffer_service import BufferChannelNotConnectedError
"""
Post Scheduler
Pushes generated posts to Buffer with optimal scheduling.
Targets: Tue/Wed/Fri 4:00 PM EST — matching your Buffer posting windows.
"""

import logging
import os
from datetime import datetime, timedelta, tzinfo
from typing import Optional
import pytz

logger = logging.getLogger(__name__)

DEFAULT_POSTING_SCHEDULE = {
    "tuesday":   {"hour": 16, "minute": 0},
    "wednesday": {"hour": 16, "minute": 0},
    "friday":    {"hour": 16, "minute": 0},
}

WEEKDAY_MAP = {
    "monday":    0,
    "tuesday":   1,
    "wednesday": 2,
    "thursday":  3,
    "friday":    4,
    "saturday":  5,
    "sunday":    6,
}


def _load_timezone() -> tzinfo:
    tz_name = os.getenv("SCHEDULER_TIMEZONE", "America/Toronto").strip() or "America/Toronto"
    try:
        return pytz.timezone(tz_name)
    except pytz.UnknownTimeZoneError:
        logger.warning(f"Invalid SCHEDULER_TIMEZONE={tz_name!r}; falling back to America/Toronto")
        return pytz.timezone("America/Toronto")


def _load_posting_schedule() -> dict[str, dict[str, int]]:
    """Parse posting slots from env.

    Env format:
      SCHEDULER_POSTING_SLOTS=tuesday@16:00,wednesday@16:00,friday@16:00
    """
    raw = os.getenv("SCHEDULER_POSTING_SLOTS", "").strip()
    if not raw:
        return dict(DEFAULT_POSTING_SCHEDULE)

    parsed: dict[str, dict[str, int]] = {}
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        if "@" not in token:
            logger.warning(f"Invalid scheduler slot token {token!r}; expected day@HH:MM")
            return dict(DEFAULT_POSTING_SCHEDULE)

        day_name, time_part = token.split("@", 1)
        day_name = day_name.strip().lower()
        time_part = time_part.strip()

        if day_name not in WEEKDAY_MAP:
            logger.warning(f"Invalid scheduler day {day_name!r}; using default schedule")
            return dict(DEFAULT_POSTING_SCHEDULE)

        if ":" not in time_part:
            logger.warning(f"Invalid scheduler time {time_part!r}; expected HH:MM")
            return dict(DEFAULT_POSTING_SCHEDULE)

        hour_raw, minute_raw = time_part.split(":", 1)
        if not (hour_raw.isdigit() and minute_raw.isdigit()):
            logger.warning(f"Invalid scheduler time {time_part!r}; expected HH:MM")
            return dict(DEFAULT_POSTING_SCHEDULE)

        hour = int(hour_raw)
        minute = int(minute_raw)
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            logger.warning(f"Out-of-range scheduler time {time_part!r}; using default schedule")
            return dict(DEFAULT_POSTING_SCHEDULE)

        parsed[day_name] = {"hour": hour, "minute": minute}

    if not parsed:
        logger.warning("SCHEDULER_POSTING_SLOTS produced no valid slots; using default schedule")
        return dict(DEFAULT_POSTING_SCHEDULE)

    return parsed


class PostScheduler:

    def __init__(self, buffer_service):
        self.buffer = buffer_service
        self.timezone = _load_timezone()
        self.posting_schedule = _load_posting_schedule()
        self.weekday_map = {k: WEEKDAY_MAP[k] for k in self.posting_schedule}

    def _resolve_channel_ids(self, channel: str) -> list[str]:
        """Return a list of Buffer channel IDs for the given channel selector."""
        if channel == "linkedin":
            return [self.buffer.get_linkedin_channel_id()]
        elif channel == "x":
            return [self.buffer.get_x_channel_id()]
        elif channel == "bluesky":
            return [self.buffer.get_bluesky_channel_id()]
        elif channel == "threads":
            return [self.buffer.get_threads_channel_id()]
        elif channel == "youtube":
            return [self.buffer.get_youtube_channel_id()]
        elif channel == "all":
            ids = [self.buffer.get_linkedin_channel_id()]
            try:
                ids.append(self.buffer.get_x_channel_id())
            except BufferChannelNotConnectedError as e:
                logger.warning(f"X channel not configured; skipping in all-channel mode. ({e})")
            try:
                ids.append(self.buffer.get_bluesky_channel_id())
            except BufferChannelNotConnectedError as e:
                logger.warning(f"Bluesky channel not configured; skipping in all-channel mode. ({e})")
            try:
                ids.append(self.buffer.get_threads_channel_id())
            except BufferChannelNotConnectedError as e:
                logger.warning(f"Threads channel not configured; skipping in all-channel mode. ({e})")
            try:
                ids.append(self.buffer.get_youtube_channel_id())
            except BufferChannelNotConnectedError as e:
                logger.warning(f"YouTube channel not configured; skipping in all-channel mode. ({e})")
            return ids
        else:
            raise ValueError(f"Unknown channel {channel!r}. Use 'linkedin', 'x', 'bluesky', 'threads', 'youtube', or 'all'.")

    def _next_slot(self, day_name: str, reference: Optional[datetime] = None) -> str:
        """Calculate the next occurrence of a given weekday posting slot."""
        if reference is None:
            reference = datetime.now(self.timezone)

        target_weekday = self.weekday_map[day_name]
        slot = self.posting_schedule[day_name]

        days_ahead = target_weekday - reference.weekday()
        if days_ahead < 0:
            days_ahead += 7
        elif days_ahead == 0:
            # Same day — check if slot has passed
            slot_today = reference.replace(hour=slot["hour"], minute=slot["minute"], second=0, microsecond=0)
            if reference >= slot_today:
                days_ahead = 7

        post_date = reference + timedelta(days=days_ahead)
        post_dt = post_date.replace(hour=slot["hour"], minute=slot["minute"], second=0, microsecond=0)
        return post_dt.astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def schedule_week(self, posts: list, week_number: int = 1, channel: str = "linkedin"):
        """
        Schedule a week of posts to Buffer.
        Posts are distributed across configured posting slots.
        Max posts/week per channel = number of configured slots.
        Posts are selected according to SSI focus weights from the environment.
        channel: 'linkedin' | 'x' | 'bluesky' | 'threads' | 'youtube' | 'all'
        """
        channel_ids = self._resolve_channel_ids(channel)
        # If posting_schedule is empty, use Buffer's default queueing (no time override)
        days = list(self.posting_schedule.keys()) if self.posting_schedule else []
        reference = datetime.now(self.timezone)

        # Advance reference by (week_number - 1) weeks
        if week_number > 1:
            reference = reference + timedelta(weeks=week_number - 1)

        # Compute how many posts per SSI component this week
        ssi_weights = get_ssi_focus_weights()
        total_posts = min(len(days), len(posts)) if days else len(posts)
        # Sort posts by SSI component for selection
        posts_by_ssi = {k: [] for k in ssi_weights}
        for post in posts:
            comp = post.get("ssi_component")
            if comp in posts_by_ssi:
                posts_by_ssi[comp].append(post)

        # Calculate how many posts per component (rounded, at least 1 if weight > 0 and enough posts)
        import math
        allocation = {k: 0 for k in ssi_weights}
        remaining = total_posts
        # First pass: floor division
        for k, w in ssi_weights.items():
            n = int(math.floor(w * total_posts))
            allocation[k] = min(n, len(posts_by_ssi[k]))
            remaining -= allocation[k]
        # Second pass: distribute remaining slots by descending fractional part, but only if posts available
        if remaining > 0:
            # Compute fractional parts
            fracs = sorted(((k, (ssi_weights[k]*total_posts)%1) for k in ssi_weights), key=lambda x: -x[1])
            for k, _ in fracs:
                if remaining == 0:
                    break
                if allocation[k] < len(posts_by_ssi[k]) and ssi_weights[k] > 0:
                    allocation[k] += 1
                    remaining -= 1

        # Now select posts in allocation order, preserving original order within each component
        selected_posts = []
        for k in allocation:
            selected_posts.extend(posts_by_ssi[k][:allocation[k]])
        # If not enough posts, fill with any remaining posts
        if len(selected_posts) < total_posts:
            used_ids = {id(p) for p in selected_posts}
            for post in posts:
                if id(post) not in used_ids and len(selected_posts) < total_posts:
                    selected_posts.append(post)


        scheduled = []
        for channel_id in channel_ids:
            for i, post in enumerate(selected_posts):
                if days:
                    day_name     = days[i % len(days)]
                    scheduled_at = self._next_slot(day_name, reference=reference)
                else:
                    day_name     = None
                    scheduled_at = None  # Let Buffer use its own next-available slot
                text         = post.get("generated_text", "")

                if not text:
                    logger.warning(f"Post {i+1} has no generated text — skipping")
                    continue

                result = self.buffer.create_post(
                    channel_id=channel_id,
                    text=text,
                    scheduled_at=scheduled_at
                )
                if scheduled_at:
                    logger.info(f"[{channel_id}] Scheduled post {i+1}/{len(selected_posts)} → {day_name} {scheduled_at}")
                else:
                    logger.info(f"[{channel_id}] Scheduled post {i+1}/{len(selected_posts)} → Buffer queue (no time override)")
                scheduled.append(result)

        logger.info(f"Week {week_number}: {len(scheduled)} posts scheduled to Buffer ({channel})")
        return scheduled
