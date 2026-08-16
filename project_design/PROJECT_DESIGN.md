# Claude Code Friction Map — Project Design

Product design, scope, mechanism, and timeline. Separate from PROJECT_INSTRUCTIONS.md, which is about how Claude and Adeline work together on it.

> **Status note (added after the fact).** Milestone 2 — the debugger — was cut on May 30,
> 2026, after a practical utility evaluation. Phase 5b shipped; nothing is sequenced after
> it in v1. Future work is the v2 validation study, tracked separately.
>
> Everything below is preserved as the design record as written, including the Milestone 2
> specs and the ordering rationale. Read the milestone sequencing as history, not as the
> current plan.

## The product

A CLI tool that parses Claude Code session logs (from `~/.claude/projects/` or a user-supplied directory) and produces friction analysis at two scopes — corpus-wide (the friction map) and per-session (the debugger).

Three product surfaces ship in three milestones:

1. **Friction map (Milestone 1)** — `ai-friction-map scan` produces a self-contained interactive HTML report scoring every file in a codebase by how much friction Claude Code experienced working with it, across all historical sessions. Plus `ai-friction-map session <id>` produces a terminal summary of a specific session for quick diagnostic readout.
2. **Debugger (Milestone 2)** — `ai-friction-map session <id>` gains an HTML output (`session-<id>.html`) that surfaces a turn-ordered timeline of one session: user prompts as anchors, Claude's responses (thinking blocks with marker highlighting, tool calls, text) rendered inline, friction signals visible where they fired. Different schema slice from the friction map (Turn structure, ordered blocks, timestamps); different design problem; different product surface.
3. **Skill (Milestone 3)** — Claude Code skill `/friction` with three subcommands wrapping both views. `/friction scan`, `/friction active`, `/friction session`. The session subcommand returns terminal summary inline in chat plus a path to the debugger HTML.

Friction map and debugger are both powered by the same parser. They differ in what they surface: the map answers "where in the codebase does Claude get tangled?" by aggregating across sessions; the debugger answers "what happened in this session, turn by turn?" by rendering one session's events in time order.

**Friction map output (Milestone 1):** one `report.html` file. Single-page app with data embedded as JSON. No backend. Opens in any browser. Shareable by email, Gist, or Slack. Pattern matches `coverage.py`, `pytest-html`, `plotly --include-plotlyjs=inline`. Plus 5–15 lines of formatted terminal output for `session <id>` — session metadata, top friction files for that session, marker counts, leakage counts. Sub-second.

**Debugger output (Milestone 2):** `session-<id>.html` — same self-contained-HTML pattern as the friction map. Renders the session as a timeline plus reading view: per-turn thinking blocks, tool calls, optional text output, all in order. Files-touched panel acts as a filter. Schema bumps (Turn structure, ordered blocks with timestamps, user prompts surfaced) to support the view.

**Skill output (Milestone 3):** chat-rendered terminal summary for `session <id>`, plus link to `session-<id>.html` for deeper inspection. `/friction scan` opens the corpus map.

**Interface:**
- Primary CLI: `ai-friction-map scan` (Milestone 1) — writes `report.html` to CWD.
- Subcommand: `ai-friction-map active-sessions` (list recent sessions, Milestone 1), `ai-friction-map session <id>` (terminal summary at Milestone 1; adds `session-<id>.html` at Milestone 2).
- Claude Code skill `/friction` with three subcommands (Milestone 3).

**Not in scope (any milestone):** web server, upload UI, multi-user, live daemon, IDE integration beyond the skill, refactor recommendations, continuous inline coaching. Those are post-Milestone-3 territory.

## The core mechanism

Claude Code writes rich JSONL session data to `~/.claude/projects/<project>/*.jsonl`. Each line is one event. Events include tool calls (Read, Edit, Bash, Grep, Glob, Write, and others) with structured file paths and/or command strings, token usage, and **extended thinking blocks** when enabled.

**Validated from Monday T1 tests against full corpus of 73 attune sessions (re-measured against April 22 corpus of 65 sessions / 8,481 events):**
- 99% of sessions contain thinking blocks
- 636 thinking blocks in Apr 20 corpus, 607 in Apr 22 corpus — 45.9% mention at least one file by raw-lexical match
- Full-corpus parse completes in 0.307s at 2A (1.921s through full 2B pipeline) — well inside 3s budget
- JSONL is streaming-appended during active sessions (live mode viable)
- Tool distribution: Bash 31.7%, Read 20.7%, Edit 20.5%, Grep 7.2%, Write 3.9%, Glob 2.6% — these six cover ~87% of all tool use
- Bash tool_use events include both `input.command` (raw command string) and `input.description` (Claude's own summary of intent)
- **Agent sub-task work is recoverable via `progress` events with `data.type: "agent_progress"`** — the nested `tool_use` blocks live inside `data.message.message.content[]` and are extracted by the parser's `agent_progress` walker. Sub-agent tool-behavior (reads, edits, greps, bashes) participates in attribution and leakage normally.
- **`system/compact_boundary` events mark context-compaction points** where the model lost prior context. All window-based detectors (temporal proximity, re-read bursts, edit churn, leakage patterns) treat boundaries as hard stops via the `window_events` helper.

### Friction score — the signal set

The v1 scoring function ranks on three signals: re-evaluation markers (lexical), re-read bursts, and edit churn (behavioral). Structural signals (block length, question rate, tool-use coupling) and the leakage cluster are still computed and emitted in the report payload, but are parked at weight=0 — corpus-level diagnostics didn't bear them out as per-file friction signal at v1 (see TRADEOFFS.md → "Parked structural signals"). Every signal is per-file attributed using the co-location rule (see §Attribution below).

**Primary signal — re-evaluation markers in thinking blocks:**
Lexical markers detected inside thinking blocks, code-fence-stripped before matching. Calibrated 13-marker lexicon (post-Phase-3b):

`actually`, `wait`, `hmm`, `no,`, `let me reconsider`, `on second thought`, `scratch that`, `hold on`, `reconsidering`, `i was wrong`, `let me think`, `now I'm realizing`, `however`

(Initial lexicon swapped two markers in Phase 3b: dropped `but` and `let me check` for low precision, added `let me think` and `however`. Phase 5 lexicon validation (#4) confirmed the post-swap lexicon at corpus scale.)

**Per-file aggregation uses presence/intensity split, not robust z-score.** File-level marker contribution = (fraction of attributed blocks containing any markers) × (mean `markers_per_100w` among marker-bearing blocks). Decided after the marker baseline reshape design session (April 27, 2026); see TRADEOFFS.md for the rationale and rejected alternatives. The shape: `markers_per_100w` is sparse-positive (66.1% zero rate corpus-wide, measured on two unrelated codebases), so the standard robust z-score normalization that other signals use collapses to division by zero. Presence/intensity split keeps both information channels — how often markers fire on a file, and how dense they are when they do — without needing a non-zero baseline spread to function.

This is the differentiator of the product. The marker-highlight view in the report is the primary surface — the place where someone reading a file's score can see the underlying evidence and judge whether the ranking is right.

**Cluster structure within blocks (schema 1.1):** markers inside a single thinking block may form one coherent cluster or multiple distant clusters. A 1,240-word block with "Wait" / "Actually" near the top and "Hmm" / "Hold on" / "Let me reconsider" 600 words later is two clusters — a different shape of friction than a single dense cluster of equivalent marker count. The parser emits one excerpt per cluster, and the scoring function weights multi-cluster blocks above single-cluster blocks of equivalent total marker density.

**Structural signals per thinking block** (adapted from Attune's structural-signals review):

*v1 status: parked.* All three are computed and emitted at weight=0 — the per-file rollup hypothesis didn't hold at v1 (baselines healthy; the failure is downstream at per-file attribution). Parked, not patched; redefinition candidates carry to v2. See the parking handoffs (`question_rate_per_100w_parking_handoff.md`, `bash_coupling_rate_parking_handoff.md`, `block_length_words_parking_handoff.md`).

- `block_length_chars` and `block_length_words` — long blocks concentrate where the task is hard
- `question_rate_per_100w` — self-questioning as a proxy for uncertainty; code-stripped, normalized. **Parked at weight=0 in #3 — orthogonal to markers at block level, but per-file candidates dominated by attribution-noise + small-N. See `question_rate_per_100w_parking_handoff.md`.**
- `tool_use_coupling` **(parked #3a)** — did this thinking block resolve into a tool call within N events? (inverse also informative: high-reasoning/low-action sessions are design mode)

*Dropped from the plan:* root TTR, avg sentence length, length trend. Low signal on Claude text or redundant with block length.

**Behavioral signals per file:**
- **Re-read bursts** — same file read multiple times within a short turn window (window TBD by T2.2). Raw re-read count is too noisy.
- **Edit churn** — file edited, then re-edited within a small turn window in the same session.
- **Reasoning-to-output ratio** — total thinking chars per turn vs. final-output chars. High ratio = heavy deliberation for small output = hard turn. Novel to thinking-block-bearing data; no Attune analog.

**Tool-behavior leakage signals per file (schema 1.1):**
- **Edit failures** — Edit tool_use where tool_result contains error text or an immediate re-Read of the same file followed.
- **Grep reformulations** — consecutive Greps on the same scope where the pattern changed (narrowing or broadening after failure).
- **Bash retries** — consecutive Bash calls with shared prefix where the first returned non-zero exit.
- **Read-after-Edit** — Read of a file within N events of an Edit to that file. Exploratory signal — can be legitimate verification. Weighted low.

All pattern-based on structured tool inputs and results. No NLP. Counting, not interpretation.

**Session-level signals** (multiplier on per-file scores):
- **Session intensity** — Bash count + TodoWrite count + ExitPlanMode count. Captures activity Bash doesn't attribute cleanly at file level.
- **Top-session status** — is this one of the heaviest sessions in the corpus? Heavy sessions likely indicate focused implementation work where friction patterns are most informative.

**Baselines (schema 1.1, normalization shape extended in 1.3):** corpus-level and session-level medians + MADs (not mean/SD) for continuous-around-a-center signals like `block_length_words` and `reasoning_to_output_ratio`. Per-block z-scores computed as `(value − median) / (1.4826 * MAD)`. Transforms absolute-state signals into change-detection signals — a block that's long compared to the session baseline carries different information than a block that's long compared to the corpus. Session baselines with <20 blocks are omitted (low-confidence flag).

Sparse-positive signals (zero-mode with positive tail) use a different normalization: presence/intensity split at the file level, not block-level z-score. Currently applies to `markers_per_100w`. The schema's `BaselineStat.kind` discriminator names which method runs per signal. See TRADEOFFS.md "Normalization: presence/intensity split for sparse-positive signals" for the design rationale.

**Dropped or punted:**
- Cache creation tokens — dropped. Infrastructure-level, not task-level.
- User corrections following a file touch — punted to v2. Regex-based detection too lossy.
- Temporal signals (inter-message gaps, active duration) — not applicable to thinking-block streams; no idle-gap analog.

**Normalization:** per-file scores divided by file size or LOC to avoid "big file = hot" artifacts. Second axis: divided by cyclomatic complexity for Python files (file-intrinsic difficulty). The report renders both axes.

### Attribution — the Option A co-location rule

A thinking-block file mention counts toward a file's friction score **only if that file is also touched by a tool call within the same session**. This filters out recall mentions (Claude referencing documentation it read for context) from focus mentions (Claude actively working on a file).

Why this matters: the top-15 files mentioned in thinking blocks across the corpus are dominated by documentation (DECISIONS.md, IMPLEMENTATION.md, DECISIONS_ARCHIVE.md, NOTES.md, CLAUDE.md). These show up because Claude consults them constantly, not because it struggles with them. Without co-location filtering, the heatmap would show "your docs are the gnarliest code," which is uninformative. With it, the heatmap shows which code files Claude wrestles with.

**Tiered attribution (schema 1.2):** the parser records *how* each block was attributed, not just which files it resolved to. Three tiers, all live in practice:

- `exact_path` (high confidence) — thinking text contains a full path or a path-*fragment* suffix (one containing a `/`, e.g. `core/storage.py`) of a session-touched file. Attribution may point to multiple files if the thinking text names multiple distinct paths.
- `unique_basename` (medium) — thinking text names a bare filename (no `/`) that resolves to exactly one session-touched file. Bare basenames are deliberately *not* matched at Tier 1 — doing so over-claimed every same-basename file (the C2 bug) — so they fall through to this tier and attribute only when the basename is unique in the session. Fires routinely (33% of attributed blocks on attune, 5% on brownfield).
- `temporal_proximity` (low) — no filename match; block attributed to the files touched by the nearest tool call within N events (default N=3). Multi-file: if the nearest tool call touches N files, the block attributes to all N. Windows do not cross compact boundaries.

**Multi-file attribution (schema 1.2):** `Attribution.file_paths` is a list, not a scalar. A thinking block may attribute to zero files (12.7% of the attune corpus — genuine unattributed), one file (46.1%), or multiple files (41.2%). Multi-file attribution can come from two shapes: (a) multiple distinct path mentions at Tier 1, or (b) a multi-file-touching tool call at Tier 3. Both shapes are treated uniformly by the attribution layer; scoring weight across multiple files is a Phase 3 decision.

Ambiguous basenames (multiple session files sharing a basename) fall through to temporal proximity rather than being resolved. Counting, not interpretation.

### File path extraction per tool

Different tools expose file paths differently. The parser extracts accordingly:

| Tool | Extraction method | Confidence |
|------|-------------------|-----------|
| Read, Edit, Write | `input.file_path` directly | High |
| Grep | `input.path` for scope; result enumerates matched files | High |
| Glob | `input.pattern` + `input.path`; result enumerates matches | High |
| Bash | Regex file paths from `input.command` AND `input.description` (both are structured fields; combining increases coverage) | Medium |
| Agent | Tool_use itself returns `[]`. Sub-agent's tool calls are recovered via the `agent_progress` walker, which extracts nested tool_use blocks from `progress` events and applies the same per-tool extraction to them. Sub-agent tool-behavior participates fully in attribution and leakage. | High (for tool-behavior; nested thinking empirically absent in attune corpus) |
| TodoWrite, ExitPlanMode, ToolSearch, AskUserQuestion, WebSearch, Skill, TaskOutput, TaskStop | Not file-touching; skip | N/A |

Bash extraction combines `input.command` (regex-based, catches literal paths) with `input.description` (Claude's natural-language summary of intent, which often names files). Either source matching attributes the tool call.

**On the Agent walker:** earlier drafts of this document treated Agent sub-task file attribution as a v1 limitation (opaque). 2B resolved this — sub-agent tool calls are logged to the parent session's JSONL as `progress` events with full structured `tool_use` blocks inside `data.message.message.content[]`. The walker extracts these and emits them as blocks on the progress event itself with `agent_sourced: True`. Attribution, cluster detection, and leakage treat walker-emitted blocks identically to top-level blocks. The one empirical caveat: sub-agents in the attune corpus do not emit `thinking` blocks, so Agent-sourced reasoning-level signal is absent. Agent-sourced signal is tool-behavior only.

## Performance targets

Demo responsiveness matters but isn't gating. Validated:
- **Stub parser (2A, April 20):** 0.24s for full 73-session corpus.
- **Real parser (2A, April 22):** 0.307s for 65 sessions / 8,481 events.
- **Full 2B pipeline (April 22):** 1.921s (parser + resolve + attribution + clusters + leakage).

Targets:
- **Corpus scan (Milestone 1):** well under 3-second target. Silent execution, one status line at end: `Parsed N sessions across M files. Report: report.html`.
- **Session terminal summary (Milestone 1):** sub-second, imperceptible. Single session ≈ 3 milliseconds at 2A; similar order of magnitude through 2B.
- **Debugger HTML (Milestone 2):** sub-second for the data work; HTML assembly adds a small constant. The debugger renders one session's events in order, which is at most a few thousand events; not a performance concern.
- **Scale headroom:** 1,000 sessions projects to comfortably under 30 seconds through full pipeline. No optimization needed for v1.
- **Caching unnecessary:** full re-parse is cheap. Don't build incremental parsing logic.

## Scale and known limits

Documented in README under "Known limits," not engineered around for v1:

- **Session count:** linear and fast. 65–73 attune-scale fine; 1,000+ fine. No specific ceiling tested.
- **Session size:** individual JSONL files can be large for heavy debug sessions. Streaming parse handles this — do not load full files into memory.
- **Codebase file count:** HTML file-tree breaks at 10,000+ files. Attune-scale (100–200 files) fine. Large monorepos need directory grouping + friction-score filtering — v2.
- **Active session write latency:** Claude Code appends to JSONL during sessions. Buffering may delay events by seconds. Single-session output reflects events at last flush, not the literal last turn. Re-running the command picks up new events.
- **Sub-agent thinking absence:** in the attune corpus, sub-agents invoked via the Agent tool do not emit `thinking` blocks. Sub-agent friction signal is tool-behavior only (reads, edits, bashes). If future corpora carry nested thinking, the walker already emits it and the rest of the pipeline consumes it unchanged.

**Architectural rule, applies from day one:** parser is streaming, line-by-line, accumulating aggregates only. Do not hold all events in memory.

## Timeline and parallelization

**Three milestones on a self-imposed timeline. No external deadline; ship each when ready.**

*(Milestone 2 was later cut — see the status note at the top of this file. The sequencing
below is the plan as it stood, kept as a record.)*

- **Milestone 1 — Friction map.** CLI `ai-friction-map scan` produces an interactive HTML report of corpus-wide friction. CLI `ai-friction-map session <id>` produces a terminal summary for a specific session. Plus `active-sessions` for discovery. Shareable HTML, no backend. Original target was Sunday April 26; that target was self-imposed and is non-binding.
- **Milestone 2 — Debugger.** CLI `ai-friction-map session <id>` adds an HTML output (`session-<id>.html`) with turn-ordered timeline, marker-highlighted thinking-block reading view, files-touched filter. Schema bump (1.3) for Turn structure with user prompts and ordered blocks. Builds on Milestone 1's parser; no changes to corpus view.
- **Milestone 3 — Skill.** `/friction` Claude Code skill with three subcommands. `scan`, `active`, `session`. Wraps the existing CLI; the session subcommand returns terminal summary inline plus HTML link. Recursive demo possible (`/friction scan` analyzing this project's own sessions).

**Why this ordering.** The friction map is the project's central claim — "find friction surfaces in your codebase by aggregating across sessions." That's the wedge for any future expansion. Ship the claim first. The debugger is a strong second product surface that benefits from its own milestone with full design attention; folding it into Milestone 1 would dilute both. The skill ships last because it wraps both views — wrapping at Milestone 2 would leave the skill incomplete relative to the surfaces available.

**Parallelization plan.** The hard work parallelizes along a Claude Code division of labor. Adeline holds the architecture and scoring logic; Claude Code implements:

- **Track A (Adeline + chat review):** scoring function design, marker lexicon calibration, validation on attune data, product narrative, design judgment calls. Doesn't hand off cleanly.
- **Track B (Claude Code, handed off):** JSONL parser, structural-signals module, HTML components, Tailwind styling, terminal formatter, schema bumps, skill wrapper. Well-scoped implementation tasks with clear specs.

**Operational rule:** mornings write specs for Claude Code, afternoons run validation on what came back. Matches burst-cadence and maximizes throughput without forcing fake concurrency.

**Where parallelization actually saves time:** parser + UI skeleton run truly in parallel once the JSON schema is frozen (schema 1.2 for Milestone 1; schema 1.3 lands at Milestone 2). Claude Code can build UI components against mocked JSON data while the parser is still being tuned on real sessions.

**Where parallelization is a lie:** scoring function tuning is sequential with data validation. Polish is sequential with the data being interpretable. The marker-highlight view depends on marker detection working.

Detailed per-phase task list and time estimates in IMPLEMENTATION.md.

## Source of truth on data schema

Schema is `schema.md` 1.2, bumped Wednesday April 22 evening (post-2B: `Attribution.file_path: str | None` → `Attribution.file_paths: list[str]`). Summary:

Event shape (JSONL, one per line), confirmed from full corpus scan April 20 plus 2A/2B checkpoints:
- Top-level keys: `type`, `timestamp`, `sessionId`, `parentUuid`, `isSidechain`, `uuid`, `userType`, `entrypoint`, `cwd`, `gitBranch`, `version`, `requestId`, `message`
- `type` values: `assistant`, `user`, `file-history-snapshot`, `queue-operation`, `attachment`, `pr-link`, `ai-title`, `last-prompt`, `progress`, `system`
- `system` events carry a `subtype` field; `subtype: "compact_boundary"` marks context-compaction points
- `progress` events with `data.type: "agent_progress"` carry nested assistant messages at `data.message.message.content[]` containing full tool_use / thinking / text / tool_result blocks from sub-agent invocations
- `message.content[]` for assistant events: array of blocks with `type` in `text`, `thinking`, `tool_use`, `tool_result`
- `tool_use` for Read/Edit/Write: has `name`, `input.file_path`, `caller.type`
- `tool_use` for Bash: has `input.command` (literal string) and `input.description` (Claude's own summary)
- `tool_use` for Grep/Glob: has `input.path` and/or `input.pattern`
- `thinking`: has `thinking` string (text content, sometimes long, may contain code fences)
- `tool_result`: has `tool_use_id` matching the originating `tool_use.id`, `content` (string or structured blocks with file content)
- `message.usage`: `input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `output_tokens`, `service_tier`, `inference_geo`

Project directory naming: `-Users-<user>-Projects-<n>` (full absolute path with `/` → `-`). Not `attune/` as a bare name.

Report output shape: `Report` → `CodebaseMeta` + `Baselines` + `session_baselines` (map) + `FileFriction[]`. Each `FileFriction` has `ScoreComponents`, `FileComplexity`, `LeakageCounts`, `ToolUsage`, and up to 5 `ThinkingExcerpt` entries. Each excerpt has `Attribution` (with `file_paths: list[str]`), `BlockSignals`, and `Highlight[]`. Details in `schema.md`.

## Identifying the current session for in-progress runs

The `session` subcommand can target a session that's still in progress. Heuristic, in order:

1. Match `cwd` field in events against the user's current working directory. Find sessions where `cwd` matches.
2. Among those, pick the one with the most recent event timestamp (or most recent file mtime).
3. If ambiguous (two sessions open in same directory), print a disambiguation prompt.

Edge case: the invocation may itself appear as an event in the session being analyzed (recursive observation). Filter the skill's own invocation events before scoring.

## File locations on Adeline's machine

- Sessions: `~/.claude/projects/-Users-adelinelatruwe-Projects-attune/` (65 sessions as of Apr 22, 73 as of Apr 20 — primary corpus)
- Also present: `-Users-adelinelatruwe/` (3 sessions), `-Users-adelinelatruwe-Projects-attune-1/` (3 sessions)
- File history: `~/.claude/file-history/` — unused in v1, may be useful for richer edit-churn signal in v2
- Plans: `~/.claude/plans/` (40 entries) — plan-mode artifacts, unused in v1

## Canonical sessions for validation

From T1.2 full-corpus scan, top 5 heaviest sessions by event count:

| Events | Session ID | Notes |
|--------|-----------|-------|
| 764 | a70658da-6873-408d-999b-d4136d75de24 | Primary scoring validation. 0 progress events — not Agent-heavy despite event count. |
| 645 | 867b19ed-874a-4ee3-8ce0-35bd6ff9c624 | |
| 578 | 880a5ce5-2c66-44be-8d37-cfcb77d8d031 | |
| 464 | b0835e06-cd27-4427-9ec3-31a6f84bcd81 | |
| 440 | 06406cdb-9576-4d1e-a6b5-80036a55e189 | 181 progress events — Agent-heavy, candidate session if Agent-sourced work needs surfacing in the report. |

`a70658da` is the primary scoring-validation session. The session that surfaces the most interpretable thinking excerpt for the report's primary view is re-evaluated in Phase 5 based on excerpt quality, not event count alone.

## Naming

Working name: **ai-friction-map** (CLI binary), **Claude Code Friction Map** or **Friction Map** (prose references). Explicit enough to describe, searchable, no confusion with Attune.

## North star

The product succeeds if someone seeing it run says "I want this running all the time on my codebase."

Milestone 1 ships the friction map — the project's central claim. Milestone 2 ships the debugger as a second product surface. Milestone 3 ships the skill that wraps both. Continuous inline coaching and cross-codebase legibility scoring (see ECOSYSTEM.md) are post-Milestone-3 territory; the three milestones have to make those obvious.