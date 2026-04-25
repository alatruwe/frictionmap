"""Phase 2C — assemble a schema-1.2 Report object from a parsed Corpus.

This is the integration point that ties 2B's corpus-level data to the
schema's per-file shape. Scoring fields (score, tangle_count,
score_components, baselines) are emitted as zero/empty scaffolds; Phase
3 populates them.
"""
from __future__ import annotations

import re
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from ai_friction_map.clusters import find_markers
from ai_friction_map.complexity import compute_file_complexity
from ai_friction_map.events import (
    Baselines,
    BlockSignals,
    CodebaseMeta,
    Corpus,
    FileFriction,
    LeakageCounts,
    Report,
    ThinkingExcerpt,
    ToolUsage,
)


_WORD_RE = re.compile(r"\S+")


def assemble_report(corpus: Corpus, sessions_dir_name: str = "") -> Report:
    """Build a Report from a fully-parsed Corpus.

    `sessions_dir_name` is the basename of the sessions directory
    (e.g. `-Users-adelinelatruwe-Projects-attune`); used to derive
    `meta.name`. Pass `""` if unknown.
    """
    expanded_excerpts_per_session = _expand_excerpts(corpus)
    interesting_files = _interesting_files(corpus, expanded_excerpts_per_session)
    excerpts_by_file = _index_excerpts_by_file(expanded_excerpts_per_session)
    sessions_by_file = _sessions_by_file(corpus, expanded_excerpts_per_session)

    files: list[FileFriction] = []
    for path in sorted(interesting_files):
        complexity = compute_file_complexity(path)
        leakage = corpus.leakage_by_file.get(path, LeakageCounts())
        tool_usage = corpus.tool_usage_by_file.get(path, ToolUsage())
        excerpts = sorted(
            excerpts_by_file.get(path, []),
            key=lambda e: (-e.block_signals.marker_count, -e.cluster_count, e.block_index),
        )[:5]
        path_obj = Path(path)
        files.append(FileFriction(
            path=path,
            name=path_obj.name,
            directory=str(path_obj.parent) + "/",
            session_count=len(sessions_by_file.get(path, set())),
            loc=complexity.loc,
            complexity=complexity,
            leakage=leakage,
            tool_usage=tool_usage,
            excerpts=excerpts,
        ))

    files.sort(key=lambda f: f.score, reverse=True)

    meta = CodebaseMeta(
        name=_extract_codebase_name(sessions_dir_name),
        session_count=corpus.session_count,
        file_count=len(files),
        thinking_block_count=_count_thinking_blocks(corpus),
        total_event_count=corpus.event_count,
        generated_at=datetime.now(timezone.utc).isoformat(),
        schema_version="1.2",
    )

    return Report(
        meta=meta,
        baselines=Baselines(),
        session_baselines={},
        files=files,
    )


def _expand_excerpts(corpus: Corpus) -> dict[str, list[ThinkingExcerpt]]:
    """Per session, denormalize block-level metadata onto each excerpt.

    Returns session_id -> list of excerpts (in block order). Each excerpt
    is a fresh dataclass with all schema-1.2 fields populated.
    """
    out: dict[str, list[ThinkingExcerpt]] = {}
    for session_id, events in corpus.sessions.items():
        thinking_blocks = [
            (event, block)
            for event in events
            for block in event.blocks
            if block.type == "thinking" and block.thinking
        ]
        block_total = len(thinking_blocks)
        expanded: list[ThinkingExcerpt] = []
        for block_index, (_event, block) in enumerate(thinking_blocks):
            text = block.thinking or ""
            length_words = _word_count(text)
            length_chars = len(text)
            marker_count = len(find_markers(text))
            block_signals = BlockSignals(
                length_words=length_words,
                length_chars=length_chars,
                marker_count=marker_count,
            )
            for excerpt in block.excerpts:
                expanded.append(replace(
                    excerpt,
                    agent_sourced=block.agent_sourced,
                    session_id=session_id,
                    session_id_short=session_id[:8],
                    block_index=block_index,
                    block_total=block_total,
                    block_length_words=length_words,
                    attribution=block.attribution,
                    block_signals=block_signals,
                ))
        out[session_id] = expanded
    return out


def _interesting_files(
    corpus: Corpus,
    expanded_excerpts_per_session: dict[str, list[ThinkingExcerpt]],
) -> set[str]:
    files: set[str] = set()
    files.update(corpus.leakage_by_file.keys())
    files.update(corpus.tool_usage_by_file.keys())
    for excerpts in expanded_excerpts_per_session.values():
        for excerpt in excerpts:
            if excerpt.attribution and excerpt.attribution.file_paths:
                files.update(excerpt.attribution.file_paths)
    return files


def _index_excerpts_by_file(
    expanded_excerpts_per_session: dict[str, list[ThinkingExcerpt]],
) -> dict[str, list[ThinkingExcerpt]]:
    out: dict[str, list[ThinkingExcerpt]] = {}
    for excerpts in expanded_excerpts_per_session.values():
        for excerpt in excerpts:
            if not excerpt.attribution:
                continue
            for path in excerpt.attribution.file_paths:
                out.setdefault(path, []).append(excerpt)
    return out


def _sessions_by_file(
    corpus: Corpus,
    expanded_excerpts_per_session: dict[str, list[ThinkingExcerpt]],
) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for session_id, events in corpus.sessions.items():
        for event in events:
            for block in event.blocks:
                if block.type == "tool_use":
                    for path in block.file_paths:
                        if path:
                            out.setdefault(path, set()).add(session_id)
    for tc in corpus.tool_calls.values():
        for path in tc.file_paths:
            if path:
                out.setdefault(path, set()).add(tc.session_id)
    for session_id, excerpts in expanded_excerpts_per_session.items():
        for excerpt in excerpts:
            if not excerpt.attribution:
                continue
            for path in excerpt.attribution.file_paths:
                out.setdefault(path, set()).add(session_id)
    return out


def _count_thinking_blocks(corpus: Corpus) -> int:
    total = 0
    for events in corpus.sessions.values():
        for event in events:
            for block in event.blocks:
                if block.type == "thinking":
                    total += 1
    return total


def _word_count(text: str) -> int:
    return len(_WORD_RE.findall(text))


def _extract_codebase_name(sessions_dir_name: str) -> str:
    """Derive a codebase name from a Claude Code project-dir basename.

    TODO: real path-encoding parser. For v1, we use a heuristic:
    Claude Code encodes project paths by replacing slashes with dashes,
    so `-Users-x-Projects-my-cool-project` is ambiguous (was the dir
    `my-cool-project` or `my/cool/project`?). The heuristic prefers the
    common case: the project lives under a `Projects/` directory, so
    take everything after the last `-Projects-`.
    """
    if not sessions_dir_name:
        return ""
    marker = "-Projects-"
    idx = sessions_dir_name.rfind(marker)
    if idx >= 0:
        return sessions_dir_name[idx + len(marker):]
    parts = sessions_dir_name.split("-")
    return parts[-1] if parts else ""
