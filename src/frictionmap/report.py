"""Phase 2C — assemble a schema-1.2 Report object from a parsed Corpus.

This is the integration point that ties 2B's corpus-level data to the
schema's per-file shape. Scoring fields (score, tangle_count,
score_components, baselines) are emitted as zero/empty scaffolds; Phase
3 populates them.
"""
from __future__ import annotations

import fnmatch
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from frictionmap.baselines import (
    compute_corpus_baseline,
    compute_session_baselines,
)
from frictionmap.complexity import compute_file_complexity
from frictionmap.events import (
    Baselines,
    CodebaseMeta,
    Corpus,
    FileFriction,
    LeakageCounts,
    ModelDistribution,
    Report,
    ThinkingExcerpt,
    ToolUsage,
)
from frictionmap.scoring import compute_block_signals, score_corpus


IGNORE_PATTERNS: tuple[str, ...] = (
    ".git/",
    "__pycache__/",
    "*.pyc",
    "node_modules/",
    ".venv/",
    "venv/",
    "dist/",
    "build/",
    ".next/",
    ".cache/",
    ".claude/",
    ".env",
    ".env.*",
    ".DS_Store",
)


def _is_ignored(canonical_path: str) -> bool:
    """Return True if `canonical_path` matches any built-in noise pattern.

    Patterns are gitignore-flavored: trailing-slash patterns match if the
    segment appears anywhere in the path; glob patterns match the basename;
    bare names match the basename exactly.
    """
    basename = Path(canonical_path).name
    for pattern in IGNORE_PATTERNS:
        if pattern.endswith("/"):
            if f"/{pattern}" in canonical_path or canonical_path.startswith(pattern):
                return True
        elif "*" in pattern or "?" in pattern:
            if fnmatch.fnmatch(basename, pattern):
                return True
        else:
            if basename == pattern:
                return True
    return False


def assemble_report(
    corpus: Corpus,
    sessions_dir_name: str = "",
    sessions_dir: Path | None = None,
) -> Report:
    """Build a Report from a fully-parsed Corpus.

    `sessions_dir_name` is the basename of the sessions directory
    (e.g. `-Users-adelinelatruwe-Projects-attune`); used to derive
    `meta.name`. Pass `""` if unknown.

    `sessions_dir`, when provided, is iterated to populate
    `Report.session_titles` (mapping session_id_short → most-recent
    aiTitle). Sessions without an extractable title are omitted.
    """
    expanded_excerpts_per_session = _expand_excerpts(corpus)
    interesting_files = _interesting_files(corpus, expanded_excerpts_per_session)
    excerpts_by_file = _index_excerpts_by_file(expanded_excerpts_per_session)
    sessions_by_file = _sessions_by_file(corpus, expanded_excerpts_per_session)

    corpus_baseline = compute_corpus_baseline(corpus)
    session_baselines = compute_session_baselines(corpus)
    file_scores = score_corpus(corpus, corpus_baseline)

    files: list[FileFriction] = []
    for path in sorted(interesting_files):
        if _is_ignored(path):
            continue
        complexity = compute_file_complexity(path)
        leakage = corpus.leakage_by_file.get(path, LeakageCounts())
        tool_usage = corpus.tool_usage_by_file.get(path, ToolUsage())
        # Drop URL fragments, git-revision shorthand, ephemeral temp dirs,
        # and number-shaped tokens that score / max(loc, 1) = score / 1
        # boosts to the top. Filter when the file isn't on disk AND Claude
        # never edited or wrote it — keeps Claude-touched-and-deleted files.
        if (
            complexity.loc == 0
            and tool_usage.edit == 0
            and tool_usage.write == 0
        ):
            continue
        excerpts = sorted(
            excerpts_by_file.get(path, []),
            key=lambda e: (-e.block_signals.marker_count, -e.cluster_count, e.block_index),
        )[:5]
        path_obj = Path(path)
        score_result = file_scores.get(path)
        if score_result is not None:
            components = score_result.components
            score_pre = score_result.score_pre_normalization
            tangle_count = score_result.tangle_count
            thinking_resolution_rate = score_result.thinking_resolution_rate
        else:
            components = FileFriction.__dataclass_fields__["score_components"].default_factory()
            score_pre = 0.0
            tangle_count = 0
            thinking_resolution_rate = 0.0
        components.normalized_by_loc = score_pre / max(complexity.loc, 1)
        if complexity.cyclomatic and complexity.cyclomatic.sum > 0:
            components.normalized_by_complexity = score_pre / complexity.cyclomatic.sum
        else:
            components.normalized_by_complexity = None
        files.append(FileFriction(
            path=path,
            name=path_obj.name,
            directory=str(path_obj.parent) + "/",
            score=components.normalized_by_loc,
            tangle_count=tangle_count,
            thinking_resolution_rate=thinking_resolution_rate,
            session_count=len(sessions_by_file.get(path, set())),
            loc=complexity.loc,
            complexity=complexity,
            leakage=leakage,
            tool_usage=tool_usage,
            excerpts=excerpts,
            score_components=components,
        ))

    files.sort(key=lambda f: f.score, reverse=True)

    meta = CodebaseMeta(
        name=_extract_codebase_name(sessions_dir_name),
        session_count=corpus.session_count,
        file_count=len(files),
        thinking_block_count=_count_thinking_blocks(corpus),
        total_event_count=corpus.event_count,
        generated_at=datetime.now(timezone.utc).isoformat(),
        schema_version="1.3",
        model_distribution=_count_models(corpus),
    )

    return Report(
        meta=meta,
        baselines=Baselines(corpus=corpus_baseline),
        session_baselines=session_baselines,
        files=files,
        session_titles=_build_session_titles(sessions_dir),
    )


def _build_session_titles(sessions_dir: Path | None) -> dict[str, str]:
    if sessions_dir is None:
        return {}
    from frictionmap.sessions import _last_ai_title
    titles: dict[str, str] = {}
    for path in sessions_dir.glob("*.jsonl"):
        title = _last_ai_title(path)
        if title and title != "(untitled)":
            titles[path.stem[:8]] = title
    return titles


def _expand_excerpts(corpus: Corpus) -> dict[str, list[ThinkingExcerpt]]:
    """Per session, denormalize block-level metadata onto each excerpt.

    Returns session_id -> list of excerpts (in block order). Each excerpt
    is a fresh dataclass with all schema-1.2 fields populated.
    """
    out: dict[str, list[ThinkingExcerpt]] = {}
    for session_id, events in corpus.sessions.items():
        thinking_entries: list[tuple[int, object]] = []
        for event_idx, event in enumerate(events):
            for block in event.blocks:
                if block.type == "thinking" and block.thinking:
                    thinking_entries.append((event_idx, block))
        block_total = len(thinking_entries)
        expanded: list[ThinkingExcerpt] = []
        for block_index, (event_idx, block) in enumerate(thinking_entries):
            text = block.thinking or ""
            block_signals = compute_block_signals(text, event_idx, events)
            for excerpt in block.excerpts:
                expanded.append(replace(
                    excerpt,
                    agent_sourced=block.agent_sourced,
                    session_id=session_id,
                    session_id_short=session_id[:8],
                    block_index=block_index,
                    block_total=block_total,
                    block_length_words=block_signals.length_words,
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


# Schema entry for model_distribution lives in the Claude Desktop
# project's schema.md, not in this repo. Update both when the shape
# changes.
def _count_models(corpus: Corpus) -> ModelDistribution:
    events_by_model: dict[str, int] = {}
    sessions_by_model: dict[str, int] = {}
    unknown = 0
    for events in corpus.sessions.values():
        models_in_session: set[str] = set()
        for event in events:
            if event.model is not None:
                events_by_model[event.model] = events_by_model.get(event.model, 0) + 1
                models_in_session.add(event.model)
            elif event.is_assistant_like:
                unknown += 1
        for m in models_in_session:
            sessions_by_model[m] = sessions_by_model.get(m, 0) + 1
    return ModelDistribution(
        events_by_model=events_by_model,
        sessions_by_model=sessions_by_model,
        unknown_model_event_count=unknown,
    )


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
