"""Session-listing and session-matching helpers for the CLI.

Streaming-reads the JSONL files just enough to extract `ai-title` events
and filter by mtime. Heavier work (parse a single matched session through
the full pipeline) is delegated to `parse_sessions` over a temp dir
containing the one file.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_HOURS = 12.0
_UUID_PREFIX_RE = re.compile(r"^[0-9a-f]{8,}$", re.IGNORECASE)


@dataclass
class ActiveSession:
    session_id: str
    title: str
    mtime: float
    path: Path


@dataclass
class MatchResult:
    matches: list[ActiveSession]
    matched_by: str  # "uuid", "title", or "" if zero matches


def find_active_sessions(
    sessions_dir: Path,
    within_hours: float = DEFAULT_WINDOW_HOURS,
    now: float | None = None,
) -> list[ActiveSession]:
    cutoff = (now if now is not None else time.time()) - within_hours * 3600
    out: list[ActiveSession] = []
    for path in sessions_dir.glob("*.jsonl"):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime < cutoff:
            continue
        title = _last_ai_title(path)
        out.append(ActiveSession(
            session_id=path.stem,
            title=title,
            mtime=mtime,
            path=path,
        ))
    out.sort(key=lambda s: s.mtime, reverse=True)
    return out


def list_all_sessions(sessions_dir: Path) -> list[ActiveSession]:
    """All sessions with their last ai-title, sorted by mtime desc."""
    out: list[ActiveSession] = []
    for path in sessions_dir.glob("*.jsonl"):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        out.append(ActiveSession(
            session_id=path.stem,
            title=_last_ai_title(path),
            mtime=mtime,
            path=path,
        ))
    out.sort(key=lambda s: s.mtime, reverse=True)
    return out


def match_session(sessions_dir: Path, identifier: str) -> MatchResult:
    all_sessions = list_all_sessions(sessions_dir)
    if _UUID_PREFIX_RE.match(identifier):
        prefix = identifier.lower()
        uuid_matches = [s for s in all_sessions if s.session_id.lower().startswith(prefix)]
        if uuid_matches:
            return MatchResult(matches=uuid_matches, matched_by="uuid")
    needle = identifier.lower()
    title_matches = [s for s in all_sessions if needle in s.title.lower()]
    if title_matches:
        return MatchResult(matches=title_matches, matched_by="title")
    return MatchResult(matches=[], matched_by="")


def format_relative_time(mtime: float, now: float | None = None) -> str:
    delta = (now if now is not None else time.time()) - mtime
    if delta < 60:
        return "just now"
    if delta < 3600:
        minutes = int(delta // 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    hours = int(delta // 3600)
    return f"{hours} hour{'s' if hours != 1 else ''} ago"


def summarize_session(session_id: str, sessions_dir: Path) -> str:
    """Build a human-readable session summary for `session <id>` one-match.

    Re-parses just the one session by copying the file into a temp dir
    and running parse_sessions over it. Uses the cached corpus baseline
    (written by `scan`) so per-file scoring matches the HTML report's
    z-scored ranking; falls back to absolute (raw × weight) scoring
    when the cache is missing.
    """
    import tempfile

    from frictionmap.baselines import load_baseline_cache
    from frictionmap.events import BaselineSet
    from frictionmap.parser import parse_sessions
    from frictionmap.report import assemble_report
    from frictionmap.scoring import score_corpus

    src_path = sessions_dir / f"{session_id}.jsonl"
    if not src_path.exists():
        return f"Session file not found: {src_path}"

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        (td_path / src_path.name).write_bytes(src_path.read_bytes())
        corpus = parse_sessions(td_path)
        report = assemble_report(corpus, sessions_dir_name=sessions_dir.name)

    cached = load_baseline_cache()
    warning = ""
    if cached is None:
        warning = (
            "baseline cache absent — using absolute (raw × weight) scoring. "
            "Run 'frictionmap scan' first to enable z-scored ranking "
            "that matches the HTML report."
        )
        baseline = BaselineSet()  # mad=0 → z=0 → contribution = raw * 0 → effectively raw-anchored
    else:
        baseline = cached

    # Re-score against the chosen baseline (corpus cache or empty fallback).
    # Empty baseline yields z=0; we then rank by raw × weight as a fallback.
    file_scores = score_corpus(corpus, baseline)
    ranked: list[tuple[float, object, int]] = []
    for f in report.files:
        result = file_scores.get(f.path)
        if cached is None:
            # Fallback rank: sum(raw × weight) — bypasses z-score entirely.
            score = 0.0
            if result is not None:
                for sv in (
                    result.components.markers, result.components.block_length_words,
                    result.components.question_rate_per_100w,
                    result.components.tool_use_coupling, result.components.reread_bursts,
                    result.components.edit_churn,
                    result.components.reasoning_to_output_ratio,
                    result.components.edit_failures,
                    result.components.grep_reformulations,
                    result.components.bash_retries, result.components.read_after_edit,
                ):
                    score += sv.raw * sv.weight
            score = score / max(f.loc, 1)
        else:
            score = result.score_pre_normalization / max(f.loc, 1) if result else 0.0
        tool_total = (
            f.tool_usage.read + f.tool_usage.edit + f.tool_usage.write
            + f.tool_usage.bash + f.tool_usage.grep + f.tool_usage.glob
        )
        ranked.append((score, f, tool_total))
    ranked.sort(key=lambda r: r[0], reverse=True)

    title = _last_ai_title(src_path)
    events = corpus.sessions.get(session_id, [])
    turn_count = sum(1 for e in events if e.type == "user")
    files_touched = len(report.files)
    thinking_block_count = report.meta.thinking_block_count

    lines = [
        f"Session: {session_id[:8]} \"{title}\"",
        f"Turns: {turn_count} | Files touched: {files_touched} | "
        f"Thinking blocks: {thinking_block_count}",
    ]
    if warning:
        lines.append(f"Warning: {warning}")
    lines.append("")
    lines.append("Top friction this session:")
    if not ranked:
        lines.append("  (no signals)")
    else:
        for score, f, tool_total in ranked[:5]:
            summary = (
                f"score {score:.3f} | {tool_total} tool uses, "
                f"{f.leakage.total} leakage events, "
                f"{len(f.excerpts)} marker excerpts"
            )
            lines.append(f"  {f.path}    {summary}")
    return "\n".join(lines)


def _last_ai_title(path: Path) -> str:
    title = "(untitled)"
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("type") != "ai-title":
                    continue
                # Claude Code's actual field is `aiTitle`. Older synthetic
                # fixtures use `content`/`title`; try each defensively.
                candidate = (
                    record.get("aiTitle")
                    or record.get("title")
                    or record.get("content")
                    or _nested_message_text(record)
                )
                if candidate:
                    title = candidate.strip() or title
    except OSError:
        return title
    return title


def _nested_message_text(record: dict) -> str | None:
    msg = record.get("message")
    if isinstance(msg, dict):
        content = msg.get("content")
        if isinstance(content, str):
            return content
    return None
