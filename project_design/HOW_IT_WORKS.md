# How FrictionMap works


## The signal set

Three classes of signal, all extracted by counting (no semantic interpretation). Every signal can be explained in one sentence and reproduces deterministically across runs.

**Lexical.** Re-evaluation markers in extended thinking blocks. Calibrated 13-marker lexicon: `actually`, `wait`, `hmm`, `no,`, `let me reconsider`, `on second thought`, `scratch that`, `hold on`, `reconsidering`, `i was wrong`, `let me think`, `now I'm realizing`, `however`. Hand-tagged against a 30-block sample (100% recall, 42% precision) and validated across three independent codebases.

**Behavioral.** Retry patterns and failed edits in the tool stream: rapid re-reads of the same file, edits that returned errors, edit-then-immediately-edit-again sequences.

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