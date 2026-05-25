# Trade-offs

Design choices made during the build where a reasonable alternative existed and one was picked for reasons worth documenting. Each entry is a decision I'd defend in a code review — not a placeholder waiting for a future phase.

Separate from `ASSUMPTIONS.md` (properties of the data, tested) and `PROJECT_DESIGN.md` (what the product is). This file captures *why the product is shaped the way it is.*

---

## Output location: `report.html` in the current working directory

**Decision:** `ai-friction-map scan` writes `report.html` to the directory the command is run from.

**Rejected alternatives:**
- Writing next to the sessions directory (`~/.claude/projects/.../report.html`) — consistent location, but hidden from where users actually work.
- Writing to the on-disk project root (requires resolving the project directory separately from the sessions directory) — more correct in edge cases, more logic.

**Why:** matches `coverage.py` convention. The tool is meant to be run from the project root, where CWD and project root are the same. A shipped report lands where the user is, not in a hidden system directory.

**Known limit:** running from a deep subdirectory of the project writes `report.html` to that subdirectory. Acceptable — the tool isn't designed for that invocation pattern, and forcing project-root resolution would add logic for a case the demo flow never hits.

---

## Attribution: co-location rule, not pure lexical matching

**Decision:** a thinking-block file mention counts toward a file's friction score only if that file is also touched by a tool call within the same session.

**Rejected alternative:** count every file mention in a thinking block, regardless of whether the file was actually worked on.

**Why:** tested against 73 sessions in `ASSUMPTIONS.md` T1.1. Without co-location, the top-mentioned files are dominated by documentation (DECISIONS.md, IMPLEMENTATION.md, NOTES.md, CLAUDE.md) — Claude references these constantly for context but doesn't struggle with them. Co-location separates *focus mentions* (code being worked on) from *recall mentions* (docs being consulted), which is the difference between a useful heatmap and one that says "your docs are the gnarliest code."

**Known limit:** files that Claude genuinely struggles with but doesn't invoke via tools (e.g. a file it mentions repeatedly in thinking but never opens) get under-scored. Acceptable — if Claude doesn't touch a file, it isn't working on it.

---

## Scoring normalization: per-file scores divided by file size

**Decision:** raw friction signal per file is normalized by file size (LOC or char count) before ranking.

**Rejected alternative:** rank by raw aggregate signal.

**Why:** without normalization, large files dominate rankings purely because there's more code to touch. A 2,000-line file Claude reads once ranks above a 50-line file Claude wrestles with three times. Normalization surfaces *per-unit-of-code* friction, which is what the signal is meant to capture.

**Known limit:** extremely small files with a single friction incident can rank disproportionately high. Threshold on minimum file size (or minimum event count per file) handles this in the scoring function.

---

## Output format: self-contained HTML, not a web service

**Decision:** `ai-friction-map scan` produces one `report.html` file with all data embedded as JSON. No backend, no upload flow, no hosting.

**Rejected alternative:** a web application with a server, upload endpoint, and dashboard routing.

**Why:** the output is shareable as a file (email, Gist, Slack) and works anywhere HTML works. Zero deployment. Pattern matches `coverage.py`, `pytest-html`, and `plotly --include-plotlyjs=inline`. A web service adds upload handling, storage, hosting, and routing — all new surface area that doesn't improve the core product.

**Known limit:** the HTML file gets large on big codebases (>10,000 files). File-tree component breaks at that scale. Acceptable for the sessions-per-codebase distribution the tool is actually used on.

---

## Signal set: reasoning signals are primary; behavioral signals are amplifiers, not generators

**Decision:** the score function distinguishes two signal classes:

- **Reasoning signals** — re-evaluation markers in thinking blocks, block length, question rate, tool-use coupling. These measure friction *as Claude experienced it in the moment.*
- **Behavioral signals** — re-read bursts, edit churn, leakage events (Edit failures, Bash retries, Grep reformulations, Read-after-Edit). These measure *patterns of activity* that correlate with friction but can also reflect ordinary work.

Reasoning signals are the load-bearing input. Behavioral signals contribute only when reasoning signals also fire on the same file. A file with high edit churn and no marker activity is work, not friction; its score does not surface it as a friction surface.

**Rejected alternatives:**

1. *Behavioral signals alone (no thinking blocks).* Produces plausible rankings but no inspectable mechanism. The marker-highlight evidence panel — the place where a reader can see *why* a file ranks high — only exists because reasoning signals are primary.

2. *Behavioral signals as fully additive (the v1-pre-Phase-5 shape).* Tested on the brownfield validation corpus and observed to over-promote single-signal files. A markdown design doc ranked #1 on edit_churn alone (+1.74) with markers, block_length, and reread_bursts at zero or negative; a Python file with four positive signals (markers, block_length, reread_bursts, edit_churn) ranked third. Additive scoring rewards work volume, not friction. Brownfield made this visible because attune's calm-mode rankings have insufficient behavioral signal to expose the failure mode.

3. *LLM-judged friction.* Run an LLM over thinking blocks to classify "did Claude struggle." Rejected for v1 — see "Signal extraction: counting, not interpretation" below. Sketched as v2 territory under a `--deep` flag.

**Why:** the product distinction is *friction*, not *activity*. A senior engineer would not call "Claude edited storage.py 50 times cleanly" friction; they would call it implementation. The same is true for re-reads — multiple Reads of the same file across a session can be context re-establishment, not confusion. By gating behavioral signals on reasoning signals, the score function says: *behavioral patterns count when there's evidence Claude was reasoning hard about the file*. Otherwise, the activity is just activity.

This also resolves a small-N noise mode that would otherwise need its own min-block-count threshold. A file with one attributed block, no markers, but a few re-reads scores zero under gating. Same file with one attributed block carrying re-evaluation markers scores honestly — the reasoning signal is what licenses the behavioral signal's contribution.

**Mechanism:** the score function partitions contributions:

```
reasoning_score = sum of contributions from markers, block_length, question_rate, tool_use_coupling
behavioral_score = sum of contributions from reread_bursts, edit_churn, leakage

if reasoning_score > 0:
    score = reasoning_score + behavioral_score * gate(reasoning_score)
else:
    score = 0
```

The exact shape of `gate()` is a calibration question — hard 0/1 step, sigmoid, `min(1.0, reasoning_score / threshold)`. The structural decision is that the gate exists; the calibration of its shape is tunable.

**Known limits:**

- *Files where Claude struggled but didn't externalize it in thinking* are under-scored. Acceptable: this is the same trade-off the co-location rule makes. Friction has to leave a trace to be measured.
- *Sessions with extended thinking disabled* produce zero reasoning signal across all files in the session. Behavioral activity in those sessions contributes nothing under gating. This is correct semantics — without thinking blocks the project's primary mechanism is silent — but it does mean a corpus dominated by thinking-disabled sessions will produce a thin friction map. Documented in the README's known-limits section.
- *The v2 question* — does the gate suppress real friction signal in corpora the v1 calibration didn't see? — is genuinely open. Re-evaluation may surface differently across model families, task types, codebases. The decision rests on a hypothesis that reasoning friction is the load-bearing signal *because* re-evaluation markers in extended thinking are how the model externalizes it. If that hypothesis fails on future corpora, gating becomes the wrong shape and the v2 revisit is a structural one. The v1 stance: ship the principled shape, let multi-corpus data tell us if it bends.

---

## Dropped signals: cache tokens and user corrections

**Decision:** cache creation tokens and user-correction detection are explicitly excluded from the scoring function.

**Rejected alternative:** include both as additional signal axes.

**Why (cache tokens):** cache creation reflects infrastructure-level cache hits/misses, not task difficulty. First turn after a cache reset always looks "hard" under this metric regardless of the task. Not a clean signal.

**Why (user corrections):** classifying user messages by corrective intent is a small NLP task. A regex list produces false positives ("no" in "no problem") and misses polite corrections ("actually, could we..."). The effort to do it reliably is out of scope.

**Known limit:** user-correction signal, if done well, would be valuable. v2 territory.

---

## Signal extraction: counting, not interpretation

**Decision:** every signal in the v1 scoring function either *counts* something in thinking-block text or *counts* something in the event stream. No signal attempts to interpret what Claude meant, inferred, or intended. Specifically:

- Marker detection is regex word-match on a fixed lexicon. Counting.
- Block length, question rate, word count, char count. Counting.
- Reasoning-to-output ratio is a ratio of character counts. Counting.
- File mentions in thinking blocks are resolved by exact-path match (Tier 1) or unique-basename match within session-touched files (Tier 2). Counting.
- Ambiguous basename mentions (multiple candidates in session), pronominal references ("that file"), and descriptive references ("the filter component") are **not resolved**. They fall through to temporal-proximity attribution, which is event-adjacency, not interpretation.
- Tool-behavior leakage (edit failures, Bash retries, Grep reformulations, Read-after-Edit) is pattern-matched on structured tool inputs and results. Counting.
- The behavioral-gate decision (reasoning signals license behavioral signals) is a structural rule on counted signals, not an interpretation of them. It says "these counted things contribute when those other counted things are non-zero" — no model-in-the-loop, no judgment.

**Rejected alternatives, roughly in order of ambition:**

1. **NLP-based mention resolution.** Disambiguate "filters.jsx" among three candidates by understanding the thinking-block context. Requires a classifier, an embedding model, or an LLM in the loop. Rejected.
2. **Sequence features via semantic comparison.** Thinking→action→thinking triples where the post-action block "registers surprise" or the action "matched the announced intent." Requires understanding what was announced and whether the outcome matched it. Regex on file names catches ~40% and misses the semantic core. Rejected; already removed from the plan.
3. **User correction detection.** Classifying user messages as corrective, supportive, or continuation. Small NLP task, false positives on polite language. Rejected above.
4. **File-intrinsic complexity via abstraction analysis.** Measuring how abstract a file is via identifier names, type systems, or embedding-based "conceptual density." No defensible metric without ML in the loop. Rejected in favor of cyclomatic complexity (Tier 2, Python-only).
5. **LLM-as-validator on the score function itself.** Run an LLM over session logs and ask "did Claude struggle, and on which files," then compare to the scan's rankings. Rejected — see "Validation: human read of excerpts, not LLM-as-judge" below.

**Why:** three reasons, in order of importance.

*Defensibility.* Every kept signal can be explained in one sentence. "We count the word 'wait' per 100 words of thinking text." "We count Edit tool calls that returned an error." The interpretation-based alternatives require saying "we use a model to judge whether Claude registered surprise," and then the follow-up question is which model, how calibrated, and against what ground truth. v1's scope doesn't include answering that defensibly.

*Compute ceiling.* The full-scan architecture ran in 0.24 seconds on 73 sessions (T2.4). An LLM-in-the-loop signal — even a small model — would add seconds to minutes per session. A 100-session scan would be 5-10 minutes instead of ~0.3 seconds. The silent-execution UX (matching `coverage.py` conventions) breaks down. Even more pointedly, the `friction session` live command becomes infeasible in its current sub-second form.

*Reproducibility and honest limits.* Counting operations are deterministic. The same corpus scored twice gives the same ranking. LLM-based signals introduce stochasticity and model-version dependency. A v1 release that says "we used GPT-4o-mini to infer intent" ages badly the moment the model changes.

**Known limit:** the loss is real, not hypothetical. On large codebases with same-basename files, ambiguous mentions degrade to temporal-proximity attribution, which is strictly weaker than understanding which file Claude meant. On sessions where Claude's thinking reasons about a file without naming it explicitly, the signal attribution is approximate. Some friction events that a human reader would clearly attribute to a specific file — because they read the thinking block and understood — get unattributed or mis-attributed.

**v2 territory.** An LLM-in-the-loop pass over the thinking blocks is the obvious upgrade path. Two shapes are worth distinguishing:

- **Retrospective scan with LLM enrichment.** A full-corpus scan could optionally run an LLM pass to resolve ambiguous mentions, classify thinking-block intent, and score announce-vs-outcome mismatches. Adds minutes to the scan, runs on demand, opt-in via a `--deep` flag or similar. Compute budget: small local model or a rate-limited API call, batched across blocks. This is the natural home for the signals rejected above.

- **Live session command with LLM in the loop.** `friction session` currently runs sub-second because it's pure counting. A `--deep` or live-LLM variant could run a model against the session's thinking blocks for richer real-time analysis — but only in contexts with enough compute headroom (local hardware, or a running server). Not every demo environment has that; making it an explicit second mode is cleaner than forcing it into the default path.

Both are v2 because both require ML-ops infrastructure v1 doesn't have time for: model selection, prompt calibration, cost accounting, failure handling, and most critically, validation that the model's output is actually better than the counting-based signal it replaces. Without that validation, adding an LLM makes the signal *feel* richer without being demonstrably more accurate.

**The v1 stance, stated plainly:** counting is boring and honest. Interpretation is exciting and opens the door to a different project. Ship the counting tool first.

---

## Validation: human read of excerpts, not LLM-as-judge

**Decision:** the score function is validated by reading the marker-highlight excerpts on real corpora and judging whether the rankings are interpretable. Not by running an LLM over session logs to produce a second opinion.

**Rejected alternative:** prompt an LLM with session logs ("here's a session, did the AI struggle, on which files, explain your reasoning") and compare its output to the scan's rankings. Use disagreements as a calibration signal.

**Why:** the LLM-as-judge move imports the failure mode v1 was deliberately built to avoid. The LLM doesn't have ground truth — it reads the same thinking blocks the scan reads and produces a verdict. Agreement validates nothing (both layers ran on the same input). Disagreement provides no adjudication path, because resolving disagreement requires going back to the actual thinking blocks — which is what the marker-highlight excerpts already let a human reader do directly. The LLM layer adds cost and stochasticity without adding ground truth.

The validation that *does* matter is the engineer who knows the codebase reading the rankings, reading the highlighted excerpts, and judging whether the ranking matches the lived experience of those sessions. That's calibrated against memory and context an LLM doesn't have. It's also the validation that's reproducible across reviewers — anyone with access to the codebase and the excerpts can run the same check.

The temptation to reach for an LLM here is real and worth naming: it's faster than reading excerpts, and it feels like a second opinion. But it's not a second opinion — it's the same data interpreted by an unvalidated tool, and using it to validate a validated tool is backwards.

**Known limit:** human read of excerpts is slower than an automated check would be, and doesn't scale beyond a single reviewer. v2 territory: a calibration suite where domain experts hand-label friction on a sample of files and the score function is fit (or validated) against those labels. That's a real validation methodology — labels are ground truth, not another interpretation layer. Out of scope for v1; the cost of building it isn't justified at this scale.

**Where LLM-in-the-loop *does* belong:** as an optional enrichment feature in v2 (`--deep` mode), which is a different decision — see "Signal extraction: counting, not interpretation" above. Building an LLM into the *product* as opt-in enrichment is interesting v2 work. Using an LLM to *validate* v1's score function is a category error.

---

## Normalization: presence/intensity split for sparse-positive signals

**Decision:** signals whose distributions are zero-mode with a positive tail (most blocks contain none of the signal, some blocks contain several) are normalized using a presence/intensity split, not robust z-score. File-level contribution = (fraction of attributed blocks containing any signal) × (mean rate among signal-bearing blocks). Continuous-around-a-center signals (block length, reasoning-to-output ratio) keep robust z-score. The two methods coexist in the scoring function; a signal's `BaselineStat.kind` discriminator picks which method runs.

**Rejected alternatives:**
- *Robust z-score for all signals.* The previous default. Collapses on sparse-positive signals because median = 0 and MAD = median(|x − 0|) = 0, producing division by zero and clamping every block's contribution to zero.
- *Higher percentiles instead of MAD.* Replace the spread estimator with an interquartile range or p75 / p95 spread. Tested against the data: at 66% zero rate, p25 and p50 are both zero too. Doesn't help.
- *Constant floor under MAD (`max(MAD, ε)`).* Cheap patch that lets z-scores compute. Produces extreme z-scores for any positive observation because the divisor is artificially tiny. Inverts what z-scoring is supposed to do.
- *Threshold detector (drop the rate, count "above threshold or not").* Flattens intensity. Loses the information carried by the positive tail's spread.
- *Drop the signal entirely.* Possible for individual signals (weight tuning may decide this for `question_rate_per_100w`), but not a general normalization fix.

**Why:** measured on two corpora during the marker baseline reshape design session (April 27, 2026). On both attune (601 thinking blocks) and a brownfield codebase (466 thinking blocks), `markers_per_100w` showed exactly **66.1% zero rate** with a healthy positive tail (p25/p50/p75 of 0.60/1.07/1.47 on attune, 0.58/0.88/1.94 on brownfield among positives). The 66.1% match across two unrelated codebases is structural — a property of how Claude uses extended thinking, not a property of any one codebase. The shape is consistent and the positive tail has usable spread, which is exactly the case presence/intensity split was designed for.

The presence/intensity split keeps both pieces of information: how often the signal fires on a file, and how intense it is when it fires. Both factors are bounded and interpretable in their own right (rate ∈ [0, 1], intensity in marker-rate units). The product is per-corpus comparable without needing baselines to compute. Per-corpus baselines still exist for context ("this corpus has 34% marker-bearing blocks; this file has 60% — unusually high") but the score doesn't divide by anything that can be zero.

**Scope as shipped:** v1 implements presence/intensity split for `markers_per_100w` only. `question_rate_per_100w` is sparse-positive too (~7% positive rate on both corpora — much sparser than markers) but its scoring function role is deferred to weight tuning, which decides whether the signal earns its keep at all. Other signals with related shapes (`tool_use_coupling_rate`, `leakage_events_per_session`) are out of scope of this decision; they have their own distinct failure modes (the former is degenerate-low rather than zero-mode) and are addressed by separate tasks.

**Known limit:** the per-file mean intensity is computed over a small sample when a file has few attributed blocks. A file with 3 attributed blocks where 1 contains markers gives presence_rate = 0.33 and intensity = (whatever that one block's rate was). At small N, the intensity estimate is noisy. Mitigated structurally by the behavioral-gating rule (see "Signal set" above) — files without reasoning signal don't surface regardless of N — but small-N reasoning-signal-positive files can still rank with one or two attributed blocks. Observed once on attune: a single-block plan file (swift-mixing-thompson.md, N=1) promoted to rank 3 in calm mode under presence/intensity. Honest signal at small sample; documented in the README's known-limits section rather than thresholded out.

**Why this is a permanent shape decision, not a calibration choice:** the principle — *normalization method is signal-shape-driven, not corpus-driven* — applies to any future signal added to the scoring function. New signals get classified by shape at design time and routed to the appropriate normalization. This is the discipline that future-proofs the scoring function against the same kind of silent collapse the markers signal experienced for several phases before being caught.

---

## Attribution noise filter: presentation-layer cut, not pipeline-stage filter

**Decision:** the built-in `IGNORE_PATTERNS` filter (and its configurable extension) operates at FileFriction-assembly time only. Ignored paths participate normally in parsing, attribution, leakage detection, baseline computation, and per-file scoring. They are dropped when assembling `report.files`, not before.

**Why this and not pipeline-stage filtering:**

The corpus baseline is a statistical reference for what's normal in this corpus's thinking — marker presence rate, block length distribution, question rate, etc. It is computed at the block level: every thinking block contributes regardless of which file it ends up attributed to. That semantic — "baselines describe the corpus's thinking, period" — is what makes per-file scores comparable across files within the same run.

Three reasons in order of importance. *Calibration stability:* ignore-list edits are presentation choices ("don't show me `.env`"), not statistical claims ("`.env`-shaped thinking isn't part of this corpus's character"). Filtering at parser or baseline stage couples the two — adding `.lock` to an ignore list would silently shift the marker-rate baseline and reshape z-scores of files that survive, making the friction map move when the user expected only its row count to change. *Multi-file-attribution:* most thinking blocks attribute to several files at once; cleanly excising "ignored content" from baseline requires a policy on mixed-attribution blocks (drop them? down-weight? keep them?), each of which is a non-trivial design call dependent on per-block attribution composition. Presentation-layer filtering avoids the question. *Local failure mode:* a presentation-layer cut fails as "wrong row in the table"; an upstream cut fails as "all rows in the table moved by an unknowable amount." The former is debuggable; the latter is not.

**Rejected alternatives:**

- *Filter at parser stage* — drops ignored files from `tool_usage_by_file` and `leakage_by_file`. Cheaper memory, same baseline behavior. Rejected because it makes the filter's effect non-local and harder to audit: bug reports of the form "why did adding `.lock` to my ignore list change storage.py's score?" become hard to reason about.

- *Filter at baseline stage (block-level)* — exclude blocks whose only attributions are to ignored files. Cleanly addresses the "ignored thinking shouldn't shape the reference" intuition, but introduces a multi-file-attribution policy question (drop blocks with mixed ignored + real attributions? keep them with reduced weight?) and couples ignore-list changes to baseline drift. Rejected on calibration-stability grounds: ignore-list edits should hide files, not reshape scores of files that survive.

- *Filter at score stage* — set ignored files' scores to zero rather than dropping them. Same statistical effect as presentation-layer filtering but slower and adds a special-case branch in scoring code. No advantage; rejected on simplicity.

**Pin:** `test_filter_does_not_affect_baselines` in `tests/test_report.py`. Constructs two corpora differing only by an Edit on an ignored path (`.env`) plus its thinking block. Asserts (a) the ignored path is absent from `report.files`, and (b) `corpus_baseline.markers_per_100w.n_blocks` reflects the ignored block (i.e. the filter did *not* leak upstream of baseline computation). Leg (b) is the structural tripwire: if a future change moves filtering into `_interesting_files`, the parser, or attribution, baseline stops counting ignored-path thinking and (b) fails.

**Reversibility:** if a future corpus shows that block-level filtering materially changes rankings of real files (i.e., ignored files' thinking is dominating the baseline in a way that washes out real signal), the upgrade path is block-level: add a "block excluded from baseline if all attributions are ignored" rule in `compute_corpus_baseline`, keep the file-level presentation filter unchanged. Cost: one new policy decision (mixed-attribution blocks), one new test. Not prefactored; the property is not currently observed.

---

## Attribution: co-location rule excludes thinking-only friction

**Context:** The friction score attributes a thinking block to files via the co-location rule — files explicitly named in the block (Tier 1 exact path, Tier 2 unique basename within session-touched files) or, when the block names no file, files acted on by tool_use calls within ±N=3 events of the block's position. The rule was chosen for defensibility: every attribution traces to an exact match or a measurable temporal-proximity rule, not to interpretation. Cross-corpus hand-adjudication surfaced a class of friction the rule cannot see: rhythm breaks that occur entirely inside thinking, with no tool_use in their proximity window and no file named in the block. Two attune sessions out of 13 (`867b19ed`, `d9489e49`) showed this shape; brownfield's 12-session sample did not produce the mode but cannot rule it out.

**Decision:** Accept the gap. The co-location rule stays as-is; thinking-only friction is documented as a known unattributable case rather than a bug. Hand-adjudication confirms the rule produces empty attribution on these sessions, and that is the rule-compliant output — the tool surfaces nothing because there is nothing it can defensibly point at.

**Rejected alternatives:**

- *Widen the temporal-proximity window beyond ±N=3.* Larger windows attribute thinking to tool_use calls farther away in event time, which means attributing friction to files Claude was *also touching*, not files the friction is *about*. The mention-vs-attention decoupling established by the marker work and reinforced by the cluster-gap finding says distance matters: events that aren't co-temporal aren't co-causal. Widening converts the gap into a false-attribution problem — the local failure mode shifts from "no signal where friction lives" to "wrong file where friction lives," which is worse.

- *Synthesize an attribution from the thinking text itself via NLP or LLM-in-the-loop.* Resolves ambiguity at the cost of importing interpretation into the attribution path. Rejected on the same principle that drove the rejection of NLP mention resolution generally: every kept signal must be explainable in one sentence with no model in the loop.

- *Attribute to all session-touched files as a fallback when no co-located file exists.* Spreads thinking-only friction across the whole session's file roster, destroying per-file granularity. Rejected for the same reason multi-file attribution uses 1/N rather than full credit: the alternative makes per-file scoring uninterpretable.

**Pin:** No production test pins this directly — the rule's behavior on thinking-only blocks is to produce empty attribution, and the absence of attribution is the correct behavior, not a bug to test. The structural test that protects the calibration is the existing temporal-proximity boundary discipline in `tests/test_attribution.py`, which ensures the rule doesn't silently widen.

**Reversibility:** If v2 work (e.g., a per-session debugger view) produces a defensible way to attribute thinking-only friction — e.g., a sub-agent-aware attribution path that captures `<synthetic>` thinking the v1 pipeline misses, or a session-scoped fallback bucket distinct from per-file scoring — the rule can be extended without invalidating the current attribution. Cost: a new attribution category, a new test, a UI affordance for "session-level friction without file home." Not prefactored; the property surfaced on 2/13 attune sessions and 0/12 brownfield, below the threshold that justifies prefactoring.

---

## Discipline

Add entries when a reasonable alternative existed and one was picked for reasons worth remembering. Not every decision logs here — only ones where the reader-later would reasonably ask "why not the other way?" and the answer is substantive.

Phase-transition placeholders (stub parser, stub template, minimal CSS) don't belong here. Those are scaffolding, not trade-offs.