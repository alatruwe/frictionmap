"""Path-extraction layer (spec §8, §9.7): action → file paths.

Two sources, per the written rule scope:
  * structured tool args per format (`path` of the editor tools, old SWE-agent
    `open`/`create`/`edit`, EPAM `Str Replace Editor`), and
  * bash command strings, per the rule table below. Their parser leaves these
    `None`; SAGE depends on this entirely.

Bash rule table (§8 scope, nothing beyond it):
  R1  `cd X && …` prefix stripping before the rules apply (repeated).
  R2  path arguments of `cat` `head` `tail` `less`: every non-flag argument.
  R3  path arguments of `sed` `awk` `grep` `rg`: the first non-flag argument is
      the script / pattern; every later non-flag argument is a path. `-e`,
      `-f`, `--file` consume the next token (script), and for grep/rg
      `-e PATTERN` / `--include=…` style options are not paths.
  R4  `python <script>` / `python3 <script>`: the first non-flag argument when it
      ends in `.py` (never `-m module` or `-c code`).
  R5  `>` / `>>` redirect targets.
Compound commands are split on `&&`, `||`, `;`, `|` and each simple command is
matched independently. Tokens are shell-split; quotes are removed.

EPAM `input_text` is a Python-repr dict → `ast.literal_eval`, never
`json.loads` and never a quote-swap fallback (§8).
"""
from __future__ import annotations

import ast
import re
import shlex
from dataclasses import dataclass, field
from typing import Any

READ_CMDS = {"cat", "head", "tail", "less"}
PATTERN_CMDS = {"sed", "awk", "grep", "rg"}
PYTHON_CMDS = {"python", "python3"}
EDITOR_TOOLS = {"str_replace_editor", "str_replace_based_edit_tool", "Str Replace Editor"}
SHELL_TOOLS = {"bash", "execute_bash", "Run Command Line Tool"}

_SPLIT_RE = re.compile(r"\s*(?:&&|\|\||;|\|)\s*")
_CD_PREFIX_RE = re.compile(r"^\s*cd\s+\S+\s*(?:&&|;)\s*")
# Options that take a value in the next token, per command family.
_VALUE_FLAGS = {
    "head": {"-n", "-c", "--lines", "--bytes"},
    "tail": {"-n", "-c", "--lines", "--bytes"},
    "sed": {"-e", "--expression", "-f", "--file"},
    "awk": {"-f", "-v", "-F"},
    "grep": {"-e", "--regexp", "-f", "--file", "--include", "--exclude", "--exclude-dir", "-m", "-A", "-B", "-C"},
    "rg": {"-e", "--regexp", "-f", "--file", "-g", "--glob", "-t", "--type", "-m", "-A", "-B", "-C"},
}


@dataclass(frozen=True)
class Action:
    """One action in a step's action set, with the paths the layer extracted."""
    tool: str                                   # family-native tool / verb name
    paths: tuple[str, ...] = ()
    command: str | None = None                  # shell command string when the tool is a shell
    args: dict[str, Any] | None = None          # structured args when present
    raw: str = ""                               # short raw form for provenance


@dataclass
class OldSweAgentState:
    """Old-format SWE-agent `edit` targets the currently open file (set by
    `open` / `create`); the state is tracked across a trajectory so `edit`
    resolves to a path. Documented stateful rule, not in the §8 bash table."""
    current_file: str | None = None
    edits_without_open_file: int = 0


# ---------------------------------------------------------------------------
# bash rule table
# ---------------------------------------------------------------------------

def _tokens(cmd: str) -> list[str]:
    try:
        return shlex.split(cmd, posix=True)
    except ValueError:
        return cmd.split()


def strip_cd_prefix(cmd: str) -> str:
    """R1: drop leading `cd X &&` / `cd X;` prefixes, repeatedly."""
    prev = None
    while prev != cmd:
        prev = cmd
        cmd = _CD_PREFIX_RE.sub("", cmd, count=1)
    return cmd


def _looks_like_path(tok: str) -> bool:
    return bool(tok) and not tok.startswith("-") and tok not in ("&&", "||", ";", "|") and tok != "."


def _redirect_targets(tokens: list[str]) -> list[str]:
    """R5."""
    out = []
    for i, t in enumerate(tokens):
        if t in (">", ">>") and i + 1 < len(tokens):
            out.append(tokens[i + 1])
        elif (t.startswith(">>") or t.startswith(">")) and len(t) > 2 and t.lstrip(">"):
            out.append(t.lstrip(">"))
    return out


def _strip_redirects(tokens: list[str]) -> list[str]:
    out = []
    skip = False
    for t in tokens:
        if skip:
            skip = False
            continue
        if t in (">", ">>", "2>", "2>>", "<"):
            skip = True
            continue
        if re.match(r"^\d?>{1,2}\S", t) or t.startswith("<"):
            continue
        out.append(t)
    return out


def _positional(tokens: list[str], value_flags: set[str]) -> list[str]:
    """Non-flag arguments after the command name, honouring value-taking flags."""
    out = []
    i = 1
    while i < len(tokens):
        t = tokens[i]
        if t == "--":
            out.extend(tokens[i + 1:])
            break
        if t in value_flags:
            i += 2
            continue
        if t.startswith("-"):
            i += 1
            continue
        out.append(t)
        i += 1
    return out


def bash_paths(cmd: str) -> list[str]:
    """Apply the §8 bash rule table to one command string."""
    cmd = strip_cd_prefix(cmd)
    found: list[str] = []
    for simple in _SPLIT_RE.split(cmd):
        simple = strip_cd_prefix(simple).strip()
        if not simple:
            continue
        tokens = _tokens(simple)
        if not tokens:
            continue
        # leading VAR=value assignments
        while tokens and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[0]):
            tokens = tokens[1:]
        if not tokens:
            continue
        redirects = _redirect_targets(tokens)                          # R5 (appended after the command's own paths)
        tokens = _strip_redirects(tokens)
        name = tokens[0].rsplit("/", 1)[-1]
        if name in READ_CMDS:                                          # R2
            found.extend(t for t in _positional(tokens, _VALUE_FLAGS.get(name, set())) if not t.isdigit())
        elif name in PATTERN_CMDS:                                     # R3
            pos = _positional(tokens, _VALUE_FLAGS.get(name, set()))
            # the script/pattern is the first positional unless -e/-f supplied one
            has_inline_script = any(t in _VALUE_FLAGS.get(name, set()) & {"-e", "--expression", "-f", "--file",
                                                                            "--regexp"}
                                    for t in tokens[1:])
            found.extend(pos if has_inline_script else pos[1:])
        elif name in PYTHON_CMDS:                                      # R4
            pos = _positional(tokens, {"-m", "-c", "-W", "-X"})
            if "-m" not in tokens and "-c" not in tokens and pos and pos[0].endswith(".py"):
                found.append(pos[0])
        found.extend(redirects)
    return _dedup(p for p in found if _looks_like_path(p))


def _dedup(items) -> list[str]:
    seen: set[str] = set()
    out = []
    for p in items:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


# ---------------------------------------------------------------------------
# structured args per format
# ---------------------------------------------------------------------------

def parse_epam_input_text(input_text: str) -> dict[str, Any] | None:
    """EPAM `input_text` is a Python-repr dict (68/68 in the recon sample)."""
    try:
        v = ast.literal_eval(input_text)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return None
    return v if isinstance(v, dict) else None


def structured_paths(tool: str, args: dict[str, Any] | None) -> list[str]:
    """Paths from structured tool args: editor `path`; shell `command` via the bash table."""
    if not args:
        return []
    if tool in EDITOR_TOOLS:
        p = args.get("path")
        return [p] if isinstance(p, str) and p else []
    if tool in SHELL_TOOLS:
        c = args.get("command")
        return bash_paths(c) if isinstance(c, str) else []
    return []


def action_from_args(tool: str, args: dict[str, Any] | None, raw: str = "") -> Action:
    command = args.get("command") if args and tool in SHELL_TOOLS and isinstance(args.get("command"), str) else None
    return Action(tool=tool, paths=tuple(structured_paths(tool, args)), command=command, args=args, raw=raw)


def action_from_bash(command: str, tool: str = "bash", raw: str = "") -> Action:
    return Action(tool=tool, paths=tuple(bash_paths(command)), command=command, args=None, raw=raw or command[:200])


def sweagent_new_action(action: str) -> Action:
    """New-format SWE-agent `action` string: `str_replace_editor <cmd> <path> …` or a bash command."""
    a = strip_cd_prefix(action.strip())
    tokens = _tokens(a)
    if tokens and tokens[0] == "str_replace_editor":
        path = tokens[2] if len(tokens) > 2 and _looks_like_path(tokens[2]) else None
        return Action(tool="str_replace_editor", paths=(path,) if path else (), command=None,
                      args={"command": tokens[1] if len(tokens) > 1 else None, "path": path}, raw=action[:200])
    return action_from_bash(action, raw=action[:200])


def sweagent_old_action(action: str, state: OldSweAgentState) -> Action:
    """Old-format SWE-agent commands: `open` / `create` / `edit` / `search_file` /
    `search_dir` / `find_file`; anything else goes through the bash table."""
    a = action.strip()
    first_line = a.split("\n", 1)[0]
    tokens = _tokens(first_line)
    verb = tokens[0] if tokens else ""
    if verb in ("open", "create") and len(tokens) > 1:
        state.current_file = tokens[1]
        return Action(tool=verb, paths=(tokens[1],), args={"path": tokens[1]}, raw=first_line[:200])
    if verb == "edit":
        if state.current_file is None:
            state.edits_without_open_file += 1
            return Action(tool="edit", paths=(), args={"path": None}, raw=first_line[:200])
        return Action(tool="edit", paths=(state.current_file,), args={"path": state.current_file},
                      raw=first_line[:200])
    if verb == "search_file":
        # search_file "term" [file]
        path = tokens[2] if len(tokens) > 2 else state.current_file
        return Action(tool=verb, paths=(path,) if path else (), args={"path": path}, raw=first_line[:200])
    if verb in ("search_dir", "find_file"):
        path = tokens[2] if len(tokens) > 2 else None
        return Action(tool=verb, paths=(path,) if path else (), args={"path": path}, raw=first_line[:200])
    if verb in ("goto", "scroll_down", "scroll_up", "submit", "exit_cost", "exit_context", "exit_error",
                "exit_format", "skip"):
        return Action(tool=verb, paths=(), raw=first_line[:200])
    return action_from_bash(a, raw=first_line[:200])


# The body may not contain another opener, so a call restarted after an abandoned
# opener (D1) matches from the *last* opener before its closer.
_TRAE_FN_RE = re.compile(r"<function=([^>\n]+)>((?:(?!<function=).)*?)</function>", re.S)
_TRAE_PARAM_RE = re.compile(r"<parameter=([^>\n]+)>(.*?)</parameter>", re.S)


def trae_actions(content: str) -> list[Action]:
    """Closed `<function=NAME>…</function>` blocks with their `<parameter=…>` args.
    An opener without a closer (abandoned call, D1) is not an action."""
    out = []
    for name, body in _TRAE_FN_RE.findall(content):
        params = {k: v.strip() for k, v in _TRAE_PARAM_RE.findall(body)}
        out.append(action_from_args(name.strip(), params, raw=f"<function={name.strip()}>"))
    return out


@dataclass
class PathIndex:
    """Touched-path set for one trajectory: every path any action produced."""
    paths: list[str] = field(default_factory=list)

    def add(self, action: Action) -> None:
        for p in action.paths:
            if p not in self.paths:
                self.paths.append(p)
