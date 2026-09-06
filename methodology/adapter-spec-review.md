# Adapter Spec Review — Designated-Reasoning Extraction (Phase 2)

*Review of `swe-bench-adapter-spec.md` (DRAFT, 2026-09-06). Reviewer: CC, 2026-09-06. Review only — no extractor code, no spec edits.*
*Inputs read, in order: the spec (as handed off; not yet on disk in `methodology/`), `swe-bench-recon.md`, pre-registration §6 (frozen), `substrate_class_examples.md`, and the replication package's `scripts/data_processing/extract_enriched_encoding_all.py` (sha256 `4754346e…875a0fe`) and `scripts/config.py` (sha256 `8f6da96e…822e276e`).*

## 0. Fence statement and environment limits

**Affirmed:** this session opened neither `resolution_status.json` nor `verified_trajectory_features.csv`. It also opened no `results/` directory of the swe-bench experiments clone (those hold resolved-id lists) and no `enriched_encodings_all.csv`. No marker counts, no signal values, no v1 code was run over any trajectory.

**Environment finding (affects Task 2):** the full download exists at `~/Documents/zenodo/replication-package/dataset/trajectories/verified/` (the handoff path is relative to the package). In this session every file under `dataset/` and `data/` returns `EPERM` on open and on directory listing, sandboxed or not; `stat` works. Their `.py` scripts under `scripts/` are readable. This is macOS Files-and-Folders protection on `~/Documents` for the process hosting this session, not a permission-bits issue. Consequences:

- Probes 1–3 ran on the recon sample (`~/Projects/experiments/recon_samples/`, first-2-alphabetical per agent, 26 files across the 13 population agents) instead of the download, at reduced n (EPAM 2 files instead of 5, Sonar 2 instead of 3).
- Probe 4 (file discovery on the 13 download dirs) is **deferred**: it needs directory listing. Partial evidence from their download script is recorded in §7.2 below.
- The built seam suite (spec §7) cannot run until the download is readable from the build session. Fix is outside the repo: grant the terminal/IDE app access to Documents, or move/symlink the dataset under `~/Projects`.

Every file opened is listed in Appendix A.

## 1. Per-section verdicts

| § | Verdict | Summary |
|---|---|---|
| 0 Scope | CLEAR, one omission | `enriched_encodings_all.csv` carries an `is_failed` column per row (their `main()`, lines 1298–1309). It is an outcome file. Phase 2 does not touch it, but the blindness note should name it so Phase 3's spot-check strips the column. |
| 1 Population/registry | CLEAR | All 13 folder→format rows and all 7 exclusions verified against `SUBMISSION_META` (20 entries = 13 + 7). One sourcing nit and one acceptance-check design issue, §2 below. |
| 2 Unit definition | Decided; rules 1–4 stressed | Rule 1 AMBIGUOUS (text-only turns). Rule 2 CLEAR once generalized beyond EPAM/think-tool. Rule 3 CLEAR. Rule 4 CLEAR once "whitespace-only designated text" is defined. Multiplicity-per-anchor is 1 everywhere in the sample, including EPAM. |
| 3 Per-family extraction | **BLOCKED** for `thought` field (one-line fix); Trae row not low-risk; Sonar/EPAM TBDs resolved | `history` ≠ `trajectory` on real files: old-format `history` carries `is_demo` reasoning, new-format `history` drops text-only turns. Spec must name `trajectory[]` and never read `history` for reasoning. Trae: 7/36 messages have stray `</think>` closers. |
| 4 SAGE rule | AMBIGUOUS | "First code fence" truncates reasoning when output-quote fences precede the bash fence; `THOUGHT:` is not always at offset 0. Refined template proposed. |
| 5 Audit | CLEAR, three small definitions | Start index of the every-k-th walk, sort key, word definition, and discovery rule applied before sampling. |
| 6 Parse-failure | AMBIGUOUS | Not computable with zero judgment calls as written: registry shape expectations are unwritten, the unit-level threshold is set after the audit that it gates, and the denominator admits non-trajectory files. All three are one-line fixes. |
| 7 Seam tests | Test 1 needs redefinition; 3, 4, 6 resolved; 2 deferred; 5 pending derivation | No ordering field exists in EPAM (third outcome). See §3. |
| 8 Attribution | AMBIGUOUS on "reused as-is" | v1 attribution is not text-only: tiers 1–2 index paths from tool_use blocks, tier 3 is temporal proximity to tool_use events. Reuse needs v1-shaped events and the §8 path layer. |
| 9 Deliverables | CLEAR with sequencing changes | Audit (9.3) needs extractors (9.4); fence (9.7) should be built first; anchoring engine should precede family extractors. |

Nothing here makes further review moot. The one BLOCKED item has an obvious fix that the spec owner can confirm in a line.

## 2. Section notes

### §0 Scope

Confirmed the parser is action-channel only: `_classify_tool_call` returns `None` for `think` (line 503), `extract_steps_epam` skips `author_name == "Thoughts"` (line 882), the lossy parser skips `[think]` steps (line 690). Reasoning extraction is entirely ours, as the tracker says.

### §1 Population and registry

- Sourcing: `config.py` lives at `scripts/config.py`, not beside the parser; the parser imports it via `parents[1]`. Cite it that way.
- `openhands` format serves six folders (two in population), `trae` serves two (one in population), `openhands-lossy` serves only `20251127_…` — spec claims hold.
- `20250415_openhands` is in `SUBMISSION_META` with `llm: "unknown"`; exclusion stands.
- **Acceptance check "import their `SUBMISSION_META`":** importing `config.py` executes `FIGURES_DIR.mkdir()` and `RESULTS_DIR.mkdir()` at import time inside the replication package, and requires an out-of-repo path at test time. Recommend vendoring the 20-entry table into the registry module and asserting against the recorded sha256 of `config.py` instead. Open question Q8.

### §2 Unit definition — anchoring rules against real containers

Observed container facts the rules must handle (recon sample, structure only):

| Family | Emission per action step | Emissions with no action in their container | Trajectory ends with an unanchored emission |
|---|---|---|---|
| `thought` (old, 4 agents) | exactly 1 per `trajectory` step (8/8 files) | none in sample | no (last step is `submit`/`exit_cost` with its own thought) |
| `thought` (new, 3 agents) | 1 per step; **empty** on 14/53, 23/74 (claude-4-sonnet), 3/34, 2/15 (lm_32b), 2/12, 4/16 (codesweep) | 1 interior step with `action == ""` and a long thought (claude-4-sonnet 12907 step 35; codesweep 12907 has one too) | no (last step `submit`, thought empty) |
| `Thoughts` (EPAM) | strict alternation Thoughts→action, 0 consecutive Thoughts in 138 entries; **empty `message`** on 6/27 and 13/43 Thoughts entries, almost always before `Run Command Line Tool` | — | yes, both files (2.2k and 2.7k-char summaries) |
| thinking blocks (Sonar) | exactly 1 per assistant message (75/75) | final assistant message: thinking + text, no tool call (2/2) | yes, both files |
| `<think>` (Trae) | 1 closed span per message (36/36), always at offset 0 | final message: think + summary, no `<function=` (2/2) | yes, both files |
| think-tool (OpenHands) | 0 for most steps; think calls are singleton messages (10/10 have no other tool call) | every think call | no in sample |

Rule-by-rule:

- **Rule 1 (decision point) — AMBIGUOUS.** "Assistant message / trajectory entry / tool-bearing entry" gives two readings for a turn that has designated reasoning and no action: it is either its own anchor (unit with `action=None`) or a free-standing emission that forward-attaches under rule 2. The two readings produce different unit counts and different judge inputs. Both interior (SWE-agent step 35 followed by `submit`) and terminal (Sonar, Trae, EPAM) cases exist. Q2.
- **Rule 2 (forward-attach) — CLEAR once generalized.** The spec lists it for EPAM and think-tool only; the same situation arises in SWE-agent new (`action == ""` steps) and Sonar (no `tool_calls`). Phrase it family-agnostically: any designated emission whose container carries no action forward-attaches to the next action step.
- **Rule 3 (terminal) — CLEAR.** Observed in 6/8 files of four families. Note for the audit: terminal units are systematically wrap-up summaries, a different genre from mid-trajectory reasoning; the audit already reports the rate, and the writeup should keep them stratified.
- **Rule 4 (empty anchors) — CLEAR with one definition.** Empty anchors are common outside think-tool agents (up to 31% of steps for SWE-agent claude-4-sonnet; 19/70 EPAM Thoughts entries are empty strings). Define: designated text that is empty or whitespace-only is *no emission*; the anchor is empty; no zero-length unit is created. Q3.
- **Multiplicity.** `fragment_count > 1` did not occur anywhere in the sample. The step-anchoring rationale is a construct decision and stands, but spec §3's "multiple entries per anchor expected; that's the point of the unit rule" for EPAM is contradicted by the data: EPAM is 1:1. The reversibility rider costs nothing and should stay.

### §3 Per-family extraction

**`thought` field — BLOCKED as written; one-line fix.** "Two container shapes; handle both" underdetermines the extractor, and the two containers differ on real files:

- Old format: `history` holds `is_demo: true` assistant messages with `thought` and `action` — 11 per file for claude3opus and gpt4, 1 per file for claude3.5sonnet and gpt4o. These are demonstration text, not the agent's reasoning. `trajectory` excludes them. Non-demo `history` thoughts equal `trajectory` thoughts 1:1 (19/19, 9/9).
- New format: `trajectory` has one more step than `history` has assistant messages when the model emits a text-only turn (claude-4-sonnet 12907: 54 vs 53; codesweep 12907: 12 vs 11). The dropped turn's text appears nowhere in `history`.

Fix: container is `trajectory[]`, key `thought`, for both format versions; `history` is never read for reasoning. Their parser's history-first order is for actions and is irrelevant here. Q1.

Also: "new format `thought` ≡ `content`" is true for claude-4-sonnet (53/53, 74/74) and false for lm_32b (0/34, 0/15 — `content` carries the `<function=` XML, `thought` the prose). No extraction consequence, but the recon generalization is agent-specific.

**`Thoughts` entries — TBD resolved.** Text is in `message`; `input_text` is the empty string on 70/70 Thoughts entries. Matches `substrate_class_examples.md`. Entry keys are exactly `{author_name, message, input_text}` on 138/138 entries. Action entries' `input_text` is a Python-repr dict (`{'command': 'view', 'path': '.'}`) on 68/68 — relevant to §8, not §3.

**`THOUGHT:` prefix — see §4.**

**thinking blocks — TBD resolved.** `block_type == "thinking"`; text is in the `content` key, whereas text blocks use `text`. The spec must name `content`. Block order is always `(thinking, text)`; `num_tokens` is `null` on 75/75; `additional_information.signature` present. Tool calls live in `additional_kwargs.tool_calls` (one per message, 73/75); `blocks[]` never carried `tool_use` in the sample. Tool messages carry `additional_kwargs.tool_call_id`.

**`<think>` tags — not low risk.** 7/36 assistant messages (4/15, 3/21) have one `<think>` opener and 2–4 `</think>` closers. The text between successive closers reads as continued reasoning and no `<function=` occurs before the last `</think>` in any message (36/36). A closed-span regex keeps only the first span. This needs a pre-committed boundary rule with the same provenance discipline as §4. Candidates: (A) first closed span only — strictest designer-boundary reading, drops the tail; (B) `<think>` through the last `</think>` in the message; (C) quarantine affected messages. The affected rate must be an audit output either way. Q4.

Secondary: Trae-doubao actions are inline `<function=…>` pseudo-XML, one per message (36/36); 14/36 messages also contain ``` fences inside prose. Their `extract_steps_trae` parses `tool_calls` or code fences, never `<function=` XML, so their action encoding for this agent likely misreads prose fences as commands. Flag for the Phase 3 spot-check (§7.6 below).

**think-tool args — CLEAR.** `arguments` is a JSON string on 10/10 calls, key `thought`; every think call is a singleton message; observation is "Your thought has been logged."; 2–3 calls per trajectory as the recon said.

### §4 SAGE end-boundary rule

Observed on 59 assistant messages (format `trajectory_format: mini-swe-agent-1`; `content` equals `extra.response.choices[0].message.content` on 59/59):

- `THOUGHT:` at offset 0 on 58/59; on 1/59 it follows 129 chars of prose. "Prefix" must mean first occurrence, with preceding text excluded (undesignated).
- Exactly one ```` ```bash ```` fence per message (59/59); no text after the closing fence (59/59).
- 1/59 has two non-bash fences (quoted output) *before* the bash fence. The spec's "first code fence" boundary would cut that message at char 389 of 1331 and drop two reasoning segments.

Refined template for derivation: first `THOUGHT:` occurrence through the first ```` ```bash ```` opener; no `THOUGHT:` → no emission; no bash fence → to end of message (free-standing/terminal per §2). Per the §4 protocol this is an inspection observation, not the derivation. The two recon files are now an inspection sample and the derivation/validation samples must be disjoint from them. Q5.

### §5 Audit

Clear. Add: (a) the walk starts at index 0 of the bytewise-sorted list; (b) "trajectory filenames" means files passing the §6 discovery rule (Q7), so `preds.json`-type files never enter the sample; (c) "words" = whitespace-split tokens; (d) the audit needs the extractors (outputs 1–4 are unit-level), so it cannot run before deliverable 9.4 — see §5 of this review.

### §6 Parse-failure definitions

Can the >10% rule be computed with no judgment calls? Not as written. Three gaps:

1. **Registry shape expectation is unwritten.** From the sample, the file-level acceptance shape per family is: `thought` → dict with a `trajectory` list; EPAM → list of length 1 whose sole element is a dict of dicts carrying `author_name`; Sonar → list of dicts with `role` and `blocks`; SAGE → dict with a `messages` list; Trae and OpenHands → list of dicts with `role`. Write these into the registry.
2. **Unit-level threshold is set after the audit it gates** ("expected ~99%, TBD pending audit"). Either fix 99% now, or drop the number: apply unit-level failure to every family whose designation is per-step structural (all six families except think-tool) and report the audit's presence rate descriptively. Q6.
3. **Denominator admits non-trajectory files.** Their glob plus stem-dedupe keeps `preds.json` (stem `preds`), which the download script will fetch for `20250522_sweagent_claude-4-sonnet` (see §7.2). Define the denominator as deduped files whose stem matches the instance-id pattern `<owner>__<repo>-<n>`; everything else is quarantined as `non_trajectory` and excluded from both numerator and denominator. Q7.

Also state: `>10%` is strict; a trajectory that parses but yields zero *action* steps is not a failure under this section; whitespace-only designated text is not a unit (Q3).

### §7 Seam tests

1. **EPAM ordering — third outcome: no ordering field exists.** Entry keys are exactly `{author_name, message, input_text}` on 138/138; UUID keys are not monotone. Dict insertion order is therefore the only order, and `json.load` preserves document order (guaranteed since Python 3.7), so there is nothing to compare it against — the test as specified cannot pass or fail. What the data does offer: strict Thoughts/action alternation (every action is preceded by exactly one Thoughts entry, 0 consecutive Thoughts), and Thoughts text that names a `.py` file resolves to the *next* action's `input_text` in 3 cases, the previous action's in 0, both in 1, neither in 2. That is consistent with document order being chronological and with forward-attach. **Consequence for §2:** forward-attach is buildable for EPAM; the HARD GATE must be rewritten as (i) alternation regularity on the audit sample and (ii) next-vs-previous path resolution, plus a build rule that the loader never sorts keys.
2. **File discovery — DEFERRED** (dataset unreadable). See §7.2 evidence below.
3. **EPAM text field — resolved:** `message`.
4. **Sonar block type — resolved:** `"thinking"`, text key `content`.
5. **SAGE rule validation — pending derivation;** observations in §4.
6. **`target_file` sparsity — CONFIRMED from code.** `_classify_bash_command` returns `target_file=None` on every branch (lines 156–201); `file_editor` → `None` (line 478). Paths come only from structured `str_replace_editor`/`str_replace_based_edit_tool` args, EPAM `Str Replace Editor`, and old SWE-agent `open`/`create`/`edit` (via `state.open_file`). So `Pr` can never fire for SAGE, for bash-mediated edits in any format, or for Trae-doubao (whose `<function=` XML their trae parser does not read at all). The Phase 3 spot-check should oversample SAGE and Trae-doubao rows.

#### §7.2 File-discovery evidence available without listing the dataset

Their `download_leaderboard_trajectories.py` keeps only S3 keys ending `.traj` or `.json` and writes each to `<sub>/<basename>` — it **flattens** nested prefixes and would silently overwrite basename collisions. The S3 layout for `20250522_sweagent_claude-4-sonnet-20250514`, as mirrored in the experiments git clone (`~/Projects/experiments`, commit 1faa91c), is nested: `trajs/<iid>/<iid>.{traj,pred,patch,config.yaml}` plus `trajs/preds.json`. After download that yields 500 `.traj` files plus `preds.json`; the `.pred`/`.patch`/`.yaml` extras are filtered by extension (the recon's re-pull used a different path and saw them). `preds.json` passes `*.json` and survives stem-dedupe → Q7. SAGE's `.traj.json` double extension is handled by their stem logic. The handoff count of 9,893 files against 9,374 paper trajectories leaves 519 unexplained; `20250415_openhands` at ~500 plus a handful of non-trajectory files would account for it, but this is unverified until a per-dir `find -type f | wc -l` can run.

### §8 Attribution mapping

- unit → trajectory: trivial, CLEAR.
- unit → file, "v1's mention-based attribution reused as-is (text-level, format-independent)": **the parenthetical is wrong.** `src/frictionmap/attribution.py` builds a per-session index of canonical paths from `tool_use` blocks' `file_paths` (tiers 1–2 match thinking text against *that* set, not against arbitrary path-like strings), and tier 3 attributes by temporal proximity to the nearest `tool_use` within ±3 events. Reusing it as-is means constructing v1-shaped `ParsedEvent`/`Block` sequences from adapter output, which requires the §8 action→file layer for every format (bash-derived for SAGE). Feasible, and it keeps the e2d6db2 pin literal, but unit→file quality then inherits action→file quality per format, and tier-3 attributions should carry v1's `low` confidence. Alternative: reimplement tiers 1–2 only on text plus the touched-path set, no tier 3. Q10.
- action → file: scope CLEAR; needs a written rule table for bash strings (`cat`/`head`/`tail`/`less`/`sed`/`awk`/`grep`/`rg` path args, `python <script>`, `>`/`>>` targets, `cd X && …` prefix). EPAM `input_text` is Python-repr (68/68) → `ast.literal_eval`, not `json.loads`; their `replace("'", '"')` fallback breaks on apostrophes inside commands and must not be inherited. SAGE user messages (observations) are also Python-repr list strings.

### §9 Deliverables and acceptance

Testable as written except: 9.2's EPAM gate (no field to test against — redefine per §7.1); 9.6 "with its own tests" has no acceptance criterion (propose: per-format fixture tests plus a table-driven test over the bash rule table); 9.7 "enforced structurally" should name the mechanism: mirror `tests/test_judge_blindness.py` — monkeypatch `builtins.open` and `Path.open` to raise on `resolution_status.json`, `verified_trajectory_features.csv`, `enriched_encodings_all.csv` (Q9), and any `results/` path; the adapter takes the trajectories root as an explicit argument and never imports their `config.py` at runtime (it resolves `RESOLUTION_FILE` and creates directories on import).

Provenance fields to add to 9.4: `family`, `rule_version` for the SAGE and Trae boundary rules, `container` (`trajectory`), and `emission_kind` (`in-step` / `free-standing` / `terminal`).

## 3. Probe results

All probes: deterministic selection (first-alphabetical in the recon sample), raw structure dumped with string truncation, no marker counting, no signal values, no outcome contact. Scripts in the session scratchpad, not committed.

| Probe | Result | Files |
|---|---|---|
| 1 EPAM ordering | **No ordering field exists** (third outcome). Insertion order is the only order; alternation and path-mention direction support it as chronological and forward-attach as correct. Consequence: §7.1 test must be redefined; forward-attach is buildable. | `20250804_epam-ai-run-claude-4-sonnet/astropy__astropy-12907.traj`, `…-13033.traj` (2 of the requested 5; download unreadable) |
| 2 EPAM text field | `message`. `input_text` empty on 70/70 Thoughts entries. 19/70 Thoughts have empty `message`. Matches `substrate_class_examples.md`. | same |
| 3 Sonar block type | `"thinking"`, text under `content`; exactly one thinking block per assistant message (75/75); none with more than one; final message has no tool call. | `20251205_sonar-foundation-agent_claude-opus-4-5/astropy__astropy-12907.json`, `…-13033.json` (2 of 3) |
| 4 File discovery | **Deferred** — dataset directories unreadable in this session. Indirect evidence in §7.2. | none opened |

Additional structure facts recorded above came from the remaining 22 recon-sample files (Appendix A).

## 4. Open questions for Adeline

Each answerable in one line.

1. **Q1 — `thought` container:** confirm `trajectory[]` only, `history` never read for reasoning? (Fixes demo leakage and text-only-turn loss.)
2. **Q2 — Rule 1:** a turn with designated reasoning and no action: its own anchor, or free-standing (forward-attach per rule 2)?
3. **Q3 — Empty designated text:** whitespace-only `thought`/`message` = no emission (empty anchor), never a zero-length unit?
4. **Q4 — Trae stray closers:** (A) first closed span only, (B) through the last `</think>`, or (C) quarantine? Rate reported either way.
5. **Q5 — SAGE template:** adopt "first `THOUGHT:` through first ```` ```bash ```` opener" as the template to derive, with the two recon files counted as inspection sample (derivation/validation disjoint from them)?
6. **Q6 — §6 unit-level failure:** all non-think-tool families with no numeric threshold, or fix 99% now, before the audit?
7. **Q7 — Denominator:** exclude non-instance-id files (e.g. `preds.json`) from per-agent rates, quarantined as `non_trajectory`?
8. **Q8 — Registry:** vendor the 20-entry `SUBMISSION_META` with `config.py`'s sha256 recorded, instead of importing it?
9. **Q9 — Fence:** add `enriched_encodings_all.csv` (carries `is_failed`) to the Phase 2 hard fence?
10. **Q10 — §8 reuse:** v1-shaped events + `attribute_thinking_blocks` (tiers 1–3, needs action paths), or tiers 1–2 only on text + touched-path set?
11. **Q11 — Environment (not a spec question):** grant Documents access to the session's host app, or move/symlink the dataset under `~/Projects`, before the build session? Nothing in spec §5–§7 can run until then.

## 5. Build plan proposal

Estimates in tracker blocks; envelope is 2–3 blocks for extractors + parse-validation harness. Gates named per task. Total ≈ 2.8 blocks, at the top of the envelope; SAGE and Trae boundary-rule derivations are [A] work outside it.

| # | Task | Est. | Gated on |
|---|---|---|---|
| 0 | Desktop resolves Q1–Q10; dataset readable (Q11) | — | — |
| 1 | Registry module: vendored 20-entry table + `config.py` sha256; §1 assertions; file-discovery function (`*.traj`/`*.json`, stem dedupe, `.traj.json`, instance-id pattern, `non_trajectory` quarantine); explicit trajectories-root argument. **Includes the blindness tripwire tests** (9.7) — built first, not last. | 0.4 | Q7, Q8, Q9 |
| 2 | Seam-test suite (§7 as redefined): EPAM alternation + path-direction check; Sonar block census; SAGE structure census (`THOUGHT:` offset, fence languages, text-after-fence); Trae tag-balance census; think-tool arg-type census; SWE-agent `trajectory` vs non-demo `history` equality. Runs on the audit sample; emits a report. **Probe 4 runs here for real.** | 0.4 | Task 1; Q11 |
| 3 | Family-agnostic anchoring engine: ordered (emission \| action-step) events → units per §2 with `fragment_count`, offsets, `terminal`, empty-anchor handling, `emission_kind`; synthetic-sequence tests for rules 2–4. | 0.4 | Q2, Q3 |
| 4 | Family extractors emitting the event sequence: `thought` (trajectory container, both versions), Sonar, think-tool — unconditionally; EPAM after task 2's alternation check passes; Trae after Q4; SAGE after the §4 derivation is logged. | 0.6 | Task 3; Q1, Q4, Q5; task 2 for EPAM |
| 5 | Parse-validation harness (§6): per-agent file-level + unit-level rates, strict >10%, quarantine listing with failure class, no silent skips. | 0.3 | Task 4; Q6, Q7 |
| 6 | Structural audit script + report (§5 outputs 1–5, plus Trae stray-closer rate and SAGE anomaly rates). | 0.3 | Task 4 (needs units) |
| 7 | Path-extraction layer (§8): structured args per format; bash rule table; EPAM `literal_eval`; fixture + table-driven tests. Feeds Phase 3 and the §8 unit→file reuse. | 0.4 | Q10; independent of 3–6, can run in parallel |

**Sequenced differently from §9, and why:**

- **9.7 (fence) first, not last.** The tripwire is cheapest before any loader exists and protects every later task, matching how the judge harness was built.
- **Anchoring engine before family extractors.** §9.4 bundles them; rules 2–4 are the spec's own flagged risk and should be tested once on synthetic sequences rather than six times inside format code.
- **9.3 (audit) after 9.4, not before.** Four of the five audit outputs are unit-level and need the extractors. Only raw-structure censuses (task 2) can precede them.
- **9.2 EPAM gate redefined** (§7.1): the timestamp comparison has nothing to compare against; the alternation/direction check is the gate.

## Appendix A — files opened this session

Replication package (readable): `scripts/config.py`, `scripts/data_processing/extract_enriched_encoding_all.py`, `scripts/data_processing/download_leaderboard_trajectories.py`. Attempted and refused (`EPERM`, not read): the `dataset/trajectories/verified/` tree and `data/enriched_encodings_all.csv` (attempted only to characterize the access failure; its first bytes were never returned). Never attempted: `data/resolution_status.json`, `data/verified_trajectory_features.csv`.

Experiments clone (`~/Projects/experiments`, 1faa91c): directory listings only, under `evaluation/verified/<13 population dirs + 20250415_openhands>/` and `…/20250522_sweagent_claude-4-sonnet-20250514/trajs/`; no `results/` content opened.

Recon sample (`~/Projects/experiments/recon_samples/`), all 26 parsed with `json.load`, structure dumped with truncation:

```
20240402_sweagent_claude3opus/astropy__astropy-12907.traj
20240402_sweagent_claude3opus/astropy__astropy-13033.traj
20240402_sweagent_gpt4/astropy__astropy-12907.traj
20240402_sweagent_gpt4/astropy__astropy-13033.traj
20240620_sweagent_claude3.5sonnet/astropy__astropy-12907.traj
20240620_sweagent_claude3.5sonnet/astropy__astropy-13033.traj
20240728_sweagent_gpt4o/astropy__astropy-12907.traj
20240728_sweagent_gpt4o/astropy__astropy-13033.traj
20250511_sweagent_lm_32b/astropy__astropy-12907.traj
20250511_sweagent_lm_32b/astropy__astropy-13033.traj
20250522_sweagent_claude-4-sonnet-20250514/astropy__astropy-12907.traj
20250522_sweagent_claude-4-sonnet-20250514/astropy__astropy-13033.traj
20250804_codesweep_sweagent_kimi_k2_instruct/astropy__astropy-12907.traj
20250804_codesweep_sweagent_kimi_k2_instruct/astropy__astropy-13033.traj
20250804_epam-ai-run-claude-4-sonnet/astropy__astropy-12907.traj
20250804_epam-ai-run-claude-4-sonnet/astropy__astropy-13033.traj
20251021_SalesforceAIResearch_SAGE_bash_only/astropy__astropy-12907.traj.json
20251021_SalesforceAIResearch_SAGE_bash_only/astropy__astropy-13033.traj.json
20251205_sonar-foundation-agent_claude-opus-4-5/astropy__astropy-12907.json
20251205_sonar-foundation-agent_claude-opus-4-5/astropy__astropy-13033.json
20250928_trae_doubao_seed_code/astropy__astropy-12907.json
20250928_trae_doubao_seed_code/astropy__astropy-13033.json
20250524_openhands_claude_4_sonnet/astropy__astropy-12907.json
20250524_openhands_claude_4_sonnet/astropy__astropy-13033.json
20250716_openhands_kimi_k2/astropy__astropy-12907.json
20250716_openhands_kimi_k2/astropy__astropy-13033.json
```

Repo files read for context: `methodology/pre-registration.md` (§2, §3, §6, §7, §9), `methodology/swe-bench-recon.md`, `methodology/substrate_class_examples.md`, `methodology/judge_harness/{README.md,units.py}`, `tests/test_judge_blindness.py`, `src/frictionmap/attribution.py`, `src/frictionmap/extraction.py` (suffix list), `~/Projects/v2_IMPLEMENTATION.md`.
