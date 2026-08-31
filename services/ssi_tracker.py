"""
SSI Tracker
Tracks LinkedIn Social Selling Index targets per component
and prints a weekly action report with specific tips.
"""

import json
import os
import logging
from datetime import datetime, date
from pathlib import Path
from colorama import Fore, Style

logger = logging.getLogger(__name__)


def fetch_bluesky_stats(handle: str | None = None, password: str | None = None, feed_limit: int = 20) -> dict | None:
    """Fetch live Bluesky profile stats + engagement from recent posts.

    handle     — Bluesky handle, e.g. 'samjd-zz.bsky.social'. Falls back to
                 BLUESKY_HANDLE env var, then BLUESKY_IDENTIFIER.
    password   — App password. Falls back to BLUESKY_APP_PASSWORD env var.
    feed_limit — Number of recent posts to analyse for engagement (default 20).

    Returns a dict with keys:
      handle, followers, following, posts,
      total_likes, total_replies, total_reposts, total_quotes,
      avg_engagement, top_post (dict with text/likes/replies/reposts/url)
    Returns None if credentials are missing or the request fails.
    """
    try:
        from atproto import Client  # optional dependency
    except ImportError:
        logger.warning("atproto package not installed — run: pip install atproto")
        return None

    handle   = handle   or os.getenv("BLUESKY_HANDLE") or os.getenv("BLUESKY_IDENTIFIER")
    password = password or os.getenv("BLUESKY_APP_PASSWORD")

    if not handle or not password:
        logger.warning("BLUESKY_HANDLE and BLUESKY_APP_PASSWORD are required for Bluesky stats")
        return None

    try:
        client = Client()
        client.login(handle, password)
        profile = client.get_profile(handle)

        # Pull recent posts for engagement analysis
        feed_resp = client.get_author_feed(actor=handle, limit=feed_limit, filter="posts_no_replies")
        items = getattr(feed_resp, "feed", []) or []

        total_likes = total_replies = total_reposts = total_quotes = 0
        top_post: dict | None = None
        top_score = -1

        for item in items:
            post = getattr(item, "post", None)
            if post is None:
                continue
            likes    = getattr(post, "like_count",   0) or 0
            replies  = getattr(post, "reply_count",  0) or 0
            reposts  = getattr(post, "repost_count", 0) or 0
            quotes   = getattr(post, "quote_count",  0) or 0
            total_likes   += likes
            total_replies += replies
            total_reposts += reposts
            total_quotes  += quotes
            score = likes + replies + reposts + quotes
            if score > top_score:
                top_score = score
                record = getattr(post, "record", None)
                text   = getattr(record, "text", "") if record else ""
                uri    = getattr(post, "uri", "") or ""
                # Convert at:// URI → web URL: at://did:.../app.bsky.feed.post/rkey
                url = ""
                if uri.startswith("at://"):
                    parts = uri.split("/")
                    if len(parts) >= 5:
                        url = f"https://bsky.app/profile/{handle}/post/{parts[-1]}"
                top_post = {
                    "text":     (text[:100] + "…") if len(text) > 100 else text,
                    "likes":    likes,
                    "replies":  replies,
                    "reposts":  reposts,
                    "url":      url,
                }

        analysed = len(items)
        avg_engagement = round((total_likes + total_replies + total_reposts + total_quotes) / analysed, 1) if analysed else 0.0

        return {
            "handle":         profile.handle,
            "followers":      profile.followers_count or 0,
            "following":      profile.follows_count   or 0,
            "posts":          profile.posts_count      or 0,
            "analysed":       analysed,
            "total_likes":    total_likes,
            "total_replies":  total_replies,
            "total_reposts":  total_reposts,
            "total_quotes":   total_quotes,
            "avg_engagement": avg_engagement,
            "top_post":       top_post,
        }
    except Exception as e:
        logger.warning(f"Could not fetch Bluesky stats: {e}")
        return None

SSI_TARGETS = {
    "establish_brand":      {"target": 25.0, "max": 25.0},
    "find_right_people":    {"target": 20.0, "max": 25.0},
    "engage_with_insights": {"target": 25.0, "max": 25.0},
    "build_relationships":  {"target": 25.0, "max": 25.0},
}

SSI_ACTIONS = {
    "establish_brand": [
        "Post 3x this week (Buffer handles scheduling)",
        "Update LinkedIn headline to include 'RAG | Neo4j | AI-TDD'",
        "Add your G7 GovAI project to Featured section",
        "Complete LinkedIn Skills section with AI/ML skills",
    ],
    "find_right_people": [
        "Connect with 5 people who liked/commented your last post",
        "Search and connect with GovTech AI professionals in Ottawa",
        "Join: 'Graph Database & Neo4j', 'RAG Practitioners', 'GovAI' LinkedIn groups",
        "Follow: Anthropic, G7 GovAI Challenge, Spring AI accounts",
    ],
    "engage_with_insights": [
        "Leave 5 thoughtful comments on AI posts (not just 'Great post!')",
        "Share a curated article with your own 2-sentence take",
        "React to posts from your target connections daily",
        "Comment on a post from someone you want to connect with",
    ],
    "build_relationships": [
        "Reply to every comment on your posts within 24 hours",
        "Send a personalised message to 3 new connections",
        "Thank anyone who shares your post with a DM",
        "Endorse 5 connections for relevant skills",
    ]
}


class SSITracker:

    def __init__(self, data_file: str = "ssi_history.json"):
        self.data_file = Path(data_file)
        self.history = self._load_history()

    def _load_history(self) -> list:
        if self.data_file.exists():
            with open(self.data_file) as f:
                return json.load(f)
        return []

    def save_scores(self, establish: float, find: float, engage: float, build: float):
        """Record today's SSI scores."""
        entry = {
            "date": date.today().isoformat(),
            "establish_brand": establish,
            "find_right_people": find,
            "engage_with_insights": engage,
            "build_relationships": build,
            "total": establish + find + engage + build
        }
        self.history.append(entry)
        with open(self.data_file, "w") as f:
            json.dump(self.history, f, indent=2)
        logger.info(f"Saved SSI scores: total={entry['total']:.2f}")

    def print_report(self):
        """Print a weekly SSI action report to the console."""
        print("\n" + str(Fore.CYAN) + str(Style.BRIGHT) + "="*60 + str(Style.RESET_ALL))
        print(str(Fore.CYAN) + str(Style.BRIGHT) + "  📊 LINKEDIN SSI WEEKLY REPORT" + str(Style.RESET_ALL))
        print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(str(Fore.CYAN) + str(Style.BRIGHT) + "="*60 + str(Style.RESET_ALL))

        # Current values always come from the most recent history entry
        latest: dict[str, float] = {}
        if self.history:
            last = self.history[-1]
            latest = {
                "establish_brand":      last.get("establish_brand", 0.0),
                "find_right_people":    last.get("find_right_people", 0.0),
                "engage_with_insights": last.get("engage_with_insights", 0.0),
                "build_relationships":  last.get("build_relationships", 0.0),
            }

        if not latest:
            print(str(Fore.YELLOW) + "\n  ⚠️  No SSI data saved yet. Run: python main.py --save-ssi <brand> <find> <engage> <build>\n" + str(Style.RESET_ALL))
            print(str(Fore.CYAN) + "=" * 60 + str(Style.RESET_ALL) + "\n")
            return

        # Previous entry for trend comparison
        prev: dict[str, float] = {}
        if len(self.history) >= 2:
            p = self.history[-2]
            prev = {
                "establish_brand":      p.get("establish_brand", 0.0),
                "find_right_people":    p.get("find_right_people", 0.0),
                "engage_with_insights": p.get("engage_with_insights", 0.0),
                "build_relationships":  p.get("build_relationships", 0.0),
            }

        total_current = sum(latest.values())
        total_target  = sum(v["target"] for v in SSI_TARGETS.values())

        print(str(Fore.WHITE) + str(Style.BRIGHT) + f"\n  OVERALL: {total_current:.2f} / 100  →  TARGET: {total_target:.0f} / 100" + str(Style.RESET_ALL))
        print(f"  Gap to close: {str(Fore.YELLOW)}{total_target - total_current:.2f}{str(Style.RESET_ALL)} points\n")

        component_labels = {
            "establish_brand":      "Establish professional brand",
            "find_right_people":    "Find the right people",
            "engage_with_insights": "Engage with insights",
            "build_relationships":  "Build relationships",
        }

        for key, vals in SSI_TARGETS.items():
            label   = component_labels[key]
            current = latest[key]
            target  = vals["target"]
            gap     = target - current
            bar_filled = int((current / vals["max"]) * 20)
            bar_empty  = 20 - bar_filled

            # Colour the progress bar based on progress toward target
            pct = current / target if target else 0
            if pct >= 0.85:
                bar_colour = Fore.GREEN
            elif pct >= 0.6:
                bar_colour = Fore.YELLOW
            else:
                bar_colour = Fore.RED
            bar = str(bar_colour) + "█" * bar_filled + str(Fore.WHITE) + "░" * bar_empty + str(Style.RESET_ALL)

            # Week-over-week delta
            if key in prev:
                delta = current - prev[key]
                if delta > 0:
                    trend = str(Fore.GREEN) + f"  ↑ +{delta:.2f} since last entry" + str(Style.RESET_ALL)
                elif delta < 0:
                    trend = str(Fore.RED) + f"  ↓ {delta:.2f} since last entry" + str(Style.RESET_ALL)
                else:
                    trend = str(Fore.YELLOW) + "  ↔ no change since last entry" + str(Style.RESET_ALL)
            else:
                trend = ""

            print(str(Fore.WHITE) + str(Style.BRIGHT) + f"  {label}" + str(Style.RESET_ALL) + trend)
            print(f"  [{bar}] {bar_colour}{current:.2f}{Style.RESET_ALL} → {target:.0f}  (gap: +{gap:.2f})")
            print(f"  Actions this week:")
            for action in SSI_ACTIONS[key]:
                print(f"    • {action}")
            print()

        # History summary table
        if len(self.history) >= 2:
            print(str(Fore.CYAN) + "  SCORE HISTORY (last 5 entries)" + str(Style.RESET_ALL))
            print(f"  {'Date':<12} {'Brand':>6} {'Find':>6} {'Engage':>7} {'Build':>6} {'Total':>7}")
            print("  " + str(Fore.CYAN) + "-"*48 + str(Style.RESET_ALL))
            for entry in self.history[-5:]:
                print(
                    f"  {entry['date']:<12}"
                    f" {entry.get('establish_brand', 0):>6.2f}"
                    f" {entry.get('find_right_people', 0):>6.2f}"
                    f" {entry.get('engage_with_insights', 0):>7.2f}"
                    f" {entry.get('build_relationships', 0):>6.2f}"
                    f" {entry.get('total', 0):>7.2f}"
                )
            print()

        print(str(Fore.CYAN) + str(Style.BRIGHT) + "  QUICK WINS (do these daily, 15 mins):" + str(Style.RESET_ALL))
        print("    1. Check Buffer queue — confirm this week's posts are queued")
        print("    2. Leave 3 meaningful comments on AI/GovTech posts")
        print("    3. Accept + message 2 new connection requests")
        print("    4. Check linkedin.com/sales/ssi — track your score")
        print("    5. Run: python main.py --save-ssi <brand> <find> <engage> <build>")
        print("\n" + str(Fore.CYAN) + str(Style.BRIGHT) + "="*60 + str(Style.RESET_ALL) + "\n")
