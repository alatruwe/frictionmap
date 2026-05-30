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
    assert '"schema_version": "1.4"' in rendered
    assert "{{DATA}}" not in rendered


# --- Phase 5b: passive noise hint --------------------------------------------

def _edit(tool_id: str, file_path: str) -> dict:
    return {"type": "tool_use", "id": tool_id, "name": "Edit",
            "input": {"file_path": file_path, "old_string": "a", "new_string": "b"}}


def _assistant_session(uuid: str, edits: list[dict]) -> dict:
    return {
        "type": "assistant",
        "sessionId": "s1",
        "uuid": uuid,
        "parentUuid": None,
        "timestamp": "2026-04-22T00:00:00Z",
        "cwd": "/proj",
        "message": {"role": "assistant", "content": edits},
    }


def test_scan_emits_noise_hint_and_writes_no_ignore_file(fake_home, tmp_path, monkeypatch, capsys):
    proj = tmp_path / "proj"
    proj.mkdir()
    sessions = _make_sessions_dir(fake_home, proj)
    # Two Edit-touched noise files survive the loc==0 filter into the top-20.
    records = [_assistant_session(
        "u1",
        [_edit("t1", "/proj/poetry.lock"), _edit("t2", "/proj/static/app.min.js")],
    )]
    (sessions / "s1.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8"
    )

    monkeypatch.chdir(proj)
    assert main(["scan"]) == 0
    out = capsys.readouterr().out
    assert "match common generated/vendored patterns" in out
    # The hint must not mutate the project dir.
    assert not (proj / ".frictionmap-ignore").exists()


def test_scan_silent_when_top_files_clean(fake_home, tmp_path, monkeypatch, capsys):
    proj = tmp_path / "proj"
    proj.mkdir()
    sessions = _make_sessions_dir(fake_home, proj)
    records = [_assistant_session(
        "u1", [_edit("t1", "/proj/src/real.py"), _edit("t2", "/proj/src/other.py")],
    )]
    (sessions / "s1.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8"
    )

    monkeypatch.chdir(proj)
    assert main(["scan"]) == 0
    out = capsys.readouterr().out
    assert "generated/vendored patterns" not in out


def test_scan_ignore_flag_hides_path_for_one_run(fake_home, tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    proj.mkdir()
    sessions = _make_sessions_dir(fake_home, proj)
    records = [_assistant_session(
        "u1", [_edit("t1", "/proj/src/secret.py"), _edit("t2", "/proj/src/keep.py")],
    )]
    (sessions / "s1.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8"
    )

    monkeypatch.chdir(proj)
    assert main(["scan", "--ignore", "secret.py"]) == 0
    rendered = (proj / "report.html").read_text(encoding="utf-8")
    assert "secret.py" not in rendered
    assert "keep.py" in rendered
    # One-off: no .frictionmap-ignore written.
    assert not (proj / ".frictionmap-ignore").exists()
