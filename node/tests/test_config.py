from __future__ import annotations

from pathlib import Path

import pytest

from bridge.config import ConfigError, load_config

_MINIMAL = """
BRIDGE_SERVER_URL=http://localhost:8090/
BRIDGE_NODE_ID=1
BRIDGE_SECRET=abc123
BRIDGE_SITE_SLUG=pornic
BRIDGE_DB_PATH=/tmp/birdnet.db
BRIDGE_CLIPS_DIR=/tmp/clips
BRIDGE_STATE_FILE=/tmp/state.json
"""


def _write(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "pornic.env"
    path.write_text(content, encoding="utf-8")
    return path


def test_load_config_minimal_applies_defaults(tmp_path: Path) -> None:
    config = load_config(_write(tmp_path, _MINIMAL))
    assert config.server_url == "http://localhost:8090"  # slash final retiré
    assert config.node_id == 1
    assert config.node_api == "http://localhost:8080"
    assert config.sync_interval_s == 20.0
    assert config.batch_size == 200
    assert config.node_readonly is False
    assert config.api_base_url == "http://localhost:8090/api/v1"


def test_load_config_missing_required_lists_all_missing(tmp_path: Path) -> None:
    path = _write(tmp_path, "BRIDGE_SERVER_URL=http://localhost:8090\n")
    with pytest.raises(ConfigError) as exc_info:
        load_config(path)
    message = str(exc_info.value)
    assert "BRIDGE_NODE_ID" in message
    assert "BRIDGE_SECRET" in message


def test_load_config_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(tmp_path / "absent.env")


def test_load_config_rejects_batch_size_out_of_range(tmp_path: Path) -> None:
    path = _write(tmp_path, _MINIMAL + "BRIDGE_BATCH_SIZE=500\n")
    with pytest.raises(ConfigError, match="BRIDGE_BATCH_SIZE"):
        load_config(path)


def test_load_config_parses_node_readonly_flag(tmp_path: Path) -> None:
    path = _write(tmp_path, _MINIMAL + "BRIDGE_NODE_READONLY=1\n")
    assert load_config(path).node_readonly is True


def test_load_config_rejects_line_without_equals(tmp_path: Path) -> None:
    path = _write(tmp_path, _MINIMAL + "ceci-nest-pas-une-ligne-valide\n")
    with pytest.raises(ConfigError):
        load_config(path)


def test_load_config_ignores_comments_and_blank_lines(tmp_path: Path) -> None:
    content = _MINIMAL + "\n# un commentaire\n\nBRIDGE_LOG_LEVEL=DEBUG\n"
    config = load_config(_write(tmp_path, content))
    assert config.log_level == "DEBUG"
