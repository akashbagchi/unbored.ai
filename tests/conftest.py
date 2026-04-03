"""Shared fixtures for unbored.ai test suite."""
import json
import pytest


@pytest.fixture
def tmp_repo(tmp_path):
    """Minimal fake repo with a single Python file."""
    (tmp_path / "main.py").write_text("# entry point\n")
    return tmp_path


@pytest.fixture
def sample_graph():
    return {
        "nodes": [{"id": "a.py", "label": "a.py"}, {"id": "b.py", "label": "b.py"}],
        "edges": [{"source": "a.py", "target": "b.py"}],
    }


@pytest.fixture
def mock_scan_data():
    return {
        "root": "/tmp/repo",
        "ascii_tree": "repo\n└─ main.py",
        "tree": [{"path": "main.py", "type": "file", "size": 100, "lang": "Python"}],
        "ecosystem": {"primary": "python", "secondaries": [], "frameworks": []},
        "key_files": {},
        "folder_summaries": [],
        "signals": {
            "has_tests": False,
            "has_ci": False,
            "has_containerization": False,
            "has_migrations": False,
        },
    }


@pytest.fixture
def mock_pages():
    return [
        {
            "filename": "intro.md",
            "title": "Overview",
            "sidebar_position": 1,
            "content": "# Overview\n\nProject overview content.",
        },
        {
            "filename": "module.md",
            "title": "Core Module",
            "sidebar_position": 2,
            "content": "# Core Module\n\nModule content.",
        },
    ]
