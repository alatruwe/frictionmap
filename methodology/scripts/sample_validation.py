"""Draw the N=100 validation hand-labeling sample and its sealed reserves (§3, §4).

Pre-registration §3 deliverable. Everything random here comes from
VALIDATION_SAMPLE_SEED; Q1_SPLIT_SEED is unused by this script and lives here
only so the Phase 3 contested-task split seed (§7) is committed before the
SWE-bench data exists.

Read-only against session data: uses v1 parsing exactly as shipped. Writes
five files — four local and gitignored at repo root (`labeling-sheet.md`,
`sample-manifest.csv`, `reserve-list.md`, `relabel-sheet.md`) and one committed
(`methodology/sample-seal.txt`).

The three local files are the sample; the seal is the public commitment to it.
Brownfield thinking text must never be committed, and the manifest must stay
sealed until labels are committed and hashed (§4 step 4) — so the seal carries
their SHA-256 instead of their contents.

The labeling sheet is the blind input required by §4 step 3: unit key and
thinking text, nothing else. No stratum, no corpus, no marker flag, no signal
values, no file paths. Console output is counts only, for the same reason —
per-unit values seen before labeling contaminate the unit (§4 contamination
rule) and cost a reserve.

The relabel sheet is the §4 step 5 blind-relabel input; it is written at draw
time and sealed by hash, and stays closed until the 48-hour gap has passed.

Sampling runs only against a corpus that still matches methodology/corpus-manifest.txt;
a hash drift is a hard exit, not a warning. Sessions listed in
methodology/anchor-sessions.txt are already contaminated and are dropped from
the pool before the draw.

Usage: uv run python methodology/scripts/sample_validation.py <corpus-root>
where <corpus-root> contains attune/ and brownfield/ session dirs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import random
from dataclasses import dataclass
from pathlib import Path

from frictionmap.clusters import find_markers
from frictionmap.parser import parse_sessions

# Committed constants. Never changed — changing one invalidates the seal.
VALIDATION_SAMPLE_SEED = 18   # drives every random draw in this script
Q1_SPLIT_SEED = 31            # NOT used here. Reserved for the Phase 3 contested-task
                              # 50/50 split (pre-registration §7). Committed in this
                              # script so the seed predates the SWE-bench data.
N_RANDOM = 50
N_OVERSAMPLE = 50
N_RESERVE_PER_STRATUM = 10
N_RELABEL_PER_STRATUM = 10    # §4 step 5: 20-unit blind relabel subset, 10 per stratum

CORPORA = ("attune", "brownfield")
STRATA = ("random", "oversample")

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "methodology" / "corpus-manifest.txt"
EXCLUSION_PATH = REPO_ROOT / "methodology" / "anchor-sessions.txt"

SHEET_PATH = REPO_ROOT / "labeling-sheet.md"
SAMPLE_MANIFEST_PATH = REPO_ROOT / "sample-manifest.csv"
RESERVE_PATH = REPO_ROOT / "reserve-list.md"
RELABEL_PATH = REPO_ROOT / "relabel-sheet.md"
SEAL_PATH = REPO_ROOT / "methodology" / "sample-seal.txt"

UNIT_HEADER = "## unit "


@dataclass(frozen=True)
class Unit:
    """One thinking block. `key` is (session_id, block_index), where
    block_index counts thinking blocks within the session in event order —
    the same keying as count_units.py.
    """
    session_id: str
    block_index: int
    corpus: str
    marker_positive: bool
    file_attached: bool
    text: str

    @property
    def key(self) -> tuple[str, int]:
        return (self.session_id, self.block_index)

    @property
    def key_str(self) -> str:
        return f"{self.session_id}#{self.block_index}"


# --- Step 1: manifest verification (hard gate) -----------------------------


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_manifest() -> dict[str, str]:
    """Manifest lines are `<sha256>  <relative path>`; # lines are comments."""
    entries: dict[str, str] = {}
    for line in MANIFEST_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        digest, _, rel = line.partition(" ")
        rel = rel.strip()
        if not digest or not rel:
            raise SystemExit(f"malformed manifest line: {line!r}")
        entries[rel] = digest
    return entries


def verify_corpus(root: Path) -> int:
    """Exit nonzero on any drift. Returns the number of verified files.

    No sampling occurs on a corpus that has drifted from the manifest, so
    this runs before anything is parsed and before anything is written.
    """
    expected = read_manifest()
    found = {
        str(path.relative_to(root)): path
        for path in sorted(root.rglob("*.jsonl"))
    }

    missing = sorted(set(expected) - set(found))
    extra = sorted(set(found) - set(expected))
    changed = sorted(
        rel for rel in set(expected) & set(found)
        if sha256_file(found[rel]) != expected[rel]
    )

    if missing or extra or changed:
        for label, paths in (
            ("missing (in manifest, not on disk)", missing),
            ("extra (on disk, not in manifest)", extra),
            ("hash mismatch", changed),
        ):
            for rel in paths:
                print(f"{label}: {rel}")
        raise SystemExit(
            f"corpus does not match {MANIFEST_PATH.name} "
            f"({len(missing)} missing, {len(extra)} extra, {len(changed)} changed) "
            "— no sample drawn"
        )
    return len(expected)


# --- Step 2: the pool ------------------------------------------------------


def read_exclusions() -> set[str]:
    if not EXCLUSION_PATH.exists():
        return set()
    return {
        line.strip()
        for line in EXCLUSION_PATH.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }


def build_pool(root: Path, excluded: set[str]) -> tuple[list[Unit], int]:
    """All thinking blocks in both corpora, minus anchor sessions.

    §3: the pool is a pipeline stage, not a filter — blocks with empty
    file_paths are units too. File attachment is recorded per unit as a
    descriptive split; only marker positivity stratifies.

    Returns (pool sorted by unit key, units dropped by exclusion).
    """
    pool: list[Unit] = []
    dropped = 0
    for label in CORPORA:
        corpus = parse_sessions(root / label)
        for session_id, events in corpus.sessions.items():
            block_index = 0
            for event in events:
                for block in event.blocks:
                    if block.type != "thinking" or not block.thinking:
                        continue
                    attribution = block.attribution
                    unit = Unit(
                        session_id=session_id,
                        block_index=block_index,
                        corpus=label,
                        marker_positive=bool(find_markers(block.thinking)),
                        file_attached=bool(
                            attribution and attribution.file_paths
                        ),
                        text=block.thinking,
                    )
                    block_index += 1
                    if session_id in excluded:
                        dropped += 1
                        continue
                    pool.append(unit)
    pool.sort(key=lambda u: u.key)
    return pool, dropped


# --- Step 3: the draw ------------------------------------------------------


@dataclass
class Draw:
    main: list[Unit]                     # shuffled into labeling order
    stratum_of: dict[tuple[str, int], str]
    reserves: dict[str, list[Unit]]      # per stratum, in consumption order
    relabel: list[Unit]                  # §4 step 5 subset, in presentation order


def draw(pool: list[Unit]) -> Draw:
    """Every draw below is without replacement, off one seeded RNG stream.

    Call order is part of the commitment: random stratum, oversample
    stratum, random reserve, oversample reserve, presentation shuffle,
    relabel subset (random then oversample), relabel shuffle.
    Reordering these changes the sample even at the same seed.
    """
    rng = random.Random(VALIDATION_SAMPLE_SEED)

    def remaining(units: list[Unit], taken: set[tuple[str, int]]) -> list[Unit]:
        return [u for u in units if u.key not in taken]

    marker_positive = [u for u in pool if u.marker_positive]
    need_random = N_RANDOM + N_RESERVE_PER_STRATUM
    need_marker = N_OVERSAMPLE + N_RESERVE_PER_STRATUM
    if len(pool) < need_random + need_marker:
        raise SystemExit(
            f"pool too small: {len(pool)} units, need "
            f"{need_random + need_marker}"
        )
    if len(marker_positive) < need_marker:
        raise SystemExit(
            f"too few marker-positive units: {len(marker_positive)}, need "
            f"{need_marker}"
        )

    taken: set[tuple[str, int]] = set()
    stratum_of: dict[tuple[str, int], str] = {}

    def take(units: list[Unit], n: int, stratum: str) -> list[Unit]:
        picked = rng.sample(remaining(units, taken), n)
        for unit in picked:
            taken.add(unit.key)
            stratum_of.setdefault(unit.key, stratum)
        return picked

    random_units = take(pool, N_RANDOM, "random")
    oversample_units = take(marker_positive, N_OVERSAMPLE, "oversample")
    reserves = {
        "random": take(pool, N_RESERVE_PER_STRATUM, "random"),
        "oversample": take(marker_positive, N_RESERVE_PER_STRATUM, "oversample"),
    }

    main = random_units + oversample_units
    rng.shuffle(main)

    # §4 step 5 relabel subset — LAST draws on the stream. Appending here
    # leaves main, reserves, and the shuffle unchanged at the same seed.
    by_stratum = {s: [u for u in main if stratum_of[u.key] == s] for s in STRATA}
    relabel: list[Unit] = []
    for stratum in STRATA:
        relabel += rng.sample(by_stratum[stratum], N_RELABEL_PER_STRATUM)
    rng.shuffle(relabel)

    return Draw(main=main, stratum_of=stratum_of, reserves=reserves,
                relabel=relabel)


# --- Step 4: outputs -------------------------------------------------------


def render_units(title: str, preamble: list[str], units: list[Unit],
                 group_labels: list[str] | None = None) -> str:
    """Unit key + thinking text and nothing else — the §4 blind input.

    group_labels, when given, is one label per unit; it is written as a
    section heading. Used only by the reserve list, which is sealed.
    """
    lines = [f"# {title}", ""] + preamble + [""]
    current: str | None = None
    for position, unit in enumerate(units, start=1):
        if group_labels is not None and group_labels[position - 1] != current:
            current = group_labels[position - 1]
            lines += [f"# {current}", ""]
        lines += [f"{UNIT_HEADER}{position:03d} · {unit.key_str}", "",
                  unit.text, ""]
    return "\n".join(lines) + "\n"


def write_sheet(main: list[Unit]) -> None:
    SHEET_PATH.write_text(render_units(
        "Validation labeling sheet (LOCAL — never commit)",
        [
            "100 thinking blocks in labeling order. Unit key and text only —",
            "no stratum, no corpus, no signal values, no file paths (§4 step 3).",
            "",
            "Score each unit 0-3 per methodology/labeling-rubric.md.",
        ],
        main,
    ))


def write_sample_manifest(main: list[Unit],
                          stratum_of: dict[tuple[str, int], str],
                          relabel_keys: set[tuple[str, int]]) -> None:
    with SAMPLE_MANIFEST_PATH.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "session_id", "block_index", "stratum", "corpus",
            "file_attachment", "sheet_position", "relabel_subset",
        ])
        for position, unit in enumerate(main, start=1):
            writer.writerow([
                unit.session_id, unit.block_index, stratum_of[unit.key],
                unit.corpus, int(unit.file_attached), position,
                int(unit.key in relabel_keys),
            ])


def write_reserves(reserves: dict[str, list[Unit]]) -> None:
    units: list[Unit] = []
    labels: list[str] = []
    for stratum in STRATA:
        for unit in reserves[stratum]:
            units.append(unit)
            labels.append(f"{stratum} stratum reserves (consume in order)")
    RESERVE_PATH.write_text(render_units(
        "Reserve units (LOCAL — SEALED)",
        [
            "Open ONE unit only when the §4 contamination rule fires, and log",
            "the event in §9. Replacements are consumed top to bottom within",
            "the stratum of the discarded unit.",
        ],
        units,
        group_labels=labels,
    ))


def write_relabel_sheet(relabel: list[Unit]) -> None:
    RELABEL_PATH.write_text(render_units(
        "Relabel sheet (LOCAL — SEALED until §4 step 5)",
        [
            "20 units from the validation sample, fresh order. Open no sooner",
            "than 48 hours after the first labeling pass completes, with no",
            "access to first-pass labels, signal values, or judge output.",
            "Score each unit 0-3 per methodology/labeling-rubric.md.",
        ],
        relabel,
    ))


def write_seal(pool: list[Unit], excluded_sessions: int,
               excluded_units: int, verified_files: int) -> None:
    marker_positive = sum(1 for u in pool if u.marker_positive)
    per_corpus = {
        label: sum(1 for u in pool if u.corpus == label) for label in CORPORA
    }
    lines = [
        "# FrictionMap v2 validation sample seal — pre-registration §3, §4.",
        "#",
        "# Public commitment to a sample whose contents stay local: the four",
        "# hashed files are gitignored (brownfield text must never be committed),",
        "# and sample-manifest.csv is committed only after the labels are",
        "# committed and hashed (§4 step 4). reserve-list.md and relabel-sheet.md",
        "# stay sealed until their §4 triggers fire. The hashes fix the sample now.",
        "#",
        "# Regenerating this file from the same corpus and the same seed",
        "# reproduces it byte for byte.",
        "",
        f"seed_validation_sample   {VALIDATION_SAMPLE_SEED}",
        f"seed_q1_split            {Q1_SPLIT_SEED}",
        "",
        f"corpus_files_verified    {verified_files}",
        f"excluded_sessions        {excluded_sessions}",
        f"excluded_units           {excluded_units}",
        f"pool_units               {len(pool)}",
        f"pool_marker_positive     {marker_positive}",
    ]
    for label in CORPORA:
        lines.append(f"pool_{label:<20}{per_corpus[label]}")
    lines += [
        "",
        f"n_random                 {N_RANDOM}",
        f"n_oversample             {N_OVERSAMPLE}",
        f"n_reserve_per_stratum    {N_RESERVE_PER_STRATUM}",
        f"n_relabel_per_stratum    {N_RELABEL_PER_STRATUM}",
        "",
    ]
    for path in (SHEET_PATH, SAMPLE_MANIFEST_PATH, RESERVE_PATH, RELABEL_PATH):
        lines.append(f"sha256  {path.name:<20} {sha256_file(path)}")
    SEAL_PATH.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("corpus_root", type=Path,
                        help="directory containing attune/ and brownfield/")
    args = parser.parse_args()

    verified_files = verify_corpus(args.corpus_root)
    excluded = read_exclusions()
    pool, excluded_units = build_pool(args.corpus_root, excluded)
    result = draw(pool)

    write_sheet(result.main)
    write_sample_manifest(result.main, result.stratum_of,
                          {u.key for u in result.relabel})
    write_reserves(result.reserves)
    write_relabel_sheet(result.relabel)
    write_seal(pool, len(excluded), excluded_units, verified_files)

    marker_positive = sum(1 for u in pool if u.marker_positive)
    print(f"corpus verified against manifest: {verified_files} session files")
    print(f"excluded sessions: {len(excluded)} ({excluded_units} units dropped)")
    print(f"pool: {len(pool)} units, {marker_positive} marker-positive")
    for label in CORPORA:
        print(f"  {label}: {sum(1 for u in pool if u.corpus == label)}")
    print(f"sample: {len(result.main)} units "
          f"({N_RANDOM} random + {N_OVERSAMPLE} oversample)")
    print(f"reserves: " + ", ".join(
        f"{len(result.reserves[s])} {s}" for s in STRATA))
    print(f"relabel subset: {len(result.relabel)} units "
          f"({N_RELABEL_PER_STRATUM} per stratum)")
    for path in (SHEET_PATH, SAMPLE_MANIFEST_PATH, RESERVE_PATH, RELABEL_PATH,
                 SEAL_PATH):
        print(f"wrote {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
