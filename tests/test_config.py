"""Tests for unbored/config.py"""
import stat
import yaml
import pytest


def test_load_config_missing_file(monkeypatch, tmp_path):
    from unbored import config
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "nonexistent.yaml")
    assert config.load_config() == {}


def test_load_config_returns_dict(monkeypatch, tmp_path):
    from unbored import config
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.safe_dump({"github_token": "tok123"}))
    monkeypatch.setattr(config, "CONFIG_FILE", cfg_file)
    result = config.load_config()
    assert result == {"github_token": "tok123"}


def test_save_config_creates_file(monkeypatch, tmp_path):
    from unbored import config
    cfg_dir = tmp_path / "unbored"
    monkeypatch.setattr(config, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config, "CONFIG_FILE", cfg_dir / "config.yaml")
    config.save_config({"key": "value"})
    cfg_file = cfg_dir / "config.yaml"
    assert cfg_file.exists()
    data = yaml.safe_load(cfg_file.read_text())
    assert data == {"key": "value"}


def test_save_config_permissions(monkeypatch, tmp_path):
    from unbored import config
    cfg_dir = tmp_path / "unbored"
    monkeypatch.setattr(config, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config, "CONFIG_FILE", cfg_dir / "config.yaml")
    config.save_config({})
    dir_mode = stat.S_IMODE(cfg_dir.stat().st_mode)
    file_mode = stat.S_IMODE((cfg_dir / "config.yaml").stat().st_mode)
    assert dir_mode == 0o700
    assert file_mode == 0o600


def test_resolve_token_cli_wins(monkeypatch, tmp_path):
    from unbored import config
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "nonexistent.yaml")
    monkeypatch.delenv("MY_TOKEN", raising=False)
    result = config.resolve_token("cli-value", "MY_TOKEN", "some_key")
    assert result == "cli-value"


def test_resolve_token_env_wins_over_config(monkeypatch, tmp_path):
    from unbored import config
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.safe_dump({"some_key": "config-value"}))
    monkeypatch.setattr(config, "CONFIG_FILE", cfg_file)
    monkeypatch.setenv("MY_TOKEN", "env-value")
    result = config.resolve_token(None, "MY_TOKEN", "some_key")
    assert result == "env-value"


def test_resolve_token_config_fallback(monkeypatch, tmp_path):
    from unbored import config
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.safe_dump({"some_key": "config-value"}))
    monkeypatch.setattr(config, "CONFIG_FILE", cfg_file)
    monkeypatch.delenv("MY_TOKEN", raising=False)
    result = config.resolve_token(None, "MY_TOKEN", "some_key")
    assert result == "config-value"


def test_resolve_token_all_missing(monkeypatch, tmp_path):
    from unbored import config
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "nonexistent.yaml")
    monkeypatch.delenv("MY_TOKEN", raising=False)
    result = config.resolve_token(None, "MY_TOKEN", "some_key")
    assert result is None
