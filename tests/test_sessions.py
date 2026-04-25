from __future__ import annotations

import json
import os
import time
from pathlib import Path

from ai_friction_map.sessions import (
    DEFAULT_WINDOW_HOURS,
    find_active_sessions,
    format_relative_time,
    match_session,
)


def _ai_title(session_id: str, content: str, uuid: str = "u1") -> dict:
    return {
        "type": "ai-title",
        "sessionId": session_id,
        "uuid": uuid,
        "parentUuid": None,
        "timestamp": "2026-04-22T00:00:00Z",
        "cwd": "/proj",
        "content": content,
    }


def _other(session_id: str, uuid: str) -> dict:
    return {
        "type": "user",
        "sessionId": session_id,
        "uuid": uuid,
        "parentUuid": None,
        "timestamp": "2026-04-22T00:00:01Z",
        "cwd": "/proj",
        "message": {"role": "user", "content": "hello"},
    }


def _write(path: Path, records: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n",
        encoding="utf-8",
    )


def _set_mtime(path: Path, hours_ago: float) -> None:
    target = time.time() - hours_ago * 3600
    os.utime(path, (target, target))


def test_find_active_sessions_filters_by_mtime(tmp_path: Path) -> None:
    recent = tmp_path / "recent.jsonl"
    old = tmp_path / "old.jsonl"
    _write(recent, [_ai_title("recent", "Recent work")])
    _write(old, [_ai_title("old", "Old work")])
    _set_mtime(recent, hours_ago=1)
    _set_mtime(old, hours_ago=DEFAULT_WINDOW_HOURS + 5)
    sessions = find_active_sessions(tmp_path)
    ids = [s.session_id for s in sessions]
    assert "recent" in ids
    assert "old" not in ids


def test_find_active_sessions_extracts_last_ai_title(tmp_path: Path) -> None:
    path = tmp_path / "s.jsonl"
    _write(path, [
        _ai_title("s", "First title", uuid="u1"),
        _other("s", "u2"),
        _ai_title("s", "Final title", uuid="u3"),
    ])
    _set_mtime(path, hours_ago=1)
    sessions = find_active_sessions(tmp_path)
    assert len(sessions) == 1
    assert sessions[0].title == "Final title"


def test_find_active_sessions_untitled(tmp_path: Path) -> None:
    path = tmp_path / "s.jsonl"
    _write(path, [_other("s", "u1")])
    _set_mtime(path, hours_ago=1)
    sessions = find_active_sessions(tmp_path)
    assert len(sessions) == 1
    assert sessions[0].title == "(untitled)"


def test_match_session_by_uuid_prefix(tmp_path: Path) -> None:
    path = tmp_path / "abc12345-aaaa-bbbb-cccc-deadbeef0000.jsonl"
    _write(path, [_ai_title("abc12345-aaaa-bbbb-cccc-deadbeef0000", "Some work")])
    result = match_session(tmp_path, "abc12345")
    assert len(result.matches) == 1
    assert result.matched_by == "uuid"


def test_match_session_by_title_substring_case_insensitive(tmp_path: Path) -> None:
    path = tmp_path / "ses-123.jsonl"
    _write(path, [_ai_title("ses-123", "Fix migration order")])
    result = match_session(tmp_path, "MIGRATION")
    assert len(result.matches) == 1
    assert result.matched_by == "title"


def test_match_session_zero_matches(tmp_path: Path) -> None:
    path = tmp_path / "s.jsonl"
    _write(path, [_ai_title("s", "Some title")])
    result = match_session(tmp_path, "nothing-matches-this")
    assert result.matches == []
    assert result.matched_by == ""


def test_match_session_multiple_matches(tmp_path: Path) -> None:
    for idx in range(3):
        path = tmp_path / f"s{idx}.jsonl"
        _write(path, [_ai_title(f"s{idx}", f"fix bug {idx}")])
    result = match_session(tmp_path, "fix")
    assert len(result.matches) == 3
    assert result.matched_by == "title"


def test_match_session_uuid_prefix_takes_precedence(tmp_path: Path) -> None:
    # An 8-hex-char identifier matches one session by uuid prefix AND
    # appears as a substring of another's title. UUID match wins.
    path1 = tmp_path / "abcdef01-1111-2222-3333-444455556666.jsonl"
    _write(path1, [_ai_title("abcdef01-1111-2222-3333-444455556666", "Real work")])
    path2 = tmp_path / "fff999.jsonl"
    _write(path2, [_ai_title("fff999", "abcdef01 appears in title")])
    result = match_session(tmp_path, "abcdef01")
    assert len(result.matches) == 1
    assert result.matched_by == "uuid"
    assert result.matches[0].session_id == "abcdef01-1111-2222-3333-444455556666"


def test_find_active_sessions_uses_aitTitle_field(tmp_path: Path) -> None:
    # Real Claude Code JSONL uses the `aiTitle` field on ai-title events,
    # not `content` or `title`. Verify against that shape.
    path = tmp_path / "real.jsonl"
    path.write_text(
        json.dumps({
            "type": "ai-title",
            "sessionId": "real",
            "aiTitle": "Real-shape title",
        }) + "\n",
        encoding="utf-8",
    )
    _set_mtime(path, hours_ago=1)
    sessions = find_active_sessions(tmp_path)
    assert sessions[0].title == "Real-shape title"


def test_format_relative_time() -> None:
    now = time.time()
    assert format_relative_time(now - 30, now=now) == "just now"
    assert format_relative_time(now - 120, now=now) == "2 minutes ago"
    assert format_relative_time(now - 3600, now=now) == "1 hour ago"
    assert format_relative_time(now - 7200, now=now) == "2 hours ago"
