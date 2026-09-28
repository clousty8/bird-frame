from __future__ import annotations

from pathlib import Path

from bridge.state import load_state, save_state


def test_load_state_missing_file_returns_zero_cursor(tmp_path: Path) -> None:
    state = load_state(tmp_path / "absent.json")
    assert state.cursor == 0
    assert state.updated_at is None


def test_save_then_load_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "state" / "pornic.json"
    save_state(path, 4512)
    state = load_state(path)
    assert state.cursor == 4512
    assert state.updated_at is not None


def test_load_state_corrupt_file_falls_back_to_zero(tmp_path: Path) -> None:
    path = tmp_path / "pornic.json"
    path.write_text("ceci n'est pas du JSON", encoding="utf-8")
    state = load_state(path)
    assert state.cursor == 0


def test_save_state_is_atomic_no_temp_file_left(tmp_path: Path) -> None:
    path = tmp_path / "pornic.json"
    save_state(path, 1)
    save_state(path, 2)
    leftovers = list(tmp_path.glob(".*"))
    assert leftovers == []
    assert load_state(path).cursor == 2
