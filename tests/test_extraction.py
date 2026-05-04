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


# Phantom-rejection regressions (Task #13). Each test uses a string from
# (or representative of) the path_extractor_audit_*.txt diagnostic.

def test_bash_rejects_url_fragment_https():
    cmd = (
        'curl -s "https://registry.hub.docker.com/v2/repositories/ollama/ollama/tags/0.20.3" '
        '2>/dev/null | head -5'
    )
    paths = extract_file_paths("Bash", {"command": cmd}, None)
    assert not any("hub.docker.com" in p for p in paths)
    assert not any(p.startswith("//") for p in paths)
    assert not any("://" in p for p in paths)


def test_bash_rejects_url_fragment_localhost_with_port():
    cmd = "curl -s http://localhost:11434/api/tokenize -d '{\"model\":\"x\"}'"
    paths = extract_file_paths("Bash", {"command": cmd}, None)
    assert not any(p.startswith("//") for p in paths)
    assert not any("://" in p for p in paths)


def test_bash_rejects_numeric_literal_from_arithmetic():
    # Real attune phantom: SQL arithmetic `(duration_seconds % 86400)/3600`
    # extracts /3600 as a path-shaped token.
    cmd = 'sqlite3 db "SELECT (duration_seconds % 86400)/3600 AS hrs FROM x"'
    paths = extract_file_paths("Bash", {"command": cmd}, None)
    assert "/3600" not in paths
    assert "/86400" not in paths


def test_bash_rejects_numeric_literal_with_decimal():
    cmd = "sleep 3600.0 && echo /1000.0 done"
    paths = extract_file_paths("Bash", {"command": cmd}, None)
    assert "/3600.0" not in paths
    assert "/1000.0" not in paths


def test_bash_rejects_system_path_curl():
    cmd = 'docker compose exec ollama sh -c "ls /usr/bin/curl 2>/dev/null"'
    paths = extract_file_paths("Bash", {"command": cmd}, None)
    assert "/usr/bin/curl" not in paths


def test_bash_rejects_dev_null_redirect():
    cmd = "grep -n foo bar.py 2>/dev/null"
    paths = extract_file_paths("Bash", {"command": cmd}, None)
    assert "/dev/null" not in paths
    # Real path still extracted.
    assert "bar.py" in paths


def test_bash_rejects_tmp_scratch_path():
    cmd = 'cp /tmp/settings_main.json .claude/settings.json'
    paths = extract_file_paths("Bash", {"command": cmd}, None)
    assert not any(p.startswith("/tmp/") for p in paths)
    assert ".claude/settings.json" in paths


def test_bash_rejects_glob_star_pattern():
    cmd = 'find /Users/me/proj -type f -name "*.py" -o -name "*.md"'
    paths = extract_file_paths("Bash", {"command": cmd}, None)
    assert not any("*" in p for p in paths)


def test_bash_strips_markdown_bold_to_real_filename():
    # `gh pr create --body "**embeddings.py is broken**"` should yield
    # the bare filename, not `**embeddings.py`.
    cmd = 'gh pr create --body "rewrite **embeddings.py** to use new API"'
    paths = extract_file_paths("Bash", {"command": cmd}, None)
    assert "embeddings.py" in paths
    assert not any("*" in p for p in paths)


def test_read_keeps_system_path():
    # The Bash-only filter must NOT touch Read.file_path. Real reads of
    # /private/tmp/... session-task outputs (from sub-agents) appeared
    # in the attune audit and must be preserved.
    fp = "/private/tmp/claude-502/-Users-x-Projects-y/tasks/abc.output"
    paths = extract_file_paths("Read", {"file_path": fp}, None)
    assert paths == [fp]


def test_grep_result_keeps_api_directory_path():
    # The audit's classifier flagged `<cwd>/api/...` as URL — but real
    # files under a top-level `api/` directory must survive extraction.
    # This guards against any future tightening that confuses the two.
    result = (
        "/Users/me/proj/api/internal/views.py:10:def view():\n"
        "/Users/me/proj/api/external/handler.py:7:    pass\n"
    )
    paths = extract_file_paths("Grep", {"pattern": "view"}, result)
    assert "/Users/me/proj/api/internal/views.py" in paths
    assert "/Users/me/proj/api/external/handler.py" in paths
