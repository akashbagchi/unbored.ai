"""Tests for unbored/github_client.py"""
import datetime
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from github import UnknownObjectException, GithubException

from unbored.github_client import GitHubClient, IssueLite, keyword_filter


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_mock_issue(
    number=1,
    title="Test issue",
    state="closed",
    pull_request=None,
    body="Some body",
    labels=None,
    created_at=None,
    closed_at=None,
    comments=0,
):
    issue = MagicMock()
    issue.pull_request = pull_request
    issue.number = number
    issue.title = title
    issue.state = state
    issue.body = body
    issue.labels = [MagicMock(name=l) for l in (labels or [])]
    issue.created_at = created_at or datetime.datetime(2024, 1, 1)
    issue.closed_at = closed_at
    issue.user = MagicMock(login="testuser")
    issue.url = f"https://api.github.com/repos/owner/repo/issues/{number}"
    issue.html_url = f"https://github.com/owner/repo/issues/{number}"
    issue.comments = comments
    return issue


def _make_client_with_issues(issues):
    with patch("unbored.github_client.Github") as MockGithub:
        mock_repo = MagicMock()
        mock_repo.get_issues.return_value = iter(issues)
        MockGithub.return_value.get_repo.return_value = mock_repo
        client = GitHubClient(token="fake-token")
        client._gh = MockGithub.return_value
        client._gh.get_repo.return_value = mock_repo
        return client


# ── fetch_all_issues ──────────────────────────────────────────────────────────

def test_fetch_all_issues_excludes_prs():
    pr_issue = _make_mock_issue(number=1, title="A PR", pull_request=MagicMock())
    real_issue = _make_mock_issue(number=2, title="A real issue")
    client = _make_client_with_issues([pr_issue, real_issue])
    results = client.fetch_all_issues("owner/repo", limit=10)
    numbers = [r.number for r in results]
    assert 1 not in numbers
    assert 2 in numbers


def test_fetch_all_issues_respects_limit():
    issues = [_make_mock_issue(number=i) for i in range(20)]
    client = _make_client_with_issues(issues)
    results = client.fetch_all_issues("owner/repo", limit=5)
    assert len(results) == 5


def test_fetch_all_issues_repo_not_found():
    with patch("unbored.github_client.Github") as MockGithub:
        MockGithub.return_value.get_repo.side_effect = UnknownObjectException(
            404, {"message": "Not Found"}, {}
        )
        client = GitHubClient(token="fake-token")
        with pytest.raises(ValueError, match="Repository not found"):
            client.fetch_all_issues("owner/nonexistent", limit=10)


def test_fetch_all_issues_api_error():
    with patch("unbored.github_client.Github") as MockGithub:
        MockGithub.return_value.get_repo.side_effect = GithubException(
            500, {"message": "Internal Server Error"}, {}
        )
        client = GitHubClient(token="fake-token")
        with pytest.raises(RuntimeError, match="GitHub error"):
            client.fetch_all_issues("owner/repo", limit=10)


# ── keyword_filter ────────────────────────────────────────────────────────────

def _make_issue_lite(**kwargs):
    defaults = dict(
        number=1, title="Test issue", state="open",
        created_at="2024-01-01T00:00:00", closed_at=None,
        author="user", labels=[], url="http://example.com",
        html_url="http://example.com", body=None, comments_count=0,
    )
    defaults.update(kwargs)
    return IssueLite(**defaults)


def test_keyword_filter_scores_title_match():
    issue = _make_issue_lite(title="setup and installation guide")
    results = keyword_filter([issue], keywords=["setup"])
    assert len(results) == 1
    assert results[0]["keyword_hits"] >= 1


def test_keyword_filter_scores_label_match():
    issue = _make_issue_lite(title="random title", labels=["bug"])
    results = keyword_filter([issue], keywords=["bug"])
    assert results[0]["keyword_hits"] >= 1


def test_keyword_filter_fallback_no_matches():
    issues = [_make_issue_lite(number=i, title=f"Issue {i}") for i in range(60)]
    results = keyword_filter(issues, keywords=["xyz-never-matches"])
    assert len(results) <= 50


def test_keyword_filter_sorting():
    issue_a = _make_issue_lite(number=1, title="setup docs", closed_at="2024-01-01T00:00:00")
    issue_b = _make_issue_lite(number=2, title="setup install help", closed_at="2024-06-01T00:00:00")
    results = keyword_filter([issue_a, issue_b], keywords=["setup", "help"])
    # issue_b matches 2 keywords, should rank first
    assert results[0]["number"] == 2


def test_keyword_filter_empty_keywords_returns_issues():
    issues = [_make_issue_lite(number=i) for i in range(5)]
    results = keyword_filter(issues, keywords=[])
    assert len(results) == 5
    for r in results:
        assert r["keyword_hits"] == 0


# ── IssueLite.to_json ─────────────────────────────────────────────────────────

def test_issue_lite_to_json():
    issue = _make_issue_lite(
        number=42,
        title="Fix the bug",
        state="closed",
        created_at="2024-01-15T10:00:00",
        closed_at="2024-01-20T12:00:00",
        author="dev",
        labels=["bug", "help wanted"],
        url="https://api.github.com/repos/o/r/issues/42",
        html_url="https://github.com/o/r/issues/42",
        body="Description here",
        comments_count=3,
    )
    data = issue.to_json()
    assert data["number"] == 42
    assert data["title"] == "Fix the bug"
    assert data["state"] == "closed"
    assert data["labels"] == ["bug", "help wanted"]
    assert data["comments_count"] == 3
    assert data["body"] == "Description here"
