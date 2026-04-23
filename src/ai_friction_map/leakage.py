"""Per-file tool-behavior leakage counts.

Four detectors: edit_failures, grep_reformulations, bash_retries,
read_after_edit. All windowed detectors use windows.window_events so
compact_boundary events are hard stops.
"""
from __future__ import annotations

from ai_friction_map.events import Block, Corpus, LeakageCounts, ParsedEvent
from ai_friction_map.windows import window_events

_DEFAULT_N = 3

_EDIT_ERROR_MARKERS = (
    "string not found",
    "does not match",
    "no match",
    "error",
)
_ERROR_ANCHOR_CHARS = 100


def aggregate_leakage(corpus: Corpus, n: int = _DEFAULT_N) -> None:
    counts: dict[str, LeakageCounts] = {}
    for events in corpus.sessions.values():
        _count_edit_failures(events, corpus, counts, n)
        _count_grep_reformulations(events, counts, n)
        _count_bash_retries(events, corpus, counts, n)
        _count_read_after_edit(events, counts, n)
    for c in counts.values():
        c.total = (
            c.edit_failures
            + c.grep_reformulations
            + c.bash_retries
            + c.read_after_edit
        )
    corpus.leakage_by_file = counts


def _bump(counts: dict[str, LeakageCounts], path: str, field: str) -> None:
    if not path:
        return
    entry = counts.setdefault(path, LeakageCounts())
    setattr(entry, field, getattr(entry, field) + 1)


def _bump_all(counts: dict[str, LeakageCounts], paths: list[str], field: str) -> None:
    seen: set[str] = set()
    for p in paths:
        if p and p not in seen:
            seen.add(p)
            _bump(counts, p, field)


def _iter_tool_uses(events: list[ParsedEvent], tool_name: str):
    for idx, event in enumerate(events):
        for block in event.blocks:
            if block.type == "tool_use" and block.tool_name == tool_name:
                yield idx, event, block


def _result_content_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                t = item.get("text")
                if isinstance(t, str):
                    parts.append(t)
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return ""


def _has_edit_error(content) -> bool:
    text = _result_content_text(content)
    if not text:
        return False
    head = text[:_ERROR_ANCHOR_CHARS].lower()
    return any(m in head for m in _EDIT_ERROR_MARKERS)


def _result_looks_errored(content) -> bool:
    """Generic error signal for Bash: non-zero exit or stderr-shaped text.
    The session format doesn't expose exit codes directly; fall back to
    scanning result content for error markers anywhere (not just anchored).
    """
    text = _result_content_text(content).lower()
    if not text:
        return False
    markers = ("error", "traceback", "failed", "command not found",
               "syntax error", "permission denied")
    return any(m in text for m in markers)


def _count_edit_failures(
    events: list[ParsedEvent],
    corpus: Corpus,
    counts: dict[str, LeakageCounts],
    n: int,
) -> None:
    for idx, event, block in _iter_tool_uses(events, "Edit"):
        if not block.tool_use_id:
            continue
        tc = corpus.tool_calls.get(block.tool_use_id)
        edit_paths = list(block.file_paths)
        failure = False
        if tc is not None and _has_edit_error(tc.result_content):
            failure = True
        if not failure and edit_paths:
            _lo, hi = window_events(events, idx, n)
            for j in range(idx + 1, hi + 1):
                if _event_has_read_of(events[j], edit_paths):
                    failure = True
                    break
        if failure:
            _bump_all(counts, edit_paths, "edit_failures")


def _event_has_read_of(event: ParsedEvent, paths: list[str]) -> bool:
    target = set(paths)
    for block in event.blocks:
        if block.type == "tool_use" and block.tool_name == "Read":
            if any(p in target for p in block.file_paths):
                return True
    return False


def _count_grep_reformulations(
    events: list[ParsedEvent],
    counts: dict[str, LeakageCounts],
    n: int,
) -> None:
    greps = list(_iter_tool_uses(events, "Grep"))
    for i, (idx_a, _ev_a, block_a) in enumerate(greps):
        lo, hi = window_events(events, idx_a, n)
        for (idx_b, _ev_b, block_b) in greps[i + 1:]:
            if idx_b <= idx_a:
                continue
            if idx_b > hi or idx_b < lo:
                continue
            scope_a = (block_a.tool_input or {}).get("path")
            scope_b = (block_b.tool_input or {}).get("path")
            pat_a = (block_a.tool_input or {}).get("pattern")
            pat_b = (block_b.tool_input or {}).get("pattern")
            if scope_a != scope_b:
                continue
            if pat_a == pat_b:
                continue
            # Attribute to first Grep's canonical file_paths (post-resolve).
            _bump_all(counts, list(block_a.file_paths), "grep_reformulations")
            break  # only count one reformulation per first Grep


def _count_bash_retries(
    events: list[ParsedEvent],
    corpus: Corpus,
    counts: dict[str, LeakageCounts],
    n: int,
) -> None:
    bashes = list(_iter_tool_uses(events, "Bash"))
    for i, (idx_a, _ev_a, block_a) in enumerate(bashes):
        lo, hi = window_events(events, idx_a, n)
        cmd_a = (block_a.tool_input or {}).get("command", "")
        if not isinstance(cmd_a, str) or not cmd_a.strip():
            continue
        tokens_a = cmd_a.split()
        if not tokens_a:
            continue
        tc_a = corpus.tool_calls.get(block_a.tool_use_id) if block_a.tool_use_id else None
        a_errored = tc_a is not None and _result_looks_errored(tc_a.result_content)
        if not a_errored:
            continue
        for (idx_b, _ev_b, block_b) in bashes[i + 1:]:
            if idx_b <= idx_a:
                continue
            if idx_b > hi or idx_b < lo:
                continue
            cmd_b = (block_b.tool_input or {}).get("command", "")
            if not isinstance(cmd_b, str) or not cmd_b.strip():
                continue
            tokens_b = cmd_b.split()
            if not tokens_b or tokens_a[0] != tokens_b[0]:
                continue
            # Strict prefix-extension (continuation, not retry): cmd_b starts
            # with cmd_a plus more text. Excluded from retries.
            if cmd_b.startswith(cmd_a) and cmd_b != cmd_a:
                continue
            combined = list(block_a.file_paths) + list(block_b.file_paths)
            _bump_all(counts, combined, "bash_retries")
            break


def _count_read_after_edit(
    events: list[ParsedEvent],
    counts: dict[str, LeakageCounts],
    n: int,
) -> None:
    for idx, _event, block in _iter_tool_uses(events, "Edit"):
        if not block.file_paths:
            continue
        _lo, hi = window_events(events, idx, n)
        edit_paths = list(block.file_paths)
        for j in range(idx + 1, hi + 1):
            if _event_has_read_of(events[j], edit_paths):
                _bump_all(counts, edit_paths, "read_after_edit")
                break
