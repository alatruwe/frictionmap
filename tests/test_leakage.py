from __future__ import annotations

from frictionmap.leakage import aggregate_leakage
from frictionmap.parser import parse_sessions
from tests._factories import (
    assistant,
    jsonl,
    system_compact,
    user,
)


def _edit_use(tool_id: str, file_path: str) -> dict:
    return {"type": "tool_use", "id": tool_id, "name": "Edit",
            "input": {"file_path": file_path, "old_string": "x", "new_string": "y"}}


def _read_use(tool_id: str, file_path: str) -> dict:
    return {"type": "tool_use", "id": tool_id, "name": "Read",
            "input": {"file_path": file_path}}


def _grep_use(tool_id: str, path: str | None, pattern: str) -> dict:
    inp: dict = {"pattern": pattern}
    if path is not None:
        inp["path"] = path
    return {"type": "tool_use", "id": tool_id, "name": "Grep", "input": inp}


def _bash_use(tool_id: str, command: str) -> dict:
    return {"type": "tool_use", "id": tool_id, "name": "Bash",
            "input": {"command": command}}


def _tool_result(tool_id: str, content) -> dict:
    return {"type": "tool_result", "tool_use_id": tool_id, "content": content}


def test_edit_failure_from_error_result(tmp_path):
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [_edit_use("t1", "/proj/a.py")]),
        user("s1", "u2", [_tool_result("t1", "Error: String not found in file")]),
    ])
    corpus = parse_sessions(tmp_path)
    aggregate_leakage(corpus)
    assert corpus.leakage_by_file["/proj/a.py"].edit_failures == 1


def test_edit_failure_from_reread(tmp_path):
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [_edit_use("t1", "/proj/a.py")]),
        user("s1", "u2", [_tool_result("t1", "File edited successfully")]),
        assistant("s1", "u3", [_read_use("t2", "/proj/a.py")]),
    ])
    corpus = parse_sessions(tmp_path)
    aggregate_leakage(corpus)
    assert corpus.leakage_by_file["/proj/a.py"].edit_failures == 1


def test_edit_success_no_reread_no_increment(tmp_path):
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [_edit_use("t1", "/proj/a.py")]),
        user("s1", "u2", [_tool_result("t1", "File edited successfully")]),
    ])
    corpus = parse_sessions(tmp_path)
    aggregate_leakage(corpus)
    assert "/proj/a.py" not in corpus.leakage_by_file


def test_grep_reformulation_same_scope_different_pattern(tmp_path):
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [_grep_use("g1", "src", "foo")]),
        user("s1", "u2", [_tool_result("g1", "src/a.py:1:foo\n")]),
        assistant("s1", "u3", [_grep_use("g2", "src", "foobar")]),
        user("s1", "u4", [_tool_result("g2", "")]),
    ])
    corpus = parse_sessions(tmp_path)
    aggregate_leakage(corpus)
    # Attributed to first Grep's resolved file_paths (scope + matched).
    assert any(c.grep_reformulations >= 1 for c in corpus.leakage_by_file.values())


def test_grep_reformulation_across_compact_boundary_not_counted(tmp_path):
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [_grep_use("g1", "src", "foo")]),
        user("s1", "u2", [_tool_result("g1", "src/a.py:1:foo\n")]),
        system_compact("s1", "u3"),
        assistant("s1", "u4", [_grep_use("g2", "src", "foobar")]),
        user("s1", "u5", [_tool_result("g2", "")]),
    ])
    corpus = parse_sessions(tmp_path)
    aggregate_leakage(corpus)
    total_grep = sum(c.grep_reformulations for c in corpus.leakage_by_file.values())
    assert total_grep == 0


def test_bash_retry_same_program_after_failure(tmp_path):
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [_bash_use("b1", "pytest tests/test_x.py")]),
        user("s1", "u2", [_tool_result("b1",
              "tests/test_x.py::test_foo FAILED\nE   AssertionError: nope\nTraceback")]),
        assistant("s1", "u3", [_bash_use("b2", "pytest -v tests/test_x.py")]),
        user("s1", "u4", [_tool_result("b2", "1 passed")]),
    ])
    corpus = parse_sessions(tmp_path)
    aggregate_leakage(corpus)
    total_bash = sum(c.bash_retries for c in corpus.leakage_by_file.values())
    assert total_bash >= 1


def test_bash_continuation_not_retry(tmp_path):
    # cat foo.py (success) → cat foo.py bar.py — second is prefix-extension,
    # should NOT count.
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [_bash_use("b1", "cat foo.py")]),
        user("s1", "u2", [_tool_result("b1", "contents of foo")]),
        assistant("s1", "u3", [_bash_use("b2", "cat foo.py bar.py")]),
        user("s1", "u4", [_tool_result("b2", "contents of both")]),
    ])
    corpus = parse_sessions(tmp_path)
    aggregate_leakage(corpus)
    total_bash = sum(c.bash_retries for c in corpus.leakage_by_file.values())
    assert total_bash == 0


def test_read_after_edit_same_file(tmp_path):
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [_edit_use("t1", "/proj/a.py")]),
        user("s1", "u2", [_tool_result("t1", "ok")]),
        assistant("s1", "u3", [_read_use("t2", "/proj/a.py")]),
    ])
    corpus = parse_sessions(tmp_path)
    aggregate_leakage(corpus)
    assert corpus.leakage_by_file["/proj/a.py"].read_after_edit == 1


def test_read_after_edit_different_file_not_counted(tmp_path):
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [_edit_use("t1", "/proj/a.py")]),
        user("s1", "u2", [_tool_result("t1", "ok")]),
        assistant("s1", "u3", [_read_use("t2", "/proj/b.py")]),
    ])
    corpus = parse_sessions(tmp_path)
    aggregate_leakage(corpus)
    entry = corpus.leakage_by_file.get("/proj/a.py")
    if entry is not None:
        assert entry.read_after_edit == 0


def test_leakage_counts_total_matches_sum(tmp_path):
    jsonl(tmp_path / "s.jsonl", [
        assistant("s1", "u1", [_edit_use("t1", "/proj/a.py")]),
        user("s1", "u2", [_tool_result("t1", "Error: no match")]),
        assistant("s1", "u3", [_read_use("t2", "/proj/a.py")]),
    ])
    corpus = parse_sessions(tmp_path)
    aggregate_leakage(corpus)
    for c in corpus.leakage_by_file.values():
        assert c.total == (c.edit_failures + c.grep_reformulations
                           + c.bash_retries + c.read_after_edit)
