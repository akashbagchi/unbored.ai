"""Tests for unbored/generator.py"""
import json
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from unbored.generator import send_to_claude, update_existing_site, generate_all


# ── helpers ───────────────────────────────────────────────────────────────────

def _mock_anthropic_response(text):
    """Build a mock anthropic response object."""
    mock_content = MagicMock()
    mock_content.text = text
    mock_response = MagicMock()
    mock_response.content = [mock_content]
    return mock_response


def _make_scan_file(tmp_path):
    scan_file = tmp_path / "scan.jsonl"
    scan_file.write_text('{"section": "meta", "root": "/tmp/repo"}\n')
    return scan_file


SAMPLE_PAGES = json.dumps([
    {"filename": "intro.md", "title": "Overview", "sidebar_position": 1, "content": "# Overview\n\nContent."},
    {"filename": "module.md", "title": "Module", "sidebar_position": 2, "content": "# Module\n\nContent."},
])


# ── send_to_claude ────────────────────────────────────────────────────────────

def test_send_to_claude_returns_pages(tmp_path):
    scan_file = _make_scan_file(tmp_path)
    with patch("unbored.generator.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _mock_anthropic_response(SAMPLE_PAGES)
        pages = send_to_claude(str(scan_file), "my-repo", api_key="test-key")
    assert isinstance(pages, list)
    assert len(pages) == 2
    assert pages[0]["filename"] == "intro.md"


def test_send_to_claude_strips_markdown_fence(tmp_path):
    scan_file = _make_scan_file(tmp_path)
    fenced = f"```json\n{SAMPLE_PAGES}\n```"
    with patch("unbored.generator.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _mock_anthropic_response(fenced)
        pages = send_to_claude(str(scan_file), "my-repo", api_key="test-key")
    assert isinstance(pages, list)
    assert len(pages) == 2


def test_send_to_claude_partial_json_recovery(tmp_path):
    scan_file = _make_scan_file(tmp_path)
    # Truncated JSON: only first object is complete
    truncated = '[{"filename": "intro.md", "title": "Intro", "sidebar_position": 1, "content": "# Intro"}, {"filename": "cut'
    with patch("unbored.generator.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _mock_anthropic_response(truncated)
        pages = send_to_claude(str(scan_file), "my-repo", api_key="test-key")
    # Should recover at least the first complete page
    assert pages is not None
    assert len(pages) >= 1
    assert pages[0]["filename"] == "intro.md"


def test_send_to_claude_missing_api_key(tmp_path, monkeypatch):
    scan_file = _make_scan_file(tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # load_config is imported inline inside send_to_claude; patch at source module
    with patch("unbored.config.load_config", return_value={}):
        result = send_to_claude(str(scan_file), "my-repo", api_key=None)
    assert result is None


def test_send_to_claude_auth_error(tmp_path):
    scan_file = _make_scan_file(tmp_path)
    # Create a dummy AuthenticationError class that generator.py will catch
    with patch("unbored.generator.anthropic") as mock_anthropic:
        AuthErr = type("AuthenticationError", (Exception,), {})
        mock_anthropic.AuthenticationError = AuthErr
        mock_anthropic.RateLimitError = type("RateLimitError", (Exception,), {})
        mock_anthropic.Anthropic.return_value.messages.create.side_effect = AuthErr()
        result = send_to_claude(str(scan_file), "my-repo", api_key="bad-key")
    assert result is None


def test_send_to_claude_rate_limit_error(tmp_path):
    scan_file = _make_scan_file(tmp_path)
    with patch("unbored.generator.anthropic") as mock_anthropic:
        RateLimitErr = type("RateLimitError", (Exception,), {})
        mock_anthropic.RateLimitError = RateLimitErr
        mock_anthropic.AuthenticationError = type("AuthenticationError", (Exception,), {})
        mock_anthropic.Anthropic.return_value.messages.create.side_effect = RateLimitErr()
        result = send_to_claude(str(scan_file), "my-repo", api_key="test-key")
    assert result is None


# ── update_existing_site ──────────────────────────────────────────────────────

def _make_site(tmp_path):
    site_dir = tmp_path / "site"
    docs_dir = site_dir / "docs"
    docs_dir.mkdir(parents=True)
    return site_dir, docs_dir


def test_update_existing_site_writes_markdown(tmp_path, mock_pages):
    site_dir, docs_dir = _make_site(tmp_path)
    update_existing_site(mock_pages, "my-repo", str(site_dir))
    written = list(docs_dir.glob("*.md"))
    assert len(written) == 2
    filenames = {f.name for f in written}
    assert "intro.md" in filenames
    assert "module.md" in filenames


def test_update_existing_site_clears_old_files(tmp_path, mock_pages):
    site_dir, docs_dir = _make_site(tmp_path)
    # Pre-existing file that should be removed
    old_file = docs_dir / "old_page.md"
    old_file.write_text("old content")
    update_existing_site(mock_pages, "my-repo", str(site_dir))
    assert not old_file.exists()


def test_update_existing_site_intro_gets_root_slug(tmp_path, mock_pages):
    site_dir, docs_dir = _make_site(tmp_path)
    update_existing_site(mock_pages, "my-repo", str(site_dir))
    intro_content = (docs_dir / "intro.md").read_text()
    assert "slug: /" in intro_content


def test_update_existing_site_updates_config_ts(tmp_path, mock_pages):
    site_dir, docs_dir = _make_site(tmp_path)
    config_path = site_dir / "docusaurus.config.ts"
    config_path.write_text("title: 'unbored - Claude Builder HackASU',\ntagline: 'Turn any repo into a self-explaining codebase',\n")
    update_existing_site(mock_pages, "my-repo", str(site_dir))
    updated = config_path.read_text()
    assert "my-repo Documentation" in updated


# ── generate_all ──────────────────────────────────────────────────────────────

@pytest.fixture
def patched_generate_all(tmp_path, mock_pages, mock_scan_data):
    """Context that patches heavy dependencies for generate_all tests."""
    output_dir = str(tmp_path / "outputs")

    with patch("unbored.generator.scan_repo", return_value=mock_scan_data), \
         patch("unbored.generator.build_dependency_graph", return_value={"nodes": [], "edges": []}), \
         patch("unbored.generator.generate_graph_positions"), \
         patch("unbored.generator.send_to_claude", return_value=mock_pages):
        yield output_dir


def test_generate_all_skip_github(tmp_path, mock_pages, mock_scan_data, patched_generate_all):
    output_dir = patched_generate_all
    with patch("unbored.generator.GitHubClient") as MockGH:
        generate_all(
            repo_path=str(tmp_path),
            output_dir=output_dir,
            gh_repo="owner/repo",
            skip_github=True,
        )
        MockGH.return_value.fetch_all_issues.assert_not_called()


def test_generate_all_writes_scan_jsonl(tmp_path, patched_generate_all):
    output_dir = patched_generate_all
    generate_all(repo_path=str(tmp_path), output_dir=output_dir, skip_github=True)
    assert (Path(output_dir) / "scan.jsonl").exists()


def test_generate_all_writes_graph_json(tmp_path, patched_generate_all):
    output_dir = patched_generate_all
    generate_all(repo_path=str(tmp_path), output_dir=output_dir, skip_github=True)
    assert (Path(output_dir) / "scan.jsonl.graph.json").exists()
