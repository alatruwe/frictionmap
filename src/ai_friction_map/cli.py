from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from ai_friction_map import __version__
from ai_friction_map.baselines import save_baseline_cache
from ai_friction_map.parser import parse_sessions
from ai_friction_map.render import load_template_assets, render_report
from ai_friction_map.report import assemble_report
from ai_friction_map.sessions import (
    find_active_sessions,
    format_relative_time,
    match_session,
    summarize_session,
)
from ai_friction_map.windows import get_boundary_clip_count, reset_boundary_clip_count

ACTIVE_SESSION_WINDOW_HOURS = 12


def resolve_sessions_dir(start: Path | None = None) -> Path:
    """Find the Claude Code sessions directory for the current project.

    Walks up from `start` (default: CWD) checking each ancestor directory
    for a matching entry under ~/.claude/projects/. Returns the first
    match found — so the nearest (deepest) match wins.

    Raises FileNotFoundError with a message listing every checked path
    if no ancestor has Claude Code sessions.
    """
    start_path = (start or Path.cwd())
    path = start_path
    checked: list[Path] = []
    while True:
        # Order is load-bearing: check the current path BEFORE stepping to
        # parent. This is what makes nearest-match-wins work when both a
        # directory and its subdirectory have sessions dirs.
        slug = str(path).replace("/", "-")
        candidate = Path.home() / ".claude" / "projects" / slug
        checked.append(candidate)
        if candidate.exists():
            return candidate
        if path.parent == path:
            break
        path = path.parent
    raise FileNotFoundError(_format_not_found(start_path, checked))


def _format_not_found(start: Path, checked: list[Path]) -> str:
    lines = [
        "No Claude Code sessions found for this directory or any parent.",
        f"  Started from: {start}",
        "  Checked:",
    ]
    lines.extend(f"    {p}" for p in checked)
    lines.append("")
    lines.append("cd to a project where you've used Claude Code and try again.")
    return "\n".join(lines)


def _cmd_scan(args: argparse.Namespace) -> int:
    sessions_dir = resolve_sessions_dir()
    reset_boundary_clip_count()
    corpus = parse_sessions(sessions_dir)
    report = assemble_report(
        corpus,
        sessions_dir_name=sessions_dir.name,
        sessions_dir=sessions_dir,
    )
    template, app_jsx, styles_css = load_template_assets()
    rendered = render_report(report, template, app_jsx, styles_css)
    Path("report.html").write_text(rendered, encoding="utf-8")
    save_baseline_cache(report.baselines.corpus)
    print(
        f"Parsed {corpus.session_count} sessions across "
        f"{corpus.event_count} events. "
        f"{len(report.files)} files with friction signals. "
        f"Report: report.html"
    )
    if args.checkpoint or os.environ.get("AI_FRICTION_MAP_CHECKPOINT") == "1":
        _print_checkpoint(corpus, report)
    return 0


def _cmd_active_sessions(args: argparse.Namespace) -> int:
    sessions_dir = resolve_sessions_dir()
    sessions = find_active_sessions(sessions_dir, within_hours=ACTIVE_SESSION_WINDOW_HOURS)
    if not sessions:
        print(f"No sessions with activity in the last {ACTIVE_SESSION_WINDOW_HOURS} hours.")
        return 0
    print(
        f"{len(sessions)} session{'s' if len(sessions) != 1 else ''} "
        f"with activity in the last {ACTIVE_SESSION_WINDOW_HOURS} hours:"
    )
    for s in sessions:
        print(
            f"  [{s.session_id[:8]}]  \"{s.title}\"    {format_relative_time(s.mtime)}"
        )
    print("Run: ai-friction-map session <id-or-title-query>")
    return 0


def _print_checkpoint(corpus, report) -> None:
    """Phase 3 diagnostic snapshot. Surface anomalies; do not fix.

    Seven sections: top-20 ranking, leakage signal correlation, baseline
    stability, model distribution, multi-file weight distribution,
    boundary-clip count, file count. Tuning lives in Phase 5.
    """
    from statistics import mean
    print()
    print("=" * 70)
    print("Phase 3 checkpoint")
    print("=" * 70)

    # 1. Top-20 ranking with dominant-component flag.
    top = sorted(report.files, key=lambda f: f.score, reverse=True)[:20]
    print("\n[1] Top-20 by score (normalized_by_loc):")
    print(f"{'rank':>4}  {'score':>10}  {'tangle':>6}  {'mfw':>5}  "
          f"{'top-component':<28}  path")
    for i, f in enumerate(top, 1):
        comp_pairs = [
            (name, getattr(f.score_components, name).contribution)
            for name in (
                "markers", "block_length_words", "question_rate_per_100w",
                "tool_use_coupling", "reread_bursts", "edit_churn",
                "reasoning_to_output_ratio", "edit_failures",
                "grep_reformulations", "bash_retries", "read_after_edit",
            )
        ]
        comp_pairs.sort(key=lambda p: abs(p[1]), reverse=True)
        top_name, top_contrib = comp_pairs[0]
        print(
            f"{i:>4}  {f.score:>10.4f}  {f.tangle_count:>6}  "
            f"{f.score_components.multi_file_weight:>5.2f}  "
            f"{top_name + f'({top_contrib:+.2f})':<28}  {f.path}"
        )

    # 2. Mean pairwise correlation among the four leakage raw values.
    leak_signals = ("edit_failures", "grep_reformulations", "bash_retries", "read_after_edit")
    rows = [
        [getattr(f.score_components, s).raw for s in leak_signals]
        for f in report.files
    ]
    print("\n[2] Mean pairwise correlation across 4 leakage raw values:")
    if len(rows) >= 2:
        cols = list(zip(*rows))
        corrs: list[float] = []
        for i in range(len(leak_signals)):
            for j in range(i + 1, len(leak_signals)):
                corrs.append(_pearson(cols[i], cols[j]))
        if corrs:
            avg = mean(corrs)
            flag = "  [FLAG: > 0.5 — Phase 5 may want to collapse leakage]" if avg > 0.5 else ""
            print(f"  mean(r) = {avg:+.3f}{flag}")
        else:
            print("  (no correlations computable)")
    else:
        print("  (not enough files)")

    # 3. Baseline stability — corpus baseline + qualifying-session count.
    print("\n[3] Corpus baseline (median, MAD, n):")
    bs = report.baselines.corpus
    robust_z_fields = (
        "block_length_words", "question_rate_per_100w",
        "reasoning_to_output_ratio", "tool_use_coupling_rate",
        "leakage_events_per_session", "reread_bursts_per_file",
        "edit_churn_per_file",
    )
    for name in robust_z_fields:
        stat = getattr(bs, name)
        print(
            f"  {name:<32}  median={stat.median:>9.3f}  "
            f"mad={stat.mad:>9.3f}  n={stat.n:>5}"
            f"{'  (low_confidence)' if stat.low_confidence else ''}"
        )
    # markers_per_100w uses the schema-1.3 presence/intensity branch.
    mk = bs.markers_per_100w
    print(
        f"  {'markers_per_100w':<32}  presence_rate={mk.presence_rate_corpus:>6.3f}  "
        f"median_intensity_pos={mk.median_intensity_among_positives:>7.3f}  "
        f"n_blocks={mk.n_blocks:>5}  n_pos={mk.n_positive_blocks:>5}"
        f"{'  (low_confidence)' if mk.low_confidence else ''}"
    )
    print(f"  Sessions qualifying for session_baselines: {len(report.session_baselines)}")

    # 4. Models in corpus.
    md = report.meta.model_distribution
    print("\n[4] Models in corpus:")
    rows = sorted(md.events_by_model.items(), key=lambda kv: -kv[1])
    for name, ev_count in rows:
        sess_count = md.sessions_by_model.get(name, 0)
        print(f"  {name:<32}  {ev_count:>7,d} events  {sess_count:>4d} sessions")
    if md.unknown_model_event_count > 0:
        print(f"  {'(unknown model)':<32}  {md.unknown_model_event_count:>7,d} events")
    if not rows and md.unknown_model_event_count == 0:
        print("  (no model-bearing events)")

    # 5. Multi-file weight distribution.
    weights = [f.score_components.multi_file_weight for f in report.files]
    print("\n[5] multi_file_weight distribution:")
    if weights:
        weights_sorted = sorted(weights)
        n = len(weights_sorted)
        p50 = weights_sorted[n // 2]
        p10 = weights_sorted[max(0, n // 10)]
        at_one = sum(1 for w in weights if w >= 0.999)
        print(f"  n={n}  p10={p10:.3f}  p50={p50:.3f}  "
              f"max={max(weights):.3f}  files_at_1.0={at_one}")
    else:
        print("  (no files)")

    # 6. Boundary-clip count.
    clips = get_boundary_clip_count()
    print(f"\n[6] Window boundary-clip count: {clips}")

    # 7. File count.
    print(f"\n[7] Files with friction signals: {len(report.files)}")
    print(f"    Sessions parsed: {corpus.session_count}")
    print(f"    Events parsed: {corpus.event_count}")
    print()


def _pearson(xs, ys) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx2 = sum((x - mx) ** 2 for x in xs)
    dy2 = sum((y - my) ** 2 for y in ys)
    denom = (dx2 * dy2) ** 0.5
    if denom <= 0:
        return 0.0
    return num / denom


def _cmd_session(args: argparse.Namespace) -> int:
    sessions_dir = resolve_sessions_dir()
    result = match_session(sessions_dir, args.identifier)
    if not result.matches:
        print(f"No session matched {args.identifier!r}.")
        return 1
    if len(result.matches) > 1:
        print(f"Multiple sessions matched {args.identifier!r}:")
        for s in result.matches:
            print(
                f"  [{s.session_id[:8]}]  \"{s.title}\"    "
                f"{format_relative_time(s.mtime)}"
            )
        print("Re-run with a more specific identifier.")
        return 1
    matched = result.matches[0]
    print(summarize_session(matched.session_id, sessions_dir))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-friction-map",
        description="Parse Claude Code session logs and report friction across your codebase.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser(
        "scan",
        help="Retrospective scan of all historical sessions for the current project.",
    )
    scan.add_argument(
        "--checkpoint",
        action="store_true",
        help="Print Phase 3 diagnostic checkpoint after scanning.",
    )
    scan.set_defaults(func=_cmd_scan)

    active = subparsers.add_parser(
        "active-sessions",
        help=f"List sessions with activity in the last {ACTIVE_SESSION_WINDOW_HOURS} hours.",
    )
    active.set_defaults(func=_cmd_active_sessions)

    session = subparsers.add_parser(
        "session",
        help="Analyze one session, identified by ID prefix or title substring.",
    )
    session.add_argument("identifier")
    session.set_defaults(func=_cmd_session)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
