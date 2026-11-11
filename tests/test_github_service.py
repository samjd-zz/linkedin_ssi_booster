"""Offline tests for GitHub profile-context fetching, caching, and formatting."""

import base64
import json
import logging
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
import requests

import services.github_service as github_service
from services.github_service import GitHubService, build_github_profile_context


class FakeResponse:
    def __init__(
        self,
        payload: Any = None,
        *,
        status_code: int = 200,
        error: Exception | None = None,
    ) -> None:
        self.payload = payload
        self.status_code = status_code
        self.error = error

    def json(self) -> Any:
        return self.payload

    def raise_for_status(self) -> None:
        if self.error:
            raise self.error


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.headers: dict[str, str] = {}
        self.responses = iter(responses)
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append((url, kwargs))
        return next(self.responses)


def _repo(name: str, **kwargs: Any) -> dict[str, Any]:
    return {
        "name": name,
        "full_name": f"owner/{name}",
        "owner": {"login": "owner"},
        **kwargs,
    }


def test_service_sets_github_request_headers() -> None:
    service = GitHubService("octocat")

    assert service._session.headers["Accept"] == "application/vnd.github+json"
    assert service._session.headers["X-GitHub-Api-Version"] == "2022-11-28"


def test_repo_filter_is_normalized_and_empty_entries_are_ignored() -> None:
    service = GitHubService("octocat", repo_filter=["  Python ", "AI", ""])

    assert service.repo_filter == ["python", "ai", ""]


def test_fetch_repos_filters_forks_and_sends_expected_request() -> None:
    service = GitHubService("octocat")
    session = FakeSession([FakeResponse([
        _repo("kept"),
        _repo("forked", fork=True),
    ])])
    service._session = session

    repos = service._fetch_repos()

    assert [repo["name"] for repo in repos] == ["kept"]
    assert session.calls == [(
        "https://api.github.com/users/octocat/repos",
        {
            "params": {
                "type": "public",
                "sort": "updated",
                "per_page": 100,
                "page": 1,
            },
            "timeout": 10,
        },
    )]


def test_fetch_repos_paginates_full_pages() -> None:
    service = GitHubService("octocat")
    first_page = [_repo(f"repo-{index}") for index in range(100)]
    session = FakeSession([FakeResponse(first_page), FakeResponse([_repo("last")])])
    service._session = session

    repos = service._fetch_repos()

    assert len(repos) == 101
    assert session.calls[0][1]["params"]["page"] == 1
    assert session.calls[1][1]["params"]["page"] == 2


def test_fetch_repos_stops_when_api_returns_empty_page() -> None:
    service = GitHubService("octocat")
    session = FakeSession([FakeResponse([])])
    service._session = session

    assert service._fetch_repos() == []
    assert len(session.calls) == 1


def test_fetch_repos_raises_for_missing_user_and_http_errors() -> None:
    service = GitHubService("missing-user")
    service._session = FakeSession([FakeResponse(status_code=404)])

    with pytest.raises(ValueError, match="GitHub user not found: missing-user"):
        service._fetch_repos()

    service._session = FakeSession([
        FakeResponse(error=requests.HTTPError("rate limited")),
    ])
    with pytest.raises(requests.HTTPError, match="rate limited"):
        service._fetch_repos()


def test_repo_cache_loads_fresh_data_and_rejects_stale_or_invalid_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_path = tmp_path / "repos.json"
    monkeypatch.setattr(github_service, "CACHE_FILE", cache_path)
    monkeypatch.setattr(github_service.time, "time", lambda: 100_000)
    service = GitHubService("octocat")
    repos = [_repo("cached")]

    assert service._load_cache() is None

    cache_path.write_text(json.dumps({"fetched_at": 99_000, "repos": repos}), encoding="utf-8")
    assert service._load_cache() == repos

    cache_path.write_text(json.dumps({"fetched_at": 0, "repos": repos}), encoding="utf-8")
    assert service._load_cache() is None

    cache_path.write_text("{", encoding="utf-8")
    assert service._load_cache() is None

    cache_path.write_text(json.dumps({"fetched_at": 9_000}), encoding="utf-8")
    assert service._load_cache() is None


def test_get_repos_uses_fresh_cache_without_requesting_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_path = tmp_path / "repos.json"
    repos = [_repo("cached")]
    cache_path.write_text(
        json.dumps({"fetched_at": 10_000, "repos": repos}), encoding="utf-8",
    )
    monkeypatch.setattr(github_service, "CACHE_FILE", cache_path)
    monkeypatch.setattr(github_service.time, "time", lambda: 10_001)
    service = GitHubService("octocat")
    service._fetch_repos = Mock(side_effect=AssertionError("unexpected API request"))

    assert service.get_repos() == repos
    service._fetch_repos.assert_not_called()


def test_get_repos_fetches_and_saves_when_cache_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_path = tmp_path / "repos.json"
    monkeypatch.setattr(github_service, "CACHE_FILE", cache_path)
    service = GitHubService("octocat")
    service._fetch_repos = Mock(return_value=[_repo("fresh")])

    assert service.get_repos() == [_repo("fresh")]
    assert json.loads(cache_path.read_text(encoding="utf-8"))["repos"] == [_repo("fresh")]


def test_readme_cache_loads_fresh_dict_and_rejects_invalid_shapes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_path = tmp_path / "readmes.json"
    monkeypatch.setattr(github_service, "README_CACHE_FILE", cache_path)
    monkeypatch.setattr(github_service.time, "time", lambda: 200_000)
    service = GitHubService("octocat")

    assert service._load_readme_cache() == {}
    cache_path.write_text(
        json.dumps({"fetched_at": 199_000, "readmes": {"owner/repo": "summary"}}),
        encoding="utf-8",
    )
    assert service._load_readme_cache() == {"owner/repo": "summary"}

    cache_path.write_text(
        json.dumps({"fetched_at": 199_000, "readmes": []}), encoding="utf-8",
    )
    assert service._load_readme_cache() == {}
    cache_path.write_text("{", encoding="utf-8")
    assert service._load_readme_cache() == {}
    cache_path.write_text(json.dumps({"fetched_at": 0, "readmes": {"old": "value"}}), encoding="utf-8")
    assert service._load_readme_cache() == {}


def test_markdown_cleanup_removes_code_images_and_formatting() -> None:
    markdown = (
        "# Project\n\n"
        "A [useful link](https://example.test) and `inline code`.\n\n"
        "![diagram](image.png)\n\n"
        "```python\nignored()\n```\n\n"
        "* item one\n+ item two\n\n\nDone."
    )

    plain = GitHubService._markdown_to_text(markdown)

    assert plain == "Project\n\nA useful link and inline code.\n\n- item one\n- item two\n\nDone."


@pytest.mark.parametrize(
    ("text", "max_chars", "expected"),
    [
        ("Short sentence.", 40, "Short sentence."),
        ("First sentence. Second sentence continues", 25, "First sentence."),
        ("Words with no sentence boundary here", 15, "Words with no"),
        ("abcdefghijklmnopqrstuvwxyz", 10, "abcdefghij"),
    ],
)
def test_clip_at_sentence_respects_limit_and_prefers_sentence_boundary(
    text: str, max_chars: int, expected: str,
) -> None:
    assert GitHubService._clip_at_sentence(text, max_chars) == expected


def test_fetch_readme_summary_decodes_markdown_and_handles_unavailable_payloads() -> None:
    service = GitHubService("octocat")
    markdown = "# Repo\n\nA useful README sentence."
    encoded = base64.b64encode(markdown.encode()).decode()

    service._session = FakeSession([FakeResponse({"content": encoded})])
    assert service._fetch_readme_summary("owner", "repo", 100) == (
        "Repo\n\nA useful README sentence."
    )

    service._session = FakeSession([FakeResponse(status_code=404)])
    assert service._fetch_readme_summary("owner", "missing", 100) == ""

    service._session = FakeSession([FakeResponse({"content": "", "encoding": "base64"})])
    assert service._fetch_readme_summary("owner", "empty", 100) == ""

    service._session = FakeSession([FakeResponse({"content": encoded, "encoding": "utf-8"})])
    assert service._fetch_readme_summary("owner", "wrong-encoding", 100) == ""


def test_fetch_readme_summary_returns_empty_for_invalid_base64_or_http_error() -> None:
    service = GitHubService("octocat")
    service._session = FakeSession([FakeResponse({"content": "not-base64???"})])
    assert service._fetch_readme_summary("owner", "bad-content", 100) == ""

    service._session = FakeSession([
        FakeResponse(error=requests.HTTPError("failed")),
    ])
    with pytest.raises(requests.HTTPError, match="failed"):
        service._fetch_readme_summary("owner", "repo", 100)


def test_get_readme_summaries_uses_cache_and_skips_incomplete_repo_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_path = tmp_path / "readmes.json"
    monkeypatch.setattr(github_service, "README_CACHE_FILE", cache_path)
    monkeypatch.setattr(github_service.time, "time", lambda: 30_000)
    cache_path.write_text(json.dumps({
        "fetched_at": 29_000,
        "readmes": {"owner/cached": "saved summary"},
    }), encoding="utf-8")
    service = GitHubService("fallback-owner")
    service._fetch_readme_summary = Mock(return_value="fetched summary")

    summaries = service._get_readme_summaries([
        _repo("cached"),
        _repo("fresh", owner={"login": "contributor"}),
        {"full_name": "owner/no-name"},
        {"name": "no-full-name"},
    ], 100)

    assert summaries == {
        "owner/cached": "saved summary",
        "owner/fresh": "fetched summary",
    }
    service._fetch_readme_summary.assert_called_once_with("contributor", "fresh", 100)


def test_get_readme_summaries_caches_fetch_failures_as_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    cache_path = tmp_path / "readmes.json"
    monkeypatch.setattr(github_service, "README_CACHE_FILE", cache_path)
    monkeypatch.setattr(github_service.time, "time", lambda: 40_000)
    service = GitHubService("octocat")
    service._fetch_readme_summary = Mock(side_effect=requests.Timeout("timed out"))

    with caplog.at_level(logging.DEBUG):
        summaries = service._get_readme_summaries([_repo("repo")], 100)

    assert summaries == {"owner/repo": ""}
    assert "README fetch failed for owner/repo" in caplog.text
    assert json.loads(cache_path.read_text(encoding="utf-8"))["readmes"] == summaries


def test_build_context_filters_repositories_and_formats_readme_summary() -> None:
    service = GitHubService("octocat", repo_filter=["selected"])
    service.get_repos = Mock(return_value=[
        _repo("selected", description="  Helpful project  ", language="Python",
              topics=["ai", "retrieval"], stargazers_count=4),
        _repo("excluded"),
    ])
    service._get_readme_summaries = Mock(return_value={
        "owner/selected": "A concise summary.",
    })

    block = service.build_profile_context_block(max_repo_count=5)

    assert "GitHub projects (use these as real reference points when relevant):" in block
    assert "- selected  Helpful project  [Python | topics: ai, retrieval | 4 stars]" in block
    assert "README summary: A concise summary." in block
    assert "excluded" not in block
    service._get_readme_summaries.assert_called_once()


def test_build_context_without_readmes_respects_repo_limit_and_empty_results() -> None:
    service = GitHubService("octocat")
    service.get_repos = Mock(return_value=[
        _repo("first", description=None, language=None, topics=None, stargazers_count=0),
        _repo("second"),
    ])
    service._get_readme_summaries = Mock(side_effect=AssertionError("README fetch disabled"))

    block = service.build_profile_context_block(
        include_readme_summaries=False, max_repo_count=1,
    )

    assert "- first" in block
    assert "second" not in block
    service._get_readme_summaries.assert_not_called()
    assert service.build_profile_context_block(
        include_readme_summaries=False, max_repo_count=0,
    ) == ""


def test_build_context_stays_within_budget_and_skips_failed_repo_fetch(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = GitHubService("octocat")
    service.get_repos = Mock(return_value=[
        _repo("large", description="A" * 200),
        _repo("unreachable"),
    ])

    block = service.build_profile_context_block(
        include_readme_summaries=False, max_chars=90,
    )
    assert len(block) <= 90
    assert "unreachable" not in block

    service.get_repos = Mock(side_effect=requests.Timeout("offline"))
    with caplog.at_level(logging.WARNING):
        assert service.build_profile_context_block() == ""
    assert "GitHub fetch failed — skipping repo context: offline" in caplog.text


def test_build_context_removes_readme_and_repo_when_together_over_budget() -> None:
    service = GitHubService("octocat")
    service.get_repos = Mock(return_value=[_repo("large")])
    service._get_readme_summaries = Mock(return_value={
        "owner/large": "A long README summary that pushes the context over the limit.",
    })

    block = service.build_profile_context_block(max_chars=90)

    assert len(block) <= 90
    assert "README summary" not in block
    assert "- large" not in block


@pytest.mark.parametrize(
    ("raw", "default", "expected"),
    [
        ("", True, True),
        (" YES ", False, True),
        ("on", False, True),
        ("1", False, True),
        ("no", True, False),
        ("anything", False, False),
    ],
)
def test_env_bool_parses_supported_values(raw: str, default: bool, expected: bool) -> None:
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("TEST_GITHUB_BOOL", raw)
        assert github_service._env_bool("TEST_GITHUB_BOOL", default) is expected


@pytest.mark.parametrize(
    ("raw", "default", "expected"),
    [("", 12, 12), (" 5 ", 12, 5), ("invalid", 12, 12)],
)
def test_env_int_parses_or_defaults(raw: str, default: int, expected: int) -> None:
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("TEST_GITHUB_INT", raw)
        assert github_service._env_int("TEST_GITHUB_INT", default) == expected


def test_build_github_profile_context_reads_environment_and_forwards_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_USER", "  octocat  ")
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("GITHUB_REPO_FILTER", "alpha, beta")
    monkeypatch.setenv("GITHUB_INCLUDE_README_SUMMARIES", "false")
    monkeypatch.setenv("GITHUB_REPO_MAX_COUNT", "4")
    monkeypatch.setenv("GITHUB_README_MAX_CHARS", "500")
    service = Mock()
    service.build_profile_context_block.return_value = "profile context"
    monkeypatch.setattr(github_service, "GitHubService", Mock(return_value=service))

    result = build_github_profile_context(max_chars=1234)

    assert result == "profile context"
    github_service.GitHubService.assert_called_once_with(
        username="octocat", token="token", repo_filter=["alpha", " beta"],
    )
    service.build_profile_context_block.assert_called_once_with(
        include_readme_summaries=False,
        max_repo_count=4,
        readme_max_chars=500,
        max_chars=1234,
    )


def test_build_github_profile_context_defaults_invalid_settings_and_skips_without_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_USER", raising=False)
    assert build_github_profile_context() == ""

    monkeypatch.setenv("GITHUB_USER", "octocat")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPO_FILTER", raising=False)
    monkeypatch.setenv("GITHUB_INCLUDE_README_SUMMARIES", "invalid")
    monkeypatch.setenv("GITHUB_REPO_MAX_COUNT", "invalid")
    monkeypatch.setenv("GITHUB_README_MAX_CHARS", "invalid")
    service = Mock()
    service.build_profile_context_block.return_value = ""
    monkeypatch.setattr(github_service, "GitHubService", Mock(return_value=service))

    assert build_github_profile_context() == ""
    github_service.GitHubService.assert_called_once_with(
        username="octocat", token=None, repo_filter=None,
    )
    service.build_profile_context_block.assert_called_once_with(
        include_readme_summaries=False,
        max_repo_count=12,
        readme_max_chars=1200,
        max_chars=30000,
    )
