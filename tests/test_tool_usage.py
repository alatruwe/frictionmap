from __future__ import annotations

from pathlib import Path

from ai_friction_map.parser import parse_sessions
from tests._factories import assistant, jsonl, progress


def test_single_read_increments_read_count(tmp_path: Path) -> None:
    content = [{"type": "tool_use", "id": "t1", "name": "Read",
                "input": {"file_path": "/proj/a.py"}}]
    jsonl(tmp_path / "s.jsonl", [assistant("s1", "u1", content)])
    corpus = parse_sessions(tmp_path)
    assert corpus.tool_usage_by_file["/proj/a.py"].read == 1


def test_multiple_tools_on_same_file(tmp_path: Path) -> None:
    records = [
        assistant("s1", "u1", [
            {"type": "tool_use", "id": "t1", "name": "Read",
             "input": {"file_path": "/proj/a.py"}},
            {"type": "tool_use", "id": "t2", "name": "Read",
             "input": {"file_path": "/proj/a.py"}},
            {"type": "tool_use", "id": "t3", "name": "Read",
             "input": {"file_path": "/proj/a.py"}},
            {"type": "tool_use", "id": "t4", "name": "Edit",
             "input": {"file_path": "/proj/a.py"}},
            {"type": "tool_use", "id": "t5", "name": "Edit",
             "input": {"file_path": "/proj/a.py"}},
            {"type": "tool_use", "id": "t6", "name": "Bash",
             "input": {"command": "cat /proj/a.py"}},
        ]),
    ]
    jsonl(tmp_path / "s.jsonl", records)
    corpus = parse_sessions(tmp_path)
    usage = corpus.tool_usage_by_file["/proj/a.py"]
    assert usage.read == 3
    assert usage.edit == 2
    assert usage.bash == 1


def test_multiple_files_same_tool_call(tmp_path: Path) -> None:
    use = [{"type": "tool_use", "id": "tg", "name": "Grep",
            "input": {"path": "src", "pattern": "foo"}}]
    res = [{"type": "tool_result", "tool_use_id": "tg",
            "content": (
                "/proj/a.py\n/proj/b.py\n/proj/c.py\n/proj/d.py\n/proj/e.py\n"
            )}]
    from tests._factories import user
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", use),
        user("s1", "u2", res),
    ])
    corpus = parse_sessions(tmp_path)
    for path in ("/proj/a.py", "/proj/b.py", "/proj/c.py", "/proj/d.py", "/proj/e.py"):
        assert corpus.tool_usage_by_file[path].grep == 1


def test_agent_sourced_tool_use_counted(tmp_path: Path) -> None:
    nested = [{"type": "tool_use", "id": "tn1", "name": "Read",
               "input": {"file_path": "/proj/nested.py"}}]
    jsonl(tmp_path / "s.jsonl", [progress("s1", "u1", nested)])
    corpus = parse_sessions(tmp_path)
    assert corpus.tool_usage_by_file["/proj/nested.py"].read == 1


def test_file_never_touched_not_in_dict(tmp_path: Path) -> None:
    content = [{"type": "tool_use", "id": "t1", "name": "Read",
                "input": {"file_path": "/proj/a.py"}}]
    jsonl(tmp_path / "s.jsonl", [assistant("s1", "u1", content)])
    corpus = parse_sessions(tmp_path)
    assert "/proj/never_seen.py" not in corpus.tool_usage_by_file
