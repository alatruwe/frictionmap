"""On-disk layout under judge-runs/<run_id>/ (gitignored).

  run-manifest.json      reproducibility record, merged across invocations
  infra.log              transient API errors and backoff; never unit text
  <pass_id>/ledger.jsonl append-only, one line per API attempt (source of truth)
  <pass_id>/raw/<pos>-<attempt>.json  full response for that attempt
  <pass_id>/scores.csv   rendered from the ledger; spec columns

The ledger is what resume reads. A line is written only after its raw file
exists, and is flushed + fsynced before the next call.
"""
from __future__ import annotations

import csv
import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

LEDGER_NAME = "ledger.jsonl"
RAW_DIR = "raw"
SCORES_NAME = "scores.csv"
MANIFEST_NAME = "run-manifest.json"
INFRA_LOG_NAME = "infra.log"

SCORES_COLUMNS = [
    "pass_id", "sheet_position", "session_id", "block_index", "score",
    "justification", "raw_response_path", "retry_flag", "missing_flag",
]
MAX_ATTEMPTS = 2  # one call + one retry (judge-prompts/README.md parse-failure rule)


@dataclass(frozen=True)
class Attempt:
    pass_id: str
    sheet_position: int
    session_id: str
    block_index: int
    attempt: int
    valid: bool
    score: int | None
    justification: Any
    reason: str | None
    raw_response_path: str      # relative to the run dir
    request_id: str | None
    stop_reason: str | None
    input_tokens: int | None
    output_tokens: int | None
    infra_retries: int
    latency_s: float
    timestamp: str


_ATTEMPT_FIELDS = {f.name for f in fields(Attempt)}


def pass_dir(run_dir: Path, pass_id: str) -> Path:
    return run_dir / pass_id


def write_raw(run_dir: Path, pass_id: str, position: int, attempt: int, payload: dict) -> str:
    rel = Path(pass_id) / RAW_DIR / f"{position:03d}-{attempt}.json"
    path = run_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
    return str(rel)


def append_ledger(run_dir: Path, attempt: Attempt) -> None:
    path = pass_dir(run_dir, attempt.pass_id) / LEDGER_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(attempt), ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def load_ledger(run_dir: Path, pass_id: str) -> dict[int, list[Attempt]]:
    """position -> attempts in ledger order. Missing ledger = empty."""
    path = pass_dir(run_dir, pass_id) / LEDGER_NAME
    out: dict[int, list[Attempt]] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        attempt = Attempt(**{k: v for k, v in rec.items() if k in _ATTEMPT_FIELDS})
        out.setdefault(attempt.sheet_position, []).append(attempt)
    return out


def unit_complete(attempts: list[Attempt]) -> bool:
    return any(a.valid for a in attempts) or len(attempts) >= MAX_ATTEMPTS


def final_attempt(attempts: list[Attempt]) -> Attempt:
    for a in attempts:
        if a.valid:
            return a
    return attempts[-1]


def render_scores(run_dir: Path, pass_id: str) -> tuple[Path, int, int]:
    """Write scores.csv from the ledger. Returns (path, rows written,
    incomplete units omitted). Only completed units get a row."""
    ledger = load_ledger(run_dir, pass_id)
    path = pass_dir(run_dir, pass_id) / SCORES_NAME
    rows = 0
    incomplete = 0
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=SCORES_COLUMNS)
        writer.writeheader()
        for position in sorted(ledger):
            attempts = ledger[position]
            if not unit_complete(attempts):
                incomplete += 1
                continue
            final = final_attempt(attempts)
            writer.writerow({
                "pass_id": pass_id,
                "sheet_position": position,
                "session_id": final.session_id,
                "block_index": final.block_index,
                "score": "" if final.score is None else final.score,
                "justification": "" if final.justification is None
                                 else (final.justification if isinstance(final.justification, str)
                                       else json.dumps(final.justification, ensure_ascii=False)),
                "raw_response_path": final.raw_response_path,
                "retry_flag": int(len(attempts) > 1),
                "missing_flag": int(not final.valid),
            })
            rows += 1
    return path, rows, incomplete


def read_manifest(run_dir: Path) -> dict:
    path = run_dir / MANIFEST_NAME
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


MERGED_KEYS = ("passes", "prompts", "scaffold_tokens")


def update_manifest(run_dir: Path, updates: dict) -> dict:
    """Shallow-merge top-level keys. 'passes', 'prompts' and 'scaffold_tokens'
    merge per entry so a later invocation with different passes keeps what
    earlier ones recorded."""
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest = read_manifest(run_dir)
    for key, value in updates.items():
        if key in MERGED_KEYS:
            manifest.setdefault(key, {})
            for name, info in value.items():
                if isinstance(info, dict):
                    manifest[key].setdefault(name, {}).update(info)
                else:
                    manifest[key][name] = info
        else:
            manifest[key] = value
    tmp = run_dir / (MANIFEST_NAME + ".tmp")
    tmp.write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, run_dir / MANIFEST_NAME)
    return manifest


def log_infra(run_dir: Path, line: str) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / INFRA_LOG_NAME).open("a", encoding="utf-8") as fh:
        fh.write(line.rstrip("\n") + "\n")
