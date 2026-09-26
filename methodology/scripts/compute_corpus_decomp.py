"""Per-corpus decomposition of judge-vs-human agreement (pre-registration §5 secondary view; §9 row dated 2026-09-26).

Counts only. Interpretation is W1 writing.

Pre-committed analysis rules (from the §9 row, committed on main before this
script existed):
- Human score = labels.csv first pass. Judge score = v1-pass1. Corpus from
  sample-manifest.csv. Join on sheet_position.
- Per corpus: 4x4 confusion matrix (rows = human, cols = judge), exact
  agreement, MAD, misses by distance, quadratic-weighted kappa, and kappa's
  chance-expected disagreement term.
- Kappa must reproduce the committed per-corpus values (attune 0.4216,
  brownfield 0.8050, results/phase1-kappa.txt) to 4 decimals or the script stops.
- Decision quantity (one): delta = MAD_attune - MAD_brownfield on units with
  human score in {0, 1}; 95% percentile bootstrap CI, 10,000 resamples of
  units within each corpus, seed 26.

Bootstrap convention (matches compute_kappa.py): numpy default_rng(seed); each
resample draws attune units with replacement, then brownfield units with
replacement, from the same generator, and recomputes delta.

Quadratic-weighted kappa, as computed here (identical to sklearn's
cohen_kappa_score(weights="quadratic", labels=[0,1,2,3]) up to a constant that
cancels in the ratio):
    observed = mean over units of (h - j)^2
    expected = sum_{a,b} p_h(a) * p_j(b) * (a - b)^2   (marginals independent)
    kappa    = 1 - observed / expected
"expected" is the chance-expected disagreement term reported below.

Usage:
    uv run --with numpy python methodology/scripts/compute_corpus_decomp.py

Reads (paths relative to repo root):
    labels.csv
    methodology/results/v1-pass1-scores.csv
    sample-manifest.csv
Writes:
    methodology/results/phase1-corpus-decomp.txt
"""

import csv
import sys
from collections import Counter
from pathlib import Path

import numpy as np

BOOTSTRAP_SEED = 26
N_BOOT = 10_000
SCORES = (0, 1, 2, 3)
CORPORA = ("attune", "brownfield")
EXPECTED_N = {"attune": 54, "brownfield": 46}
EXPECTED_KAPPA = {"attune": 0.4216, "brownfield": 0.8050}

LABELS_CSV = Path("labels.csv")
JUDGE_CSV = Path("methodology/results/v1-pass1-scores.csv")
MANIFEST_CSV = Path("sample-manifest.csv")
OUT_TXT = Path("methodology/results/phase1-corpus-decomp.txt")

SECTION_9_ROW = (
    "| 2026-09-26 | §5 (secondary view: per-corpus κ) | Reading rule for the per-corpus split, committed before the per-corpus decomposition exists. Known at commit time: per-corpus κ attune 0.4216 (n = 54), brownfield 0.8050 (n = 46), and per-corpus score counts (`results/phase1-corpus-distributions.txt`). Two candidate explanations: **(A) spread arithmetic** — the judge errs at similar rate and size in both corpora; attune κ is lower because attune scores bunch near 0 (human 3s: 2 vs 6), shrinking κ's chance-expected disagreement. **(B) judge deficit on attune text** — the judge errs more, or by more, on attune blocks. Decision quantity (one): Δ = MAD_attune − MAD_brownfield (judge `v1-pass1` vs human first pass), restricted to units with human score 0 or 1 (like-for-like cells; attune n = 46, brownfield n = 36), with a 95% percentile bootstrap CI (10,000 resamples of units within each corpus, seed 26). Rule: CI lower bound > 0 → reported as (B). Otherwise → reported as consistent with (A); if the CI includes 0, a small deficit is not ruled out at this n. A deficit confined to scores 2–3 is untestable (attune n = 8) and is stated as such. Reported descriptively regardless: per-corpus confusion matrices, exact agreement, misses by distance, chance-expected disagreement. | The per-corpus view is a registered guard; a reading chosen after the decomposition exists would be a story, not a rule. Restricting Δ to human scores 0–1 removes the spread difference the two explanations dispute. | Characterization only. No gate, band, or Q1/Q2 eligibility change; pooled κ decides per §5. |"
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def parse_score(raw: str, where: str) -> int:
    if raw is None or raw.strip() == "":
        sys.exit(f"missing score: {where}")
    s = int(raw)
    if s not in SCORES:
        sys.exit(f"score out of range ({s}): {where}")
    return s


def load_units() -> list[dict]:
    labels = {int(r["sheet_position"]): r for r in read_csv(LABELS_CSV)}
    judge = {int(r["sheet_position"]): r for r in read_csv(JUDGE_CSV)}
    manifest = {int(r["sheet_position"]): r for r in read_csv(MANIFEST_CSV)}

    for name, d in (("labels", labels), ("judge", judge), ("manifest", manifest)):
        if len(d) != 100:
            sys.exit(f"{name}: expected 100 rows keyed by sheet_position, got {len(d)}")
    if not (set(labels) == set(judge) == set(manifest)):
        sys.exit("sheet_position sets differ across inputs")

    units = []
    for sp in sorted(labels):
        h, j, m = labels[sp], judge[sp], manifest[sp]
        if not (h["session_id"] == j["session_id"] == m["session_id"]):
            sys.exit(f"session_id mismatch at sheet_position {sp}")
        if not (h["block_index"] == j["block_index"] == m["block_index"]):
            sys.exit(f"block_index mismatch at sheet_position {sp}")
        if m["corpus"] not in CORPORA:
            sys.exit(f"unknown corpus {m['corpus']!r} at sheet_position {sp}")
        units.append(
            {
                "sheet_position": sp,
                "corpus": m["corpus"],
                "human": parse_score(h["score"], f"labels sheet_position {sp}"),
                "judge": parse_score(j["score"], f"judge sheet_position {sp}"),
            }
        )

    if len(units) != 100:
        sys.exit(f"expected 100 joined units, got {len(units)}")
    n_by_corpus = Counter(u["corpus"] for u in units)
    if dict(n_by_corpus) != EXPECTED_N:
        sys.exit(f"corpus counts {dict(n_by_corpus)} != expected {EXPECTED_N}")
    return units


def confusion(h: np.ndarray, j: np.ndarray) -> list[list[int]]:
    return [[int(((h == a) & (j == b)).sum()) for b in SCORES] for a in SCORES]


def qwk_terms(h: np.ndarray, j: np.ndarray) -> tuple[float, float, float]:
    """Return (kappa, observed disagreement, chance-expected disagreement)."""
    n = len(h)
    observed = float(((h - j) ** 2).mean())
    ph = [float((h == a).sum()) / n for a in SCORES]
    pj = [float((j == b).sum()) / n for b in SCORES]
    expected = sum(ph[a] * pj[b] * (a - b) ** 2 for a in SCORES for b in SCORES)
    return 1.0 - observed / expected, observed, expected


def mad(h: np.ndarray, j: np.ndarray) -> float:
    return float(np.abs(h - j).mean())


def main() -> None:
    units = load_units()
    out: list[str] = []
    w = out.append

    w("Counts only. Interpretation is W1 writing.")
    w("")
    w("Phase 1 characterization — per-corpus decomposition of judge-vs-human agreement")
    w("Human = labels.csv first pass. Judge = v1-pass1. Corpus from sample-manifest.csv. Join on sheet_position.")
    w(f"Script: methodology/scripts/compute_corpus_decomp.py. Units: {len(units)}.")
    w("")

    per_corpus = {}
    for corpus in CORPORA:
        sub = [u for u in units if u["corpus"] == corpus]
        h = np.array([u["human"] for u in sub])
        j = np.array([u["judge"] for u in sub])
        n = len(sub)
        per_corpus[corpus] = (h, j)

        cm = confusion(h, j)
        exact = int((h == j).sum())
        dist = np.abs(h - j)
        misses = {d: int((dist == d).sum()) for d in (1, 2, 3)}
        kappa, observed, expected = qwk_terms(h, j)

        if round(kappa, 4) != EXPECTED_KAPPA[corpus]:
            sys.exit(
                f"{corpus}: kappa {kappa:.4f} does not reproduce committed "
                f"{EXPECTED_KAPPA[corpus]:.4f} (results/phase1-kappa.txt); stopping"
            )

        w(f"=== corpus = {corpus} (n = {n}) ===")
        w("")
        w("confusion (rows = human, cols = judge):")
        w("          judge=0  judge=1  judge=2  judge=3")
        for a in SCORES:
            w(f"human={a}  " + "  ".join(f"{cm[a][b]:7d}" for b in SCORES))
        w("")
        w(f"exact agreement: {exact} / {n} ({exact / n * 100:.1f}%)")
        w(f"MAD (all units): {mad(h, j):.4f}")
        w(f"misses by distance: 1 step = {misses[1]}, 2 steps = {misses[2]}, 3 steps = {misses[3]}")
        w(f"quadratic-weighted kappa: {kappa:.4f}  (reproduces committed {EXPECTED_KAPPA[corpus]:.4f})")
        w(f"observed disagreement, mean (h - j)^2: {observed:.4f}")
        w(f"chance-expected disagreement, sum p_h(a) p_j(b) (a - b)^2: {expected:.4f}")
        w("")

    # --- Decision quantity (single, pre-committed) ---------------------------
    w("=== decision quantity (§9 row, 2026-09-26) ===")
    w("")
    w("delta = MAD_attune - MAD_brownfield, units with human score in {0, 1}, judge v1-pass1 vs human first pass")
    subsets = {}
    for corpus in CORPORA:
        h, j = per_corpus[corpus]
        keep = (h == 0) | (h == 1)
        subsets[corpus] = (h[keep], j[keep])
        w(f"  n {corpus} (human in {{0, 1}}): {int(keep.sum())}")
    ha, ja = subsets["attune"]
    hb, jb = subsets["brownfield"]
    mad_a, mad_b = mad(ha, ja), mad(hb, jb)
    point = mad_a - mad_b

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    na, nb = len(ha), len(hb)
    boots = np.empty(N_BOOT)
    for i in range(N_BOOT):
        ia = rng.integers(0, na, na)
        ib = rng.integers(0, nb, nb)
        boots[i] = mad(ha[ia], ja[ia]) - mad(hb[ib], jb[ib])
    lo, hi = np.percentile(boots, [2.5, 97.5])

    w(f"  MAD_attune (subset):     {mad_a:.4f}")
    w(f"  MAD_brownfield (subset): {mad_b:.4f}")
    w(f"  delta point estimate:    {point:.4f}")
    w(f"  95% percentile bootstrap CI: [{lo:.4f}, {hi:.4f}]  (n_boot = {N_BOOT}, seed = {BOOTSTRAP_SEED}, resampled within each corpus)")
    w("")
    for corpus in CORPORA:
        h, _ = per_corpus[corpus]
        w(f"  n {corpus} (human in {{2, 3}}): {int(((h == 2) | (h == 3)).sum())}")
    w("")

    w("=== §9 row (verbatim) ===")
    w("")
    w(SECTION_9_ROW)
    w("")

    OUT_TXT.write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
