from __future__ import annotations

import json
from pathlib import Path

from ai_friction_map.parser import parse_sessions


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def test_empty_dir_returns_zeros(tmp_path):
    assert parse_sessions(tmp_path) == {"session_count": 0, "event_count": 0}


def test_counts_files_and_lines(tmp_path):
    _write_jsonl(tmp_path / "a.jsonl", [{"i": i} for i in range(3)])
    _write_jsonl(tmp_path / "b.jsonl", [{"i": i} for i in range(5)])

    assert parse_sessions(tmp_path) == {"session_count": 2, "event_count": 8}


def test_skips_malformed_lines(tmp_path):
    path = tmp_path / "mixed.jsonl"
    path.write_text(
        '{"ok": 1}\n'
        "not json at all\n"
        '{"ok": 2}\n'
        '{"ok": 3}\n',
        encoding="utf-8",
    )

    assert parse_sessions(tmp_path) == {"session_count": 1, "event_count": 3}


def test_ignores_non_jsonl_files(tmp_path):
    _write_jsonl(tmp_path / "session.jsonl", [{"i": 1}, {"i": 2}])
    (tmp_path / "notes.md").write_text("line one\nline two\n", encoding="utf-8")

    assert parse_sessions(tmp_path) == {"session_count": 1, "event_count": 2}
