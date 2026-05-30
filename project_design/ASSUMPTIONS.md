# Friction Map — Assumptions to Test

This file lists the load-bearing assumptions the Friction Map project depends on, ranked by impact. Each assumption has a test, a cost estimate, and a named consequence for "assumption fails."

Tier 1 tests were gating — run Monday April 20 before parser code. All passed with real data logged inline below. Tier 2 tests run during build as we hit them. Tier 3 is cosmetic or already handled.

**Status as of Wednesday April 22, late evening (Phase 2 complete — 2A, 2B, 2C all committed):** all gating tests resolved. Schema 1.2 stable. Pipeline produces a full `Report` object with attribution, leakage, complexity, tool-usage, and excerpts. Project cleared to proceed to Phase 3 (signals, baselines, scoring).

**Corpus drift note (April 22):** the attune corpus observed today is 65 sessions / 8,481 events (vs. 73 / 9,473 on April 20). Some sessions were moved or deleted between snapshots. Original test percentages still hold to within 0.2%; absolute counts have been re-baselined against the April 22 snapshot where relevant.

---

## Tier 1 — Kill-or-shape-the-project. All tests complete.

### T1.1 — Thinking blocks reference file paths in-text ✅ PARTIAL PASS (stronger than initially measured)

**Assumption:** Thinking blocks usually mention file paths explicitly (e.g. "storage.py", "/path/to/file.py") when reasoning about a file, so file-attribution for friction markers is cheap string matching.

**Why it's load-bearing:** The entire thinking-block scoring mechanism depends on being able to associate a marker cluster ("wait," "actually," etc.) with a specific file. If thinking blocks describe problems symbolically without naming files, attribution becomes a full NLP task.

**Test results (April 20, full corpus, 73 sessions at time of test):**
- 636 total thinking blocks
- 292 blocks with at least one file reference
- **Coverage: 45.9%**

**Verdict: partial pass (25–50% range).** Scoring works; per-file signal is noisier than ideal. **Mitigation: co-location rule (Option A)** — thinking-block file mentions count toward a file's score only if that file is also touched by a tool call in the same session.

**Important observation:** top-mentioned files across corpus are dominated by documentation:

```
108  DECISIONS.md        (recall)
 94  IMPLEMENTATION.md   (recall)
 69  DECISIONS_ARCHIVE.md (recall)
 50  server.py           (focus)
 42  NOTES.md            (recall)
 33  claude/settings.json (focus)
 32  docker-compose.yml  (mixed)
 25  pyproject.toml      (focus)
 22  storage.py          (focus)
 21  embeddings.py       (focus)
 19  CLAUDE.md           (recall)
  9  test_storage.py     (focus)
```

Without co-location filtering, the heatmap would show "your docs are the gnarliest code." Co-location is the difference between a useful product and a confused one.

**2B re-measurement (April 22, post-attribution; corrected May 29 post-C2-fix):** Tier 1 attributes thinking blocks via path-*fragment* suffix matching (suffixes containing a `/`); bare basenames fall through to Tier 2 (unique_basename), which attributes when the basename is unique in the session. Post-fix the tiers split, on attune (601 blocks), 12% exact_path / 33% unique_basename / 55% temporal_proximity, and on brownfield (466 blocks), 12% / 5% / 84%. **The 46% target from T1.1 no longer applies.** _The original 2B note recorded "61% Tier 1 / 0% Tier 2 / 39% Tier 3" and concluded Tier 2 was "architecturally subsumed." That was an artifact of the C2 bug: Tier 1 also matched bare basenames, over-claiming every same-basename file and pre-empting Tier 2's uniqueness guard so it could never fire. With Tier 1 correctly gated to fragments, Tier 2 fires routinely and is the dominant non-temporal tier on attune._

---

### T1.2 — Tool results are logged with contents ✅ PASS

**Assumption:** When Claude reads a file via the Read tool, the file's contents appear in a subsequent `tool_result` event. This lets the evidence panel show "here's what Claude saw when it read this file."

**Why it's load-bearing:** Evidence richness depends on this. If we only know *that* a file was read, not *what content was returned*, the evidence panel is thinner.

**Test results (April 20, 5-session sample, full corpus for distribution):**
- Read/Edit/Write tool_use events include `input.file_path` directly ✅
- Tool_result events include full file contents (e.g. 10,865 chars for a storage.py read) ✅
- tool_use_id matches tool_use_id across events ✅
- 2,433 total tool_result events across 73 sessions

**Tool distribution across full corpus** (this matters for attribution logic):

```
772 (31.7%)  Bash         — needs command + description regex
505 (20.7%)  Read         — structured file_path
499 (20.5%)  Edit         — structured file_path
176 ( 7.2%)  Grep         — structured path + pattern
100 ( 4.1%)  TodoWrite    — skip, not file-touching
 94 ( 3.9%)  Write        — structured file_path
 84 ( 3.4%)  ExitPlanMode — skip
 63 ( 2.6%)  Glob         — structured pattern + path
 60 ( 2.5%)  Agent        — sub-task; recovered via progress-events walker in 2B
 46 ( 1.9%)  ToolSearch   — skip
 13 ( 0.5%)  WebSearch    — skip
 12 ( 0.5%)  AskUserQuestion — skip
```

**Bonus finding:** Bash tool_use events have **two** structured fields:
- `input.command` — literal command string (e.g. `git log --all --oneline --follow -- DESIGN_PRINCIPLES.md`)
- `input.description` — Claude's own natural-language summary (e.g. "Check git history for DESIGN_PRINCIPLES.md")

Combining both sources improves Bash file-attribution significantly. Description is higher-confidence; command is higher-coverage.

**Verdict: pass.** Full evidence panel is viable. File-path extraction strategy per tool is documented in PROJECT_DESIGN.md.

**April 22 re-baseline note:** 2A checkpoint run on the April 22 corpus (65 sessions / 8,481 events) produced 2,378 tool_result events and a Bash/Read/Edit/Grep distribution of 31.9% / 20.7% / 20.6% / 7.3% — matching April 20 percentages to within 0.2%. Tool distribution is stable across the drift.

---

### T1.3 — Enough sessions have thinking enabled ✅ DECISIVE PASS

**Assumption:** Extended thinking is enabled in enough of the attune sessions to produce a meaningful signal.

**Why it's load-bearing:** Thinking-block friction markers are the differentiator of the whole project. If they're sparse, the demo rests on weaker signals.

**Test results (April 20, full corpus):**
- 71 sessions with at least one thinking block
- 72 total sessions (at time of initial T1.3 — now 73 including active)
- **Coverage: 98.6%**

**Verdict: decisive pass.** Thinking signal is abundant. Primary scoring input is reliable across effectively the entire corpus.

**2B re-measurement (April 22):** 607 thinking blocks across the April 22 corpus — proportional to the April 20's 636 given the session drift.

---

### T1.4 — Session JSONL is streaming-appended during active sessions ✅ PASS

**Assumption:** Claude Code writes events to the session JSONL file as they happen (streaming append), not all at once when the session ends. This enables `/friction now` to read a session in progress.

**Why it's load-bearing:** If sessions only flush at the end, `/friction now` can't read a session in progress and the live subcommand is impossible.

**Test results (April 20, single-session observation on active Claude Code session):**
- File `978c30c2-...jsonl` mtime went 12:29 → 12:34 after a new interaction
- File size grew from 24,484 → 36,148 bytes (~11.6KB of new events in ~5 min of active use)
- No session close required for flush

**Verdict: pass.** Streaming append confirmed. Live subcommand architecturally viable. Small caveat: buffering may introduce seconds of lag between a response completing and the event landing on disk. Not visible to users at human timescales.

---

### T1.5 — Agent sub-task file attribution via `progress` events ✅ VIABLE (walker works) / ❌ nested thinking absent

**Assumption (new):** Agent tool invocations log their sub-agent's own tool calls to the parent session's JSONL as top-level events with `type: "progress"`. The nested `tool_use` blocks inside `data.message.message.content[]` carry full structured file-path information.

**Why it's load-bearing:** PROJECT_DESIGN.md originally documented Agent sub-task work as a v1 limitation (opaque, 2.5% of tool use, attribution lost). This assumption, if true, dissolves that limitation.

**Test results (April 22, 2A checkpoint inspection):**
- `progress` events with `data.type: "agent_progress"` carry nested `tool_use` blocks with full `input` — a sub-agent `Read` on an absolute path appears as a complete, structured tool_use one level deeper.
- 566 `progress` events in the April 22 corpus (~7%).

**2B walker results (April 22, post-commit):**
- Walker emits 75 nested tool_use, 75 nested tool_result, and 6 nested text blocks corpus-wide.
- **0 nested thinking blocks.** Sub-agents in this corpus emit tool calls and occasional text, but no extended thinking.

**Verdict: partial.** Walker works — Agent sub-task tool-behavior attribution is recovered, not opaque. But the nested-thinking follow-up resolves in the negative for this corpus: sub-agents don't carry thinking blocks. Sub-agent friction signal is tool-behavior only (reads, edits, bashes), not reasoning-level.

**Consequences:**
- Leakage attribution now covers sub-agent tool calls — Agent-heavy sessions get accurate per-file leakage counts.
- The evidence panel will never show sub-agent thinking (there is none). Not a regression — we never had it.
- The "Agent v1 limitation" in PROJECT_DESIGN.md is wrong as written; the walker recovers sub-agent tool work. Only sub-agent reasoning is absent, and that's an empirical property of this corpus, not an architectural limit.
- Canonical session `a70658da-6873-408d-999b-d4136d75de24` turns out to have zero progress events despite being the heaviest session by event count. The scoring-validation pipeline does not depend on Agent-sourced work — re-evaluation markers in top-level thinking are the primary mechanism. Candidate sessions for surfacing Agent-sourced work specifically (if needed): `06406cdb` (181 progress events) and `0d71f58b` (153). Phase 5 decides which session surfaces the most interpretable excerpts for the primary view.

---

### T1.6 — `system/compact_boundary` events mark signal-reset boundaries ✅ VIABLE (rule correct) / rarely-fires on this corpus

**Assumption (new):** `type: "system"` events with `subtype: "compact_boundary"` mark points in a session where context was compacted. Window-based detectors crossing a boundary would produce false positives.

**Why it's load-bearing:** 2B implements re-read bursts, edit churn, cluster detection, and tool-behavior leakage — all of which look at "within N events" windows. If those windows cross compact boundaries uncorrected, Read-after-compaction gets scored as re-read churn when it is actually context re-establishment.

**Test results (April 22, 2A checkpoint):**
- `system/compact_boundary` structure: `{type: "system", subtype: "compact_boundary", content: "Conversation compacted", compactMetadata: {...}}`
- 104 `system` events in the April 22 corpus (9 boundaries on the 65-session subset used for 2B probe).

**2B empirical measurement (April 22, post-commit):**
- Synthetic probe (call `window_events(n=3)` on every event corpus-wide): 54 clips across 9 boundaries — exactly what ±3 math predicts, confirming instrumentation works.
- Real-parse clip count: **1**. Attribution Tier 3 produces 0 clips (runs only on 239 blocks that fall through to temporal proximity, none within 3 events of a boundary). Leakage detectors produce 1 clip corpus-wide.

**Verdict: viable, but rarely-exercised on this corpus.** The defensive rule is the right rule; boundary-adjacent friction events are infrequent in attune. Do not interpret the low clip count as "T1.6 was overkill" — on a corpus with heavier compaction patterns (more sessions, more compactions per session, denser tool calls around boundaries), the rule would fire substantially more. Keep boundary handling active; no tuning against the single clip.

---

## Tier 2 — Affects quality, not feasibility. Test during build.

### T2.4 — Parser completes full corpus scan in under 3 seconds ✅ DECISIVE PASS

**Assumption:** A streaming parser over the full attune corpus completes in under 3 seconds. Under 2 seconds ideal (silent execution matches `coverage.py` conventions). Under 1 second for live single-session scan.

**Why it matters:** the user experience depends on responsive execution. If parsing is slow, the silent-execution UX of `ai-friction-map scan` (matching `coverage.py` conventions) breaks down.

**Test results (April 20, stub parser, Adeline's MacBook Air):**
- 9,473 events across 73 sessions
- **Full parse: 0.23 seconds (41,678 events/sec)**
- Projected: 1,000 sessions ≈ 3 seconds; 10,000 sessions ≈ 30 seconds
- Single-session (live mode): ≈ 3 milliseconds

**2A checkpoint results (April 22, real parser on April 22 corpus):**
- 8,481 events across 65 sessions
- **Full parse: 0.307 seconds** — ~30% slower than stub, still ~10× under budget

**2B checkpoint results (April 22, real parser + attribution + clusters + leakage):**
- 9,151 events across 65 sessions
- **Full parse: 1.921 seconds** — ~6× slower than 2A, well within the 10× ceiling and the 3-second budget

**2C checkpoint results (April 22, full pipeline + complexity + tool usage + report assembly):**
- **Warm cache: 2.58s wall (2.32s CPU)** — within the 3s budget.
- **Cold cache: ~14s wall on first run** — bottlenecked on 412 disk reads for per-file complexity computation (139 of those are radon parses).
- Real-world users will be warm-cache (they just edited their own project files; OS page cache is hot). Cold-case relevance is fresh-shell or CI integration, neither of which is v1.

**Verdict: decisive pass on warm cache, with cold-cache caveat.** Performance is a non-issue at any realistic scale. **Phase 4 watch-for:** if cold-start performance becomes user-visible (demo on someone else's laptop, CI integration, fresh clone), add a per-path complexity cache keyed on `(path, mtime)` persisted to `~/.cache/ai-friction-map/complexity.json`. Don't build it preemptively.

---

### T2.1 — Friction markers generalize across models and task types

**Assumption:** The marker lexicon ("wait," "actually," "let me reconsider," "I see," "hmm," "but", etc.) identifies re-evaluation across different models and task types.

**Why it matters:** If markers are task-specific or model-specific, the scoring function needs per-slice tuning, which complicates the tool and weakens the "works on any codebase" claim.

**Test plan during build (2 hours, Phase 5):**

**Order matters:** hand-tag the calibration sample BEFORE running regex. This preserves the discipline of committing the lexicon before seeing what it produces. Fitting the lexicon to the results after the fact would mean the signal can't be falsified.

1. Commit the current lexicon to code (no additions, no removals).
2. Sample 20 thinking blocks from sessions of varying shapes: short debug, long implementation, planning-heavy, tool-heavy.
3. Hand-tag each block: does it show re-evaluation (yes/no) and which markers would you expect to trigger?
4. Only then: run the regex detector against the sample.
5. Compare hand-tags to regex output. Compute precision, recall, agreement rate.

**Pass criteria:** Agreement ≥80%.
**Partial pass:** 60–80% — use markers as a signal, not a classifier. Combine with block length and structural features.
**Fail:** <60% — expand lexicon or rebuild around structural features. Scoring function weight on markers drops.

**Cost:** 2 hours during Phase 5.

**Note:** 2B ships with a stub marker detector (case-insensitive substring match on a small lexicon) to make cluster detection testable. Phase 3 replaces it with the production word-boundary regex. The stub's false positives (e.g. `let me` matching `delete me`) are expected and deliberately not tuned for — T2.1 runs against the real detector.

---

### T2.2 — Re-reads within a short window are a real confusion signal

**Assumption:** When Claude reads the same file multiple times within N turns of a session, that pattern correlates with confusion about the file. Raw re-read count across a whole session is not the signal — *burst* re-reads are.

**Why it matters:** Raw re-read count is noisy (context compaction, multi-topic sessions, legitimate revisits). Window-based re-reads are cleaner but need a window size, and the window size is a parameter you shouldn't guess.

**Test plan during build (2 hours, Phase 5):**

Compute re-reads per file at multiple windows (3 turns, 5 turns, 10 turns, full session). Correlate each against sessions that ended with user corrections or git reverts. Pick the window with the highest correlation.

**Important correction (April 22, per T1.6):** re-read windows must NOT cross compact boundaries. 2B's `window_events` helper enforces this. Tuning happens on windows *within* compact regions, not across them.

**Pass criteria:** Some window produces a meaningfully higher correlation than raw count. Use that window as the default.
**Fail:** No window produces correlation above noise. Re-read as a signal is weaker than expected; lean harder on thinking markers and edit churn.

**Cost:** 2 hours during Phase 5.

---

### T2.3 — Schema completeness ✅ RESOLVED

**Assumption:** The event types I've seen plus the tools discovered during T1.2 are the full set for the sessions we care about.

**Why it matters:** The parser needs to handle every event type gracefully. Unknown types should be logged and skipped, not crash.

**Status (April 22, updated after 2A checkpoint):** 2A surfaced two undocumented top-level event types (`progress` — 566 events — and `system` — 104 events) and three undocumented tool names (`Skill`, `TaskOutput`, `TaskStop`). All resolved:

- `progress` — re-classified as work signal (see T1.5); known-type, consumed by 2B's `agent_progress` walker.
- `system` — re-classified as structural boundary marker (see T1.6); known-type, parsed-but-blocks-empty, consumed as a signal-reset boundary by 2B's `window_events` helper.
- `Skill` — sub-delegation (invokes a named skill); no files in tool input; skip-listed in extraction.
- `TaskOutput` / `TaskStop` — Agent task lifecycle control events (task_id, block, timeout); no files in tool input; skip-listed in extraction.

Known-type set is now: `assistant`, `user`, `file-history-snapshot`, `queue-operation`, `attachment`, `pr-link`, `ai-title`, `last-prompt`, `progress`, `system`. Skip-listed tools are now: `TodoWrite`, `ExitPlanMode`, `ToolSearch`, `AskUserQuestion`, `WebSearch`, `Skill`, `TaskOutput`, `TaskStop`. `Agent` remains a distinct case — tool_use returns `[]` at extraction layer (its nested work is recovered via the `progress`-events walker in 2B).

**2B confirmed no further unknown types.** Schema surface is closed for v1.

**Verdict: pass.**

---

### T2.5 — Current-session identification heuristic works

**Assumption:** For `/friction now`, matching events' `cwd` field against the user's CWD, then picking the most recent, reliably identifies the session in progress.

**Why it matters:** If the heuristic picks the wrong session, the live readout shows data from a stale or unrelated session.

**Test during live subcommand implementation (Phase 7):**
1. Open two Claude Code sessions in different projects simultaneously.
2. Run the identification heuristic and confirm it picks the correct one for each CWD.
3. Open two Claude Code sessions in the *same* project (edge case). Confirm the "most recent event" tiebreaker picks the right one, or prompt for disambiguation.

**Pass criteria:** Correct identification in both the common case (one session per project) and the two-session-same-project case.
**Fail:** Ambiguity not handled. Add an explicit disambiguation prompt or session-id flag.

**Cost:** 30 minutes during build.

---

### T2.6 — Structural signals correlate with perceived friction ✅ CLOSED

**Status (May 4, post Phase 5 #7):** of the 6 originally-listed structural signals, 3 were dropped during Phase 3 (root TTR, sentence length, length trend), 2 were parked during Phase 5 (`question_rate_per_100w` in #3, `tool_use_coupling` in #3a), and the last — `block_length_words` — is parked in #7. The structural-signals module is empty in v1 scoring; redefinition candidates (`bash_coupling_rate`, `investigative_coupling_rate`, others) carry to v2. Full chain in `block_length_words_parking_handoff.md`.

**Assumption (new, surfaced April 20 from Attune review):** The structural signals ported from Attune — block length, question rate, root TTR, sentence length, tool-use coupling, length trend — correlate with friction enough to be worth including in the scoring function alongside marker detection.

**Why it matters:** The structural signals module adds ~50 lines of code to the scoring function. If they don't carry signal beyond markers, it's wasted complexity.

**Test plan during build (1 hour, Phase 5, after T2.1 completes):**

Compute structural signals per thinking block across the corpus. For each signal, check whether it correlates with the presence of re-evaluation markers (the primary signal). Signals that agree with markers add confidence; signals that disagree interestingly (long block but no markers, or high question rate but no markers) surface different friction patterns and are worth keeping as orthogonal axes.

**Pass criteria:** At least 3 of the 6 structural signals show meaningful variation across high-vs-low-marker blocks and either correlate or add orthogonal signal.
**Partial:** Some signals are noise; keep the ones that aren't. Document which did and didn't.
**Fail:** None of the structural signals carry signal. Drop the module, rely on markers + behavioral signals only.

**Cost:** 1 hour during Phase 5.

---

### T2.7 — Multi-file attribution cardinality ✅ CLOSED

**Status (May 25, post Phase 5 #9):** equal-share (1/N) weighting validated via 30-block cross-corpus hand-tag (15 attune, 15 brownfield; stratified by split count). Both corpora cleared the pre-committed keep threshold (attune 11/15, brownfield 12/15); equal-share ships unchanged.

**Assumption (new, implicit in schema 1.2 rollout):** The schema-1.2 shift from `Attribution.file_path: str | None` to `Attribution.file_paths: list[str]` preserves signal — thinking blocks that attribute to multiple files represent real multi-file reasoning, not attribution noise. A non-trivial fraction is expected; if every block ends up multi-file, the scoring function's per-file weighting becomes load-bearing.

**Why it matters:** Phase 3 scoring must decide how a multi-file thinking block distributes friction across its N files (equal share, downweighted, or other rule). The shape of the cardinality distribution drives that decision.

**Test results (April 22, 2B checkpoint, 607 thinking blocks):**
- **0 files attributed:** 77 blocks (12.7%) — genuine unattributed cases.
- **1 file:** 280 blocks (46.1%) — clean single-file attribution.
- **2 files:** 92 blocks (15.2%) — real two-file co-reasoning.
- **3+ files:** 158 blocks (26.0%) — substantial multi-file tail.

**Verdict: multi-file attribution is real, not noise.** 41% of attributed blocks (or 26% of all blocks) touch 3+ files. The ECOSYSTEM.md entry on file co-occurrence as structural signal is well-supported — this is measurable corpus-level behavior.

**2C re-measurement:** 143 of 421 files in the report carry at least one excerpt with multi-file attribution (length > 1). Well above the 15% spec threshold. Confirms the cardinality distribution is a corpus-level property, not a per-block quirk.

**Phase 3 flag:** scoring function must pick a multi-file weighting rule. Default candidates: (1) equal share — each file gets `1/N` of the block's friction contribution; (2) floor at 1 — each file gets the full contribution, accepting double-counting across sessions; (3) decay — first file full weight, subsequent files downweighted. Decision deferred to Phase 3 weight tuning.

---

### T2.8 — `ai-title` event field name ✅ RESOLVED (new April 22, from 2C checkpoint)

**Assumption (new, implicit in 2C session-listing logic):** `ai-title` events carry their title content in a predictable field. The 2C spec assumed `content`; synthetic test fixtures used `content`; real Claude Code uses `aiTitle`.

**Why it matters:** `active-sessions` and `session <substring>` rely on extracting the title to display and to match against. If the field name is wrong, both subcommands silently fail to find anything matchable — the test corpus wouldn't catch it because the synthetic fixtures used the assumed name.

**Test results (April 22, 2C corpus checkpoint):**
- `session storage` initially returned no matches against the real attune corpus, despite obvious-by-eye title matches.
- Inspection of real Claude Code session JSONL revealed: `{"type": "ai-title", "aiTitle": "<title>", ...}`. The field is `aiTitle`, not `content` or `title`.
- Fix: prepend `record.get("aiTitle")` to the fallback chain (`aiTitle` → `title` → `content` → nested message text). Regression test added.

**Verdict: resolved, with a methodology lesson.** The streaming-read approach in `sessions.py` is cheap to write but has no real-data validation in unit tests — those use synthetic fixtures with the assumed shape. The corpus checkpoint (running the actual subcommand against the actual attune sessions) was the only place this was catchable.

**Lesson for future handoffs:** when a streaming-read or schema-extraction layer is built against synthetic fixtures, the corpus checkpoint must include a real-data exercise of that layer specifically — not just "does the report shape look right." 2C's checkpoint had `session storage` as an explicit exercise; that's what surfaced this. Pattern worth keeping.

**Cost:** ~15 minutes to debug, fix, and add regression test. Caught at checkpoint, not after Phase 7's skill work.

---

### T2.10 — Markers signal is sparse-positive across corpora ✅ RESOLVED (new April 27, from marker baseline reshape design session)

**Assumption (Phase 3b, carried into the design session):** the `markers_per_100w` corpus baseline collapsing to median = 0 / MAD = 0 on attune is a real structural problem with the signal's distribution shape, not a small-n artifact, calibration miss, or implementation bug. If true, the standard robust z-score normalization is wrong for this signal regardless of the corpus.

**Why it matters:** markers are the headline signal of the project. With baseline collapse, every block contributes z = 0 on markers and the signal goes silent — exactly what the brownfield top-file finding showed (excerpts dense with marker hits, scoring contribution of +0.000). If the shape isn't actually the problem, the design session would be solving the wrong issue.

**Test results (April 27, two corpora):**

Inspection script ([code-execution corpus walker](#)) sampled `markers_per_100w` at every thinking block in two unrelated codebases:

| | attune | brownfield |
|---|---|---|
| Sessions / blocks | 64 / 601 | 81 / 466 |
| Zero-rate (raw jsonl) | **66.1%** | **66.1%** |
| Among-positives p25/p50/p75 | 0.64 / 1.11 / 1.77 | 0.66 / 0.99 / 1.72 |
| Report's own corpus baseline | median = 0, MAD = 0 (collapsed) | median = 0, MAD = 0 (collapsed) |

The 66.1% match across two unrelated codebases is structural, not coincidental — a property of how Claude uses extended thinking, not a property of any one codebase. The positive tail has healthy spread (interquartile range of ~1.0 marker rate units on both corpora, sample sizes of 158 and 204 positive blocks).

**Verdict: confirmed sparse-positive shape. Robust z-score normalization is the wrong tool for this signal.** Phase 3b's baseline-collapse diagnosis was correct. Design session converged on **presence/intensity split** (option E from `marker_baseline_handoff.md`): file-level contribution = (fraction of attributed blocks containing any markers) × (mean rate among marker-bearing blocks). See TRADEOFFS.md "Normalization: presence/intensity split for sparse-positive signals" for full rejected-alternatives analysis.

**Methodology note:** the inspection script went through two iterations. The first pulled `markers_per_100w` from per-excerpt data only — which produced a misleading "100% positive, healthy MAD" result because excerpts are emitted only for marker-bearing blocks. The pivot was triggered by the contradiction between per-excerpt (100% positive) and report's own corpus baseline (median = 0). Second iteration added a raw-jsonl walker that samples every thinking block, unbiased. Three sources of truth — per-excerpt (biased), report baseline (authoritative), raw jsonl (unbiased) — confirmed the finding triangulated cleanly.

**Cost:** ~90 minutes design session (including pivot from per-excerpt to raw-jsonl inspection).

---

### T2.11 — Question rate is sparser than markers (~7% vs 34% positive corpus-wide) ✅ MEASURED (new April 27, from same design session)

**Status (post Phase 5 #3):** question rate parked at weight=0 — orthogonal at block level but per-file candidates dominated by attribution-noise + small-N. See `question_rate_per_100w_parking_handoff.md`. (Original verdict below preserved as the point-in-time record.)

**Assumption (carried in from Phase 3b's "lexicon swap collapsed markers, possibly other signals too" finding):** `question_rate_per_100w` shares the sparse-positive shape with `markers_per_100w`, and the same presence/intensity normalization fits.

**Why it matters:** if the shapes are similar, one design decision covers both signals. If question rate is meaningfully sparser, the presence/intensity formula technically still works but the signal will fire on fewer files — possibly so few that the signal contributes negligibly and shouldn't be in the scoring function at all.

**Test results (April 27, same two corpora):**

| | attune | brownfield |
|---|---|---|
| Zero-rate (raw jsonl) | **93.2%** | **92.9%** |
| Positive blocks (raw jsonl) | 41 / 601 | 33 / 466 |
| Among-positives p25/p50/p75 | 0.32 / 0.55 / 1.23 | 0.32 / 0.47 / 0.69 |
| Report's own corpus baseline | median = 0, MAD = 0 (collapsed) | median = 0, MAD = 0 (collapsed) |

Same shape as markers (sparse-positive, baseline collapses, positive tail has spread), but 4–5× sparser. Stable cross-corpus rate — the 93% / 93% match is structural, like the 66% / 66% match for markers. The positive tail's spread is similar to markers (interquartile range of ~0.5–0.9 in rate units), so intensity carries information when the signal fires.

**Verdict: same shape, much sparser.** Presence/intensity split formula technically applies, but with corpus-level positive rate of ~7%, most files will have presence_rate = 0 and contribute nothing on this signal. Whether question rate earns its keep at this firing rate is an empirical question about whether its positive contributions land on files that other signals don't already flag (signal orthogonality). Decision deferred to **Phase 5 weight tuning**, which will:
1. Apply option E to question rate as a candidate normalization, OR keep its weight at 0.
2. Compute correlation between question rate's contributions and markers / behavioral signals.
3. Eyeball-test the files where question rate contributes meaningfully — are they friction-laden in ways the other signals miss?
4. Decide: keep at low weight (precision-targeted signal), drop entirely (not earning its keep), or re-think the operationalization.

The implementation handoff for the markers reshape (separate session) does *not* include question rate. Adding it later if Phase 5 decides to is a ~30 min follow-up.

**Cost:** ~10 minutes added to the design session (inspection script extension + interpretation).

---

### T2.12 — Cluster-gap N = 200 (was 100) ✅ TUNED + KNOWN LIMIT (May 15)

Cluster-gap N = 200 (was 100), 2026-05-15. Two-corpus hand-tag (attune + brownfield, 20 boundary blocks). N=50 over-splits on both corpora (0/20 exact matches to hand-judged moment count). N=200 best-fits both. Known limit: `cluster_count` over-segments on long, high-marker blocks (≥~12 markers, continuous-interrogation debugging). "actually" fires as a discourse tic ("in fact"), not always re-evaluation, inflating marker count and fracturing single reasoning stretches at narrow N. N=200 chosen partly for robustness to this. No N value cleanly tracks hand-judged moments on the highest-marker blocks; this is a documented limit of word-gap clustering, not a pending task.

---

## Tier 3 — Cosmetic, already handled, or punt to v2.

### T3.1 — Cache creation tokens as a friction signal

**Original assumption:** High `cache_creation_input_tokens` correlates with hard task context.

**Verdict: DROPPED.** Cache creation is heavily influenced by infrastructure-level cache hits/misses, not task difficulty. First turn after a reset always looks "hard" under this metric. Not a clean signal.

---

### T3.2 — User correction detection

**Original assumption:** User messages following assistant turns, especially short ones ("no," "undo," "that's wrong"), are detectable corrections.

**Verdict: PUNTED to v2.** Classifying user messages by intent is a small NLP task. A regex list would give false positives and miss polite corrections. Skip this signal entirely in v1.

---

### T3.3 — Static HTML output is the right form

**Verdict: CONFIRMED, REFINED.** The output is a self-contained single-page app — one HTML file with data embedded as JSON, interactive without a server. Pattern matches `coverage.py` HTML reports.

---

### T3.4 — Judges care about novelty over completeness

**Verdict: OPERATING ASSUMPTION, not testable.** (Historical note: this assumption was framed for a hackathon submission that was not accepted. Project is now on a self-imposed timeline; the underlying scoping principle still holds — prioritize the marker-highlight view as the primary product surface, don't over-build polish, one surface, one question, one clear product moment.)

---

## Summary — April 22 late-evening status (Phase 2 complete)

All gating tests complete. 2A, 2B, and 2C each surfaced findings that reshaped the design without re-opening earlier work. Phase 2's staged-handoff + corpus-checkpoint pattern caught six bugs across maybe two hours of total checkpoint inspection time — every one of them would have been a silent issue if discovered later.

Findings that reshaped the design:

1. **Attribution is viable via co-location (Option A), not pure lexical matching.** (T1.1)
2. **Bash is 31.7% of tool use and has two structured fields** (command + description). (T1.2)
3. **Performance is comfortably under budget at every checkpoint.** (T2.4) Real parser 0.307s at 2A, 1.921s at 2B, 2.58s warm at 2C; cold cache 14s flagged for Phase 4 if it becomes user-visible.
4. **Thinking signal is 99% present.** (T1.3)
5. **Agent sub-task work is recoverable via `progress`-events walker.** (T1.5)
6. **Sub-agents in this corpus don't emit thinking blocks.** (T1.5 follow-up)
7. **Canonical scoring-validation session `a70658da` has zero progress events** despite being the heaviest by event count.
8. **`system/compact_boundary` handling is correct but rarely-exercised on attune.** (T1.6)
9. ~~**Tier 2 attribution (`unique_basename`) is architecturally subsumed by Tier 1.**~~ (T1.1 re-measurement) — **VERDICT REVERSED (May 29, C2 fix).** This was false, caused by the C2 bug: Tier 1 matched bare basenames, over-claiming and pre-empting Tier 2's uniqueness guard so it never fired. With Tier 1 gated to path fragments, **Tier 2 fires routinely** (33% of attributed blocks on attune, 5% on brownfield). The "two-tier story in prose" cleanup that followed from this assumption is withdrawn.
10. **Multi-file attribution is real: 41% of attributed blocks touch 2+ files, 26% touch 3+.** (T2.7)
11. **Schema surface fully resolved.** (T2.3)
12. **Structural signals from Attune port cleanly** to thinking blocks. (T2.6, tested in Phase 5.)
13. **`ai-title` events use the `aiTitle` field, not `content`.** (T2.8) Caught at 2C corpus checkpoint, not unit tests — synthetic fixtures had the wrong shape.
14. **Markers signal is structurally sparse-positive across corpora: 66.1% zero rate on both attune and brownfield, identical to two decimal places.** (T2.10) Confirms Phase 3b's baseline-collapse diagnosis. Robust z-score is the wrong tool for this distribution shape. Presence/intensity split adopted; see TRADEOFFS.md.
15. **Question rate is sparser than markers (~93% zero rate vs 66%) but same shape.** (T2.11) Presence/intensity formula applies mechanically, but signal will fire on far fewer files. Decision to keep / drop / reweight deferred to Phase 5 weight tuning where empirical orthogonality can be tested.
16. **User-managed ignore negation cannot un-hide a default match.** (Phase 5b) Because the 13 built-in defaults and the user `.frictionmap-ignore`/`--ignore` patterns are independent matchers OR'd together, a user negation (`!pattern`) in `.frictionmap-ignore` overrides other *user* patterns but cannot un-hide a path matched by a built-in default.

Design changes locked into PROJECT_DESIGN.md, IMPLEMENTATION.md, and schema.md based on these findings.

---

## Discipline

This file is live. When a test runs, paste the result inline under the assumption. When a scoring parameter is chosen based on a test result, note it here. When a new assumption surfaces during build, add it with a tier and a test.

The document tracks what we know, not what we assumed.