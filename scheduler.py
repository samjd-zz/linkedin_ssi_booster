from services.buffer_service import BufferChannelNotConnectedError
from services.shared import get_ssi_focus_weights
"""
Post Scheduler
Pushes generated posts to Buffer's queue.
Buffer owns the posting cadence and publish times.
"""

import logging

logger = logging.getLogger(__name__)


class PostScheduler:

    def __init__(self, buffer_service):
        self.buffer = buffer_service

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
        elif channel == "facebook":
            return [self.buffer.get_facebook_channel_id()]
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
            try:
                ids.append(self.buffer.get_facebook_channel_id())
            except BufferChannelNotConnectedError as e:
                logger.warning(f"Facebook channel not configured; skipping in all-channel mode. ({e})")
            return ids
        else:
            raise ValueError(f"Unknown channel {channel!r}. Use 'linkedin', 'x', 'bluesky', 'threads', 'youtube', 'facebook', or 'all'.")

    def schedule_week(self, posts: list, week_number: int = 1, channel: str = "linkedin"):
        """
        Add a week of posts to Buffer's queue.
        Buffer owns posting times and queue placement.
        Posts are selected according to SSI focus weights from the environment.
        channel: 'linkedin' | 'x' | 'bluesky' | 'threads' | 'youtube' | 'facebook' | 'all'
        """
        channel_ids = self._resolve_channel_ids(channel)

        # Compute how many posts per SSI component this week
        ssi_weights = get_ssi_focus_weights()
        total_posts = len(posts)
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
                scheduled_at = None
                text = post.get("generated_text", "")

                if not text:
                    logger.warning(f"Post {i+1} has no generated text — skipping")
                    continue

                result = self.buffer.create_post(
                    channel_id=channel_id,
                    text=text,
                    scheduled_at=scheduled_at
                )
                logger.info(f"[{channel_id}] Queued post {i+1}/{len(selected_posts)} → Buffer queue")
                scheduled.append(result)

        logger.info(f"Week {week_number}: {len(scheduled)} posts scheduled to Buffer ({channel})")
        return scheduled
