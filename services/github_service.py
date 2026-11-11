"""
GitHub Service
Fetches public repository metadata for a GitHub user and formats it as a
compact profile context block suitable for LLM prompt injection.

Responses are cached to github_repos_cache.json for 24 hours to avoid
hammering the API on every run.

Config (via .env):
    GITHUB_USER          — GitHub username (required to enable)
    GITHUB_TOKEN         — Optional personal access token (avoids 60 req/hr limit)
    GITHUB_REPO_FILTER   — Comma-separated list of repo names to include.
                           If empty, all non-fork repos are included.
    GITHUB_INCLUDE_README_SUMMARIES — true/false (default: true)
    GITHUB_REPO_MAX_COUNT — Max number of repos to include (default: 12)
    GITHUB_README_MAX_CHARS — Max chars per README summary (default: 1200)
"""

import base64
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

CACHE_FILE = Path("github_repos_cache.json")
README_CACHE_FILE = Path("github_readmes_cache.json")
CACHE_TTL_SECONDS = 86400  # 24 hours
GITHUB_API_BASE = "https://api.github.com"


class GitHubService:

    def __init__(
        self,
        username: str,
        token: Optional[str] = None,
        repo_filter: Optional[list[str]] = None,
    ):
        self.username = username
        self.repo_filter = [r.strip().lower() for r in repo_filter] if repo_filter else []
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        if token:
            self._session.headers["Authorization"] = f"Bearer {token}"

    def _fetch_repos(self) -> list[dict]:
        """Fetch all non-fork public repos, paginating as needed."""
        repos: list[dict] = []
        page = 1
        while True:
            resp = self._session.get(
                f"{GITHUB_API_BASE}/users/{self.username}/repos",
                params={"type": "public", "sort": "updated", "per_page": 100, "page": page},
                timeout=10,
            )
            if resp.status_code == 404:
                raise ValueError(f"GitHub user not found: {self.username}")
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            repos.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return [r for r in repos if not r.get("fork")]

    def _load_cache(self) -> Optional[list[dict]]:
        if not CACHE_FILE.exists():
            return None
        try:
            data = json.loads(CACHE_FILE.read_text())
            if time.time() - data.get("fetched_at", 0) < CACHE_TTL_SECONDS:
                return data["repos"]
        except (json.JSONDecodeError, KeyError):
            pass
        return None

    def _save_cache(self, repos: list[dict]) -> None:
        CACHE_FILE.write_text(json.dumps({"fetched_at": time.time(), "repos": repos}))

    def _load_readme_cache(self) -> dict:
        if not README_CACHE_FILE.exists():
            return {}
        try:
            data = json.loads(README_CACHE_FILE.read_text())
            if time.time() - data.get("fetched_at", 0) < CACHE_TTL_SECONDS:
                cache = data.get("readmes", {})
                if isinstance(cache, dict):
                    return cache
        except (json.JSONDecodeError, KeyError):
            pass
        return {}

    def _save_readme_cache(self, readme_map: dict) -> None:
        README_CACHE_FILE.write_text(json.dumps({"fetched_at": time.time(), "readmes": readme_map}))

    @staticmethod
    def _markdown_to_text(markdown: str) -> str:
        """Convert README markdown to compact plain text for prompt context."""
        text = markdown
        text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
        text = re.sub(r"`([^`]*)`", r"\1", text)
        text = re.sub(r"!\[[^\]]*\]\([^\)]*\)", " ", text)
        text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
        text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"^[\-\*\+]\s+", "- ", text, flags=re.MULTILINE)
        text = re.sub(r"\r", "", text)
        text = re.sub(r"(?m)^[ \t]+$", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text.strip()

    @staticmethod
    def _clip_at_sentence(text: str, max_chars: int) -> str:
        """Clip text to max_chars, preferring a complete sentence boundary."""
        if len(text) <= max_chars:
            return text
        clipped = text[:max_chars]
        for sep in (".", "!", "?"):
            idx = clipped.rfind(sep)
            if idx != -1 and idx > max_chars // 3:
                return clipped[: idx + 1].strip()
        if " " in clipped:
            return clipped[: clipped.rfind(" ")].strip()
        return clipped.strip()

    def _fetch_readme_summary(self, owner: str, repo_name: str, max_chars: int) -> str:
        """Fetch README markdown and return compact plain-text summary."""
        resp = self._session.get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo_name}/readme",
            timeout=10,
        )
        if resp.status_code == 404:
            return ""
        resp.raise_for_status()
        data = resp.json()
        content = data.get("content", "")
        if not content:
            return ""
        encoding = data.get("encoding", "base64")
        if encoding != "base64":
            return ""
        try:
            decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
        except Exception:
            return ""
        plain = self._markdown_to_text(decoded)
        return self._clip_at_sentence(plain, max_chars)

    def _get_readme_summaries(self, repos: list[dict], max_chars: int) -> dict[str, str]:
        """Get README summaries for repos, using a local cache to avoid API churn."""
        cache = self._load_readme_cache()
        changed = False
        for repo in repos:
            full_name = repo.get("full_name", "")
            if not full_name or full_name in cache:
                continue
            owner = (repo.get("owner") or {}).get("login") or self.username
            name = repo.get("name")
            if not name:
                continue
            try:
                cache[full_name] = self._fetch_readme_summary(owner, name, max_chars)
                changed = True
            except Exception as e:
                logger.debug(f"README fetch failed for {full_name}: {e}")
                cache[full_name] = ""
                changed = True
        if changed:
            self._save_readme_cache(cache)
        return cache

    def get_repos(self) -> list[dict]:
        """Return repos from cache if fresh, otherwise fetch from API."""
        cached = self._load_cache()
        if cached is not None:
            logger.debug("GitHub repos loaded from cache")
            return cached
        logger.info(f"Fetching public repos for GitHub user: {self.username}")
        repos = self._fetch_repos()
        self._save_cache(repos)
        return repos

    def build_profile_context_block(
        self,
        include_readme_summaries: bool = True,
        max_repo_count: int = 12,
        readme_max_chars: int = 1200,
        max_chars: int = 30000,
    ) -> str:
        """Return a compact GitHub context block for prompt injection with char budgeting."""
        try:
            repos = self.get_repos()
        except Exception as e:
            logger.warning(f"GitHub fetch failed — skipping repo context: {e}")
            return ""

        if self.repo_filter:
            repos = [r for r in repos if r["name"].lower() in self.repo_filter]

        repos = repos[:max_repo_count]

        if not repos:
            return ""

        readme_map: dict[str, str] = {}
        if include_readme_summaries:
            readme_map = self._get_readme_summaries(repos, readme_max_chars)

        lines = ["GitHub projects (use these as real reference points when relevant):"]
        included_repo_count = 0
        included_readme_count = 0
        for repo in repos:
            name = repo["name"]
            desc = (repo.get("description") or "").strip()
            lang = repo.get("language") or ""
            topics = ", ".join(repo.get("topics") or [])
            stars = repo.get("stargazers_count", 0)
            full_name = repo.get("full_name", "")

            parts = [f"- {name}"]
            if desc:
                parts.append(desc)
            meta: list[str] = []
            if lang:
                meta.append(lang)
            if topics:
                meta.append(f"topics: {topics}")
            if stars:
                meta.append(f"{stars} stars")
            if meta:
                parts.append(f"[{' | '.join(meta)}]")
            lines.append("  ".join(parts))
            included_repo_count += 1

            if include_readme_summaries:
                summary = (readme_map.get(full_name) or "").strip()
                if summary:
                    lines.append(f"  README summary: {summary}")
                    included_readme_count += 1

            current = "\n".join(lines)
            if len(current) > max_chars:
                # Remove the last added repo block to stay within budget.
                if include_readme_summaries and (readme_map.get(full_name) or "").strip() and lines:
                    lines.pop()
                if lines:
                    lines.pop()
                break

        block = "\n".join(lines)
        clipped_block = self._clip_at_sentence(block, max_chars)
        logger.debug(
            "GitHub context assembled: repos=%s readmes=%s chars=%s/%s include_readmes=%s",
            included_repo_count,
            included_readme_count,
            len(clipped_block),
            max_chars,
            include_readme_summaries,
        )
        return clipped_block


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def build_github_profile_context(max_chars: int = 30000) -> str:
    """
    Convenience function called from main.py.
    Returns an empty string if GITHUB_USER is not set.
    """
    username = os.getenv("GITHUB_USER", "").strip()
    if not username:
        return ""

    token = os.getenv("GITHUB_TOKEN", "").strip() or None
    raw_filter = os.getenv("GITHUB_REPO_FILTER", "").strip()
    repo_filter = [r for r in raw_filter.split(",") if r.strip()] if raw_filter else []

    include_readme_summaries = _env_bool("GITHUB_INCLUDE_README_SUMMARIES", True)
    max_repo_count = _env_int("GITHUB_REPO_MAX_COUNT", 12)
    readme_max_chars = _env_int("GITHUB_README_MAX_CHARS", 1200)

    svc = GitHubService(username=username, token=token, repo_filter=repo_filter or None)
    return svc.build_profile_context_block(
        include_readme_summaries=include_readme_summaries,
        max_repo_count=max_repo_count,
        readme_max_chars=readme_max_chars,
        max_chars=max_chars,
    )
