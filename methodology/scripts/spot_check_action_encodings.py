"""Task 2 of the action-encoding handoff: reproducibility spot-check of their encoder.

Draws the seeded 20-trajectory sample from the joined table, builds a scratch mirror
of the replication package holding byte-identical copies of their `scripts/config.py`,
`scripts/data_processing/extract_enriched_encoding_all.py`, `data/resolution_status.json`
and the 20 sampled trajectory files (nothing else), runs THEIR script end to end,
unmodified, inside the mirror, and compares every column of the rows it emits against
the corresponding rows of their shipped `enriched_encodings_all.csv`.

Their package itself is never written to or imported from. Exits 1 on any mismatch.

    uv run python methodology/scripts/spot_check_action_encodings.py \
        --package ~/Projects/replication-package \
        --table methodology/results/action-encodings-joined.csv \
        --workdir <scratchpad>/spotcheck \
        --out methodology/action-encoding-spot-check.md
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import shlex
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from action_encoding.join import JoinedRow, load_encodings  # noqa: E402
from action_encoding.spotcheck import (  # noqa: E402
    DOUBAO_FOLDER, SAGE_FOLDER, SEED, SYMBOL_INVENTORY, draw_sample, never_fired, symbol_distribution,
)
from swebench_adapter.registry import THEIR_CONFIG_SHA256  # noqa: E402

THEIR_SCRIPT = "scripts/data_processing/extract_enriched_encoding_all.py"
THEIR_CONFIG = "scripts/config.py"
THEIR_RESOLUTION = "data/resolution_status.json"
THEIR_CSV = "data/enriched_encodings_all.csv"
TRAJ = "dataset/trajectories/verified"
COMPARED_COLUMNS = ("instance_id", "agent_name", "framework", "llm_name", "is_failed", "n_raw_steps",
                    "n_encoded_steps", "enriched_encoding", "base_encoding", "has_lb_lt_distinction")
DEFAULT_PYTHON = "uv run --no-project --with pandas --with numpy python"


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read_table(path: Path) -> list[JoinedRow]:
    with path.open(newline="") as fh:
        return [JoinedRow(r["submission_folder"], r["agent_name"], r["llm_name"], r["instance_id"],
                          r["joined"] == "1", r["enriched_encoding"] or None,
                          int(r["is_failed"]) if r["is_failed"] != "" else None)
                for r in csv.DictReader(fh)]


def trajectory_file(root: Path, folder: str, instance_id: str) -> Path:
    for ext in (".traj", ".traj.json", ".json"):   # their glob order: .traj first
        p = root / folder / f"{instance_id}{ext}"
        if p.is_file():
            return p
    raise FileNotFoundError(f"{folder}/{instance_id}")


def build_mirror(package: Path, workdir: Path, sample: list[JoinedRow]) -> dict[str, str]:
    """Copy their code + resolution file + the 20 sampled trajectories; return sha256 per copied file."""
    if workdir.exists():
        shutil.rmtree(workdir)
    hashes: dict[str, str] = {}
    for rel in (THEIR_SCRIPT, THEIR_CONFIG, THEIR_RESOLUTION):
        dst = workdir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(package / rel, dst)
        src_h, dst_h = sha256(package / rel), sha256(dst)
        assert src_h == dst_h, rel
        hashes[rel] = dst_h
    assert hashes[THEIR_CONFIG] == THEIR_CONFIG_SHA256, "their config.py drifted from the vendored hash"
    for r in sample:
        src = trajectory_file(package / TRAJ, r.submission_folder, r.instance_id)
        dst = workdir / TRAJ / r.submission_folder / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        assert sha256(src) == sha256(dst), src.name
        hashes[f"{TRAJ}/{r.submission_folder}/{src.name}"] = sha256(dst)
    return hashes


def run_their_script(workdir: Path, python_cmd: str) -> subprocess.CompletedProcess:
    cmd = shlex.split(python_cmd) + [str(workdir / THEIR_SCRIPT)]
    return subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, timeout=1800)


def compare(sample: list[JoinedRow], theirs: dict, ours: dict) -> list[dict]:
    results = []
    for r in sample:
        key = (r.agent_name, r.llm_name, r.instance_id)
        a, b = theirs.get(key), ours.get(key)
        diffs = []
        if b is None:
            diffs.append(("<row>", "present", "MISSING from rerun output"))
        else:
            for col in COMPARED_COLUMNS:
                if a[col] != b[col]:
                    diffs.append((col, a[col], b[col]))
        results.append({"row": r, "encoding_match": b is not None and a["enriched_encoding"] == b["enriched_encoding"],
                        "full_row_match": not diffs, "diffs": diffs, "theirs": a, "ours": b})
    return results


def render(sample, results, hashes, proc, python_cmd, seed, table_rows, theirs_all, package, workdir) -> str:
    n_enc = sum(1 for x in results if x["encoding_match"])
    n_full = sum(1 for x in results if x["full_row_match"])
    n_doubao_joined = sum(1 for r in table_rows if r.submission_folder == DOUBAO_FOLDER and r.joined)
    n_doubao_pop = sum(1 for r in table_rows if r.submission_folder == DOUBAO_FOLDER)
    L = []
    L.append("# Action-encoding reproducibility spot-check (Task 2)")
    L.append("")
    L.append(f"*Generated {dt.date.today().isoformat()} by `methodology/scripts/spot_check_action_encodings.py`. "
             f"Seed **{seed}** (`action_encoding.spotcheck.SEED`). Replication package: `{package}`. "
             f"Scratch mirror: `{workdir}` (not committed).*")
    L.append("")
    L.append("## Result")
    L.append("")
    L.append(f"- `enriched_encoding` exact match: **{n_enc}/{len(results)}**")
    L.append(f"- full-row match (all 10 CSV columns: {', '.join(COMPARED_COLUMNS)}): **{n_full}/{len(results)}**")
    L.append(f"- their script exit code: {proc.returncode}")
    L.append("")
    L.append("## Sample")
    L.append("")
    L.append(f"Rule: 5 × SAGE, 5 × Trae-doubao, 10 × uniform across the remaining 11 agents — implemented as 10 "
             f"distinct agents drawn uniformly from the 11, one trajectory drawn uniformly from each. All draws are "
             f"from the **joined** population only; an unjoined trajectory has no CSV row to compare against. For "
             f"Trae-doubao that universe is the joined {n_doubao_joined} of {n_doubao_pop} population files "
             f"(the 17 their parser skipped are out of the spot-check universe by construction; see "
             f"`action-encoding-ingest.md`).")
    L.append("")
    L.append("| # | submission folder | instance_id | encoding match | full-row match |")
    L.append("|---|---|---|---|---|")
    for i, x in enumerate(results, 1):
        r = x["row"]
        L.append(f"| {i} | {r.submission_folder} | {r.instance_id} | {'yes' if x['encoding_match'] else 'NO'} "
                 f"| {'yes' if x['full_row_match'] else 'NO'} |")
    L.append("")
    L.append("## Their script, unmodified")
    L.append("")
    L.append(f"Run end to end (`main()`), inside the mirror, as: `{python_cmd} {THEIR_SCRIPT}`. The mirror holds "
             f"byte-identical copies (sha256 verified against the package before the run) of their script, their "
             f"`config.py` (matches the registry-vendored hash), their `resolution_status.json`, and only the 20 "
             f"sampled trajectory files, so `main()` encodes exactly these and writes its own "
             f"`data/enriched_encodings_all.csv` in the mirror. Their package is not written to or imported from.")
    L.append("")
    L.append("| copied file | sha256 |")
    L.append("|---|---|")
    for rel in (THEIR_SCRIPT, THEIR_CONFIG, THEIR_RESOLUTION):
        L.append(f"| `{rel}` | `{hashes[rel]}` |")
    L.append("")
    L.append("<details><summary>sha256 of the 20 copied trajectory files</summary>")
    L.append("")
    for rel, h in hashes.items():
        if rel.startswith(TRAJ):
            L.append(f"- `{rel.split('/', 3)[-1]}` `{h}`")
    L.append("")
    L.append("</details>")
    L.append("")
    L.append("<details><summary>their stdout (tail)</summary>")
    L.append("")
    L.append("```")
    L.extend(proc.stdout.strip().splitlines()[-40:])
    L.append("```")
    if proc.stderr.strip():
        L.append("")
        L.append("stderr:")
        L.append("```")
        L.extend(proc.stderr.strip().splitlines()[-20:])
        L.append("```")
    L.append("")
    L.append("</details>")
    L.append("")
    mism = [x for x in results if not x["full_row_match"]]
    L.append("## Diffs")
    L.append("")
    if not mism:
        L.append("None — every compared column of every sampled row is identical between their shipped CSV and the rerun.")
    else:
        for x in mism:
            r = x["row"]
            L.append(f"### {r.submission_folder} / {r.instance_id}")
            L.append("")
            L.append("| column | their CSV | our rerun |")
            L.append("|---|---|---|")
            for col, a, b in x["diffs"]:
                L.append(f"| `{col}` | `{a}` | `{b}` |")
            L.append("")
    L.append("")
    L.append("## SAGE and Trae-doubao — observed symbol distribution (descriptive only)")
    L.append("")
    L.append("Their parser is action-channel-only with two known blind spots: `Pr` cannot fire on bash-mediated "
             "edits (SAGE is bash-fence), and it never reads Trae's `<function=` XML. Both agents are in their "
             "no-`Lb`/`Lt` group, so those two symbols cannot fire by construction. Per sampled trajectory, "
             "the rerun's encoding (identical to their CSV row wherever the table above says match):")
    L.append("")
    for folder, label in ((SAGE_FOLDER, "SAGE"), (DOUBAO_FOLDER, "Trae-doubao")):
        mine = [x for x in results if x["row"].submission_folder == folder]
        L.append(f"### {label} — {len(mine)} sampled trajectories")
        L.append("")
        L.append("| instance_id | n symbols | distinct symbols | share `G` | encoding |")
        L.append("|---|---|---|---|---|")
        for x in mine:
            enc = x["theirs"]["enriched_encoding"]
            c = symbol_distribution([enc]); n = sum(c.values())
            L.append(f"| {x['row'].instance_id} | {n} | {', '.join(f'{s}:{c[s]}' for s in SYMBOL_INVENTORY if c[s])} "
                     f"| {100 * c['G'] / n:.0f}% | `{enc}` |")
        agg = symbol_distribution([x["theirs"]["enriched_encoding"] for x in mine])
        n = sum(agg.values())
        L.append("")
        L.append(f"Aggregate over the {len(mine)}: {n} symbols; "
                 + ", ".join(f"`{s}` {agg[s]} ({100 * agg[s] / n:.1f}%)" for s in SYMBOL_INVENTORY if agg[s])
                 + f". Never fire in the sample: {', '.join(f'`{s}`' for s in never_fired(agg))}.")
        # context: the agent's full joined row set in their CSV
        sub = [r for r in table_rows if r.submission_folder == folder and r.joined]
        all_c = symbol_distribution([r.enriched_encoding for r in sub]); all_n = sum(all_c.values())
        L.append("")
        L.append(f"Context, all {len(sub)} joined rows of this agent in their CSV: {all_n} symbols; "
                 + ", ".join(f"`{s}` {100 * all_c[s] / all_n:.1f}%" for s in SYMBOL_INVENTORY if all_c[s])
                 + f". Never fire agent-wide: {', '.join(f'`{s}`' for s in never_fired(all_c))}. "
                 f"Median symbols per row: {sorted(len(r.enriched_encoding.split()) for r in sub)[len(sub) // 2]}.")
        L.append("")
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True, type=Path)
    ap.add_argument("--table", required=True, type=Path)
    ap.add_argument("--workdir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--python-cmd", default=DEFAULT_PYTHON)
    a = ap.parse_args(argv)
    package = a.package.expanduser()
    workdir = a.workdir.expanduser()

    table_rows = read_table(a.table)
    sample = draw_sample(table_rows, a.seed)
    assert len(sample) == 20 and len({(r.submission_folder, r.instance_id) for r in sample}) == 20
    hashes = build_mirror(package, workdir, sample)
    proc = run_their_script(workdir, a.python_cmd)
    print(proc.stdout[-3000:])
    if proc.returncode != 0:
        print(proc.stderr[-3000:])
        print("their script failed; not adapting it (handoff)")
        return 2
    theirs = load_encodings(package / THEIR_CSV)
    ours = load_encodings(workdir / THEIR_CSV)
    results = compare(sample, theirs, ours)
    a.out.write_text(render(sample, results, hashes, proc, a.python_cmd, a.seed, table_rows, theirs, package, workdir))
    n_full = sum(1 for x in results if x["full_row_match"])
    print(f"encoding match {sum(1 for x in results if x['encoding_match'])}/20, full-row match {n_full}/20")
    print(f"wrote {a.out}")
    return 0 if n_full == 20 else 1


if __name__ == "__main__":
    raise SystemExit(main())
