# schema.md — Friction Map report data

Decided Monday April 20, 2026. Revised Wednesday April 22 (morning) to carry Phase 2–3 signal expansion. Bumped to **1.2** Wednesday April 22 (evening, post-2B) to make `Attribution.file_paths` a list for multi-file attribution. Bumped to **1.3** Tuesday April 28 to split `markers_per_100w` baseline shape from robust-z to presence/intensity (sparse-positive distribution; robust-z collapses).

This is the contract between the parser and the HTML report.

## Version history

- **1.0** (Mon Apr 20) — initial schema, single-file attribution, three-tier resolution.
- **1.1** (Wed Apr 22 morning) — Phase 2–3 signal expansion: temporal-proximity attribution tier, tool-behavior leakage, file complexity metrics, corpus/session baselines, per-file tool usage, cluster-count signal on multi-cluster thinking blocks, session_baselines as map.
- **1.2** (Wed Apr 22 evening) — `Attribution.file_path: string | null` → `Attribution.file_paths: string[]`. Supports thinking blocks that reason about multiple files (41% of attributed blocks on attune). Supports multi-file tool_uses at Tier 3 (Grep scope, Bash multi-file commands). Empty list replaces `null` for unattributed blocks. **Additive change in practice** — the field name changed, but consumers can uniformly treat `file_paths` as "zero or more canonical paths" at every tier.
- **1.2 (additive, Sun Apr 26)** — `Report.session_titles: Record<string, string>` added, mapping `session_id_short` (first 8 chars of session UUID) → most-recent `aiTitle` for that session. Populated from existing `aiTitle` event extraction (`_last_ai_title` in `sessions.py`). UI uses for excerpt-card display. No version bump per extensibility rules — additive only.
- **1.3** (Tue Apr 28) — `BaselineStat` becomes a discriminated union with `kind: "robust_z" | "presence_intensity"`. The `markers_per_100w` baseline switches to the presence/intensity branch; every other signal stays on robust_z. Empirical grounding: 66.1% zero rate on attune and brownfield collapses MAD to 0 under robust-z, silencing the per-file marker contribution. The new branch carries `presence_rate_corpus` and `median_intensity_among_positives` as evidence-panel context numbers (not per-file score divisors); the per-file score computes presence × intensity directly from attributed blocks. Cache and emitted JSON dispatch on the `kind` field; legacy 1.2 caches invalidate on load.

## UI shape (drives the schema)

The report renders three surfaces:

- **Treemap view (primary):** top 15 files by friction score. Rectangles sized by lines of code, colored by friction score intensity. Coverage.py posture — hide the quiet files, show the hot ones.
- **List view (secondary, tab toggle):** all files with friction > 0, sorted by score descending. Same row shape as the ranked list we mocked — filename, path, friction count, color block. Scrolls.
- **Evidence panel (right side, shared across both views):** per-file. Filename, path, tangle count, 2–3 thinking excerpts with re-evaluation markers highlighted. No score breakdown, no tool trace, no session list. Coverage.py doesn't justify itself; neither do we.

Selection is shared: click a file in the treemap or list, the evidence panel updates. Switching tabs preserves selection.

**Schema-vs-UI note.** This schema carries fields the current minimal evidence panel does not render — per-file score components, baselines, leakage events, complexity metrics, tool usage, per-excerpt attribution provenance, cluster-count signal. Those fields are here so the parser and scoring function have a stable target, and so future evidence-panel iterations aren't blocked on a schema bump. The UI is free to ignore them.

**Multi-file attribution note (1.2).** When an excerpt's `attribution.file_paths` contains multiple entries, the evidence panel should display all of them (UI decides layout — ribbon, list, or comma-separated). A future evidence-panel iteration may surface co-occurrence as its own signal; the raw data is already captured.

## Top-level

```ts
type Report = {
  meta: CodebaseMeta
  baselines: Baselines                              // corpus-level baselines
  session_baselines: Record<string, BaselineSet>    // keyed by session_id; omits sessions with <20 blocks
  files: FileFriction[]                             // all files with friction > 0, sorted desc by score
  session_titles: Record<string, string>            // session_id_short → most-recent aiTitle (1.2 additive)
}
```

Files with zero friction are omitted. The report is about friction, not a codebase inventory.

Session baselines are a map, not a list, so excerpts can resolve `session_id` → baseline by lookup. Sessions with fewer than 20 thinking blocks are omitted from the map entirely; consumers fall back to the corpus baseline when a session key is absent.

`session_titles` is keyed by the first 8 characters of the session UUID (matching `ThinkingExcerpt.session_id_short`). Sessions without an extractable `aiTitle` event are omitted from the map; consumers should guard with presence checks (`titles[short] && …`). The map is small (one short string per session) and is included so the UI can label excerpt cards with the human-readable session title without re-reading session JSONLs.

## CodebaseMeta

```ts
type CodebaseMeta = {
  name: string                   // "attune" — derived from sessions dir path
  session_count: number          // 65 (as of Apr 22 corpus)
  file_count: number             // N — files with friction > 0, not total files
  thinking_block_count: number   // 607 (as of Apr 22 corpus)
  total_event_count: number      // 9,151 including progress events; feeds the header stat
  generated_at: string           // ISO 8601 timestamp
  schema_version: string         // "1.4" — bump on breaking changes
}
```

`file_count` is the number of hot files (length of `files[]`), not total files in the codebase. Header wording should clarify this — "47 files with friction" or similar.

`total_event_count` is emitted because the Phase 1 header already displays it and the parser already counts it. Free to include; saves re-counting in the UI.

## Baselines

Corpus-level medians + MADs, emitted once at report level. Feeds per-block and per-file z-score rendering for any future evidence panel that surfaces anomaly signals.

```ts
type Baselines = {
  corpus: BaselineSet
}

type BaselineSet = {
  block_length_words:         BaselineStat
  question_rate_per_100w:     BaselineStat
  markers_per_100w:           BaselineStat
  reasoning_to_output_ratio:  BaselineStat
  tool_use_coupling_rate:     BaselineStat
  leakage_events_per_session: BaselineStat
}

type BaselineStat =
  | {
      kind: "robust_z"
      median: number
      mad: number              // median absolute deviation, not standard deviation
      n: number                // observation count
      low_confidence: boolean  // true when n < 20
    }
  | {
      kind: "presence_intensity"
      presence_rate_corpus: number              // fraction of thinking blocks with rate > 0
      median_intensity_among_positives: number  // median rate, restricted to positive blocks
      n_blocks: number                          // total blocks observed
      n_positive_blocks: number                 // blocks with rate > 0
      low_confidence: boolean                   // true when n_positive_blocks < 20
    }
```

**Median + MAD, not mean + SD** (robust_z branch). Robust to outliers. A single 5,000-word thinking block would otherwise drag the mean and distort every z-score downstream.

**Presence/intensity** (1.3) is the branch for sparse-positive signals where the median is zero on most realistic corpora — currently `markers_per_100w` and only `markers_per_100w`. `presence_rate_corpus` and `median_intensity_among_positives` are corpus-level context for a future evidence panel ("this corpus has 34% marker-bearing blocks; this file has 60%"); they are **not** divisors in the per-file score. The per-file scorer computes `presence_rate_F × mean_intensity_F` directly from the file's attributed blocks. Other signals retain the robust_z branch even when sparse — `question_rate_per_100w` is sparse-positive (~93% zero rate) but its scoring weight is zero — parked in #3 (see the parking handoffs).

**Session baselines live at the top level**, keyed by `session_id`:

```ts
session_baselines: Record<string, BaselineSet>
```

One entry per session with ≥20 thinking blocks. Consumers doing z-score math against a session baseline look up `session_baselines[excerpt.session_id]`; missing keys fall back to `baselines.corpus`.

## FileFriction

One entry per file with friction > 0. Treemap and list both consume this array.

```ts
type FileFriction = {
  path: string                      // "src/attune/storage.py" — relative to codebase root
  name: string                      // "storage.py" — basename, duplicated for UI convenience
  directory: string                 // "src/attune/" — parent dir, duplicated for UI convenience

  // headline numbers
  score: number                     // composite friction score, 0+
  tangle_count: number              // discrete count for display ("47 tangles")
  session_count: number             // sessions where this file appeared with friction
  loc: number                       // lines of code — for treemap sizing
  thinking_resolution_rate: number  // fraction of file's attributed blocks that resolved to a tool_use within N events

  // signal breakdown (Phase 3 scoring function output)
  score_components: ScoreComponents

  // file-intrinsic complexity (Phase 2 complexity metrics)
  complexity: FileComplexity

  // behavioral leakage events, aggregated per file (Phase 2 leakage extraction)
  leakage: LeakageCounts

  // tool usage counts by type, aggregated per file
  tool_usage: ToolUsage

  excerpts: ThinkingExcerpt[]       // up to 5 per file, most-frictional first
}
```

**`score` vs `tangle_count`.** Score is the sorting key and the color-intensity input. Tangle_count is what the UI displays ("47 tangles"). They're related but not identical — score may be normalized by file size or complexity, tangle_count is raw. Display the meaningful number, sort by the comparable number.

**`name` and `directory` duplication.** Derivable from `path`, included for UI simplicity. Bytes are negligible at realistic scale.

**`thinking_resolution_rate`.** File-level aggregate of per-block `tool_use_coupling`. High rate means the file is actively being worked on (Claude thinks, then acts); low rate means the file is being reasoned about in the abstract without corresponding action. Low-rate files with high marker density are a distinct shape of friction — confusion that doesn't resolve into an action.

**Multi-file attribution and per-file scoring (1.2).** A thinking excerpt may attribute to multiple files via `attribution.file_paths`. The scoring function (Phase 3) decides how a multi-file block distributes friction across its files — candidates include equal share (`1/N` per file), full contribution per file (accepting cross-session double-counting), or decay (first file full weight, subsequent downweighted). The per-file `ScoreComponents.multi_file_weight` surfaces the decision for transparency. 2B corpus measurement: 46.1% of blocks attribute to 1 file, 15.2% to 2 files, 26.0% to 3+ files, 12.7% unattributed.

## ScoreComponents

The scoring function combines signals with tuned weights (Phase 5). The report precomputes components so consumers — current UI, future UI, debug tools — don't re-implement the weighting.

```ts
type ScoreComponents = {
  // primary signal
  markers: SignalValue              // re-evaluation markers per 100w

  // structural signals — all parked at weight=0 in v1 (computed + emitted, not scored)
  block_length_words:     SignalValue
  question_rate_per_100w: SignalValue
  tool_use_coupling:      SignalValue

  // behavioral signals
  reread_bursts:             SignalValue
  edit_churn:                SignalValue
  reasoning_to_output_ratio: SignalValue

  // per-file normalization axes
  normalized_by_loc: number                  // score / loc
  normalized_by_complexity: number | null    // score / cyclomatic; null if complexity.cyclomatic is null

  // multi-file attribution handling (1.2)
  multi_file_weight: number                  // weight applied to multi-file-attributed contributions for this file; 1.0 if all contributions were single-file
}

type SignalValue = {
  raw: number          // raw count or rate
  z_score: number      // robust z: (raw - corpus.median) / (1.4826 * corpus.mad)
  weight: number       // weight used in composite score; sum of all weights may not equal 1
  contribution: number // raw * weight — how much this signal contributed to `score`
}
```

**Why `contribution` is precomputed.** A future evidence panel will want to say "markers contributed 0.32 of storage.py's 0.87 score." That's `raw * weight`. Computing it in the UI is fine, but precomputing avoids mismatches between UI math and scoring-function math when weights get retuned in Phase 5.

**Why the structural set is trimmed.** Per IMPLEMENTATION.md Phase 3: root TTR, avg sentence length, length trend were dropped ("low signal value on Claude text or redundant with block length"). Schema matches the trimmed set.

## FileComplexity

Two-tier complexity per IMPLEMENTATION.md Phase 2. Tier 1 language-agnostic, Tier 2 Python-only.

```ts
type FileComplexity = {
  // Tier 1 — language-agnostic
  loc: number                    // duplicated at FileFriction top level for UI convenience
  loc_no_blanks_comments: number
  char_count: number
  function_count: number         // regex-based, per language
  class_count: number

  // Tier 2 — Python only, null for non-Python
  cyclomatic: CyclomaticMetrics | null
  halstead_volume: number | null
}

type CyclomaticMetrics = {
  max: number              // worst single function
  mean: number
  sum: number
}
```

**Missing-file behavior.** Files that no longer exist on disk get `complexity: { loc: 0, loc_no_blanks_comments: 0, char_count: 0, function_count: 0, class_count: 0, cyclomatic: null, halstead_volume: null }` and the scoring function falls back to per-LOC normalization using the last observed `tool_result` content length.

## LeakageCounts

Per-file aggregated leakage events from Phase 2 extraction. Raw event list omitted from v1 schema — the count is enough for scoring, and the evidence panel doesn't render individual leakage events in the current design.

```ts
type LeakageCounts = {
  edit_failures: number         // Edit returned error or immediate re-Read followed
  grep_reformulations: number   // consecutive Greps on same scope, pattern changed
  bash_retries: number          // consecutive Bash, shared prefix, first returned non-zero
  read_after_edit: number       // Read within N events of an Edit to same file
  total: number                 // sum; duplicated for UI convenience
}
```

**Weight note.** Per IMPLEMENTATION.md, `read_after_edit` is "exploratory signal — can be legitimate verification, not just uncertainty. Weighted low in scoring." Schema carries the count; weighting is a scoring-function concern.

## ToolUsage

Per-file counts of tool calls by type. Cheap to compute during parse, useful context for any consumer wanting to describe how Claude interacted with the file.

```ts
type ToolUsage = {
  read:  number
  edit:  number
  write: number
  bash:  number
  grep:  number
  glob:  number
}
```

Not a scored signal in v1. Included because it's effectively free during parsing and gives a future evidence panel something to describe "how Claude worked with this file" (e.g. "7 reads, 3 edits, 1 grep").

**Full tool-call trace is not included.** A file's individual tool events (with timestamps, commands, results) would enable a rendered timeline in a future evidence panel, but the parser currently emits leakage counts and discards the underlying events. Retrofitting the trace requires re-architecting parser retention. Deferred — if a future UI needs a trace, add `tool_events: ToolEvent[]` per file at that point.

## ThinkingExcerpt

Hero-shot data. Windowed thinking text around marker clusters.

```ts
type ThinkingExcerpt = {
  session_id: string           // "a70658da-6873-408d-999b-d4136d75de24"
  session_id_short: string     // "a70658da" — first 8 chars, for display
  block_index: number          // 14 — position of this thinking block within session
  block_total: number          // 22 — total thinking blocks in session
  block_length_words: number   // 1,240 — full block length

  cluster_index: number        // 0-based index of this cluster within the block
  cluster_count: number        // total clusters in the block (≥ 1)

  text: string                 // the windowed excerpt
  highlights: Highlight[]      // marker spans within `text`

  attribution: Attribution     // how this excerpt was attributed to its file(s)
  block_signals: BlockSignals  // per-block signal values for z-score rendering

  agent_sourced: boolean       // true if this block came from an agent_progress walker (1.2 addition; mirrors Block.agent_sourced)
}
```

Text is pre-windowed by the parser — the UI doesn't re-window. Window size is a parser parameter, decided at build time (see open questions).

**Embed text, don't reference source JSONL.** The report is self-contained. Referencing external files breaks that. Size cost is negligible.

**One excerpt per marker cluster, not per thinking block.** A 1,240-word block with three distinct re-evaluation moments produces three excerpts, each windowed around its cluster. Multiple excerpts from the same block share `session_id`, `block_index`, `block_length_words`, `block_signals`, and `cluster_count`, but differ in `cluster_index`, `text`, and `highlights`.

**Cluster count is itself a signal.** A block with `cluster_count: 3` is a block where Claude re-evaluated three separate times before resolving — a different shape of friction than a single long cluster. The scoring function is free to weight multi-cluster blocks above single-cluster blocks of equivalent total marker count. The duplication of `block_signals` across sibling excerpts is not waste; it's the explicit statement "this block contained N clusters," queryable from any consumer.

**`agent_sourced` (1.2).** True for excerpts from thinking blocks emitted by the parser's `agent_progress` walker (i.e. sub-agent reasoning). Empirically in the attune corpus this field is always false — sub-agents don't emit thinking blocks. Included for forward compatibility: if a future corpus carries nested thinking, the evidence panel can tag those excerpts as sub-agent reasoning.

## Attribution

Per-excerpt record of how the excerpt was attributed to its file(s). **Changed in 1.2: `file_paths: list[str]` replaces 1.1's `file_path: string | null`.**

```ts
type Attribution = {
  tier: "exact_path" | "unique_basename" | "temporal_proximity"
  confidence: "high" | "medium" | "low"
  // exact_path       → high
  // unique_basename  → medium
  // temporal_proximity → low

  file_paths: string[]  // 1.2: zero-or-more canonical paths. Empty list means the block
                        // was observed but could not be attributed to any session-touched file.

  // populated only when tier === "temporal_proximity"
  proximity_distance:  number | null          // event-count distance to attributed tool call
  proximity_direction: "before" | "after" | null
}
```

**Multi-file semantics (1.2).** Every tier can produce multiple paths:

- `exact_path` with multiple paths: the thinking text contains path-fragment suffix matches (suffixes containing a `/`, e.g. `core/storage.py`) for multiple session-touched files.
- `unique_basename` with multiple paths: the thinking text contains multiple bare filenames that each uniquely resolve to one session file. Tier 1 matches only path-*fragment* suffixes (those containing a `/`), so a bare filename like `storage.py` falls through to this tier, where it attributes iff its basename is unique in the session. This tier fires routinely — 33% of attributed blocks on attune, 5% on brownfield.
- `temporal_proximity` with multiple paths: the nearest tool_use within N events touches multiple files (Grep scope resolving to several matched files, or a Bash command mentioning multiple files). The block attributes to all of them.

**Three tiers, not four.** IMPLEMENTATION.md Phase 2 defines four resolution tiers: exact path, unique basename, ambiguous basename (falls through), no filename (falls through). Tiers 3 and 4 both resolve via temporal proximity, so the schema collapses them into a single `"temporal_proximity"` label. Signal over verbosity — a consumer wanting to distinguish "had a filename but ambiguous" from "no filename at all" is operating below the scoring function's resolution.

**Why this is in the schema even though the current evidence panel doesn't show it.** Without it, consumers can't tell a strong attribution (exact path match) from a weak one (temporal proximity with 3-event gap). A future evidence panel will want to muffle or flag low-confidence excerpts. Including it now avoids re-parsing later.

## BlockSignals

Per-block values that the scoring function consumed for this excerpt. Precomputed so z-score rendering doesn't require reaching back to raw event data.

```ts
type BlockSignals = {
  length_words:           number
  length_chars:           number
  question_rate_per_100w: number
  marker_count:           number
  markers_per_100w:       number
  tool_use_coupling:      boolean    // did this block resolve to a tool_use within N events?
}
```

All fields are raw values. Z-scores are computed in UI as `(value − baseline.median) / (1.4826 * baseline.mad)` against either corpus or session baseline. Keeping z-scores out of the excerpt avoids duplication with baselines and lets the UI choose which baseline to render against.

## Highlight

A marker span within an excerpt's `text`.

```ts
type Highlight = {
  start: number     // char offset into excerpt.text
  end: number       // char offset, exclusive
  marker: string    // the matched marker, e.g. "wait", "actually"
}
```

Example (the storage.py excerpt from the mockup):

```json
{
  "text": "…so the migration runs before the schema check. Wait, that can't be right — storage.py calls ensure_schema() inside __init__, so by the time migrations.py imports it the schema already exists. Actually, let me check the import order again…",
  "highlights": [
    { "start": 49, "end": 53, "marker": "wait" },
    { "start": 188, "end": 196, "marker": "actually" },
    { "start": 198, "end": 210, "marker": "let me check" }
  ]
}
```

UI walks `text`, applies spans, wraps each in `<span class="marker">`. No regex in the UI — detection is a parser concern.

## Size sanity check

New fields roughly double per-file JSON size vs. 1.0 estimates. Revised:

- **attune-scale (47 hot files, ~3 excerpts each):** ≈ 220 KB JSON. Well under 1 MB total report.
- **500-file codebase, 80 hot files:** ≈ 400 KB JSON. Fine.
- **5,000+ hot files or 50+ excerpts/file:** would start to matter. Not in play for v1.

Corpus baselines add ~500 bytes. Session baselines scale with session count — at 73 sessions, ~36 KB if all had ≥20 blocks; realistically ~15–20 KB after the confidence filter. Negligible.

**1.2 size impact:** `file_paths: list[str]` adds marginal bytes per excerpt (most excerpts have 1 path, some have 2–3). Total report size impact: <5%. Negligible.

`session_titles` (Apr 26 additive) adds ~50 bytes per session (one short string per UUID prefix). At 66 sessions, ~3 KB total. Negligible.

## Extensibility rules

Additive changes (new fields) don't bump `schema_version`. UI ignores unknown fields.

Renames or removals bump `schema_version`. 1.1 → 1.2 is a rename (`file_path` → `file_paths`) + type change (nullable string → list).

Known future additions (not in v1):
- Per-file raw tool-event trace (`tool_events: ToolEvent[]`) — enables rendered timelines in the evidence panel. Requires parser retention changes.
- Per-file leakage event list (`leakage.events: LeakageEvent[]`) — enables "here's the Bash retry that tangled storage.py" style rendering.
- Per-file session list (`sessions: SessionRef[]`) — enables drilling from file into session-level evidence.
- New marker categories — `Highlight.marker` is already a string, no schema change needed, UI can color-map.
- Folder-level aggregation — top-level `folders[]` array. Not needed as long as top-N + list covers the at-a-glance case.
- Co-occurrence signal — derived from `Attribution.file_paths` multi-file entries. Per ECOSYSTEM.md, file co-occurrence within attribution is a measurable structural signal (41% of attributed blocks on attune are multi-file). A future schema version may surface co-occurrence as a first-class per-file field.

## Decided parameters

- **Top-N for treemap: 15.** Starting point for readability. Reassess if the mock feels sparse or crowded on real data.
- **Max excerpts per file: 5.** Most-frictional first. UI indicates if capped ("showing 5 of 12 moments").
- **Schema `files[]` includes all files with score > 0.** Top-N slicing is a UI concern, not a data concern. Means the threshold can be retuned without re-running the parser.
- **Baseline confidence threshold: n < 20.** Matches IMPLEMENTATION.md Phase 3. Below this, a baseline is flagged `low_confidence: true` and omitted from `session_baselines`.
- **Temporal-proximity default N: 3 events.** Tunable in Phase 5 per IMPLEMENTATION.md "Temporal-proximity N tuning" task. Symmetric window (before/after). On ties, attribute to first tool_use, not all.
- **Multi-file attribution uniform across tiers (1.2).** Every tier produces `file_paths: string[]`, including Tier 1 when thinking text mentions multiple distinct paths and Tier 3 when the nearest tool_use touches multiple files. Scoring function (Phase 3) decides per-file weighting.

## Open questions (decide at parser build time, not now)

1. **Excerpt window size.** `±N words` or `±N chars` around marker clusters. Needs visual check on real data — too small loses context, too large bleeds into adjacent moments. 2B uses ±50 words as a working default; Phase 4/5 revisits with visual check on real excerpts.
2. **Multi-cluster block presentation.** The schema makes cluster structure explicit via `cluster_index` / `cluster_count`. UI presentation is still open: group sibling excerpts under a shared block header, inline them, or treat each independently. Decide when the UI has real multi-cluster data.
3. **Multi-file excerpt presentation.** New in 1.2: when `attribution.file_paths` has >1 entry, how does the UI display it? Ribbon of file tags, comma-separated list, primary-plus-others? Deferred to Phase 4 UI work.

Neither open question blocks parser or UI work.

## Empirical observations from 2B (Wed Apr 22 evening)

These are properties of the attune corpus, not schema contracts. Captured here for UI designers and Phase 3 scoring:

- **Attribution tier distribution (post-C2-fix, May 29):** Tier 1 is gated to path-*fragment* suffixes (must contain a `/`); bare basenames resolve at Tier 2. attune (601 blocks): 12% exact_path, 33% unique_basename, 55% temporal_proximity. brownfield (466 blocks): 12% exact_path, 5% unique_basename, 84% temporal_proximity. _Pre-fix, the buggy Tier 1 matched bare basenames too and read 59/0/41 on attune (the "61/0/39" recorded here before the fix), 34/0/66 on brownfield — `unique_basename` could never fire because Tier 1 pre-empted its uniqueness guard. The original T1.1 target of ~46% lexical match no longer applies._
- **Attribution cardinality:** 12.7% unattributed (empty list), 46.1% one file, 15.2% two files, 26.0% three-plus. Multi-file attribution is real; scoring must handle it.
- **Agent-sourced work:** walker emits 75 tool_use, 75 tool_result, 6 text blocks corpus-wide — zero thinking blocks. `ThinkingExcerpt.agent_sourced` is always false on this corpus.
- **Cluster counts:** 10.7% of marker-bearing blocks are multi-cluster. Distribution healthy; cluster-gap-N tuning waits for Phase 3's production marker regex.
- **Compact boundaries:** 9 boundaries in the 65-session subset. Window-clip count on real parse: 1. Defensive rule is correct; rarely exercised on attune.

## Handoff status

Schema 1.4 stable. `BaselineStat` discriminated union ships in Phase 5; `markers_per_100w` is the sole signal on the presence/intensity branch.

1.3 → 1.4 changes the source of the top-level `FileFriction.score` field: it is now the raw weighted z-sum (`score_pre_normalization`), not `score_pre / max(loc, 1)`. The LOC-normalized value remains available at `score_components.normalized_by_loc` as a future secondary lens. Driver: the May 26–28 score-axis diagnostic showed LOC normalization produced an empty-state UI on the attune corpus and mis-ranked brownfield top files; raw z-sum cleared both failure modes. See `~/score_axis_findings.md`.

If a real parser or UI implementation decision forces another structural change, bump `schema_version` to 1.5 and note the change here.
