from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_friction_map.cli import main


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


def test_scan_writes_report_html(fake_home, tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    proj.mkdir()
    sessions = _make_sessions_dir(fake_home, proj)
    (sessions / "s1.jsonl").write_text(
        json.dumps({"i": 1}) + "\n" + json.dumps({"i": 2}) + "\n",
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
        json.dumps({"i": 1}) + "\n"
        + json.dumps({"i": 2}) + "\n"
        + json.dumps({"i": 3}) + "\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(proj)
    assert main(["scan"]) == 0

    rendered = (proj / "report.html").read_text(encoding="utf-8")
    assert '"session_count": 1' in rendered
    assert '"event_count": 3' in rendered
    assert "{{DATA}}" not in rendered
