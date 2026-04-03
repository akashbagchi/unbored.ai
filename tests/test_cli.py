"""Tests for unbored/cli.py"""
import json
import sys
import pytest
from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from unbored.cli import (
    handle_config,
    update_gitignore,
    _check_diff,
    _mask,
)


# ── handle_config ─────────────────────────────────────────────────────────────

def test_handle_config_set_valid_key(monkeypatch, tmp_path):
    from unbored import config
    cfg_dir = tmp_path / "unbored"
    monkeypatch.setattr(config, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config, "CONFIG_FILE", cfg_dir / "config.yaml")

    args = Namespace(config_action="set", key="github_token", value="ghp_test123")
    handle_config(args)

    import yaml
    data = yaml.safe_load((cfg_dir / "config.yaml").read_text())
    assert data["github_token"] == "ghp_test123"


def test_handle_config_set_invalid_key(monkeypatch, capsys):
    with pytest.raises(SystemExit) as exc_info:
        args = Namespace(config_action="set", key="bad_key", value="whatever")
        handle_config(args)
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Unknown config key" in captured.out


def test_handle_config_show(monkeypatch, capsys, tmp_path):
    from unbored import config
    import yaml
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.safe_dump({"github_token": "ghp_abc123xyz"}))
    monkeypatch.setattr(config, "CONFIG_FILE", cfg_file)

    args = Namespace(config_action="show")
    handle_config(args)
    captured = capsys.readouterr()
    assert "github_token" in captured.out
    # Token should be masked
    assert "ghp_abc123xyz" not in captured.out
    assert "****" in captured.out


def test_handle_config_clear(monkeypatch, tmp_path):
    from unbored import config
    import yaml
    cfg_dir = tmp_path / "unbored"
    cfg_file = cfg_dir / "config.yaml"
    monkeypatch.setattr(config, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config, "CONFIG_FILE", cfg_file)

    # Pre-populate config
    cfg_dir.mkdir()
    cfg_file.write_text(yaml.safe_dump({"github_token": "existing"}))

    args = Namespace(config_action="clear")
    handle_config(args)

    data = yaml.safe_load(cfg_file.read_text())
    assert data is None or data == {}


# ── update_gitignore ──────────────────────────────────────────────────────────

def test_update_gitignore_adds_entry(tmp_path):
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("*.pyc\n__pycache__/\n")
    update_gitignore(str(tmp_path))
    content = gitignore.read_text()
    assert ".unbored/" in content


def test_update_gitignore_no_duplicate(tmp_path):
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("*.pyc\n.unbored/\n")
    update_gitignore(str(tmp_path))
    content = gitignore.read_text()
    assert content.count(".unbored/") == 1


def test_update_gitignore_creates_if_missing(tmp_path):
    # No .gitignore exists
    update_gitignore(str(tmp_path))
    gitignore = tmp_path / ".gitignore"
    assert gitignore.exists()
    assert ".unbored/" in gitignore.read_text()


# ── _check_diff ───────────────────────────────────────────────────────────────

def test_check_diff_no_snapshot(tmp_path):
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    status, lines = _check_diff(str(tmp_path), output_dir)
    assert status == "no_snapshot"
    assert lines == 0


def test_check_diff_unchanged(tmp_path):
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    snapshot = {"git_commit": "abc123", "generated_at": "2024-01-01T00:00:00+00:00"}
    (output_dir / "generation_snapshot.json").write_text(json.dumps(snapshot))

    with patch("unbored.cli.subprocess.run") as mock_run:
        # First call: get current HEAD
        mock_run.return_value = MagicMock(returncode=0, stdout="abc123\n")
        status, lines = _check_diff(str(tmp_path), output_dir)

    assert status == "unchanged"
    assert lines == 0


def test_check_diff_changed(tmp_path):
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    snapshot = {"git_commit": "old_commit", "generated_at": "2024-01-01T00:00:00+00:00"}
    (output_dir / "generation_snapshot.json").write_text(json.dumps(snapshot))

    def mock_run_side_effect(cmd, **kwargs):
        mock = MagicMock()
        if "rev-parse" in cmd:
            mock.returncode = 0
            mock.stdout = "new_commit\n"
        elif "diff" in cmd:
            mock.returncode = 0
            mock.stdout = " 3 files changed, 42 insertions(+), 10 deletions(-)\n"
        return mock

    with patch("unbored.cli.subprocess.run", side_effect=mock_run_side_effect):
        status, lines = _check_diff(str(tmp_path), output_dir)

    assert status == "changed"
    assert lines == 52  # 42 insertions + 10 deletions


# ── main: view subcommand ─────────────────────────────────────────────────────

def test_main_view_subcommand(tmp_path, monkeypatch):
    from unbored import cli
    site_dir = tmp_path / ".unbored" / "site"
    docs_dir = site_dir / "docs"
    docs_dir.mkdir(parents=True)
    (docs_dir / "intro.md").write_text("# Intro\n")

    monkeypatch.setattr("os.getcwd", lambda: str(tmp_path))

    with patch("unbored.cli.subprocess.run") as mock_run:
        monkeypatch.setattr(sys, "argv", ["unbored", "view"])
        cli.main()
        mock_run.assert_called_once_with(["npm", "start"], cwd=site_dir)


# ── main: config subcommand routing ──────────────────────────────────────────

def test_main_config_subcommand_routes_to_handler(monkeypatch, tmp_path):
    from unbored import cli, config
    import yaml

    cfg_dir = tmp_path / "unbored"
    monkeypatch.setattr(config, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config, "CONFIG_FILE", cfg_dir / "config.yaml")

    monkeypatch.setattr(sys, "argv", ["unbored", "config", "clear"])
    with patch("unbored.cli.handle_config") as mock_handle:
        cli.main()
        mock_handle.assert_called_once()
