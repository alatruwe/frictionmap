"""Stability metrics for pre-registration §5 (judge-vs-human κ is out of scope).

- Rerun consistency: exact-score agreement across the three v1 passes, over
  units with a score in every pass. Units missing in any pass are excluded and
  counted.
- Prompt perturbation: pairwise quadratic-weighted Cohen's κ, computed on the
  fixed 0-3 category set over units scored in both passes. No averaging. The
  v1 side of each pair is v1-pass1 (first rerun); the other two v1 passes are
  the rerun check, not additional prompt versions.
"""
from __future__ import annotations

import json
from pathlib import Path

from judge_harness.store import final_attempt, load_ledger, unit_complete

CATEGORIES = (0, 1, 2, 3)
V1_PASSES = ("v1-pass1", "v1-pass2", "v1-pass3")
PAIRS = (("v1-pass1", "paraphrase-a"), ("v1-pass1", "paraphrase-b"), ("paraphrase-a", "paraphrase-b"))
METRICS_NAME = "metrics.json"

Scores = dict[int, int | None]   # position -> score, None = missing


def load_pass_scores(run_dir: Path, pass_id: str) -> tuple[Scores, int]:
    """(scores for completed units, incomplete units excluded)."""
    ledger = load_ledger(run_dir, pass_id)
    scores: Scores = {}
    incomplete = 0
    for position, attempts in ledger.items():
        if not unit_complete(attempts):
            incomplete += 1
            continue
        scores[position] = final_attempt(attempts).score
    return scores, incomplete


def rerun_agreement(passes: list[Scores]) -> dict:
    positions = set().union(*(set(p) for p in passes)) if passes else set()
    compared = sorted(pos for pos in positions if all(p.get(pos) is not None for p in passes))
    agree = sum(1 for pos in compared if len({p[pos] for p in passes}) == 1)
    return {
        "n_passes": len(passes),
        "n_units": len(positions),
        "n_compared": len(compared),
        "n_excluded_missing": len(positions) - len(compared),
        "n_agree": agree,
        "agreement_pct": round(100.0 * agree / len(compared), 2) if compared else None,
        "disagreeing_positions": [pos for pos in compared if len({p[pos] for p in passes}) > 1],
    }


def quadratic_weighted_kappa(a: list[int], b: list[int], categories: tuple[int, ...] = CATEGORIES) -> float | None:
    """Cohen's κ with quadratic weights over a fixed category set.
    None when expected disagreement is zero (κ undefined)."""
    if len(a) != len(b):
        raise ValueError("score lists differ in length")
    n = len(a)
    if n == 0:
        return None
    index = {c: i for i, c in enumerate(categories)}
    k = len(categories)
    observed = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b):
        observed[index[x]][index[y]] += 1
    row = [sum(r) for r in observed]
    col = [sum(observed[i][j] for i in range(k)) for j in range(k)]
    denom = (k - 1) ** 2
    num = 0.0
    exp = 0.0
    for i in range(k):
        for j in range(k):
            w = (i - j) ** 2 / denom
            num += w * observed[i][j]
            exp += w * row[i] * col[j] / n
    if exp == 0:
        return None
    return 1.0 - num / exp


def pairwise_kappa(pass_a: Scores, pass_b: Scores) -> dict:
    positions = set(pass_a) | set(pass_b)
    both = sorted(pos for pos in positions if pass_a.get(pos) is not None and pass_b.get(pos) is not None)
    kappa = quadratic_weighted_kappa([pass_a[p] for p in both], [pass_b[p] for p in both])
    return {
        "n_units": len(positions),
        "n_compared": len(both),
        "n_excluded_missing": len(positions) - len(both),
        "quadratic_weighted_kappa": None if kappa is None else round(kappa, 4),
        "disagreeing_positions": [p for p in both if pass_a[p] != pass_b[p]],
    }


def compute_metrics(run_dir: Path) -> dict:
    available = {p.name for p in run_dir.iterdir() if p.is_dir() and (p / "ledger.jsonl").exists()}
    loaded = {pass_id: load_pass_scores(run_dir, pass_id) for pass_id in sorted(available)}
    per_pass = {
        pass_id: {"n_scored": sum(1 for s in scores.values() if s is not None),
                  "n_missing": sum(1 for s in scores.values() if s is None),
                  "n_incomplete": incomplete}
        for pass_id, (scores, incomplete) in loaded.items()
    }
    out: dict = {"passes": per_pass}
    if all(p in loaded for p in V1_PASSES):
        out["rerun_agreement"] = rerun_agreement([loaded[p][0] for p in V1_PASSES])
    else:
        out["rerun_agreement"] = {"skipped": f"needs all of {list(V1_PASSES)}"}
    out["pairwise_kappa"] = {}
    for a, b in PAIRS:
        key = f"{a}<->{b}"
        if a in loaded and b in loaded:
            out["pairwise_kappa"][key] = pairwise_kappa(loaded[a][0], loaded[b][0])
        else:
            out["pairwise_kappa"][key] = {"skipped": "pass missing"}
    return out


def report_run(run_dir: Path) -> str:
    metrics = compute_metrics(run_dir)
    text = json.dumps(metrics, indent=1)
    (run_dir / METRICS_NAME).write_text(text + "\n", encoding="utf-8")
    return text
