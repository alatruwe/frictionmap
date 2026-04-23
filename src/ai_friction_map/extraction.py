from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_PATH_SUFFIXES = (
    "py", "js", "ts", "jsx", "tsx",
    "md", "yaml", "yml", "toml", "json",
    "sh", "sql", "html", "css", "rs", "go",
)

_SUFFIX_ALT = "|".join(_PATH_SUFFIXES)
# Shell metacharacters + brackets. Brackets show up in prose ("[file.py]")
# and will otherwise bleed into extracted tokens.
_EXCL = r"\s'\"`;|&<>$()[\]{}"

# Two branches:
#   (a) starts with '/', './', or '../' — token run of non-metachar chars.
#       Lookbehind rules out a leading word char so that "header/separator"
#       in prose doesn't match "/separator".
#   (b) ends in a known source-file suffix (bare filenames included, by
#       design per checkpoint discussion).
_FILE_TOKEN_RE = re.compile(
    rf"(?<![\w])(?:/|\./|\.\./)[^{_EXCL}]*"
    rf"|[^{_EXCL}]+\.(?:{_SUFFIX_ALT})\b"
)

_TRAILING_TRASH = ",;:"

# Grep output format: "<path>:<linenum>:<content>" for matches and
# "<path>-<linenum>-<content>" for -C context lines. Anchored to line
# start; takes the path prefix only.
_GREP_LINE_RE = re.compile(r"^([^\s:][^\s]*?)[-:]\d+[-:]")

# Skill/TaskOutput/TaskStop share Agent's "sub-delegation, files live
# elsewhere" property; the others are genuinely non-file-touching.
_SKIP_TOOLS = frozenset({
    "TodoWrite", "ExitPlanMode", "ToolSearch", "AskUserQuestion", "WebSearch",
    "Skill", "TaskOutput", "TaskStop",
})

_logged_unknown_tools: set[str] = set()


def _reset_logged_unknown_tools() -> None:
    """Test hook: clear the process-wide dedup set so independent tests
    that exercise the unknown-tool warning path don't pollute each other.
    Not part of the public API; tests import this via a conftest fixture.
    """
    _logged_unknown_tools.clear()


def _strip_token(tok: str) -> str:
    return tok.rstrip(_TRAILING_TRASH)


def _scan_string(s: str) -> list[str]:
    if not s:
        return []
    return [t for t in (_strip_token(m) for m in _FILE_TOKEN_RE.findall(s)) if t]


def _extract_grep_result(text: str) -> list[str]:
    """Parse a Grep/Glob tool_result content string line by line.

    Grep output lines look like "path:NN:content" (match) or
    "path-NN-content" (context with -C) or bare "--" separators; Glob
    output is one path per line.
    """
    out: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line == "--":
            continue
        m = _GREP_LINE_RE.match(line)
        if m:
            out.append(m.group(1))
            continue
        # No linenum marker: line is just a path (Grep -l or Glob).
        # Fall back to the generic scanner to still tolerate weirdness.
        matches = _scan_string(line)
        if matches:
            out.extend(matches)
        elif "/" in line and " " not in line:
            out.append(line)
    return out


def _scan_result(content: str | list | None) -> list[str]:
    if content is None:
        return []
    if isinstance(content, str):
        return _extract_grep_result(content)
    out: list[str] = []
    for item in content:
        if isinstance(item, dict):
            text = item.get("text")
            if isinstance(text, str):
                out.extend(_extract_grep_result(text))
        elif isinstance(item, str):
            out.extend(_extract_grep_result(item))
    return out


def _dedup(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for p in paths:
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def extract_file_paths(
    tool_name: str,
    tool_input: dict | None,
    tool_result_content: str | list | None,
) -> list[str]:
    """Extract raw (uncanonicalized) file paths from a tool_use + its result.

    Canonicalization happens at the parser layer, not here. Returns [] for
    tools that don't reference files.
    """
    tool_input = tool_input or {}

    if tool_name in ("Read", "Edit", "Write"):
        fp = tool_input.get("file_path")
        return [fp] if isinstance(fp, str) and fp else []

    if tool_name == "Grep":
        paths: list[str] = []
        scope = tool_input.get("path")
        if isinstance(scope, str) and scope:
            paths.append(scope)
        paths.extend(_scan_result(tool_result_content))
        return _dedup(paths)

    if tool_name == "Glob":
        paths = []
        scope = tool_input.get("path")
        if isinstance(scope, str) and scope:
            paths.append(scope)
        paths.extend(_scan_result(tool_result_content))
        return _dedup(paths)

    if tool_name == "Bash":
        paths = []
        cmd = tool_input.get("command")
        if isinstance(cmd, str):
            paths.extend(_scan_string(cmd))
        desc = tool_input.get("description")
        if isinstance(desc, str):
            paths.extend(_scan_string(desc))
        return _dedup(paths)

    if tool_name == "Agent":
        # Sub-agent file touches live in `progress` events; the parser's
        # agent_progress walker recovers them. The Agent tool_use itself
        # doesn't reference files directly.
        return []

    if tool_name in _SKIP_TOOLS:
        return []

    if tool_name not in _logged_unknown_tools:
        _logged_unknown_tools.add(tool_name)
        logger.warning("unknown tool name in file-path extraction: %s", tool_name)
    return []
