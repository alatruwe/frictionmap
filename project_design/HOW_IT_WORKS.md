# How FrictionMap works


## The signal set

Three classes of signal, all extracted by counting (no semantic interpretation). Every signal can be explained in one sentence and reproduces deterministically across runs.

**Lexical.** Re-evaluation markers in extended thinking blocks. Calibrated 13-marker lexicon: `actually`, `wait`, `hmm`, `no,`, `let me reconsider`, `on second thought`, `scratch that`, `hold on`, `reconsidering`, `i was wrong`, `let me think`, `now I'm realizing`, `however`. Calibrated on a 30-block hand-tagged sample (100% recall, 42% precision; drove the `but` / `let me check` → `let me think` / `however` swap), then validated at corpus scale across attune + brownfield with a stratified hand-tagged sample (4 hits per marker per corpus, 64 hits actual after rare-marker under-sampling). The post-swap lexicon was retained unchanged; `actually` is corpus-dependent (4/4 precision on brownfield, 0/4 on attune) and kept on a recall-favoring calibration rather than dropped on the per-corpus disagreement override.

**Behavioral.** Two patterns in the tool stream contribute to the active score: rapid re-reads of the same file, and edit-then-immediately-edit-again bursts. A separate cluster of retry signals (edit failures, grep reformulations, bash retries, read-after-edit) is also detected and emitted in the report payload, but is currently parked at weight 0 — see "Currently parked signals" below.

The re-read window (`RE_READ_WINDOW = 5`) was retained after calibration. A diagnostic compared `N` ∈ {3, 5, 10, ∞ segment-bounded} on attune and brownfield by Jaccard overlap of the resulting per-file burst sets. In the bounded range, window choice is near-cosmetic: Jaccard 0.78–0.93 across `N=3 / 5 / 10` on brownfield, 0.94–1.00 on attune; the unbounded variant surfaces roughly 2× the file count and falls to 0.43–0.60 Jaccard against the bounded sets, so was rejected as too noisy. Brownfield was the discriminating corpus — attune is too calm to surface burst variance at all. The top-ranked brownfield files at `N=5` include `settings/base.py`, `oauth/tests/test_oauth.py`, and `api/common/policy/record_units.py`, known friction sites where markers are the dominant score component.

The edit churn window (`EDIT_CHURN_WINDOW = 5`) was retained after the same calibration. The diagnostic compared `N` ∈ {3, 5, 10, ∞ segment-bounded} on attune and brownfield, adding orthogonality checks against markers and re-read. Window choice is near-cosmetic in the `N=5 / N=10` range (Jaccard 0.90 on brownfield), tighter at `N=3` (0.86), and looser at `∞(seg)` (0.71 against `N=3`); per-corpus baselines at `N=5` are stable (attune 34 files / median 5 / MAD 3; brownfield 36 / 4 / 2). Edit churn surfaces a nearly-disjoint file set from markers (Jaccard ~0.10 on brownfield) — exactly what the behavioral-gating rule targets — and overlaps re-read at ~0.40, so the two behavioral signals capture different friction shapes. Live-report inspection of the `markers⁺ ∩ edit_churn ≥ 2` intersection confirmed coherent file surfacing.

**Structural.** File-intrinsic complexity (cyclomatic complexity, LOC) as a normalization input, so 2,000-line files don't dominate purely by surface area.

Equal weights were retained after cross-corpus weight calibration. The diagnostic compared the active scoring function's per-file rankings against hand-adjudication of 25 sessions stratified high/mid/low per corpus (attune N=13, brownfield N=12), with adversarial-cell kill-test reads on `7a6d0f49` (attune) and `57dd4ee3` (brownfield) read with intent to disconfirm. The adjudication rule was pre-committed before any read: a file earns the friction tag if it was edited or read in a stretch where steady progress broke; files merely mentioned or reasoned about in the broken stretch — but never touched — do not earn the tag, by design, so that any disagreement measures weighting rather than attribution semantics.

The 25 entries produced four substantive agreements (3 attune, 1 brownfield) where the rule's tagged file matched the tool's top-ranked file, and thirteen calm convergences (6 attune, 7 brownfield) where both produced empty or near-empty output. Six disagreements clustered in three modes: behavioral signals (edit churn, reread bursts) elevating files where reasoning friction is absent (1× attune, 3× brownfield, concentrated in the High bin and consistent with brownfield's denser real-source-edit profile); thinking-only friction the co-location rule cannot see by design (2× attune, 0× brownfield); and one filter-side exclusion where `IGNORE_PATTERNS` hid a rule-compliant friction file (1× attune, the documented IGNORE_PATTERNS trade behaving as designed). None of the three modes are weight-tunable — attribution-shape, definitional-limit, and filter-side respectively — so equal weights ship. One observation carries forward: behavioral-signal over-firing is more pronounced on corpora with dense real-source edits than on doc-heavy corpora, suggesting future work on reasoning-gating refinements rather than weight tuning. The thinking-only gap is recorded as an accepted trade in `TRADEOFFS.md` ("Attribution: co-location rule excludes thinking-only friction"); calibration ledgers are preserved as the durable record.

## Attribution

Signals attribute to files via a **co-location rule**: a thinking-block file mention counts toward a file's score only if that file is also touched by a tool call in the same session. This separates *focus mentions* (code being worked on) from *recall mentions* (docs being consulted). Without this rule, the top-friction files are always your README, CLAUDE.md, and other files the model references constantly but doesn't struggle with. With it, the heatmap shows the code the model actually wrestles with.

Tier 3's temporal-proximity window is fixed at `N=3` (validated against 40 boundary-sampled and 20 random-sampled hand-attributed blocks across attune and brownfield corpora). Wider windows (`N=5`, `N=10`) produce near-identical results in the regime where the algorithm's structural assumptions hold; the larger source of attribution error is structural — Tier 1 misses, Glob/Grep over-attribution, multi-target under-attribution, corpus-edge cases — not window size.

## Normalization

Lexical signals use a presence/intensity split rather than standard z-score normalization, because re-evaluation markers are sparse-positive: 66% of attributed thinking blocks contain zero markers (measured identically on two unrelated corpora). A file's marker contribution is `(fraction of attributed blocks with any markers) × (mean rate among marker-bearing blocks)`. This is documented in `TRADEOFFS.md` as a permanent shape choice, sparse-positive signals need a different tool than dense-continuous ones.

## What gets measured

- Re-evaluation marker density in attributed thinking blocks
- Retry and failed-edit behavioral patterns per file
- File-intrinsic complexity as a normalization input
- Tool-use counts (Read, Edit, Bash, Grep, Glob, Write) per file

## Currently parked signals

These signals are computed and emitted in the report payload but contribute weight 0.0 to the score, pending revisit:

- **`reasoning_to_output_ratio`** — the ratio's denominator (output chars in the same turn) is too small or zero on assistant-thinks-then-tool-uses turns, which is most turns. The ratio saturates per-file and floods the score. Needs a per-file definition rework.
- **Leakage cluster** (`edit_failures`, `grep_reformulations`, `bash_retries`, `read_after_edit`) — these detect real session-level retry patterns, but the per-file rollup does not fingerprint friction-causing files in either raw-count or per-LOC normalization, on either reference corpus. May earn a role in the per-session debugger view or be reshaped at the per-file level later.
- **`question_rate_per_100w`** — sparse-positive at ~7% of attributed thinking blocks on both reference corpora (4–5× sparser than markers had pre-reshape). A per-file orthogonality diagnostic showed a hypothetical presence/intensity migration would lift mostly attribution-noise rather than real friction sites: URL fragments, directory paths, single-attribution multi-file splits, and git-ref artifacts. On attune, every file in the hyp top-15 had `n_blocks_attributed < 3`; on brownfield, 11/15 did, and the one production file with thick evidence was already in the current top-20. May earn its weight back behind a broader question-token lexicon or once the path-extractor surfaces fewer non-file paths.
- **`tool_use_coupling`** — per-thinking-block bool ("did any tool_use fall within ±3 events?") that saturates at 97–99% pooled coupling on both reference corpora. Block-level diagnostic showed the binary collapses opposite-sign stratum effects: marker-positive thinking blocks lean *away from* investigative tools (Read/Grep/Glob; gap −0.16 / −0.15 across the two reference corpora) and *toward* bash (gap +0.13 / +0.20). The class-stratified versions — `bash_coupling_rate` and `investigative_coupling_rate` — are real v2 redefinition candidates with measured per-file spread, but validating them through full file-level analysis was deferred to keep v1 scope bounded. The `thinking_resolution_rate` aggregate (file-level fraction of coupled blocks) is still computed and exposed in the report payload, independently of the parked scoring path.
- **`block_length_words`** — per-thinking-block word count (code-stripped). The corpus baseline is healthy (attune median 71 / MAD 49; brownfield median 61 / MAD 44.5), but the per-file rollup of a length-only top-15 is dominated by attribution noise (URL fragments, bare directory paths, paths off the codebase root) and small-N evidence on both reference corpora; the few thick-evidence orthogonal candidates (e.g. CLAUDE.md at n = 9) are mostly *not* in production top-20, meaning length is surfacing files that markers + behavioral signals correctly deprioritized. Block-level Pearson r flips negative on `both_positive` blocks (−0.175 attune, −0.286 brownfield) — a denominator artifact (markers/100w is intensity, length is size) — but confirms the signal is not redundant with markers. May earn its weight back behind a cleaner path extractor, a more diverse corpus, or Phase 7 session-detail use.

## What deliberately doesn't get measured

**What the model meant or inferred.** All signals are counts in text or counts in the event stream. Trade-off chosen for defensibility, reproducibility, and sub-second runtime. LLM-based interpretation is a candidate v2 upgrade behind a `--deep` flag.

**User-correction signal.** Detecting "actually, could we…" reliably is a small NLP problem. Out of v1 scope.

**Cache token usage.** Reflects infrastructure cache hits/misses, not task difficulty.

**Sub-agent thinking.** Sub-agents invoked via the Agent tool don't currently emit thinking blocks; their friction signal is tool-behavior only.

## Methodological caveats

**Files the model struggled with but didn't externalize in thinking are under-scored.** The co-location rule means friction has to leave a trace to be measured. A model that struggles silently is a model that scores low.

**Calibration is single-tagger.** The marker lexicon was developed and validated against one developer's session corpora. Multi-corpus validation across three codebases shows the score's mode (calm / healthy / empty) generalizes; the lexicon itself is a defensible heuristic, not a validated taxonomy.

**Ambiguous file references aren't resolved.** Pronominal mentions ("that file") and same-basename collisions across directories degrade to weaker attribution. The parser records *how* each block was attributed (exact path vs basename match), so downstream analysis can filter on confidence tier if needed.

## Reading further

- `PROJECT_DESIGN.md` — product scope, the signal set in full, the attribution rule's full design.
- `TRADEOFFS.md` — decisions where a reasonable alternative existed and one was picked.
- `ASSUMPTIONS.md` — properties of the data tested before the design depended on them.
- `ECOSYSTEM.md` — where this could go beyond the retrospective view.
- `schema.md` — parser-to-report data contract.