"""Phase 2C — assemble a schema-1.2 Report object from a parsed Corpus.

This is the integration point that ties 2B's corpus-level data to the
schema's per-file shape. Scoring fields (score, tangle_count,
score_components, baselines) are emitted as zero/empty scaffolds; Phase
3 populates them.
"""
from __future__ import annotations

import fnmatch
import re
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pathspec

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
    Highlight,
    LeakageCounts,
    ModelDistribution,
    Report,
    SCHEMA_VERSION,
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


# --- User-managed ignore (Phase 5b) ------------------------------------------
#
# Users extend the built-in noise filter two ways: a `.frictionmap-ignore` file
# (gitignore-style, discovered by walk-up from CWD) and a repeatable `--ignore`
# flag. Both feed a single compiled `pathspec.PathSpec`. This is OR'd with the
# 13 built-in defaults at the SAME presentation-layer seam (the per-path loop in
# `assemble_report`, after baselines are computed) — user patterns *add* to the
# defaults, never replace them, and never reshape the corpus baseline.
#
# Pre-flight (Phase 5b) confirmed pathspec's gitwildmatch matches the absolute
# path strings we carry (`/proj/...`) directly for the common non-anchored
# patterns, so no leading-slash normalization is applied here. If a match site
# is ever added that needs it, normalize at every site.

IGNORE_FILENAME = ".frictionmap-ignore"


def find_ignore_file(start: Path | None = None) -> Path | None:
    """Walk up from `start` (default CWD) for the nearest `.frictionmap-ignore`.

    Mirrors `resolve_sessions_dir`'s loop: check the current directory BEFORE
    stepping to the parent, so the nearest (deepest) file wins. Unlike the
    sessions-dir resolver, the ignore file is optional — returns None when no
    ancestor has one, rather than raising.
    """
    path = start or Path.cwd()
    while True:
        candidate = path / IGNORE_FILENAME
        if candidate.is_file():
            return candidate
        if path.parent == path:
            return None
        path = path.parent


def build_user_ignore(
    ignore_file: Path | None, cli_patterns: list[str]
) -> pathspec.PathSpec | None:
    """Compile file + flag patterns into one gitignore-semantics PathSpec.

    File lines come first, then `cli_patterns` — so a `--ignore '!foo'` flag
    wins over a file pattern (flag-overrides-file, an intentional default).
    `from_lines` skips blanks and `#` comments. Returns None when the combined
    list is empty, keeping the per-path check a cheap None test and leaving
    behavior identical to a no-ignore run.
    """
    lines: list[str] = []
    if ignore_file is not None:
        lines.extend(ignore_file.read_text(encoding="utf-8").splitlines())
    lines.extend(cli_patterns)  # flag after file: flag-overrides-file
    if not any(line.strip() and not line.lstrip().startswith("#") for line in lines):
        return None
    return pathspec.PathSpec.from_lines("gitwildmatch", lines)


# --- Passive noise hint (Phase 5b) -------------------------------------------
#
# A loose, non-binding nudge surfaced after a scan: if several top-ranked files
# look like generated/vendored noise the defaults didn't catch, point the user
# at `.frictionmap-ignore`. Deliberately loose and allowed to overlap the
# defaults (defaults already removed their matches, so overlap is inert). NOT
# pathspec — basename globs + path-segment substrings. If this ever migrates
# onto pathspec, it must carry the same path normalization as the match seam.

_NOISE_GLOBS: tuple[str, ...] = (
    "*.lock",
    "*.min.js",
    "*.min.css",
    "*.snap",
    "*.map",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Cargo.lock",
    "Gemfile.lock",
    "composer.lock",
)
_NOISE_SEGMENTS: tuple[str, ...] = ("vendor", "dist", "generated")


def _looks_like_noise(path: str) -> bool:
    basename = Path(path).name
    if any(fnmatch.fnmatch(basename, glob) for glob in _NOISE_GLOBS):
        return True
    segments = path.split("/")
    return any(seg in segments for seg in _NOISE_SEGMENTS)


def count_likely_noise_in_top(files: list[FileFriction], top_n: int = 20) -> int:
    """Count how many of the top-`top_n` (score-sorted) files look like noise."""
    return sum(1 for f in files[:top_n] if _looks_like_noise(f.path))


# --- Display-time path relativization (issue #1) -----------------------------
#
# The shipped report must not embed machine-identifying absolute paths. Two
# jobs, kept separate:
#   1. Best-effort *repo-relative* display via a derived strip-root
#      (`derive_strip_root` + `display_path`).
#   2. The actual *no-leak guarantee*: `_HOME_PREFIX_RE` redacts ANY home-dir
#      prefix (`/Users/<u>`, `/home/<u>` — local or foreign) to `~`,
#      derivation-independent. This is what keeps corpora recorded on another
#      machine leak-free when the slug can't derive their root.
# This runs AFTER assembly; the FS-read path (`canonicalize_path` →
# `compute_file_complexity`) stays absolute and is untouched.
#
# The user segment is matched WITHOUT a trailing slash and stops at the next
# slash OR whitespace, so it redacts both `/Users/bob/x` → `~/x` (structured
# paths) and a bare clause-final `/Users/bob` → `~` (prose). Requiring a
# trailing slash would leave the bare-prose form unredacted — a latent leak the
# acceptance grep would only catch if a corpus happened to contain that shape.

_HOME_PREFIX_RE = re.compile(r"/(?:Users|home)/[^/\s]+")
_HOME_SUB = "~"


def derive_strip_root(sessions_dir_name: str, file_paths: list[str]) -> str | None:
    """Decode the Claude Code sessions-dir slug into the project root.

    Claude Code names a project's sessions dir by replacing path slashes with
    dashes, so the slug is ambiguous when a real directory name contains a dash
    (`-Users-x-Projects-ai-friction-map` could decode to `.../ai/friction/map`
    or `.../ai-friction-map`). We repair the ambiguity by aligning the slug
    against a real recorded file path: a slug `-` matches a path `/` *or* `-`,
    any other character must match exactly, and the root is the path prefix that
    consumes the whole slug body at a path boundary.

    Returns None when no recorded path aligns — notably a corpus recorded on
    another machine, whose paths carry a different username than this machine's
    import-dir slug. The caller's home-prefix backstop keeps those leak-free.
    """
    body = sessions_dir_name.lstrip("-")
    if not body:
        return None
    for fp in file_paths:
        sample = fp.lstrip("/")
        i = j = 0
        ok = True
        while i < len(body):
            if j >= len(sample):
                ok = False
                break
            if body[i] == "-":
                if sample[j] not in ("/", "-"):
                    ok = False
                    break
            elif sample[j] != body[i]:
                ok = False
                break
            i += 1
            j += 1
        if ok and (j == len(sample) or sample[j] == "/"):
            return "/" + sample[:j]
    return None


def display_path(path: str, root: str | None) -> str:
    """Repo-relative display form of `path`.

    Strips `root/` when `path` is under it; otherwise applies the home-prefix
    backstop. A path the root isn't a prefix of and that carries no home prefix
    (e.g. a `/proj/...` test fixture) is returned unchanged.
    """
    if root:
        prefix = root.rstrip("/") + "/"
        if path == root:
            return ""
        if path.startswith(prefix):
            return path[len(prefix):]
    return _HOME_PREFIX_RE.sub(_HOME_SUB, path)


def redact_prose(
    text: str, highlights: list[Highlight]
) -> tuple[str, list[Highlight]]:
    """Home-redact absolute paths mentioned inline in thinking prose.

    `excerpt.text` ships in the payload verbatim and mentions absolute paths, so
    the same backstop applies. Redaction shortens the text, so highlight char
    offsets after each redacted span must shift by the cumulative length delta —
    otherwise marker bolding lands on the wrong characters.
    """
    matches = list(_HOME_PREFIX_RE.finditer(text))
    if not matches:
        return text, highlights
    new_text = _HOME_PREFIX_RE.sub(_HOME_SUB, text)
    # (original end-of-match offset, cumulative length delta through that match)
    checkpoints: list[tuple[int, int]] = []
    cum = 0
    for m in matches:
        cum += len(_HOME_SUB) - (m.end() - m.start())
        checkpoints.append((m.end(), cum))

    def remap(off: int) -> int:
        shift = 0
        for end, delta in checkpoints:
            if off >= end:
                shift = delta
            else:
                break
        return max(0, off + shift)

    new_highlights = [
        replace(h, start=remap(h.start), end=remap(h.end)) for h in highlights
    ]
    return new_text, new_highlights


def relativize_report(report: Report, root: str | None) -> Report:
    """Return a display copy of `report` with every path-bearing field made
    repo-relative (or home-redacted) and excerpt prose home-redacted.

    Deep-rebuilds nested excerpts/attribution/highlights via `dataclasses.replace`
    so a shared excerpt object (one excerpt can attribute to several files) is
    never mutated in place. `meta` carries no paths and is left untouched
    (its `name` was already derived in `assemble_report`).
    """
    def relativize_excerpt(ex: ThinkingExcerpt) -> ThinkingExcerpt:
        new_text, new_highlights = redact_prose(ex.text, ex.highlights)
        attribution = ex.attribution
        if attribution is not None:
            attribution = replace(
                attribution,
                file_paths=[display_path(p, root) for p in attribution.file_paths],
            )
        return replace(
            ex, text=new_text, highlights=new_highlights, attribution=attribution
        )

    new_files = [
        replace(
            f,
            path=display_path(f.path, root),
            directory=display_path(f.directory, root),
            excerpts=[relativize_excerpt(ex) for ex in f.excerpts],
        )
        for f in report.files
    ]
    return replace(report, files=new_files)


def _codebase_name(sessions_dir_name: str, file_paths: list[str]) -> str:
    """Display name for the codebase.

    Prefer the basename of the derived strip-root (robust, disambiguated by the
    real file paths). Fall back to the slug's last dash-segment when the root
    can't be derived (e.g. a corpus recorded on another machine).
    """
    root = derive_strip_root(sessions_dir_name, file_paths)
    if root:
        return Path(root).name
    if not sessions_dir_name:
        return ""
    return sessions_dir_name.rsplit("-", 1)[-1]


def assemble_report(
    corpus: Corpus,
    sessions_dir_name: str = "",
    sessions_dir: Path | None = None,
    user_ignore: pathspec.PathSpec | None = None,
) -> Report:
    """Build a Report from a fully-parsed Corpus.

    `sessions_dir_name` is the basename of the sessions directory
    (e.g. `-Users-adelinelatruwe-Projects-attune`); used to derive
    `meta.name`. Pass `""` if unknown.

    `sessions_dir`, when provided, is iterated to populate
    `Report.session_titles` (mapping session_id_short → most-recent
    aiTitle). Sessions without an extractable title are omitted.

    `user_ignore`, when provided, is OR'd with the built-in noise filter at
    the per-path seam below — hiding additional paths from `report.files`
    WITHOUT affecting the already-computed corpus/session baselines. Build it
    with `build_user_ignore(find_ignore_file(), cli_patterns)`.
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
        if _is_ignored(path) or (user_ignore is not None and user_ignore.match_file(path)):
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
            score=score_pre,
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
        name=_codebase_name(sessions_dir_name, [f.path for f in files]),
        session_count=corpus.session_count,
        file_count=len(files),
        thinking_block_count=_count_thinking_blocks(corpus),
        total_event_count=corpus.event_count,
        generated_at=datetime.now(timezone.utc).isoformat(),
        schema_version=SCHEMA_VERSION,
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
