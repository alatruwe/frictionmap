"""Dump one session's thinking blocks as plain text, for rubric anchor reading (§4.1).

Companion to dump_anchor_candidates.py, which selects sessions. This one
displays a single session at a time: text only, nothing else on the page.

Read-only against session data. Writes only the (gitignored) local file
anchor_sessions/<session-id>.md and the committed exclusion list.

Marker annotations are OFF by default. The rubric's criteria are supposed to
come from reading the text, and the judge is validated against labels made
from text alone (§2, §4 step 3) — seeing which strings the v1 lexicon matched
while deriving criteria imports the marker prior into the rubric that the
judge then encodes. --markers exists for checking the lexicon against your own
reading *after* you have formed one, not for reading alongside.

Displaying a session excludes it from the validation sampling pool, per the §4
contamination rule, whether or not an anchor comes out of it — so this script
appends to methodology/anchor-sessions.txt exactly like the selector does.
--list is exempt: it shows IDs and block counts, no text and no signal values.

Usage:
  uv run python methodology/scripts/dump_session.py <corpus-root> --list
  uv run python methodology/scripts/dump_session.py <corpus-root> <session-id>
where <session-id> may be any unambiguous prefix.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from frictionmap.clusters import find_markers
from frictionmap.parser import parse_sessions

CORPUS = "attune"

REPO_ROOT = Path(__file__).resolve().parents[2]
DUMP_DIR = REPO_ROOT / "anchor_sessions"
EXCLUSION_PATH = REPO_ROOT / "methodology" / "anchor-sessions.txt"
EXCLUSION_HEADER = (
    "# Sessions excluded from the v2 validation sampling pool. Includes all "
    "sessions displayed during anchor selection, not only sessions anchors "
    "were drawn from. Pre-registration §4."
)


def thinking_blocks(root: Path) -> dict[str, list[str]]:
    """Thinking text per attune session, in session order."""
    corpus = parse_sessions(root / CORPUS)
    out: dict[str, list[str]] = {}
    for session_id, events in corpus.sessions.items():
        texts = [
            block.thinking
            for event in events
            for block in event.blocks
            if block.type == "thinking" and block.thinking
        ]
        if texts:
            out[session_id] = texts
    return out


def resolve(sessions: dict[str, list[str]], wanted: str) -> str:
    """Match a full session ID or an unambiguous prefix."""
    matches = [sid for sid in sessions if sid.startswith(wanted)]
    if not matches:
        raise SystemExit(f"no {CORPUS} session matching {wanted!r}")
    if len(matches) > 1:
        raise SystemExit(
            f"{wanted!r} is ambiguous:\n  " + "\n  ".join(sorted(matches))
        )
    return matches[0]


def render(session_id: str, texts: list[str], show_markers: bool) -> str:
    lines = [f"# {session_id}", "", f"{len(texts)} thinking blocks.", ""]
    for index, text in enumerate(texts):
        head = f"## block {index}  ·  {len(text.split())} words"
        if show_markers:
            hits = [hit[2] for hit in find_markers(text)]
            head += f"  ·  markers: {', '.join(hits) if hits else '—'}"
        lines += [head, "", text, ""]
    return "\n".join(lines)


def record_exclusion(session_id: str) -> tuple[bool, int]:
    """Append the session ID if new. Returns (was_new, total_excluded)."""
    existing: list[str] = []
    if EXCLUSION_PATH.exists():
        existing = [
            line.strip()
            for line in EXCLUSION_PATH.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]

    was_new = session_id not in existing
    if was_new:
        existing.append(session_id)
        EXCLUSION_PATH.write_text(
            EXCLUSION_HEADER + "\n" + "\n".join(existing) + "\n"
        )
    return was_new, len(existing)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("corpus_root", type=Path,
                        help="directory containing attune/ and brownfield/")
    parser.add_argument("session_id", nargs="?",
                        help="full session ID or unambiguous prefix")
    parser.add_argument("--list", action="store_true",
                        help="list session IDs and block counts, display nothing")
    parser.add_argument("--stdout", action="store_true",
                        help="print the blocks instead of writing a file")
    parser.add_argument("--markers", action="store_true",
                        help="annotate each block with its v1 marker hits "
                             "(off by default — see module docstring)")
    args = parser.parse_args()

    sessions = thinking_blocks(args.corpus_root)

    if args.list:
        for session_id in sorted(sessions):
            print(f"{session_id}  {len(sessions[session_id]):>3} blocks")
        print(f"\n{len(sessions)} {CORPUS} sessions with thinking blocks")
        return 0

    if not args.session_id:
        parser.error("a session ID is required unless --list is given")

    session_id = resolve(sessions, args.session_id)
    texts = sessions[session_id]
    page = render(session_id, texts, args.markers)

    was_new, total_excluded = record_exclusion(session_id)

    if args.stdout:
        print(page)
    else:
        DUMP_DIR.mkdir(exist_ok=True)
        path = DUMP_DIR / f"{session_id}.md"
        path.write_text(page)
        print(f"{len(texts)} blocks -> {path}")

    note = "newly excluded" if was_new else "already excluded"
    print(f"[{session_id[:8]} {note}; {total_excluded} sessions out of the pool]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
