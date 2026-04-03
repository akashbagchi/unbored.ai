"""
Configuration management for unbored.AI
Stores tokens and settings in ~/.unbored/config.yaml
"""

import os
from pathlib import Path

import yaml

CONFIG_DIR = Path.home() / ".unbored"
CONFIG_FILE = CONFIG_DIR / "config.yaml"


def load_config() -> dict:
    """Load config from ~/.unbored/config.yaml. Returns empty dict if missing."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE) as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_config(data: dict):
    """Write config to ~/.unbored/config.yaml, creating dir if needed."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.chmod(0o700)  # user-only directory
    with open(CONFIG_FILE, "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False)
    CONFIG_FILE.chmod(0o600)  # user-only read/write


def resolve_token(cli_value: str | None, env_var: str, config_key: str) -> str | None:
    """
    Resolve a token with priority: CLI flag > env var > config file.

    Args:
        cli_value: Value passed via CLI flag (highest priority)
        env_var: Environment variable name to check
        config_key: Key in config.yaml to check (lowest priority)

    Returns:
        Resolved token string, or None if not found anywhere
    """
    if cli_value:
        return cli_value
    env_value = os.environ.get(env_var)
    if env_value:
        return env_value
    config = load_config()
    return config.get(config_key)
