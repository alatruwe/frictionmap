"""Judged units: the same extraction path that built the hand-labeling sheet.

Mirrors build_pool() in methodology/scripts/sample_validation.py exactly:
v1 parse_sessions per corpus dir, events in order, a block counts iff its type
is "thinking" and its text is non-empty, block_index increments per counted
block, text is block.thinking verbatim. tests/test_judge_units.py asserts the
two paths agree on a synthetic corpus.

Three unit sources:
- anchors: all thinking blocks in sessions listed in anchor-sessions.txt
  (dry-run smoke input; these blocks appear inside the judge prompts, so their
  scores are not a quality signal).
- manifest: sample-manifest.csv, validation only. Nothing outside the
  validation branch calls manifest_units().
- tests build units directly.

Gates (hard exits, never warnings): corpus matches corpus-manifest.txt;
labels.csv raw bytes hash to the committed value; the sheet re-rendered from
the manifest hashes to the value in sample-seal.txt.
"""
from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path

from frictionmap.parser import parse_sessions
from judge_harness import REPO_ROOT

CORPORA = ("attune", "brownfield")
CORPUS_MANIFEST_PATH = REPO_ROOT / "methodology" / "corpus-manifest.txt"
ANCHOR_SESSIONS_PATH = REPO_ROOT / "methodology" / "anchor-sessions.txt"
SEAL_PATH = REPO_ROOT / "methodology" / "sample-seal.txt"
SAMPLE_MANIFEST_PATH = REPO_ROOT / "sample-manifest.csv"
LABELS_PATH = REPO_ROOT / "labels.csv"
# Commit 8900f2e message. The validation gate hashes the file's raw bytes.
LABELS_SHA256 = "fb9bb2eddf1c042417686e0858b7c5473ca544cefb364998fec2e6b9a56bd98c"

UNIT_HEADER = "## unit "
SHEET_TITLE = "Validation labeling sheet (LOCAL — never commit)"
SHEET_PREAMBLE = [
    "100 thinking blocks in labeling order. Unit key and text only —",
    "no stratum, no corpus, no signal values, no file paths (§4 step 3).",
    "",
    "Score each unit 0-3 per methodology/labeling-rubric.md.",
]


class GateError(SystemExit):
    """A pre-flight gate failed. Message carries the reason; no run proceeds."""


@dataclass(frozen=True)
class Unit:
    position: int        # sheet_position (manifest) or 1-based index (anchors)
    session_id: str
    block_index: int
    corpus: str
    text: str

    @property
    def key(self) -> tuple[str, int]:
        return (self.session_id, self.block_index)

    @property
    def key_str(self) -> str:
        return f"{self.session_id}#{self.block_index}"


# --- hashing and gates --------------------------------------------------------


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_corpus_manifest(path: Path = CORPUS_MANIFEST_PATH) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        digest, _, rel = line.partition(" ")
        rel = rel.strip()
        if not digest or not rel:
            raise GateError(f"malformed manifest line: {line!r}")
        entries[rel] = digest
    return entries


def verify_corpus(root: Path, manifest_path: Path = CORPUS_MANIFEST_PATH) -> int:
    """Same non-recursive view as v1 parse_sessions: <corpus>/<id>.jsonl only."""
    expected = read_corpus_manifest(manifest_path)
    found = {str(p.relative_to(root)): p for p in sorted(root.glob("*/*.jsonl"))}
    missing = sorted(set(expected) - set(found))
    extra = sorted(set(found) - set(expected))
    changed = sorted(rel for rel in set(expected) & set(found)
                     if sha256_file(found[rel]) != expected[rel])
    if missing or extra or changed:
        raise GateError(
            f"corpus does not match {manifest_path.name} "
            f"({len(missing)} missing, {len(extra)} extra, {len(changed)} changed)"
        )
    return len(expected)


def verify_labels(path: Path = LABELS_PATH, expected: str = LABELS_SHA256) -> None:
    actual = sha256_file(path)
    if actual != expected:
        raise GateError(f"{path.name} sha256 {actual[:12]}… != committed {expected[:12]}…")


def read_seal_hash(filename: str, seal_path: Path = SEAL_PATH) -> str:
    for line in seal_path.read_text().splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0] == "sha256" and parts[1] == filename:
            return parts[2]
    raise GateError(f"no sha256 line for {filename} in {seal_path.name}")


# --- extraction ---------------------------------------------------------------


def extract_blocks(root: Path, corpora: tuple[str, ...] = CORPORA) -> dict[tuple[str, int], tuple[str, str]]:
    """(session_id, block_index) -> (corpus, thinking text), all sessions."""
    out: dict[tuple[str, int], tuple[str, str]] = {}
    for label in corpora:
        corpus = parse_sessions(root / label)
        for session_id, events in corpus.sessions.items():
            block_index = 0
            for event in events:
                for block in event.blocks:
                    if block.type != "thinking" or not block.thinking:
                        continue
                    out[(session_id, block_index)] = (label, block.thinking)
                    block_index += 1
    return out


def read_session_list(path: Path) -> set[str]:
    return {line.strip() for line in path.read_text().splitlines()
            if line.strip() and not line.startswith("#")}


def anchor_units(root: Path, anchor_path: Path = ANCHOR_SESSIONS_PATH,
                 corpora: tuple[str, ...] = CORPORA) -> list[Unit]:
    """Every thinking block in the anchor sessions, sorted by unit key,
    positions 1..n. The dry-run smoke input."""
    sessions = read_session_list(anchor_path)
    blocks = extract_blocks(root, corpora)
    keys = sorted(k for k in blocks if k[0] in sessions)
    return [Unit(position=i, session_id=sid, block_index=bidx,
                 corpus=blocks[(sid, bidx)][0], text=blocks[(sid, bidx)][1])
            for i, (sid, bidx) in enumerate(keys, start=1)]


def manifest_units(root: Path, manifest_path: Path = SAMPLE_MANIFEST_PATH,
                   corpora: tuple[str, ...] = CORPORA) -> list[Unit]:
    """VALIDATION ONLY. Units in sheet_position order with text from the corpus.
    Never echo the returned units' fields anywhere a person reads."""
    blocks = extract_blocks(root, corpora)
    units: list[Unit] = []
    with manifest_path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            key = (row["session_id"], int(row["block_index"]))
            if key not in blocks:
                raise GateError(f"manifest unit at position {row['sheet_position']} not found in corpus")
            corpus, text = blocks[key]
            if corpus != row["corpus"]:
                raise GateError(f"manifest corpus mismatch at position {row['sheet_position']}")
            units.append(Unit(position=int(row["sheet_position"]), session_id=key[0],
                              block_index=key[1], corpus=corpus, text=text))
    units.sort(key=lambda u: u.position)
    if [u.position for u in units] != list(range(1, len(units) + 1)):
        raise GateError("manifest sheet_position is not 1..n")
    return units


# --- sheet identity gate ------------------------------------------------------


def render_sheet(units: list[Unit]) -> str:
    """Byte-for-byte the labeling sheet sample_validation.py wrote."""
    lines = [f"# {SHEET_TITLE}", ""] + SHEET_PREAMBLE + [""]
    for unit in units:
        lines += [f"{UNIT_HEADER}{unit.position:03d} · {unit.key_str}", "", unit.text, ""]
    return "\n".join(lines) + "\n"


def sheet_sha256(units: list[Unit]) -> str:
    return hashlib.sha256(render_sheet(units).encode("utf-8")).hexdigest()


def verify_sheet_identity(units: list[Unit], seal_path: Path = SEAL_PATH) -> None:
    expected = read_seal_hash("labeling-sheet.md", seal_path)
    actual = sheet_sha256(units)
    if actual != expected:
        raise GateError("re-rendered labeling sheet does not hash to the sealed value; "
                        "extraction path differs from the one Adeline labeled")
