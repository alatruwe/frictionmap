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
# and will otherwise bleed into extracted tokens. `*` and `?` are added so
# glob patterns (`*.py`, `**embeddings.py`) and `gh pr create` markdown
# bold (`**DEPLOYMENT.md`) don't survive as tokens. `:` is added so
# leading-colon artifacts (`:.claude/settings.json`) and URL host:port
# fragments (`localhost:8000`) terminate the run cleanly.
_EXCL = r"\s'\"`;|&<>$()[\]{}*?:"

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

# Bash-command text routinely contains arithmetic (`(duration_seconds %
# 86400)/3600`), system-binary paths (`/usr/bin/curl`, `/dev/null`), and
# scratch-file paths under /tmp — all of which the regex above happily
# turns into tokens. These filters apply ONLY in the Bash branch of
# extract_file_paths; Read/Edit/Write `file_path` and Grep/Glob result
# parsing are unaffected because they don't carry these artifacts.
_BASH_SYSTEM_PREFIXES = (
    "/usr/", "/bin/", "/sbin/", "/etc/", "/var/", "/tmp/",
    "/sys/", "/proc/", "/dev/",
    "/private/var/", "/private/tmp/", "/private/etc/",
)

# Grep output format: "<path>:<linenum>:<content>" for matches and
# "<path>-<linenum>-<content>" for -C context lines. Anchored to line
# start; takes the path prefix only.
_GREP_LINE_RE = re.compile(r"^([^\s:][^\s]*?)[-:]\d+[-:]")

# Tools that never attribute file paths, so extract_file_paths returns []
# for them: Skill/TaskOutput/TaskStop share Agent's "sub-delegation, files
# live elsewhere" property; the rest (TodoWrite, ExitPlanMode, ToolSearch,
# AskUserQuestion, WebSearch, WebFetch) are genuinely non-file-touching.
_SKIP_TOOLS = frozenset({
    "TodoWrite", "ExitPlanMode", "ToolSearch", "AskUserQuestion", "WebSearch",
    "WebFetch", "Skill", "TaskOutput", "TaskStop",
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


def _is_url_artifact(tok: str) -> bool:
    """Reject URL tails. The regex matches `//host/path` after the `://`
    of `https://host/path`, producing a token that starts with `//`. Real
    POSIX paths starting with `//` are vanishingly rare and not worth
    distinguishing here.
    """
    return tok.startswith("//") or "://" in tok


def _scan_string(s: str) -> list[str]:
    if not s:
        return []
    out: list[str] = []
    for raw in _FILE_TOKEN_RE.findall(s):
        tok = _strip_token(raw)
        if not tok or _is_url_artifact(tok):
            continue
        out.append(tok)
    return out


def _is_bash_numeric_only(tok: str) -> bool:
    """True when the final non-empty path segment has no alphabetic char.
    Catches arithmetic literals like /3600.0, /1000.0, /60, /2 from SQL
    or shell math that the regex picks up as paths.
    """
    segments = [s for s in tok.split("/") if s]
    if not segments:
        return False
    return not any(c.isalpha() for c in segments[-1])


def _is_bash_system_path(tok: str) -> bool:
    return any(tok.startswith(p) for p in _BASH_SYSTEM_PREFIXES)


def _filter_bash_paths(paths: list[str]) -> list[str]:
    return [
        p for p in paths
        if not _is_bash_system_path(p) and not _is_bash_numeric_only(p)
    ]


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
        return _dedup(_filter_bash_paths(paths))

    if tool_name == "Agent":
        # Sub-agent file touches live in `progress` events; the parser's
        # agent_progress walker recovers them. The Agent tool_use itself
        # doesn't reference files directly.
        return []

    if tool_name in _SKIP_TOOLS:
        return []

    # Anthropic ships new tools regularly; default to graceful skip (no
    # path extraction, no stdout output). DEBUG keeps the diagnostic
    # available without spamming users when an unknown tool appears.
    if tool_name not in _logged_unknown_tools:
        _logged_unknown_tools.add(tool_name)
        logger.debug("unknown tool name in file-path extraction: %s", tool_name)
    return []
