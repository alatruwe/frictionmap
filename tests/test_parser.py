from __future__ import annotations

import json
import tracemalloc
from pathlib import Path

from ai_friction_map.parser import parse_sessions


def _jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n",
        encoding="utf-8",
    )


def _assistant(session_id: str, uuid: str, content: list[dict], cwd: str = "/proj") -> dict:
    return {
        "type": "assistant",
        "sessionId": session_id,
        "uuid": uuid,
        "parentUuid": None,
        "timestamp": "2026-04-22T00:00:00Z",
        "cwd": cwd,
        "message": {"role": "assistant", "content": content},
    }


def _user(session_id: str, uuid: str, content, cwd: str = "/proj") -> dict:
    return {
        "type": "user",
        "sessionId": session_id,
        "uuid": uuid,
        "parentUuid": None,
        "timestamp": "2026-04-22T00:00:01Z",
        "cwd": cwd,
        "message": {"role": "user", "content": content},
    }


def _bare(session_id: str, uuid: str, ev_type: str) -> dict:
    return {
        "type": ev_type,
        "sessionId": session_id,
        "uuid": uuid,
        "parentUuid": None,
        "timestamp": "2026-04-22T00:00:02Z",
        "cwd": "/proj",
    }


def test_empty_dir_returns_empty_corpus(tmp_path):
    corpus = parse_sessions(tmp_path)
    assert corpus.session_count == 0
    assert corpus.event_count == 0
    assert corpus.sessions == {}


def test_counts_sessions_and_events(tmp_path):
    _jsonl(tmp_path / "a.jsonl", [_assistant("s1", "u1", []), _bare("s1", "u2", "ai-title")])
    _jsonl(tmp_path / "b.jsonl", [
        _assistant("s2", "u3", []),
        _assistant("s2", "u4", []),
        _user("s2", "u5", "hi"),
    ])
    corpus = parse_sessions(tmp_path)
    assert corpus.session_count == 2
    assert corpus.event_count == 5
    assert sorted(corpus.sessions.keys()) == ["s1", "s2"]


def test_preserves_event_order(tmp_path):
    records = [_bare("s1", f"u{i}", "ai-title") for i in range(5)]
    _jsonl(tmp_path / "s.jsonl", records)
    corpus = parse_sessions(tmp_path)
    events = corpus.sessions["s1"]
    assert [e.event_index for e in events] == [0, 1, 2, 3, 4]
    assert [e.uuid for e in events] == [f"u{i}" for i in range(5)]


def test_parses_assistant_blocks(tmp_path):
    content = [
        {"type": "text", "text": "hello"},
        {"type": "thinking", "thinking": "wait, reconsidering"},
        {"type": "tool_use", "id": "toolu_1", "name": "Read",
         "input": {"file_path": "/proj/storage.py"}},
    ]
    _jsonl(tmp_path / "s.jsonl", [_assistant("s1", "u1", content)])
    corpus = parse_sessions(tmp_path)
    blocks = corpus.sessions["s1"][0].blocks
    assert [b.type for b in blocks] == ["text", "thinking", "tool_use"]
    assert blocks[0].text == "hello"
    assert blocks[1].thinking == "wait, reconsidering"
    assert blocks[2].tool_name == "Read"
    assert blocks[2].tool_use_id == "toolu_1"
    assert blocks[2].file_paths == ["/proj/storage.py"]


def test_parses_tool_result_from_user_event(tmp_path):
    content = [{"type": "tool_result", "tool_use_id": "toolu_1", "content": "file contents"}]
    _jsonl(tmp_path / "s.jsonl", [_user("s1", "u1", content)])
    corpus = parse_sessions(tmp_path)
    blocks = corpus.sessions["s1"][0].blocks
    assert len(blocks) == 1
    assert blocks[0].type == "tool_result"
    assert blocks[0].tool_use_id == "toolu_1"
    assert blocks[0].tool_result_content == "file contents"


def test_matches_tool_use_to_tool_result(tmp_path):
    use = [{"type": "tool_use", "id": "toolu_x", "name": "Read",
            "input": {"file_path": "/proj/a.py"}}]
    res = [{"type": "tool_result", "tool_use_id": "toolu_x", "content": "ok"}]
    _jsonl(tmp_path / "s.jsonl", [
        _assistant("s1", "u1", use),
        _user("s1", "u2", res),
    ])
    corpus = parse_sessions(tmp_path)
    tc = corpus.tool_calls["toolu_x"]
    assert tc.use_event_index == 0
    assert tc.result_event_index == 1
    assert tc.result_content == "ok"
    assert tc.tool_name == "Read"


def test_unmatched_tool_use_has_none_result(tmp_path):
    use = [{"type": "tool_use", "id": "toolu_y", "name": "Read",
            "input": {"file_path": "/proj/a.py"}}]
    _jsonl(tmp_path / "s.jsonl", [_assistant("s1", "u1", use)])
    corpus = parse_sessions(tmp_path)
    tc = corpus.tool_calls["toolu_y"]
    assert tc.result_event_index is None
    assert tc.result_content is None


def test_grep_file_paths_populated_from_result(tmp_path):
    use = [{"type": "tool_use", "id": "toolu_g", "name": "Grep",
            "input": {"path": "src", "pattern": "foo"}}]
    res = [{"type": "tool_result", "tool_use_id": "toolu_g",
            "content": "src/a.py:1:foo\nsrc/b.py:2:foo\n"}]
    _jsonl(tmp_path / "s.jsonl", [
        _assistant("s1", "u1", use, cwd="/proj"),
        _user("s1", "u2", res, cwd="/proj"),
    ])
    corpus = parse_sessions(tmp_path)
    tc = corpus.tool_calls["toolu_g"]
    assert any(p.endswith("/proj/src/a.py") for p in tc.file_paths)
    assert any(p.endswith("/proj/src/b.py") for p in tc.file_paths)
    use_block = corpus.sessions["s1"][0].blocks[0]
    assert use_block.file_paths == tc.file_paths


def test_malformed_line_logged_and_skipped(tmp_path, caplog):
    path = tmp_path / "s.jsonl"
    path.write_text(
        json.dumps(_bare("s1", "u1", "ai-title")) + "\n"
        + "not json at all\n"
        + json.dumps(_bare("s1", "u2", "ai-title")) + "\n",
        encoding="utf-8",
    )
    with caplog.at_level("WARNING", logger="ai_friction_map.parser"):
        corpus = parse_sessions(tmp_path)
    assert corpus.event_count == 2
    assert any("malformed" in r.getMessage() for r in caplog.records)


def test_unknown_type_logged_once_and_counted(tmp_path, caplog):
    records = [
        {"type": "mystery", "sessionId": "s1", "uuid": f"u{i}",
         "timestamp": "t", "cwd": "/proj"}
        for i in range(3)
    ]
    records.append(_bare("s1", "u9", "ai-title"))
    _jsonl(tmp_path / "s.jsonl", records)
    with caplog.at_level("WARNING", logger="ai_friction_map.parser"):
        corpus = parse_sessions(tmp_path)
    assert corpus.unknown_types.get("mystery") == 3
    warnings = [r for r in caplog.records if "mystery" in r.getMessage()]
    assert len(warnings) == 1


def test_user_message_content_as_string(tmp_path):
    _jsonl(tmp_path / "s.jsonl", [_user("s1", "u1", "just a string prompt")])
    corpus = parse_sessions(tmp_path)
    assert corpus.event_count == 1
    assert corpus.sessions["s1"][0].blocks == []


def test_ignores_non_jsonl_files(tmp_path):
    _jsonl(tmp_path / "s.jsonl", [_bare("s1", "u1", "ai-title")])
    (tmp_path / "notes.md").write_text("ignore me\n", encoding="utf-8")
    corpus = parse_sessions(tmp_path)
    assert corpus.session_count == 1
    assert corpus.event_count == 1


def test_streaming_memory_smoke(tmp_path):
    # 2000 events with ~500 chars of thinking each; guardrail that parser
    # doesn't retain a total size grossly larger than the file itself.
    records = []
    for i in range(2000):
        content = [{"type": "thinking", "thinking": "x" * 500}]
        records.append(_assistant("s1", f"u{i}", content))
    path = tmp_path / "big.jsonl"
    _jsonl(path, records)
    file_size = path.stat().st_size

    tracemalloc.start()
    corpus = parse_sessions(tmp_path)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert corpus.event_count == 2000
    assert peak < file_size * 10
