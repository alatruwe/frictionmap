# SWE-bench Adapter Spec — Designated-Reasoning Extraction (Phase 2)

*FrictionMap v2. Drafted 2026-09-06 [A]; status: Rev 2 — integrates `adapter-spec-review.md` (PR #17) and its reply (`adapter-spec-review-reply.md`). Build reference.*
*Authority: pre-registration (frozen, `v2-prereg-freeze`) §6 governs population and inclusion; this spec operationalizes extraction. Where they disagree, the pre-registration wins.*
*Substrate map: `methodology/swe-bench-recon.md`. Prior-art parser read: `scripts/data_processing/extract_enriched_encoding_all.py` + `scripts/config.py` (Zenodo 19351830).*
*Change history: rev 1 was reviewed from the handoff text and never committed; every rev-2 change traces to a review finding or a reply decision (Q1–Q11 and the accepted items). No new decisions were made in rev 2.*

## 0. Scope

**In:** designated-reasoning extraction for the 13-agent population; unit definition; attribution mapping; structural audit protocol; parse-failure definitions; seam tests.
**Out:** their action encoding (consumed from `enriched_encodings_all.csv`, separate ~20-trajectory spot-check task); v1 signal computation (Phase 3); any judge contact.
**Blindness note:** nothing here touches `sample-manifest.csv`, the relabel sheet, or judge output. `resolution_status.json`, `verified_trajectory_features.csv`, and `enriched_encodings_all.csv` are off-limits to every step in this spec (audit included). `enriched_encodings_all.csv` is fenced because it carries `is_failed` per row (Q9); Phase 3's spot-check will define a column-stripped view of it when that task is specified.

## 1. Population and registry

Dispatch keys on **submission folder**, never on their format string — their `openhands` format serves both population and excluded agents, likewise `trae`.

**Trajectories root** is an explicit argument to every entry point (`~/Projects/replication-package/dataset/trajectories/verified/` on this machine; Q11). No default path resolution. Their `scripts/config.py` is never imported at runtime: it calls `mkdir()` on its figures/results directories and resolves `RESOLUTION_FILE` at import time (Q8).

### Population (13)

| Submission folder | Their format | Our family |
|---|---|---|
| 20240402_sweagent_claude3opus | swe-agent-old | `thought` field |
| 20240402_sweagent_gpt4 | swe-agent-old | `thought` field |
| 20240620_sweagent_claude3.5sonnet | swe-agent-old | `thought` field |
| 20240728_sweagent_gpt4o | swe-agent-old | `thought` field |
| 20250511_sweagent_lm_32b | swe-agent-new | `thought` field |
| 20250522_sweagent_claude-4-sonnet-20250514 | swe-agent-new | `thought` field |
| 20250804_codesweep_sweagent_kimi_k2_instruct | swe-agent-new | `thought` field |
| 20250804_epam-ai-run-claude-4-sonnet | epam | `Thoughts` entries |
| 20251021_SalesforceAIResearch_SAGE_bash_only | messages-codeblock | `THOUGHT:` prefix |
| 20251205_sonar-foundation-agent_claude-opus-4-5 | sonar | thinking blocks |
| 20250928_trae_doubao_seed_code | trae | `<think>` tags |
| 20250524_openhands_claude_4_sonnet | openhands | think-tool args |
| 20250716_openhands_kimi_k2 | openhands | think-tool args |

### Excluded (7) — each asserted excluded by the registry check

| Submission folder | Reason |
|---|---|
| 20241029_OpenHands-CodeAct-2.1-sonnet-20241022 | undesignated narration (§6) |
| 20250612_trae | undesignated (`reasoning` key never populated) |
| 20250616_Skywork-SWE-32B | undesignated narration |
| 20250520_openhands_devstral_small | undesignated narration |
| 20250807_openhands_gpt5 | none (reasoning tokens withheld) |
| 20251127_openhands_claude-opus-4-5 | none (think-tool args severed; their `openhands-lossy`) |
| 20250415_openhands | **not in the paper's 19-agent population** (present in their registry and in the download; outside §6 entirely) |

### File-level shape expectations (per family; the §6 file-level check binds against these)

Observed on the recon sample (review §2, §6.1):

| Family | Top-level shape |
|---|---|
| `thought` field (old and new) | dict with a `trajectory` list |
| `Thoughts` entries (EPAM) | list of length 1; sole element a dict of dicts, each carrying `author_name` |
| thinking blocks (Sonar) | list of dicts with `role` and `blocks` |
| `THOUGHT:` prefix (SAGE) | dict with a `messages` list |
| `<think>` tags (Trae) | list of dicts with `role` |
| think-tool args (OpenHands) | list of dicts with `role` |

### File discovery rule (Q7)

Per submission folder: candidate files = `*.traj` + `*.json`; dedupe on stem, treating the `.traj.json` double extension as one stem; the stem must then match the instance-id pattern `<owner>__<repo>-<n>`. Files whose stem does not match (e.g. `preds.json`) are quarantined as `non_trajectory` and sit outside every rate in this spec — neither numerator nor denominator of §6, and never in the §5 sample.

**Registry acceptance checks (CC):** the registry module vendors the 20-entry `SUBMISSION_META` table (13 + 7) and records the sha256 of their `scripts/config.py` — `8f6da96e829eb6b492e55a1f5569258c129987e3d988177a2ce9b3a8822e276e` — so drift in their registry is detectable without importing it (Q8). Assert all 13 population folders resolve to an extractor; assert none of the 13 routes through `openhands-lossy`; assert all 7 excluded folders (including `20250415_openhands`) are refused by the extractor even if present on disk. Directory globbing must not be the population filter.

## 2. Unit definition — DECIDED

**Decision (Adeline, 2026-09-06): step-anchored unit.** One judged unit = the ordered concatenation of all designated-reasoning emitted between the previous action step and the current action step, attached to that current step (forward-attach).

**Rationale, recorded:** fragment granularity is a harness property, not a thinking property. The judged construct is within-unit re-evaluation (rubric scores 2–3 require a deliberation arc); a harness that flushes reasoning in small fragments would make its agents structurally unable to express that arc under a native-emission unit, importing a per-harness segmentation confound directly into the score. The v1 unit (one CC thinking block) is all reasoning before that turn's action — a per-decision-point unit. Step-anchoring matches v1's construct, not merely its surface form.

**Anchoring rules:**

1. **Decision point = action step.** A unit's anchor is always an action step. A turn carrying designated reasoning and no action is a free-standing emission (rule 2), never its own anchor; the "own anchor with `action=None`" reading is rejected (Q2). For families where reasoning is embedded in the same message as the action (`thought` field, Sonar blocks, `<think>` tags, `THOUGHT:` prefix), the emission attaches to that message's action set.
2. **Free-standing emissions (family-agnostic).** Any designated emission whose container carries no action forward-attaches to the next action step; if none follows, it forms the terminal unit (rule 3). This covers EPAM `Thoughts` entries and think-tool calls by construction, and also SWE-agent new-format steps with `action == ""`, Sonar assistant messages with no `tool_calls`, and Trae messages with no `<function=` (Q2).
3. **Terminal unit:** reasoning after the last action step forms a unit with no anchored action, kept and flagged `terminal=true`. Terminal units are systematically wrap-up summaries (observed in 6/8 files across four families) — a different genre from mid-trajectory reasoning. The audit reports the rate; the writeup keeps them stratified.
4. **Empty anchors:** action steps with no preceding reasoning produce no unit. Designated text that is empty or whitespace-only is *no emission*; the anchor is empty; zero-length units never exist (Q3). Empty anchors are common outside think-tool agents (up to 31% of steps for SWE-agent claude-4-sonnet; 19/70 EPAM `Thoughts` entries in the sample are empty strings) and are expected to dominate for think-tool agents (§6 density caveat).
5. **Concatenation joiner:** `"\n\n"`. Judge input is the concatenated text only (thinking-text-only condition holds).
6. **Reversibility rider:** every unit stores `fragment_count` and fragment boundary offsets. The native-emission unit (option A) is fully recoverable from stored metadata — parking shape, not deletion. Fragment-count distributions are a structural-audit output, reported descriptively. Note: `fragment_count > 1` was observed nowhere in the recon sample; EPAM in particular shows strict 1:1 `Thoughts`→action alternation (rev 1's "multiple entries per anchor expected" was wrong). The decision stands on its recorded rationale (segmentation confound), and B degrades to A when multiplicity is 1. The rider stays.
7. **EPAM ordering.** No ordering field exists in EPAM entries (keys are exactly `{author_name, message, input_text}`; UUID keys are not monotone); dict insertion order is the only order, and `json.load` preserves document order. Build rule: the loader never sorts keys. The gate for building anything anchoring-dependent for EPAM is the consistency check defined in §7.1. **Limitation (stated once, here):** chronological insertion order is an unverifiable assumption supported by two consistency checks (alternation regularity; next-vs-previous path resolution on the audit sample).

*Review status:* rules 2–4 were stress-tested against real container shapes in the review (review §2); the structural audit (§5) reports their rates on the full sample.

## 3. Per-family extraction

| Family | Container | Extraction locus | Notes / risks |
|---|---|---|---|
| `thought` field | `trajectory[]` step dicts, both format versions | `thought` key per step | **`history` is never read for reasoning** (Q1): old-format `history` carries `is_demo: true` demonstration thoughts (11 per file for claude3opus/gpt4, 1 per file for claude3.5sonnet/gpt4o) that `trajectory` excludes; new-format `history` drops text-only turns whose text then appears nowhere in it. Non-demo `history` thoughts equal `trajectory` thoughts 1:1 (checked in §7). `thought` ≡ `content` holds for claude-4-sonnet only (53/53, 74/74), not lm_32b (0/34, 0/15 — `content` carries the `<function=` XML, `thought` the prose): the recon generalization was agent-specific; no extraction consequence, since `thought` is the only key read. |
| `Thoughts` entries | UUID-keyed dict (list of 1 dict) | entries with `author_name == "Thoughts"`; text field = **`message`** (`input_text` is the empty string on 70/70 `Thoughts` entries; matches `substrate_class_examples.md`) | Entry keys are exactly `{author_name, message, input_text}`. Ordering per §2.7 and §7.1. Sample shows strict 1:1 `Thoughts`→action alternation; rule 2 still applies by construction. |
| `THOUGHT:` prefix | assistant message content | first `THOUGHT:` occurrence to end boundary per §4 rule | End boundary is ours; provenance-tracked (§4). |
| thinking blocks | `blocks[]` in assistant messages | `block_type == "thinking"`; text under **`content`** (text blocks use `text`) | Block order is always `(thinking, text)`; exactly one thinking block per assistant message in the sample (75/75). Tool calls live in `additional_kwargs.tool_calls`, not `blocks[]` (which never carried `tool_use` in the sample). `num_tokens` field present; stored as metadata, not used. |
| `<think>` tags | assistant message content | `<think>` opener through the **last** `</think>` in the message (Q4, option B) | **Not low-risk.** 7/36 sampled messages carry one opener and 2–4 closers; text between successive closers reads as continued reasoning. Basis for B: no `<function=` occurs before the last closer in any sampled message (36/36). Per affected unit, store the first-closer offset so option A (first closed span only) is recoverable from metadata. `rule_version` provenance like SAGE's (§4). The affected-message rate is an audit output (§5). |
| think-tool args | `tool_calls` where `function.name == "think"` | `arguments` is a JSON string; parse it and read key `thought` | Think calls are singleton messages (no other tool call in the same message). Sparse (~2–3/trajectory). Zero-unit trajectories are legitimate (§6). |

## 4. Boundary rules (SAGE, Trae) — templates with provenance

**Derivation protocol (both rules):** rule inferred from a deterministic inspection sample, blind to resolution status, no marker counting. Validated by the parse harness on a **disjoint** sample. The inspection sample and the rule as derived are logged below; post-derivation changes to either rule are §9-logged deviations. Each rule carries a `rule_version` that every unit it produces records (§9).

### 4.1 SAGE end-boundary rule

**Refined template (Q5), to be derived:** first `THOUGHT:` occurrence through the first ```` ```bash ```` fence opener. Text before the first `THOUGHT:` is undesignated and excluded. No `THOUGHT:` in the message → no emission. No ```` ```bash ```` fence → the emission runs to end of message and is free-standing or terminal per §2.

*Why the rev-1 "first code fence" template was replaced (review §4):* on the two recon files (59 assistant messages) `THOUGHT:` sits at offset 0 on 58/59 and follows 129 chars of prose on 1/59; every message has exactly one ```` ```bash ```` fence with no text after its close; 1/59 has two non-bash fences (quoted output) *before* the bash fence, which "first code fence" would have cut at char 389 of 1331.

- Inspection sample (logged): `20251021_SalesforceAIResearch_SAGE_bash_only/astropy__astropy-12907.traj.json`, `20251021_SalesforceAIResearch_SAGE_bash_only/astropy__astropy-13033.traj.json` (the two recon files). Derivation and validation samples must be disjoint from these.
- Rule as derived: [filled at derivation; `rule_version` assigned then]
- Validation sample + result: [filled by CC harness]

### 4.2 Trae `<think>` boundary rule

**Rule (Q4, option B):** `<think>` opener through the **last** `</think>` in the message, as stated in §3. First-closer offset stored per affected unit (option A recoverable). Affected-message rate is an audit output.

- Inspection sample (logged): `20250928_trae_doubao_seed_code/astropy__astropy-12907.json`, `20250928_trae_doubao_seed_code/astropy__astropy-13033.json` (the two recon files; 36 assistant messages, 7 affected). Validation runs on audit-sample files disjoint from these.
- Rule as derived: [filled at derivation; `rule_version` assigned then]
- Validation sample + result: [filled by CC harness]

## 5. Structural audit protocol — frozen rule, facts to follow

Runs on the completed local download, **after the extractors exist** (outputs 1–4 are unit-level; only the raw-structure censuses in §7 precede the extractors). Same fence shape as recon: **structure only; no resolution contact; no marker counts; no signal values; no v1 code over trajectories.**

- **Sample:** per population agent, take the discovery-passing files (§1 rule — `non_trajectory` files never enter the sample), sort filenames bytewise, and walk from index 0 taking every ⌈n/50⌉-th file (~50/agent, ~650 total). Deterministic, spans repos (recon's astropy-only caveat), no seed needed.
- **"Words"** = whitespace-split tokens.
- **Outputs, all descriptive:**
  1. Emission-per-anchor multiplicity distribution per family (EPAM especially).
  2. Unit length distribution (words) per agent — feeds the pre-registration §5 length-shift limitation, reported next to κ context.
  3. Presence-per-trajectory: fraction of trajectories with ≥1 unit, per agent. Under §6 this is agent behavior, reported descriptively; it is not a failure threshold.
  4. Terminal-unit and empty-anchor rates. Terminal units are stratified as a genre (wrap-up summaries, §2.3) and that stratification is carried to the writeup.
  5. SAGE boundary-rule validation counts (from the disjoint harness sample), plus SAGE anomaly rates: `THOUGHT:` at offset ≠ 0; non-bash fences before the bash fence; missing bash fence.
  6. Trae stray-closer rate (messages with more than one `</think>`), i.e. the option-B-affected rate.
- **What the audit may not do:** change the unit definition (decided, §2), join outcome data, or rank anything.

## 6. Parse-failure definitions (the >10% rule binds against these)

- **File-level failure:** JSON unreadable, or top-level shape does not match the registry's file-level shape expectation for that submission's family (§1 table).
- **Unit-level failure (Q6):** the file parses but the family's designated **structure is absent** — no `thought` keys in `trajectory[]` steps; no `Thoughts`-authored entries; no thinking block in any `blocks[]`; no `THOUGHT:` occurrence anywhere in the assistant messages; no `<think>` tag anywhere; not applicable for think-tool agents. Zero units with the structure present (every designated slot empty or whitespace-only, or no think calls) is agent behavior, not extraction failure — the audit reports it descriptively (§5.3). No numeric threshold exists; the rule is computable now.
- **Denominator (Q7):** deduped files whose stem matches the instance-id pattern (§1 discovery rule). `non_trajectory` files are quarantined and sit outside both numerator and denominator.
- **Per-agent rate:** (file-level + unit-level failures) / instance-id-stem files. `>10%` is strict (10.0% does not drop). >10% → agent drops with documented handoff (§6 pre-reg, measure-then-dispose).
- A trajectory that parses but yields zero *action* steps is not a failure under this section.
- Quarantine path: failing files listed under `quarantine/` with the failure class (`file`, `unit`, `non_trajectory`); nothing silently skipped (their parser's silent `n_skip` pattern is explicitly not inherited).

## 7. Seam tests (gates; run against the real download at the new root)

1. **EPAM ordering (gate for §2.7, redefined):** there is no ordering field to compare insertion order against, so the rev-1 timestamp test cannot pass or fail. The gate is now: (i) alternation-regularity check on the audit sample — every action entry is preceded by exactly one `Thoughts` entry, no consecutive `Thoughts` entries (recon sample: 0 consecutive in 138 entries); (ii) next-vs-previous path-resolution check — for each `Thoughts` entry naming a `.py` file, record whether the path resolves to the *next* action's `input_text`, the *previous* action's, both, or neither. Pass criterion: among entries whose named path resolves to exactly one adjacent action, next-resolutions strictly exceed previous-resolutions on the audit sample; entries resolving to both or neither are excluded. Rationale, recorded: the check exists to falsify reversed or scrambled order — which would produce previous-dominance — not to prove chronology; the §2.7 limitation already owns that asymmetry. The recon sample (next 3, previous 0, both 1, neither 2) passes it, but the gate binds on the audit sample, not on n=6. Plus the build rule that the loader never sorts keys. Pass = EPAM anchoring is built; fail = EPAM needs its own ordering rule before build.
2. **File discovery (now runnable — dataset readable at the new root):** their `*.traj` + `*.json` glob, stem dedupe, `.traj.json` double-extension handling, instance-id pattern, `non_trajectory` quarantine — verified per submission directory against actual contents (review probe 4, deferred there, runs here for real). Includes the 9,893-vs-9,374 reconciliation: per review §7.2, `20250415_openhands` at ~500 plus non-trajectory files (e.g. `preds.json` in `20250522_sweagent_claude-4-sonnet-20250514`) should account for the difference — verify with per-directory counts and record the result.
3. **EPAM text field — resolved:** `message` (`input_text` empty on 70/70 `Thoughts` entries; matches `substrate_class_examples.md`).
4. **Sonar block type — resolved:** `block_type == "thinking"`, text under `content`.
5. **SAGE rule validation:** §4.1, disjoint sample.
6. **Their `target_file` sparsity — confirmed from code:** `_classify_bash_command` returns `target_file=None` on every branch; `file_editor` → `None`. Paths come only from structured `str_replace_editor`/`str_replace_based_edit_tool` args, EPAM `Str Replace Editor`, and old SWE-agent `open`/`create`/`edit`. So their `Pr` can never fire for SAGE, for bash-mediated edits in any format, or for Trae-doubao (their trae parser never reads the `<function=` XML and likely misreads prose ``` fences as commands; 14/36 sampled messages carry such fences). Recorded here because it feeds the Phase 3 spot-check of `enriched_encodings_all.csv`: SAGE and Trae-doubao rows are oversampled there.
7. **Trae tag-balance census:** per assistant message, count `<think>` openers and `</think>` closers; report the multi-closer rate and confirm no `<function=` precedes the last closer.
8. **SAGE structure census:** `THOUGHT:` offset distribution, fence languages and their order, text after the closing fence.
9. **SWE-agent `trajectory` vs non-demo `history` equality:** for old-format files, `trajectory[].thought` equals the `thought` of non-`is_demo` assistant `history` entries 1:1; for new-format files, `trajectory` step count minus `history` assistant-message count equals the number of text-only turns. Confirms `trajectory[]` is the complete, demo-free container (Q1).

## 8. Attribution mapping — DECIDED scope

- **unit → trajectory:** the only mapping the registered analyses (Q1, Q2 operationalized tests) require. Trivial; always present.
- **unit → file (Q10):** Q2's "where the trajectory format permits" implemented as a **reimplementation of tiers 1–2 of v1's mention attribution** on unit text plus the touched-path set produced by the path-extraction layer below. (Rev 1's "reused as-is, text-level, format-independent" was wrong: v1 tiers 1–2 match thinking text against the session's tool-derived path index, and tier 3 is temporal proximity to `tool_use` events.) Tier 3 is **not rebuilt** — superseded by step-anchoring, since the unit's anchor already *is* the adjacency tier 3 inferred; instead every unit ships `anchor_files` metadata from its anchor's path extraction. Acceptance: a fixture test comparing the reimplementation's tier-1–2 output against the pinned callable — `attribute_thinking_blocks` in `src/frictionmap/attribution.py` at `e2d6db2` — on own-corpus blocks. **Fixture-block selection must not open the sealed `sample-manifest.csv`:** draw from the anchor sessions (`methodology/anchor-sessions.txt`) or arbitrary session files. Logged-deviation wording for the writeup: "mention tiers reimplemented on adapter output, fixture-verified against the pin; proximity tier superseded by step-anchored units." Descriptive use only.
- **action → file (path-extraction layer):** required to *compute* reread_bursts and edit_churn (same-file event counts), not attribution polish. Per-format extraction of file paths from structured tool args **and from bash command strings**, per a written rule table whose scope is: path arguments of `cat`/`head`/`tail`/`less`/`sed`/`awk`/`grep`/`rg`; `python <script>`; `>`/`>>` redirect targets; `cd X && …` prefix stripping before the rules apply. Their parser leaves these `None`. SAGE depends on this entirely. Format notes: EPAM action `input_text` is a Python-repr dict (68/68) → parse with `ast.literal_eval`, never `json.loads` and never their `replace("'", '"')` fallback (breaks on apostrophes inside commands); SAGE user-message observations are Python-repr list strings. Own tests at build time (§9.7); spec'd as part of the extractor build [CC].

## 9. Deliverables and acceptance (extractor build, [CC], est. 2–3 blocks per tracker; review build plan est. 2.8)

Sequenced per the review's build plan (accepted in the reply): fence first, anchoring engine before family extractors, audit after extractors.

1. **Registry + discovery + blindness tripwires.** Registry module keyed on submission folder, vendored 20-entry table, recorded `config.py` sha256, §1 assertions; file-discovery function per §1 (`*.traj`/`*.json`, stem dedupe, `.traj.json`, instance-id pattern, `non_trajectory` quarantine); trajectories root as an explicit argument. **Tripwire tests built here, first:** monkeypatch `builtins.open` and `Path.open` to raise on `resolution_status.json`, `verified_trajectory_features.csv`, `enriched_encodings_all.csv`, and any `results/` path — mirroring `tests/test_judge_blindness.py`. Gated on: nothing.
2. **Seam-test suite (§7)** incl. the real probe 4 (file discovery on the download). Runs on the audit sample; emits a report. Gated on: 1.
3. **Family-agnostic anchoring engine:** ordered (emission | action-step) events → units per §2 with `fragment_count`, offsets, `terminal`, empty-anchor handling, `emission_kind`; synthetic-sequence tests for rules 2–4. Gated on: nothing beyond Q2/Q3 (answered).
4. **Family extractors** emitting the event sequence: `thought` (`trajectory[]`, both versions), Sonar, think-tool — unconditionally; EPAM after the §7.1 alternation check passes; Trae and SAGE after their §4 derivations are logged. Unit provenance fields: submission, file, anchor step index, `family`, `rule_version` (SAGE, Trae), `container`, `emission_kind` (`in-step` / `free-standing` / `terminal`), fragment offsets, and the Trae first-closer offset where applicable. Gated on: 3; 2 for EPAM; §4 for Trae and SAGE.
5. **Parse-validation harness (§6):** per-agent file-level + unit-level rates, strict >10%, quarantine listing with failure class, no silent skips. Gated on: 4.
6. **Structural audit script + report (§5)**, outputs 1–6. Gated on: 4.
7. **Path-extraction layer (§8)**, parallel-capable (independent of 3–6): structured args per format; bash rule table; EPAM `ast.literal_eval`. Acceptance = per-format fixture tests + a table-driven test over the bash rule table.
8. **Fence, restated:** no contact with `resolution_status.json`, `verified_trajectory_features.csv`, or `enriched_encodings_all.csv` anywhere in this phase — enforced structurally by deliverable 1's tripwires; audit and extractors take no path to those files; their `config.py` is never imported.
