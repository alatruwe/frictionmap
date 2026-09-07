"""Judge-vs-human agreement: quadratic-weighted Cohen's kappa (pre-registration §5).

Pre-committed analysis rules (fixed before any kappa was computed):
- Judge score = v1-pass1 (first pass of the deployment prompt).
- CI = 95%, bootstrap over units, 10,000 resamples, percentile method,
  seed = BOOTSTRAP_SEED below.
- Point estimate decides the band (>=0.6 validated / 0.4-0.6 partial / <0.4 failed);
  the CI is reported, not used for the band decision.

Usage:
    uv run --with pandas --with scikit-learn python methodology/scripts/compute_kappa.py

Reads (paths relative to repo root):
    judge-runs/validation-2026-09-07/v1-pass1/scores.csv
    labels.csv
    sample-manifest.csv
"""

import sys
import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

BOOTSTRAP_SEED = 27  # <-- set your chosen integer before running
N_BOOT = 10_000

JUDGE_CSV = "judge-runs/validation-2026-09-07/v1-pass1/scores.csv"
LABELS_CSV = "labels.csv"
MANIFEST_CSV = "sample-manifest.csv"

# Human self-consistency reference (relabel, Sep 7): ceiling on achievable agreement.
HUMAN_MAD = 0.35
HUMAN_EXACT_PCT = 70.0


def qwk(a, b):
    return cohen_kappa_score(a, b, weights="quadratic", labels=[0, 1, 2, 3])


def main():
    if BOOTSTRAP_SEED is None:
        sys.exit("Set BOOTSTRAP_SEED before running (pre-commitment rule).")

    judge = pd.read_csv(JUDGE_CSV)
    labels = pd.read_csv(LABELS_CSV)
    manifest = pd.read_csv(MANIFEST_CSV)

    # Sanity on the judge file: single pass, no missing/retried rows.
    assert (judge["pass_id"] == "v1-pass1").all(), "unexpected pass_id in scores file"
    assert (judge["missing_flag"] == 0).all(), "missing rows in judge scores"

    # Join on sheet_position; verify session_id/block_index agree everywhere
    # so a scrambled file can't silently produce a wrong-but-plausible kappa.
    df = labels.merge(
        judge[["sheet_position", "session_id", "block_index", "score"]],
        on="sheet_position",
        suffixes=("_human", "_judge"),
    ).merge(manifest, on="sheet_position", suffixes=("", "_manifest"))

    assert len(df) == 100, f"expected 100 matched rows, got {len(df)}"
    assert (df["session_id_human"] == df["session_id_judge"]).all(), "session_id mismatch"
    assert (df["block_index_human"] == df["block_index_judge"]).all(), "block_index mismatch"
    assert (df["session_id_human"] == df["session_id"]).all(), "manifest session_id mismatch"
    assert (df["block_index_human"] == df["block_index"]).all(), "manifest block_index mismatch"

    h = df["score_human"].to_numpy()
    j = df["score_judge"].to_numpy()

    # --- Primary: pooled kappa + bootstrap CI -------------------------------
    k_pooled = qwk(h, j)

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    n = len(df)
    boots = []
    for _ in range(N_BOOT):
        idx = rng.integers(0, n, n)
        # A resample can lack score variety; kappa is still defined with fixed labels.
        boots.append(qwk(h[idx], j[idx]))
    lo, hi = np.percentile(boots, [2.5, 97.5])

    # --- Secondary views (§5): random half, per-corpus ----------------------
    views = {}
    rand = df[df["stratum"] == "random"]
    views[f"random half (n={len(rand)})"] = qwk(rand["score_human"], rand["score_judge"])
    for corpus, sub in df.groupby("corpus"):
        views[f"corpus={corpus} (n={len(sub)})"] = qwk(sub["score_human"], sub["score_judge"])

    # --- Descriptive agreement, comparable to the human ceiling -------------
    exact_pct = float((h == j).mean() * 100)
    mad = float(np.abs(h - j).mean())

    band = "VALIDATED" if k_pooled >= 0.6 else ("PARTIALLY VALIDATED" if k_pooled >= 0.4 else "FAILED")

    print(f"pooled quadratic-weighted kappa = {k_pooled:.4f}")
    print(f"95% bootstrap CI [{lo:.4f}, {hi:.4f}]  (n_boot={N_BOOT}, seed={BOOTSTRAP_SEED})")
    print(f"band (point estimate vs 0.6/0.4): {band}")
    print()
    for name, k in views.items():
        print(f"  {name}: kappa = {k:.4f}")
    print()
    print(f"judge-vs-human: exact = {exact_pct:.1f}%, MAD = {mad:.2f}")
    print(f"human self-consistency ceiling: exact = {HUMAN_EXACT_PCT:.1f}%, MAD = {HUMAN_MAD:.2f}")

    # Cross-tab: rows = human, cols = judge. Where disagreement lives.
    print()
    print("confusion (rows=human, cols=judge):")
    print(pd.crosstab(df["score_human"], df["score_judge"]).reindex(
        index=range(4), columns=range(4), fill_value=0))


if __name__ == "__main__":
    main()