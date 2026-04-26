from __future__ import annotations

from ai_friction_map.parser import parse_sessions
from tests._factories import (
    assistant,
    jsonl,
    non_agent_progress,
    progress,
    user,
)


def test_agent_progress_emits_nested_tool_use(tmp_path):
    nested = [
        {"type": "tool_use", "id": "toolu_nest1", "name": "Read",
         "input": {"file_path": "/proj/storage.py"}},
    ]
    jsonl(tmp_path / "s.jsonl", [
        progress("s1", "u1", nested, cwd="/proj", parent_tool_use_id="toolu_parent"),
    ])
    corpus = parse_sessions(tmp_path)
    event = corpus.sessions["s1"][0]
    assert event.type == "progress"
    assert len(event.blocks) == 1
    b = event.blocks[0]
    assert b.type == "tool_use"
    assert b.tool_name == "Read"
    assert b.agent_sourced is True
    assert b.file_paths == ["/proj/storage.py"]


def test_agent_progress_emits_nested_thinking_if_present(tmp_path):
    nested = [{"type": "thinking", "thinking": "wait, sub-agent reconsidering"}]
    jsonl(tmp_path / "s.jsonl", [progress("s1", "u1", nested)])
    corpus = parse_sessions(tmp_path)
    blocks = corpus.sessions["s1"][0].blocks
    assert len(blocks) == 1
    assert blocks[0].type == "thinking"
    assert blocks[0].agent_sourced is True
    assert blocks[0].thinking == "wait, sub-agent reconsidering"


def test_agent_progress_tool_use_matches_tool_result_across_events(tmp_path):
    use_nested = [{"type": "tool_use", "id": "toolu_x", "name": "Read",
                   "input": {"file_path": "/proj/a.py"}}]
    res_nested = [{"type": "tool_result", "tool_use_id": "toolu_x", "content": "ok"}]
    jsonl(tmp_path / "s.jsonl", [
        progress("s1", "u1", use_nested, cwd="/proj"),
        progress("s1", "u2", res_nested, cwd="/proj", nested_role="user"),
    ])
    corpus = parse_sessions(tmp_path)
    tc = corpus.tool_calls["toolu_x"]
    assert tc.use_event_index == 0
    assert tc.result_event_index == 1
    assert tc.tool_name == "Read"


def test_non_agent_progress_ignored(tmp_path):
    jsonl(tmp_path / "s.jsonl", [non_agent_progress("s1", "u1")])
    corpus = parse_sessions(tmp_path)
    event = corpus.sessions["s1"][0]
    assert event.type == "progress"
    assert event.blocks == []


def test_agent_progress_malformed_nested_structure_skipped(tmp_path):
    malformed = {
        "type": "progress",
        "sessionId": "s1",
        "uuid": "u1",
        "parentUuid": None,
        "timestamp": "2026-04-22T00:00:00Z",
        "cwd": "/proj",
        "data": {"type": "agent_progress", "message": {"no_inner_message": True}},
    }
    also_malformed = {
        "type": "progress",
        "sessionId": "s1",
        "uuid": "u2",
        "parentUuid": None,
        "timestamp": "2026-04-22T00:00:00Z",
        "cwd": "/proj",
        "data": {"type": "agent_progress",
                 "message": {"message": {"content": "not-a-list"}}},
    }
    jsonl(tmp_path / "s.jsonl", [malformed, also_malformed])
    corpus = parse_sessions(tmp_path)
    for ev in corpus.sessions["s1"]:
        assert ev.type == "progress"
        assert ev.blocks == []


def test_agent_progress_grep_tool_use_gets_result_patched_back(tmp_path):
    """Regression guard: walker-emitted Grep on a progress event must
    participate in _resolve_tool_calls' file_paths patch-back. The patch
    iterates events[tc.use_event_index].blocks — if that's a progress
    event, the lookup must still reach the walker-emitted block.
    """
    use_nested = [{"type": "tool_use", "id": "toolu_g", "name": "Grep",
                   "input": {"path": "src", "pattern": "foo"}}]
    res_nested = [{"type": "tool_result", "tool_use_id": "toolu_g",
                   "content": "src/a.py:1:foo\nsrc/b.py:2:foo\n"}]
    jsonl(tmp_path / "s.jsonl", [
        progress("s1", "u1", use_nested, cwd="/proj"),
        progress("s1", "u2", res_nested, cwd="/proj", nested_role="user"),
    ])
    corpus = parse_sessions(tmp_path)
    tc = corpus.tool_calls["toolu_g"]
    assert any(p.endswith("/proj/src/a.py") for p in tc.file_paths)
    assert any(p.endswith("/proj/src/b.py") for p in tc.file_paths)
    # The walker-emitted tool_use block on the progress event must have
    # file_paths patched back to match the ToolCall.
    use_block = corpus.sessions["s1"][0].blocks[0]
    assert use_block.agent_sourced is True
    assert use_block.file_paths == tc.file_paths


def test_agent_progress_assistant_role_captures_nested_model(tmp_path):
    nested = [{"type": "tool_use", "id": "toolu_n", "name": "Read",
               "input": {"file_path": "/proj/x.py"}}]
    jsonl(tmp_path / "s.jsonl", [
        progress("s1", "u1", nested, cwd="/proj", model="claude-haiku-4-5-20251001"),
    ])
    corpus = parse_sessions(tmp_path)
    event = corpus.sessions["s1"][0]
    assert event.type == "progress"
    assert event.model == "claude-haiku-4-5-20251001"
    assert event.is_assistant_like is True


def test_agent_progress_user_role_is_not_assistant_like(tmp_path):
    nested = [{"type": "tool_result", "tool_use_id": "toolu_x", "content": "ok"}]
    jsonl(tmp_path / "s.jsonl", [
        progress("s1", "u1", nested, cwd="/proj", nested_role="user"),
    ])
    corpus = parse_sessions(tmp_path)
    event = corpus.sessions["s1"][0]
    assert event.model is None
    assert event.is_assistant_like is False


def test_non_agent_progress_carries_no_model(tmp_path):
    jsonl(tmp_path / "s.jsonl", [non_agent_progress("s1", "u1")])
    corpus = parse_sessions(tmp_path)
    event = corpus.sessions["s1"][0]
    assert event.model is None
    assert event.is_assistant_like is False


def test_agent_progress_top_level_and_nested_coexist(tmp_path):
    """Top-level assistant tool_use and a sub-agent tool_use in the same
    session both show up; agent_sourced distinguishes them."""
    top_use = [{"type": "tool_use", "id": "toolu_top", "name": "Read",
                "input": {"file_path": "/proj/top.py"}}]
    nested_use = [{"type": "tool_use", "id": "toolu_sub", "name": "Read",
                   "input": {"file_path": "/proj/sub.py"}}]
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", top_use),
        progress("s1", "u2", nested_use, cwd="/proj"),
    ])
    corpus = parse_sessions(tmp_path)
    top = corpus.sessions["s1"][0].blocks[0]
    nested = corpus.sessions["s1"][1].blocks[0]
    assert top.agent_sourced is False
    assert nested.agent_sourced is True
    assert "toolu_top" in corpus.tool_calls
    assert "toolu_sub" in corpus.tool_calls
