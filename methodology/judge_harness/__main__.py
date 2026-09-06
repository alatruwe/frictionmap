"""CLI. Default mode is dry-run over the anchor sessions.

  run     judge units with one or more passes (resumable; same --run-id resumes)
  render  regenerate scores.csv for every pass in a run dir
  metrics stability metrics over a run dir (rerun agreement, pairwise QW kappa)

Validation mode (--validation-run + --i-confirm PHRASE) is the only path that
reads sample-manifest.csv. It runs three gates first: labels.csv bytes hash to
the committed value, the corpus matches corpus-manifest.txt, and the sheet
re-rendered from the manifest hashes to the sealed value.

Usage (from the repo root):
  uv run python methodology/scripts/run_judge.py run --corpus-root ~/Projects/v2-sessions \
      --run-id smoke-anchors --pass v1-pass1
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from judge_harness import REPO_ROOT
from judge_harness.client import JUDGE_PARAMS, JudgeClient
from judge_harness.prompts import PASS_PROMPTS, assemble, load_prompt, prompt_for_pass
from judge_harness.runner import PassAborted, run_pass
from judge_harness.store import read_manifest, render_scores, update_manifest
from judge_harness.units import (
    ANCHOR_SESSIONS_PATH,
    CORPUS_MANIFEST_PATH,
    GateError,
    anchor_units,
    verify_corpus,
)

CONFIRM_PHRASE = "labels are committed and hashed"
DEFAULT_RUNS_DIR = REPO_ROOT / "judge-runs"


def _validation_units(corpus_root: Path):
    """Imported lazily and called only from the validation branch."""
    from judge_harness.units import (
        LABELS_PATH,
        LABELS_SHA256,
        SAMPLE_MANIFEST_PATH,
        SEAL_PATH,
        manifest_units,
        verify_labels,
        verify_sheet_identity,
    )
    verify_labels(LABELS_PATH, LABELS_SHA256)
    units = manifest_units(corpus_root, SAMPLE_MANIFEST_PATH)
    verify_sheet_identity(units, SEAL_PATH)
    return units


def cmd_run(args: argparse.Namespace, client_factory: Callable[[], object]) -> int:
    run_dir = Path(args.runs_dir) / args.run_id
    corpus_root = Path(args.corpus_root).expanduser()
    verified = verify_corpus(corpus_root, Path(args.corpus_manifest))

    if args.validation_run:
        if args.i_confirm != CONFIRM_PHRASE:
            raise GateError(f"--validation-run requires --i-confirm {CONFIRM_PHRASE!r}")
        mode, unit_source = "validation", "sample-manifest.csv"
        units = _validation_units(corpus_root)
    else:
        mode, unit_source = "dry-run", "anchors"
        units = anchor_units(corpus_root, Path(args.anchors))
    if args.limit:
        units = units[:args.limit]

    existing = read_manifest(run_dir)
    if existing and existing.get("mode") != mode:
        raise GateError(f"run dir {run_dir} is a {existing.get('mode')} run; refusing to mix modes")

    prompts = {name: load_prompt(name) for name in sorted({prompt_for_pass(p) for p in args.passes})}
    client = client_factory()
    scaffold = existing.get("scaffold_tokens", {})
    for name, prompt in prompts.items():
        if name not in scaffold:
            system, user = assemble(prompt, "")
            scaffold[name] = client.count_tokens(system, user)

    update_manifest(run_dir, {
        "run_id": args.run_id, "mode": mode, "unit_source": unit_source,
        "corpus_root": str(corpus_root), "corpus_files_verified": verified,
        "created_at": existing.get("created_at") or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "judge": JUDGE_PARAMS,
        "prompts": {n: {"path": str(p.path.relative_to(REPO_ROOT)), "sha256": p.sha256} for n, p in prompts.items()},
        "scaffold_tokens": scaffold,
    })

    for pass_id in args.passes:
        prompt = prompts[prompt_for_pass(pass_id)]
        print(f"[{pass_id}] {len(units)} units, prompt {prompt.name} ({prompt.sha256[:12]})")
        try:
            summary = run_pass(run_dir, pass_id, prompt, units, client,
                               progress=(print if args.verbose else None))
        except PassAborted as exc:
            update_manifest(run_dir, {"passes": {pass_id: {
                "aborted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "abort_reason": str(exc)}}})
            print(f"[{pass_id}] ABORTED: {exc}. Ledger intact; rerun with the same --run-id to resume.")
            return 2
        info = summary.as_manifest()
        info["prompt"] = prompt.name
        info["prompt_sha256"] = prompt.sha256
        info.pop("aborted_at", None)
        update_manifest(run_dir, {"passes": {pass_id: info}})
        _, rows, incomplete = render_scores(run_dir, pass_id)
        print(f"[{pass_id}] calls={summary.calls} completed={summary.units_completed} "
              f"resumed={summary.units_skipped_resume} retried={summary.retried} "
              f"missing={summary.missing} infra_retries={summary.infra_retries} "
              f"latency={summary.latency_stats()} rows={rows} incomplete={incomplete}")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir)
    for pass_id in sorted(p.name for p in run_dir.iterdir() if p.is_dir() and p.name in PASS_PROMPTS):
        path, rows, incomplete = render_scores(run_dir, pass_id)
        print(f"{path.relative_to(run_dir.parent)}: {rows} rows, {incomplete} incomplete omitted")
    return 0


def cmd_metrics(args: argparse.Namespace) -> int:
    from judge_harness.metrics import report_run
    print(report_run(Path(args.run_dir)))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="judge_harness", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="judge units (dry-run over anchors by default)")
    run.add_argument("--corpus-root", required=True)
    run.add_argument("--run-id", required=True)
    run.add_argument("--pass", dest="passes", action="append", required=True,
                     choices=sorted(PASS_PROMPTS), help="repeatable")
    run.add_argument("--limit", type=int, default=0, help="first N units only")
    run.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
    run.add_argument("--anchors", default=str(ANCHOR_SESSIONS_PATH))
    run.add_argument("--corpus-manifest", default=str(CORPUS_MANIFEST_PATH))
    run.add_argument("--verbose", action="store_true")
    run.add_argument("--validation-run", action="store_true",
                     help="judge the validation sample. Requires --i-confirm.")
    run.add_argument("--i-confirm", default="", metavar="PHRASE")

    render = sub.add_parser("render", help="regenerate scores.csv from ledgers")
    render.add_argument("run_dir")

    metrics = sub.add_parser("metrics", help="stability metrics for a run")
    metrics.add_argument("run_dir")
    return parser


def main(argv: list[str] | None = None, client_factory: Callable[[], object] = JudgeClient) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "run":
            return cmd_run(args, client_factory)
        if args.command == "render":
            return cmd_render(args)
        return cmd_metrics(args)
    except GateError as exc:
        print(f"gate failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
