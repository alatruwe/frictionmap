from __future__ import annotations

import json
from pathlib import Path

import pytest

from frictionmap.cli import main


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


def _event(session_id: str, uuid: str, ev_type: str = "ai-title") -> dict:
    return {
        "type": ev_type,
        "sessionId": session_id,
        "uuid": uuid,
        "parentUuid": None,
        "timestamp": "2026-04-22T00:00:00Z",
        "cwd": "/proj",
    }


def test_scan_writes_report_html(fake_home, tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    proj.mkdir()
    sessions = _make_sessions_dir(fake_home, proj)
    (sessions / "s1.jsonl").write_text(
        json.dumps(_event("s1", "u1")) + "\n"
        + json.dumps(_event("s1", "u2")) + "\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(proj)
    assert main(["scan"]) == 0
    assert (proj / "report.html").exists()


def test_scan_report_contains_counts(fake_home, tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    proj.mkdir()
    sessions = _make_sessions_dir(fake_home, proj)
    (sessions / "s1.jsonl").write_text(
        json.dumps(_event("s1", "u1")) + "\n"
        + json.dumps(_event("s1", "u2")) + "\n"
        + json.dumps(_event("s1", "u3")) + "\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(proj)
    assert main(["scan"]) == 0

    rendered = (proj / "report.html").read_text(encoding="utf-8")
    assert '"session_count": 1' in rendered
    assert '"total_event_count": 3' in rendered
    assert '"schema_version": "1.3"' in rendered
    assert "{{DATA}}" not in rendered
