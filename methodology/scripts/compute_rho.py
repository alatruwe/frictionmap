"""W1 characterization: judge-vs-deterministic Spearman ρ (pre-registration §5,
secondary) and per-corpus score distributions.

Descriptive only — no thresholds, no pass/fail. Deterministic: no randomness,
no seed. Zero API calls; everything comes from committed judge output and a
local v1 run over the pinned corpus.

Pre-committed interpretation (§9, 2026-09-07, committed before this ran):
- "files with n_blocks_attributed >= 3" = files with >= 3 *validation-sample*
  blocks attributed to them by v1's attribution output (Attribution.file_paths,
  whichever tier produced it).
- Blocks with empty file_paths are excluded from per-file aggregation.
- A block attributing to multiple files counts toward each file.

Signal values are v1's per-file raw values (ScoreComponents.<signal>.raw) from
score_corpus(), computed per corpus with v1's shipped formulas:
- markers_per_100w: presence x intensity (schema 1.3), 1/N dilution-weighted
- reread_bursts, edit_churn: per-file burst counts
Raw values, not z-scores: Spearman is rank-based, and z-scoring per corpus
would reorder files across the pooled set.

Usage:
    uv run --with pandas --with scipy python methodology/scripts/compute_rho.py [CORPUS_ROOT]

Reads (relative to repo root):
    judge-runs/validation-2026-09-07/v1-pass1/scores.csv
    labels.csv
    sample-manifest.csv
    methodology/corpus-manifest.txt   (corpus hash gate, same as sampling)
Writes:
    methodology/results/phase1-rho.txt
    methodology/results/phase1-corpus-distributions.txt

Privacy: outputs are numbers and file basenames only. No thinking text, no
full local paths, no session text of any kind.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "methodology" / "scripts"))

from frictionmap.events import BaselineSet  # noqa: E402
from frictionmap.parser import parse_sessions  # noqa: E402
from frictionmap.scoring import score_corpus  # noqa: E402
from sample_validation import CORPORA, verify_corpus  # noqa: E402

JUDGE_CSV = REPO_ROOT / "judge-runs/validation-2026-09-07/v1-pass1/scores.csv"
LABELS_CSV = REPO_ROOT / "labels.csv"
MANIFEST_CSV = REPO_ROOT / "sample-manifest.csv"
RHO_OUT = REPO_ROOT / "methodology/results/phase1-rho.txt"
DIST_OUT = REPO_ROOT / "methodology/results/phase1-corpus-distributions.txt"
DEFAULT_CORPUS_ROOT = Path("~/Projects/v2-sessions").expanduser()

MIN_BLOCKS_PER_FILE = 3
SIGNALS = ("markers_per_100w", "reread_bursts", "edit_churn")
# ScoreComponents field name per signal (markers_per_100w lives on `markers`).
COMPONENT_FIELD = {
    "markers_per_100w": "markers",
    "reread_bursts": "reread_bursts",
    "edit_churn": "edit_churn",
}

# §5, restated verbatim (pre-registration.md, "Judge-vs-deterministic agreement").
PREREG_S5_VERBATIM = (
    "**Judge-vs-deterministic agreement (secondary):** Spearman ρ between mean judge score "
    "per file and v1 per-file signal values, per signal, restricted to files with "
    "`n_blocks_attributed ≥ 3` (small-N floor; thin-evidence files are established "
    "attribution noise). No pass threshold — this is characterization, not gating. "
    "**Predictions:** ρ > 0 vs `markers_per_100w` (same substrate, overlapping construct); "
    "weaker or null vs reread bursts and edit churn (they measure action-level friction the "
    "judge cannot see from thinking text alone, except where the model narrates its actions). "
    "**Anticipated surprise, named in advance:** if judge-vs-churn ρ matched or exceeded "
    "judge-vs-markers, that would indicate models narrate action struggles thoroughly enough "
    "that text carries the action layer — an interesting result, not a failure."
)


def load_units() -> pd.DataFrame:
    """Judge scores + human labels + manifest, joined and cross-checked
    (same assert-the-join discipline as compute_kappa.py)."""
    judge = pd.read_csv(JUDGE_CSV)
    labels = pd.read_csv(LABELS_CSV)
    manifest = pd.read_csv(MANIFEST_CSV)

    assert (judge["pass_id"] == "v1-pass1").all(), "unexpected pass_id in scores file"
    assert (judge["missing_flag"] == 0).all(), "missing rows in judge scores"

    df = labels.merge(
        judge[["sheet_position", "session_id", "block_index", "score"]],
        on="sheet_position",
        suffixes=("_human", "_judge"),
    ).merge(manifest, on="sheet_position", suffixes=("", "_manifest"))

    assert len(df) == 100, f"expected 100 matched rows, got {len(df)}"
    assert df["sheet_position"].is_unique, "duplicate sheet_position after join"
    assert (df["session_id_human"] == df["session_id_judge"]).all(), "session_id mismatch"
    assert (df["block_index_human"] == df["block_index_judge"]).all(), "block_index mismatch"
    assert (df["session_id_human"] == df["session_id"]).all(), "manifest session_id mismatch"
    assert (df["block_index_human"] == df["block_index"]).all(), "manifest block_index mismatch"
    assert set(df["corpus"]) <= set(CORPORA), f"unexpected corpus label: {set(df['corpus'])}"
    assert df["score_judge"].isin([0, 1, 2, 3]).all(), "judge score outside 0..3"
    assert df["score_human"].isin([0, 1, 2, 3]).all(), "human score outside 0..3"
    return df


def run_v1(root: Path):
    """Parse both corpora with v1 as shipped; return
    (unit_paths, unit_corpus, signals) where
      unit_paths[(session_id, block_index)] = attributed file_paths (list)
      unit_corpus[(session_id, block_index)] = corpus label
      signals[(corpus, path)] = {signal: raw value}
    block_index counts non-empty thinking blocks per session in event order —
    identical to sample_validation.build_pool, so unit keys line up.
    """
    unit_paths: dict[tuple[str, int], list[str]] = {}
    unit_corpus: dict[tuple[str, int], str] = {}
    signals: dict[tuple[str, str], dict[str, float]] = {}
    for label in CORPORA:
        corpus = parse_sessions(root / label)
        for session_id, events in corpus.sessions.items():
            block_index = 0
            for event in events:
                for block in event.blocks:
                    if block.type != "thinking" or not block.thinking:
                        continue
                    key = (session_id, block_index)
                    assert key not in unit_paths, f"duplicate unit key {key}"
                    attribution = block.attribution
                    unit_paths[key] = list(attribution.file_paths) if attribution else []
                    unit_corpus[key] = label
                    block_index += 1
        # Raw per-file values only; BaselineSet() defaults leave raw untouched.
        for path, result in score_corpus(corpus, BaselineSet()).items():
            c = result.components
            signals[(label, path)] = {
                s: float(getattr(c, COMPONENT_FIELD[s]).raw) for s in SIGNALS
            }
    return unit_paths, unit_corpus, signals


def part_a(df: pd.DataFrame, root: Path) -> str:
    n_corpus_files = verify_corpus(root)
    unit_paths, unit_corpus, signals = run_v1(root)

    # --- Map the 100 units onto v1's attribution; hard-fail on any gap. ----
    keys = list(zip(df["session_id"], df["block_index"]))
    missing = [k for k in keys if k not in unit_paths]
    assert not missing, f"{len(missing)} validation units not found in v1 parse: {missing[:3]}"
    corpus_mismatch = [
        k for k, c in zip(keys, df["corpus"]) if unit_corpus[k] != c
    ]
    assert not corpus_mismatch, f"manifest corpus disagrees with v1 parse for {corpus_mismatch[:3]}"
    # Manifest's file_attachment flag was recorded at draw time from the same
    # attribution; it must agree with what v1 produces now.
    attach_mismatch = [
        k for k, fa in zip(keys, df["file_attachment"])
        if bool(unit_paths[k]) != bool(fa)
    ]
    assert not attach_mismatch, f"file_attachment flag disagrees with v1 attribution for {attach_mismatch[:3]}"

    # --- Per-file aggregation over validation-sample blocks. ---------------
    per_file_scores: dict[tuple[str, str], list[int]] = defaultdict(list)
    n_attributed = n_excluded_empty = 0
    multi_file_units = 0
    for k, corpus, score in zip(keys, df["corpus"], df["score_judge"]):
        paths = unit_paths[k]
        if not paths:
            n_excluded_empty += 1
            continue
        n_attributed += 1
        if len(paths) > 1:
            multi_file_units += 1
        for p in paths:
            per_file_scores[(corpus, p)].append(int(score))
    assert n_attributed + n_excluded_empty == 100, "unit accounting does not sum to 100"

    for fk in per_file_scores:
        assert fk in signals, f"attributed file missing from v1 score output: {fk[1]!r}"

    rows = []
    for (corpus, path), scores in per_file_scores.items():
        rows.append({
            "corpus": corpus,
            "basename": Path(path).name,
            "n_blocks": len(scores),
            "mean_judge": sum(scores) / len(scores),
            **signals[(corpus, path)],
        })
    files = pd.DataFrame(rows)
    kept = files[files["n_blocks"] >= MIN_BLOCKS_PER_FILE].copy()
    kept = kept.sort_values(["corpus", "basename", "n_blocks"]).reset_index(drop=True)

    # --- Spearman ρ per signal over kept files. ----------------------------
    out: list[str] = []
    out.append("Phase 1 characterization — judge-vs-deterministic Spearman ρ (§5 secondary)")
    out.append("Judge scores: v1-pass1. Signal values: v1 per-file raw values (score_corpus, per corpus).")
    out.append(f"Corpus hash gate: {n_corpus_files} session files verified against corpus-manifest.txt.")
    out.append("")
    out.append("Unit accounting (100 validation units):")
    out.append(f"  attributed (non-empty file_paths): {n_attributed}")
    out.append(f"  excluded (empty file_paths):        {n_excluded_empty}")
    out.append(f"  sum:                                {n_attributed + n_excluded_empty}")
    out.append(f"  of attributed, multi-file blocks (count toward each file): {multi_file_units}")
    out.append("")
    out.append("Per-file aggregation (rule fixed in §9 before computation):")
    out.append(f"  distinct files with >= 1 sample block: {len(files)}")
    out.append(f"  files with >= {MIN_BLOCKS_PER_FILE} sample blocks (kept):     {len(kept)}"
               f"  (attune {int((kept['corpus'] == 'attune').sum())}, "
               f"brownfield {int((kept['corpus'] == 'brownfield').sum())})")
    out.append(f"  sample blocks covered by kept files:  {int(kept['n_blocks'].sum())} block-file pairs")
    dist = files["n_blocks"].value_counts().sort_index()
    out.append("  files by sample-block count: " + ", ".join(f"{k}:{v}" for k, v in dist.items()))
    out.append("")
    out.append(f"Spearman ρ (mean judge score vs signal raw value), n = {len(kept)} kept files:")
    out.append(f"  {'signal':<18} {'rho':>8} {'p':>8} {'n_files':>8}   note")
    for s in SIGNALS:
        x = kept["mean_judge"].to_numpy()
        y = kept[s].to_numpy()
        n_nonzero = int((y != 0).sum())
        if len(kept) < 3 or (y == y[0]).all():
            rho_s, p_s = "nan", "nan"
        else:
            r = spearmanr(x, y)
            rho_s, p_s = f"{r.statistic:.4f}", f"{r.pvalue:.4f}"
        out.append(f"  {s:<18} {rho_s:>8} {p_s:>8} {len(kept):>8}   "
                   f"{n_nonzero}/{len(kept)} files have nonzero signal")
    out.append("")
    out.append("Kept files (basenames only; mean_judge over that file's sample blocks):")
    out.append(f"  {'corpus':<11} {'basename':<34} {'n_blk':>5} {'mean_j':>7} "
               f"{'markers':>8} {'reread':>7} {'churn':>6}")
    for _, r in kept.iterrows():
        out.append(f"  {r['corpus']:<11} {r['basename'][:34]:<34} {int(r['n_blocks']):>5} "
                   f"{r['mean_judge']:>7.3f} {r['markers_per_100w']:>8.3f} "
                   f"{r['reread_bursts']:>7.0f} {r['edit_churn']:>6.0f}")
    out.append("")
    out.append("Pre-registration §5, restated verbatim:")
    out.append("")
    out.append(PREREG_S5_VERBATIM)
    out.append("")
    out.append("Characterization only. Interpretation is W1 writing, not part of this output.")
    return "\n".join(out) + "\n"


def part_b(df: pd.DataFrame) -> str:
    out: list[str] = []
    out.append("Phase 1 characterization — per-corpus score distributions (counts only)")
    out.append("Human = labels.csv first pass. Judge = v1-pass1. Corpus from sample-manifest.csv.")
    out.append("")
    out.append(f"  {'source':<7} {'corpus':<11} {'n':>4}   {'0':>4} {'1':>4} {'2':>4} {'3':>4}")
    for source, col in (("human", "score_human"), ("judge", "score_judge")):
        for corpus in CORPORA:
            sub = df[df["corpus"] == corpus]
            counts = sub[col].value_counts().reindex(range(4), fill_value=0)
            assert int(counts.sum()) == len(sub)
            out.append(f"  {source:<7} {corpus:<11} {len(sub):>4}   "
                       + " ".join(f"{int(counts[k]):>4}" for k in range(4)))
    out.append("")
    out.append(f"  units per corpus sum to {len(df)}.")
    out.append("Counts only. Interpretation is W1 writing, not part of this output.")
    return "\n".join(out) + "\n"


def main() -> int:
    root = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else DEFAULT_CORPUS_ROOT
    df = load_units()
    a = part_a(df, root)
    b = part_b(df)
    RHO_OUT.write_text(a)
    DIST_OUT.write_text(b)
    print(a)
    print(b)
    print(f"wrote {RHO_OUT.relative_to(REPO_ROOT)} and {DIST_OUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
