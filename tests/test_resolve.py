from __future__ import annotations

import pytest
from pathlib import Path

from frictionmap.cli import resolve_sessions_dir


def _slug(path: Path) -> str:
    return str(path).replace("/", "-")


def _make_sessions_dir(home: Path, for_project: Path) -> Path:
    sessions = home / ".claude" / "projects" / _slug(for_project)
    sessions.mkdir(parents=True)
    return sessions


@pytest.fixture
def fake_home(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


def test_direct_match(fake_home, tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    expected = _make_sessions_dir(fake_home, proj)

    assert resolve_sessions_dir(proj) == expected


def test_walks_up_to_parent(fake_home, tmp_path):
    proj = tmp_path / "proj"
    deep = proj / "sub" / "deep"
    deep.mkdir(parents=True)
    expected = _make_sessions_dir(fake_home, proj)

    assert resolve_sessions_dir(deep) == expected


def test_nearest_match_wins(fake_home, tmp_path):
    proj = tmp_path / "proj"
    sub = proj / "sub"
    sub.mkdir(parents=True)
    _make_sessions_dir(fake_home, proj)
    expected_sub = _make_sessions_dir(fake_home, sub)

    assert resolve_sessions_dir(sub) == expected_sub


def test_no_match_raises(fake_home, tmp_path):
    nowhere = tmp_path / "nowhere"
    nowhere.mkdir()

    with pytest.raises(FileNotFoundError) as excinfo:
        resolve_sessions_dir(nowhere)

    message = str(excinfo.value)
    assert "No Claude Code sessions found" in message
    # The final checked path must be for "/" — the root slug "-" — which
    # guards against a loop that terminates before checking the filesystem root.
    root_candidate = fake_home / ".claude" / "projects" / "-"
    assert str(root_candidate) in message
    assert message.rstrip().splitlines()[-1] == (
        "cd to a project where you've used Claude Code and try again."
    )
