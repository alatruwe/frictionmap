"""Anchor-candidate dump for the v2 labeling rubric (§4.1).

Read-only against session data: uses v1 parsing exactly as shipped, and
writes only two files inside this repo — the (gitignored) local dump
`anchor_candidates.md` at repo root, and the committed exclusion list
`methodology/anchor-sessions.txt`.

Selection is by session-level marker density (marker-positive thinking
blocks / total thinking blocks), attune corpus only; brownfield is skipped
because anchors must not quote brownfield text (privacy, per the rubric's
§5 provenance note). Density picks sessions to *read*; the anchor block
itself is chosen by hand from the dump.

Every session dumped here is contaminated for sampling purposes and is
appended to the exclusion list, whether or not an anchor comes out of it.

Usage: uv run python methodology/scripts/dump_anchor_candidates.py <corpus-root>
where <corpus-root> contains attune/ and brownfield/ session dirs.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from frictionmap.clusters import find_markers
from frictionmap.parser import parse_sessions

CORPUS = "attune"
MIN_THINKING_BLOCKS = 5
# Total session files in the frozen corpus manifest (66 attune + 81
# brownfield); the sampling pool shrinks by every session dumped here.
CORPUS_SESSIONS = 147

REPO_ROOT = Path(__file__).resolve().parents[2]
DUMP_PATH = REPO_ROOT / "anchor_candidates.md"
EXCLUSION_PATH = REPO_ROOT / "methodology" / "anchor-sessions.txt"
EXCLUSION_HEADER = (
    "# Sessions excluded from the v2 validation sampling pool. Includes all "
    "sessions displayed during anchor selection, not only sessions anchors "
    "were drawn from. Pre-registration §4."
)


@dataclass
class BlockRecord:
    index: int
    words: int
    markers: list[str]
    text: str


@dataclass
class SessionRecord:
    session_id: str
    blocks: list[BlockRecord]

    @property
    def n_marker_positive(self) -> int:
        return sum(1 for b in self.blocks if b.markers)

    @property
    def density(self) -> float:
        return self.n_marker_positive / len(self.blocks)


def collect_sessions(root: Path) -> list[SessionRecord]:
    """Thinking blocks per attune session, in order, with marker hits."""
    corpus = parse_sessions(root / CORPUS)

    records: list[SessionRecord] = []
    for session_id, events in corpus.sessions.items():
        blocks: list[BlockRecord] = []
        for event in events:
            for block in event.blocks:
                if block.type != "thinking" or not block.thinking:
                    continue
                hits = find_markers(block.thinking)
                blocks.append(BlockRecord(
                    index=len(blocks),
                    words=len(block.thinking.split()),
                    markers=[hit[2] for hit in hits],
                    text=block.thinking,
                ))
        if len(blocks) < MIN_THINKING_BLOCKS:
            continue
        records.append(SessionRecord(session_id=session_id, blocks=blocks))
    return records


def select(
    records: list[SessionRecord], n_hot: int, n_calm: int
) -> tuple[list[SessionRecord], list[SessionRecord]]:
    """Top-n_hot by density, then lowest-n_calm from what remains.

    Session ID breaks density ties so re-runs select the same sessions.
    """
    by_density = sorted(records, key=lambda r: (-r.density, r.session_id))
    hot = by_density[:n_hot]
    remaining = by_density[n_hot:]
    calm = sorted(remaining, key=lambda r: (r.density, r.session_id))[:n_calm]
    return hot, calm


def render(hot: list[SessionRecord], calm: list[SessionRecord]) -> str:
    lines = [
        "# Anchor candidates (LOCAL — never commit)",
        "",
        "Raw session thinking text, dumped for rubric anchor selection.",
        "This file is gitignored. Every session below is excluded from the",
        "validation sampling pool (methodology/anchor-sessions.txt).",
        "",
    ]
    for group, records in (("Hot", hot), ("Calm", calm)):
        lines.append(f"## {group} sessions")
        lines.append("")
        for record in records:
            lines.append(f"### {record.session_id}")
            lines.append("")
            lines.append(
                f"density {record.density:.3f} "
                f"({record.n_marker_positive}/{len(record.blocks)} "
                f"marker-positive thinking blocks)"
            )
            lines.append("")
            for block in record.blocks:
                markers = ", ".join(block.markers) if block.markers else "—"
                lines.append(
                    f"#### block {block.index} — {block.words} words — "
                    f"markers: {markers}"
                )
                lines.append("")
                lines.append(block.text)
                lines.append("")
    return "\n".join(lines)


def update_exclusions(session_ids: list[str]) -> tuple[int, int]:
    """Append new session IDs to the exclusion list. Returns (added, total)."""
    existing: list[str] = []
    if EXCLUSION_PATH.exists():
        existing = [
            line.strip()
            for line in EXCLUSION_PATH.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]

    seen = set(existing)
    added: list[str] = []
    for sid in session_ids:
        if sid not in seen:
            seen.add(sid)
            added.append(sid)

    EXCLUSION_PATH.write_text(
        EXCLUSION_HEADER + "\n" + "\n".join(existing + added) + "\n"
    )
    return len(added), len(existing) + len(added)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("corpus_root", type=Path,
                        help="directory containing attune/ and brownfield/")
    parser.add_argument("--hot", type=int, default=5,
                        help="highest-density sessions to dump (default 5)")
    parser.add_argument("--calm", type=int, default=2,
                        help="lowest-density sessions to dump (default 2)")
    args = parser.parse_args()

    records = collect_sessions(args.corpus_root)
    if not records:
        raise SystemExit(
            f"no {CORPUS} sessions with >= {MIN_THINKING_BLOCKS} thinking blocks "
            f"under {args.corpus_root}"
        )

    hot, calm = select(records, args.hot, args.calm)
    DUMP_PATH.write_text(render(hot, calm))

    selected = hot + calm
    added, total_excluded = update_exclusions([r.session_id for r in selected])

    n_blocks = sum(len(r.blocks) for r in selected)
    print(f"eligible sessions ({CORPUS}, >= {MIN_THINKING_BLOCKS} blocks): "
          f"{len(records)}")
    print(f"selected: {len(hot)} hot + {len(calm)} calm = {len(selected)} sessions")
    for label, group in (("hot ", hot), ("calm", calm)):
        for record in group:
            print(f"  {label}  {record.session_id}  density {record.density:.3f} "
                  f"({record.n_marker_positive}/{len(record.blocks)})")
    print(f"blocks dumped: {n_blocks} -> {DUMP_PATH}")
    print(f"exclusion list: +{added} new, {total_excluded} total -> {EXCLUSION_PATH}")
    print(f"remaining sampling pool: {CORPUS_SESSIONS} - {total_excluded} = "
          f"{CORPUS_SESSIONS - total_excluded} sessions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
