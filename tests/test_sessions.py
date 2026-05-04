from __future__ import annotations

import json
import os
import time
from pathlib import Path

from frictionmap.sessions import (
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


def _last_prompt(session_id: str, prompt: str, uuid: str = "lp1") -> dict:
    return {
        "type": "last-prompt",
        "sessionId": session_id,
        "uuid": uuid,
        "parentUuid": None,
        "timestamp": "2026-04-22T00:00:02Z",
        "cwd": "/proj",
        "lastPrompt": prompt,
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


def test_last_ai_title_uses_ai_title_when_present(tmp_path: Path) -> None:
    # When both record types exist, ai-title wins over the last-prompt fallback.
    path = tmp_path / "s.jsonl"
    _write(path, [
        _last_prompt("s", "Original opening prompt", uuid="lp1"),
        _ai_title("s", "Auto-generated title", uuid="t1"),
    ])
    _set_mtime(path, hours_ago=1)
    sessions = find_active_sessions(tmp_path)
    assert sessions[0].title == "Auto-generated title"


def test_last_ai_title_falls_back_to_first_last_prompt(tmp_path: Path) -> None:
    # No ai-title record → use the FIRST last-prompt's first non-empty line.
    path = tmp_path / "s.jsonl"
    _write(path, [
        _last_prompt("s", "First prompt\nsecond line", uuid="lp1"),
        _last_prompt("s", "Second prompt", uuid="lp2"),
    ])
    _set_mtime(path, hours_ago=1)
    sessions = find_active_sessions(tmp_path)
    assert sessions[0].title == "First prompt"


def test_last_ai_title_strips_markdown_heading_marker(tmp_path: Path) -> None:
    path = tmp_path / "s.jsonl"
    _write(path, [_last_prompt("s", "# Handoff: phase 5 cleanup")])
    _set_mtime(path, hours_ago=1)
    sessions = find_active_sessions(tmp_path)
    assert sessions[0].title == "Handoff: phase 5 cleanup"


def test_last_ai_title_truncates_long_last_prompt_to_60_chars(tmp_path: Path) -> None:
    # 60 chars total INCLUDING the single Unicode … (U+2026); 59 content + 1 ellipsis.
    path = tmp_path / "s.jsonl"
    _write(path, [_last_prompt("s", "x" * 100)])
    _set_mtime(path, hours_ago=1)
    sessions = find_active_sessions(tmp_path)
    title = sessions[0].title
    assert len(title) == 60
    assert title.endswith("…")
    assert title == ("x" * 59) + "…"


def test_last_ai_title_falls_back_to_untitled_when_neither_present(tmp_path: Path) -> None:
    path = tmp_path / "s.jsonl"
    _write(path, [_other("s", "u1")])
    _set_mtime(path, hours_ago=1)
    sessions = find_active_sessions(tmp_path)
    assert sessions[0].title == "(untitled)"


def test_format_relative_time() -> None:
    now = time.time()
    assert format_relative_time(now - 30, now=now) == "just now"
    assert format_relative_time(now - 120, now=now) == "2 minutes ago"
    assert format_relative_time(now - 3600, now=now) == "1 hour ago"
    assert format_relative_time(now - 7200, now=now) == "2 hours ago"
