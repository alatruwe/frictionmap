# How FrictionMap works


## The signal set

Three classes of signal, all extracted by counting (no semantic interpretation). Every signal can be explained in one sentence and reproduces deterministically across runs.

**Lexical.** Re-evaluation markers in extended thinking blocks. Calibrated 13-marker lexicon: `actually`, `wait`, `hmm`, `no,`, `let me reconsider`, `on second thought`, `scratch that`, `hold on`, `reconsidering`, `i was wrong`, `let me think`, `now I'm realizing`, `however`. Hand-tagged against a 30-block sample (100% recall, 42% precision) and validated across three independent codebases.

**Behavioral.** Two patterns in the tool stream contribute to the active score: rapid re-reads of the same file, and edit-then-immediately-edit-again bursts. A separate cluster of retry signals (edit failures, grep reformulations, bash retries, read-after-edit) is also detected and emitted in the report payload, but is currently parked at weight 0 — see "Currently parked signals" below.

**Structural.** File-intrinsic complexity (cyclomatic complexity, LOC) as a normalization input, so 2,000-line files don't dominate purely by surface area.

## Attribution

Signals attribute to files via a **co-location rule**: a thinking-block file mention counts toward a file's score only if that file is also touched by a tool call in the same session. This separates *focus mentions* (code being worked on) from *recall mentions* (docs being consulted). Without this rule, the top-friction files are always your README, CLAUDE.md, and other files the model references constantly but doesn't struggle with. With it, the heatmap shows the code the model actually wrestles with.

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