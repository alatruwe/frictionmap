from __future__ import annotations

from frictionmap.extraction import extract_file_paths


def test_read_extracts_file_path():
    assert extract_file_paths(
        "Read",
        {"file_path": "/x/y/storage.py"},
        None,
    ) == ["/x/y/storage.py"]


def test_edit_extracts_file_path():
    assert extract_file_paths(
        "Edit",
        {"file_path": "/x/y/main.py", "old_string": "a", "new_string": "b"},
        None,
    ) == ["/x/y/main.py"]


def test_write_extracts_file_path():
    assert extract_file_paths(
        "Write",
        {"file_path": "/x/y/new.py", "content": "..."},
        None,
    ) == ["/x/y/new.py"]


def test_read_without_file_path_returns_empty():
    assert extract_file_paths("Read", {}, None) == []


def test_grep_scope_and_result():
    result = (
        "src/foo.py:42:def bar():\n"
        "src/baz.py:17:    return\n"
    )
    paths = extract_file_paths("Grep", {"path": "src", "pattern": "bar"}, result)
    assert "src" in paths
    assert "src/foo.py" in paths
    assert "src/baz.py" in paths


def test_glob_result():
    result = "src/a.py\nsrc/b/c.py\nsrc/d.py\n"
    paths = extract_file_paths("Glob", {"pattern": "**/*.py"}, result)
    assert "src/a.py" in paths
    assert "src/b/c.py" in paths
    assert "src/d.py" in paths


def test_bash_real_command_pytest():
    # Real command from attune corpus.
    cmd = "uv run pytest tests/test_server.py -v 2>&1"
    paths = extract_file_paths("Bash", {"command": cmd, "description": ""}, None)
    assert "tests/test_server.py" in paths


def test_bash_real_command_absolute_paths():
    # Real command from attune corpus with two absolute paths.
    cmd = (
        'ls /Users/adelinelatruwe/Projects/attune/probes/ && echo "---" && '
        'ls /Users/adelinelatruwe/Downloads/ | grep "emotion"'
    )
    paths = extract_file_paths("Bash", {"command": cmd, "description": "x"}, None)
    assert any(p.startswith("/Users/adelinelatruwe/Projects/attune/probes") for p in paths)
    assert any(p.startswith("/Users/adelinelatruwe/Downloads") for p in paths)


def test_bash_real_command_no_paths():
    # Real command from attune corpus; no file paths expected.
    cmd = "docker compose build attune 2>&1 | tail -5"
    paths = extract_file_paths("Bash", {"command": cmd, "description": "Rebuild image"}, None)
    assert paths == []


def test_bash_bare_filename():
    # Conscious permissive branch: bare filename (no /) with known suffix is extracted.
    cmd = "python storage.py --flag"
    paths = extract_file_paths("Bash", {"command": cmd}, None)
    assert "storage.py" in paths


def test_bash_union_of_command_and_description():
    paths = extract_file_paths(
        "Bash",
        {"command": "cat ./foo.py", "description": "reading bar.py for context"},
        None,
    )
    assert "./foo.py" in paths
    assert "bar.py" in paths


def test_bash_deduplicates():
    paths = extract_file_paths(
        "Bash",
        {"command": "cat foo.py; head foo.py", "description": "inspect foo.py"},
        None,
    )
    assert paths.count("foo.py") == 1


def test_agent_returns_empty():
    assert extract_file_paths(
        "Agent",
        {"description": "refactor", "prompt": "touch src/main.py"},
        None,
    ) == []


def test_skip_list_tools_return_empty():
    for name in (
        "TodoWrite", "ExitPlanMode", "ToolSearch", "AskUserQuestion",
        "WebSearch", "WebFetch",
    ):
        assert extract_file_paths(name, {"anything": "here"}, None) == []


def test_unknown_tool_returns_empty_silently_with_debug_log(caplog):
    # Anthropic ships new tools regularly; unknown tools default to a
    # graceful skip — no WARNING. DEBUG fires exactly once for the first
    # occurrence (diagnostic visibility) and is suppressed thereafter
    # via the _logged_unknown_tools dedup set. Both invariants matter:
    # silent stdout/stderr for users, and a one-shot diagnostic that
    # survives future refactors.
    with caplog.at_level("DEBUG", logger="frictionmap.extraction"):
        result1 = extract_file_paths("MysteryTool1", {"x": 1}, None)
        result2 = extract_file_paths("MysteryTool1", {"x": 2}, None)
    assert result1 == []
    assert result2 == []
    warnings = [
        r for r in caplog.records
        if "MysteryTool1" in r.getMessage() and r.levelname == "WARNING"
    ]
    assert warnings == []
    debugs = [
        r for r in caplog.records
        if "MysteryTool1" in r.getMessage() and r.levelname == "DEBUG"
    ]
    assert len(debugs) == 1, (
        "expected exactly one DEBUG log on first occurrence; got "
        f"{len(debugs)}"
    )


def test_grep_result_with_dict_content():
    # tool_result content can be a list of dicts with "text" keys.
    content = [{"type": "text", "text": "src/x.py\nsrc/y.py\n"}]
    paths = extract_file_paths("Grep", {"path": "src"}, content)
    assert "src/x.py" in paths
    assert "src/y.py" in paths
