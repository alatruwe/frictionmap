from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ai_friction_map import __version__

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
    print(f"scan: would parse {sessions_dir} and write {args.output}")
    return 0


def _cmd_active_sessions(args: argparse.Namespace) -> int:
    sessions_dir = resolve_sessions_dir()
    print(
        f"active-sessions: would list sessions modified within "
        f"{ACTIVE_SESSION_WINDOW_HOURS}h in {sessions_dir}"
    )
    return 0


def _cmd_session(args: argparse.Namespace) -> int:
    sessions_dir = resolve_sessions_dir()
    print(f"session: would analyze session matching {args.identifier!r} in {sessions_dir}")
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
    scan.add_argument("-o", "--output", default="report.html")
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
