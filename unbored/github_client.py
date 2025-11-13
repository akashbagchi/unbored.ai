from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Iterable, List, Optional, Dict, Any
import datetime as dt
import os

from github import Github, UnknownObjectException, GithubException  # PyGithub

DEFAULT_KEYWORDS = {
    'labels': ['bug', 'documentation', 'docs', 'question', 'help wanted',
                'good first issue', 'setup', 'enhancement', 'feat'],
    'body': ['how do i', 'how to', 'setup', 'install', 'getting started',
                'environment', 'dependency', 'configuration', 'error', 'failed']
}

@dataclass
class IssueLite:
    number: int
    title: str
    state: str
    created_at: str
    closed_at: Optional[str]
    author: Optional[str]
    labels: List[str]
    url: str
    html_url: str
    body: Optional[str]
    comments_count: int

    def to_json(self) -> Dict[str, Any]:
        return asdict(self)

def _iso(t) -> Optional[str]:
    if not t:
        return None
    # ensure naive ISO string
    if isinstance(t, dt.datetime):
        return t.replace(tzinfo=None).isoformat()
    try:
        return str(t)
    except Exception:
        return None

class GitHubClient:
    def __init__(self, token: Optional[str] = None):
        # token can be None for public data; but rate limit is tiny.
        self._gh = Github(login_or_token=token or os.getenv("GITHUB_TOKEN"))

    def fetch_all_issues(
        self,
        repo_full_name: str,
        limit: int,
        include_body: bool = True,
    ) -> List[IssueLite]:
        """
        Fetch last N issues (excluding PRs) in reverse-chronological closed order.
        """
        try:
            repo = self._gh.get_repo(repo_full_name)
        except UnknownObjectException:
            raise ValueError(f"Repository not found: {repo_full_name}")
        except GithubException as e:
            raise RuntimeError(f"GitHub error: {e.data or e.status}")

        issues = repo.get_issues()  # PyGithub lacks sort=closed_at; we’ll slice manually later.

        out: List[IssueLite] = []
        count = 0
        for i in issues:  # most recently updated first
            # Skip PRs (PyGithub: issue.pull_request is not None on PRs)
            # TODO - Optionally give the option to include PRs if the user deems it sufficiently relevant.
            if getattr(i, "pull_request", None):
                continue
            body = i.body or None
            if not include_body:
                body = None
            out.append(
                IssueLite(
                    number=i.number,
                    title=i.title or "",
                    state=i.state or "closed",
                    created_at=_iso(i.created_at),
                    closed_at=_iso(i.closed_at),
                    author=(i.user.login if i.user else None),
                    labels=[l.name for l in (i.labels or [])],
                    url=i.url,
                    html_url=i.html_url,
                    body=body,
                    comments_count=i.comments,
                )
            )
            count += 1
            if count >= limit:
                break

        # Sort by closed_at desc if available; fallback to created_at
        out.sort(key=lambda x: (x.closed_at or x.created_at or ""), reverse=True)
        return out


def keyword_filter(
    issues: Iterable[IssueLite],
    keywords: Iterable[str],
    min_hits: int = 1,
) -> List[Dict[str, Any]]:
    """
    Return issues with keyword scoring. Falls back to all (max 50) issues if no matches.
    """
    kw = [k.lower() for k in keywords if k]

    if not kw:
        results = []
        for i, iss in enumerate(issues):
            if i>=50:
                break
            rec = iss.to_json()
            rec["keyword_hits"] = 0
            results.append(rec)
        results.sort(key = lambda r: r.get("closed_at") or r.get("created_at") or "", reverse=True)
        return results

    results: List[Dict[str, Any]] = []
    all_issues: List[Dict[str, Any]] = []

    for iss in issues:
        hay_title = (iss.title or "").lower()
        hay_body = (iss.body or "")[:40_000].lower()  # cap to keep memory sane
        hay_labels = " ".join(iss.labels).lower()

        hits = 0
        for k in kw:
            if k in hay_title or k in hay_body or k in hay_labels:
                hits += 1

        rec = iss.to_json()
        rec["keyword_hits"] = hits
        all_issues.append(rec)

        if hits >= min_hits:
            results.append(rec)

    # Fallback: no matches
    if not results:
        results = all_issues[:50]

    # sort by hits desc then by closed_at desc
    results.sort(key=lambda r: (r.get("keyword_hits", 0), r.get("closed_at") or r.get("created_at") or ""), reverse=True)
    return results
