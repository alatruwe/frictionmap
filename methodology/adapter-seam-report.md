# Adapter seam report (spec §7)

*Generated 2026-09-06 by `methodology/scripts/run_adapter_seam.py` against `/Users/adelinelatruwe/Projects/replication-package/dataset/trajectories/verified`. Structure only: no resolution contact, no marker counts, no signal values, no v1 code over trajectories. Fence enforced by `tests/test_adapter_blindness.py`.*

- Audit sample rule (§5): per population agent, discovery-passing files sorted bytewise, every ⌈n/50⌉-th from index 0. Sampled: 647 files across 13 agents.
- Their `scripts/config.py`: matches vendored sha256 `8f6da96e829e…` (read as bytes, never imported).

## Verdicts

| section | verdict | stop-early |
|---|---|---|
| §7.2 File discovery (probe 4), shape table, and 9,893-vs-9,374 reconciliation | PASS | no |
| §7.1 EPAM ordering gate | PASS | no |
| §7.3 EPAM text field | PASS | no |
| §7.4 Sonar block type | PASS | no |
| §7.5 SAGE rule validation (template applied provisionally; rule_version unassigned) | INFO | no |
| §7.6 Their `target_file` sparsity | INFO | no |
| §7.7 Trae tag-balance census | FAIL | no |
| §7.8 SAGE structure census | INFO | no |
| §7.9 SWE-agent `trajectory` vs non-demo `history` | FAIL (identity as written); containment PASS | no |
| Think-tool structure (supports §3) | INFO | no |

## Findings for the checkpoint

- Probe 4: discovery rule and §1 shape table hold on every directory; 1 `non_trajectory` file (preds.json); 0 file-level failures across all 6404 population files.
- Reconciliation: 9893 files − 500 (`20250415_openhands`) − 1 non-trajectory = 9392 vs paper 9374: residual 18, not explained by anything visible to discovery or the population file-level census (the review's 'handful of non-trajectory files' guess was 1). Candidate explanation, unverifiable without their pipeline: per-agent counts the paper reports after its own parser's silent skips.
- EPAM gate PASS: (i) 0 consecutive `Thoughts`, 0 unpreceded actions in 4748 entries; (ii) next 73 vs previous 8 (basename variant; full-token 72 vs 4). 48/50 files end on a `Thoughts` entry (terminal unit).
- SAGE: §4.1 refined template yields an emission on 1851/1852 messages of the disjoint sample; `THOUGHT:` at offset 0 on 1848, >0 on 3, absent on 1; bash fence present on all 1852; non-bash fences before the bash fence on 10 (the rev-1 template's cut class).
- Trae: multi-closer rate 162/1712 (9.5%). **Spec-contradicting fact:** 4 messages carry `<function=` before the last `</think>` (§3 basis for option B said 0/36); in all of them the opener is unclosed (an abandoned call), 0 have a closed call there. Goes to the §4.2 derivation slot.
- SWE-agent: old-format 1:1 equality holds on every sampled file (demo thoughts excluded by `trajectory[]`); the new-format arithmetic identity as written fails (31/50, 47/50, 45/50) because `history` keeps some text-only turns — but containment (history ⊆ trajectory, ordered) holds everywhere. No extraction consequence; §3's description of new-format `history` is inexact.
- **For the checkpoint:** 27 of 54 new-format text-only steps carry a harness exit string (`Exit due to…`) in the `thought` slot; under §2.2–2.3 these would become emissions (mostly terminal units). The spec does not distinguish harness strings from model text in the designated slot.

## §7.2 File discovery (probe 4), shape table, and 9,893-vs-9,374 reconciliation

Per submission directory, from the §1 discovery rule (glob `*.traj` + `*.json`, stem dedupe with `.traj.json`, instance-id pattern, `non_trajectory` quarantine). Discovery opens no file.

| submission folder | candidates | .traj/.json/.traj.json kept | instance-id files | quarantined (non_trajectory) | stem dups | registry |
|---|---|---|---|---|---|---|
| 20240402_sweagent_claude3opus | 443 | 443/0/0 | 443 | — | 0 | population |
| 20240402_sweagent_gpt4 | 496 | 496/0/0 | 496 | — | 0 | population |
| 20240620_sweagent_claude3.5sonnet | 500 | 500/0/0 | 500 | — | 0 | population |
| 20240728_sweagent_gpt4o | 465 | 465/0/0 | 465 | — | 0 | population |
| 20241029_OpenHands-CodeAct-2.1-sonnet-20241022 | 500 | 0/500/0 | 500 | — | 0 | excluded |
| 20250415_openhands | 500 | 0/500/0 | 500 | — | 0 | excluded |
| 20250511_sweagent_lm_32b | 500 | 500/0/0 | 500 | — | 0 | population |
| 20250520_openhands_devstral_small | 500 | 0/500/0 | 500 | — | 0 | excluded |
| 20250522_sweagent_claude-4-sonnet-20250514 | 501 | 500/0/0 | 500 | preds.json | 0 | population |
| 20250524_openhands_claude_4_sonnet | 500 | 0/500/0 | 500 | — | 0 | population |
| 20250612_trae | 499 | 0/499/0 | 499 | — | 0 | excluded |
| 20250616_Skywork-SWE-32B | 500 | 0/500/0 | 500 | — | 0 | excluded |
| 20250716_openhands_kimi_k2 | 500 | 0/500/0 | 500 | — | 0 | population |
| 20250804_codesweep_sweagent_kimi_k2_instruct | 500 | 500/0/0 | 500 | — | 0 | population |
| 20250804_epam-ai-run-claude-4-sonnet | 500 | 500/0/0 | 500 | — | 0 | population |
| 20250807_openhands_gpt5 | 500 | 0/500/0 | 500 | — | 0 | excluded |
| 20250928_trae_doubao_seed_code | 500 | 0/500/0 | 500 | — | 0 | population |
| 20251021_SalesforceAIResearch_SAGE_bash_only | 500 | 0/0/500 | 500 | — | 0 | population |
| 20251127_openhands_claude-opus-4-5 | 489 | 0/489/0 | 489 | — | 0 | excluded |
| 20251205_sonar-foundation-agent_claude-opus-4-5 | 500 | 0/500/0 | 500 | — | 0 | population |

**Reconciliation (review §7.2):**

| quantity | count |
|---|---|
| candidate files on disk (all 20 dirs) | 9893 |
| quarantined `non_trajectory` | 1 |
| instance-id files (all 20 dirs) | 9892 |
| `20250415_openhands` instance-id files (outside the 19-agent population) | 500 |
| instance-id files across the 19 paper agents | 9392 |
| paper trajectory count | 9374 |
| residual (19-agent instance-id files − paper count) | 18 |

**File-level shape check (§1 table) on the audit sample:**

| submission folder | family | sampled | shape ok | file-level failures |
|---|---|---|---|---|
| 20240402_sweagent_claude3opus | thought | 50 | 50 | 0 |
| 20240402_sweagent_gpt4 | thought | 50 | 50 | 0 |
| 20240620_sweagent_claude3.5sonnet | thought | 50 | 50 | 0 |
| 20240728_sweagent_gpt4o | thought | 47 | 47 | 0 |
| 20250511_sweagent_lm_32b | thought | 50 | 50 | 0 |
| 20250522_sweagent_claude-4-sonnet-20250514 | thought | 50 | 50 | 0 |
| 20250524_openhands_claude_4_sonnet | think_tool | 50 | 50 | 0 |
| 20250716_openhands_kimi_k2 | think_tool | 50 | 50 | 0 |
| 20250804_codesweep_sweagent_kimi_k2_instruct | thought | 50 | 50 | 0 |
| 20250804_epam-ai-run-claude-4-sonnet | epam | 50 | 50 | 0 |
| 20250928_trae_doubao_seed_code | trae | 50 | 50 | 0 |
| 20251021_SalesforceAIResearch_SAGE_bash_only | sage | 50 | 50 | 0 |
| 20251205_sonar-foundation-agent_claude-opus-4-5 | sonar | 50 | 50 | 0 |

**Full-directory file-level census (population dirs, every instance-id file):**

| submission folder | instance-id files | file-level failures (unreadable or wrong shape) |
|---|---|---|
| 20240402_sweagent_claude3opus | 443 | 0 |
| 20240402_sweagent_gpt4 | 496 | 0 |
| 20240620_sweagent_claude3.5sonnet | 500 | 0 |
| 20240728_sweagent_gpt4o | 465 | 0 |
| 20250511_sweagent_lm_32b | 500 | 0 |
| 20250522_sweagent_claude-4-sonnet-20250514 | 500 | 0 |
| 20250524_openhands_claude_4_sonnet | 500 | 0 |
| 20250716_openhands_kimi_k2 | 500 | 0 |
| 20250804_codesweep_sweagent_kimi_k2_instruct | 500 | 0 |
| 20250804_epam-ai-run-claude-4-sonnet | 500 | 0 |
| 20250928_trae_doubao_seed_code | 500 | 0 |
| 20251021_SalesforceAIResearch_SAGE_bash_only | 500 | 0 |
| 20251205_sonar-foundation-agent_claude-opus-4-5 | 500 | 0 |
| **total** | 6404 | 0 |

## §7.1 EPAM ordering gate

Audit sample: 50 EPAM files, 4748 entries (2398 `Thoughts`, 2350 action entries). Entries read in document order; the loader never sorts keys (§2.7 build rule).

**(i) Alternation regularity** — every action entry preceded by exactly one `Thoughts` entry; no consecutive `Thoughts` entries.

| check | count |
|---|---|
| consecutive `Thoughts` entries | 0 |
| action entries not immediately preceded by a `Thoughts` entry | 0 |
|   of which action-after-action | 0 |
| files with a trailing `Thoughts` entry (terminal unit under §2.3) | 48 |
| files with any consecutive `Thoughts` | 0 |

(i) result: **PASS**

**(ii) Next-vs-previous path resolution** — `Thoughts` entries naming a `.py` path, classified by whether the path resolves to the next action's `input_text`, the previous action's, both, or neither. Pass criterion (frozen, §7.1): among entries resolving to exactly one adjacent action, next strictly exceeds previous. Match variant fixed before running: `basename` is primary; `full` token reported alongside.

| variant | next only | previous only | both | neither | no `.py` named |
|---|---|---|---|---|---|
| basename | 73 | 8 | 9 | 58 | 2250 |
| full | 72 | 4 | 9 | 63 | 2250 |

(ii) result on the primary variant: next 73 vs previous 8 → **PASS**

Recorded limitation (§2.7): this check falsifies reversed/scrambled order; it does not prove chronology.

**Gate verdict: PASS — EPAM anchoring may be built**

## §7.3 EPAM text field

Resolved in the review; confirmed here on the audit sample.

| check | count |
|---|---|
| entries | 4748 |
| entry key sets | `['author_name', 'input_text', 'message']`: 4748 |
| author names | `Thoughts`: 2398; `Str Replace Editor`: 1199; `Run Command Line Tool`: 1151 |
| `Thoughts` entries | 2398 |
|   with `input_text == ''` | 2398 |
|   with empty / whitespace-only `message` (no emission under §2.4) | 649 |
| action entries | 2350 |
|   with `input_text` starting `{` (Python-repr dict, §8) | 2350 |

Text field = `message`: **CONFIRMED**.

## §7.4 Sonar block type

Resolved in the review; confirmed here on the audit sample.

| check | count |
|---|---|
| assistant messages | 3076 |
| block types | `thinking`: 3076; `text`: 3076 |
| thinking blocks per message | 1: 3076 |
| block order patterns | `['thinking', 'text']`: 3076 |
| thinking blocks with `content` str | 3076 |
| thinking blocks carrying a `text` key | 0 |
| thinking blocks carrying `num_tokens` | 3076 |
| text blocks carrying a `text` key | 3076 |
| messages with `additional_kwargs.tool_calls` | 3026 |
| messages without tool_calls (free-standing under §2.2) | 50 |
| `tool_use` blocks in `blocks[]` | 0 |

`block_type == "thinking"`, text under `content`: **CONFIRMED**.

## §7.5 SAGE rule validation (template applied provisionally; rule_version unassigned)

The §4.1 **refined template** (first `THOUGHT:` through the first ```` ```bash ```` opener; no `THOUGHT:` → no emission; no bash fence → end of message) applied **provisionally** to the disjoint sample. `rule_version` is unassigned until [A] fills the §4.1 derivation slot at the checkpoint; the extractor is not built here.

| check | count |
|---|---|
| assistant messages | 1852 |
| template yields a non-empty emission | 1851 |
| template yields no emission (`THOUGHT:` absent or empty) | 1 |
| emission end boundary = bash fence | 1852 |
| emission end boundary = end of message | 0 |

## §7.6 Their `target_file` sparsity

Confirmed from their code in the review (no run needed): `_classify_bash_command` returns `target_file=None` on every branch; `file_editor` → `None`. Their `Pr` can never fire for SAGE, for bash-mediated edits in any format, or for Trae-doubao. Consequence lives in the Phase 3 spot-check (SAGE and Trae-doubao rows oversampled).

## §7.7 Trae tag-balance census

Audit sample minus the §4.2 inspection files (1 excluded): 49 files, 1712 assistant messages.

| check | count |
|---|---|
| `<think>` openers per message | 1: 1712 |
| `</think>` closers per message | 1: 1550; 2: 89; 3: 38; 4: 15; 5: 6; 6: 3; 7: 1; 8: 5; 9: 2; 10: 1; 12: 1; 18: 1 |
| multi-closer messages (option-B-affected) | 162 (9.5%) |
| messages with `<function=` before the last closer (§7.7 as written) | 4 |
|   of which with a *closed* `</function>` before the last closer (added diagnostic) | 0 |
| messages with no `<think>` opener | 0 |
| messages with no `<function=` (free-standing / terminal under §2) | 6 |

No `<function=` precedes the last closer: **NOT CONFIRMED**.

Messages contradicting the §3 basis for option B ("no `<function=` occurs before the last closer"). Offsets are character positions in the message content; structure only.

| file | msg # | len | `</think>` offsets | `<function=` offsets | `</function>` offsets |
|---|---|---|---|---|---|
| sympy__sympy-13031.json | 42 | 3255 | [515, 2194] | [525, 2203] | [3244] |
| sympy__sympy-13031.json | 52 | 5316 | [1396, 3257, 5204] | [1405, 3266, 5214] | [5305] |
| sympy__sympy-13031.json | 62 | 3673 | [1366, 3480] | [1376, 3490] | [3662] |
| sympy__sympy-23413.json | 44 | 6913 | [151, 6229] | [255, 6326] | [6902] |

Reading of the structure (for the §4.2 checkpoint, not a decision): in every listed message the `<function=` before the last closer has no `</function>` before that closer — an opener the model abandoned, then reasoned further, closed `</think>`, and restarted the call. Option B would include the abandoned call's XML in the unit; option A would drop the continued reasoning. Both remain recoverable from the stored first-closer offset (§3 rider).

## §7.8 SAGE structure census

Audit sample minus the §4.1 inspection files (1 excluded: ['astropy__astropy-12907', 'astropy__astropy-13033']): 49 files, 1852 assistant messages.

| check | count |
|---|---|
| `THOUGHT:` offset = 0 | 1848 |
| `THOUGHT:` offset > 0 (prose before it, excluded as undesignated) | 3 |
| `THOUGHT:` absent (no emission) | 1 |
| messages with a ```` ```bash ```` fence | 1852 |
| messages missing a bash fence (emission runs to end of message) | 0 |
| messages with non-whitespace text after the last fence close | 0 |
| messages with an odd number of ``` markers | 0 |

Fence-opener language sequences (top 8):

| opener sequence | messages |
|---|---|
| `['bash']` | 1822 |
| `['python', 'bash']` | 7 |
| `['bash', '']` | 7 |
| `['bash', '', '', '']` | 6 |
| `['bash', '', '']` | 4 |
| `['python', 'python', 'bash']` | 3 |
| `['bash', '', '', '', '', '', '']` | 2 |
| `['bash', '', '', '', '']` | 1 |

Non-bash fences before the first bash fence (the class the rev-1 'first code fence' template would have cut):

| non-bash fences before bash | messages |
|---|---|
| 0 | 1842 |
| 1 | 7 |
| 2 | 3 |

## §7.9 SWE-agent `trajectory` vs non-demo `history`

**As written in §7.9.** Old format: `trajectory[].thought` equals the `thought` of non-`is_demo` assistant `history` entries, 1:1 (column 4). New format: `len(trajectory) − #assistant history entries == #text-only steps` (steps whose `action` is empty; column 5). **Added diagnostic** (column 7): non-demo assistant `history` thoughts form an ordered subsequence of `trajectory[].thought` — the containment property Q1 actually needs, whether or not `history` drops text-only turns.

| submission folder | format | sampled | old: 1:1 equality | new: spec identity | detail | added: history ⊆ trajectory (ordered) |
|---|---|---|---|---|---|---|
| 20240402_sweagent_claude3opus | old | 50 | 50/50 | — | 1100 demo entries; 550 demo assistant thoughts | 50/50 |
| 20240402_sweagent_gpt4 | old | 50 | 50/50 | — | 50 demo entries; 0 demo assistant thoughts | 50/50 |
| 20240620_sweagent_claude3.5sonnet | old | 50 | 50/50 | — | 1100 demo entries; 550 demo assistant thoughts | 50/50 |
| 20240728_sweagent_gpt4o | old | 47 | 47/47 | — | 47 demo entries; 0 demo assistant thoughts | 47/47 |
| 20250511_sweagent_lm_32b | new | 50 | — | 31/50 | 20 text-only steps / 2122 steps; files with len(trajectory) == #assistant history: 49 | 50/50 |
| 20250522_sweagent_claude-4-sonnet-20250514 | new | 50 | — | 47/50 | 26 text-only steps / 3156 steps; files with len(trajectory) == #assistant history: 29 | 50/50 |
| 20250804_codesweep_sweagent_kimi_k2_instruct | new | 50 | — | 45/50 | 8 text-only steps / 1448 steps; files with len(trajectory) == #assistant history: 47 | 50/50 |

§7.9 identity as written: **FAIL**. Containment (`trajectory[]` holds every non-demo assistant thought, in order): **CONFIRMED**. Extraction reads `trajectory[]` only (Q1), so the identity's failure has no extraction consequence; it is a description error in §3's `thought` row ("new-format `history` drops text-only turns" — it drops some and keeps others).

**Text-only step census (steps with empty `action`; these become free-standing or terminal emissions under §2.2–2.3).** `harness exit string` counts `thought` values starting with the SWE-agent template `Exit due to…` (e.g. cost limit, context window, command timeouts) — a harness string in the designated slot, counted by template prefix, not a re-evaluation marker. Surfaced for the checkpoint: the spec treats every non-empty `thought` on an `action == ""` step as designated reasoning.

| submission folder | text-only steps | at last step | `thought` present in history | `thought` empty (no emission) | harness exit string |
|---|---|---|---|---|---|
| 20240402_sweagent_claude3opus | 0 | 0 | 0 | 0 | 0 |
| 20240402_sweagent_gpt4 | 0 | 0 | 0 | 0 | 0 |
| 20240620_sweagent_claude3.5sonnet | 0 | 0 | 0 | 0 | 0 |
| 20240728_sweagent_gpt4o | 0 | 0 | 0 | 0 | 0 |
| 20250511_sweagent_lm_32b | 20 | 19 | 19 | 0 | 19 |
| 20250522_sweagent_claude-4-sonnet-20250514 | 26 | 3 | 6 | 3 | 3 |
| 20250804_codesweep_sweagent_kimi_k2_instruct | 8 | 5 | 5 | 1 | 5 |

## Think-tool structure (supports §3)

Recorded for §3 (think-tool row): singleton think messages, `arguments` JSON with key `thought`, zero-unit trajectories legitimate under §6.

| submission folder | sampled | think messages | think + other call in same msg | `arguments` JSON parse | args with `thought` key | trajectories with zero think calls |
|---|---|---|---|---|---|---|
| 20250524_openhands_claude_4_sonnet | 50 | 147 | 0 | 147 ok / 0 fail | 147 | 0 |
| 20250716_openhands_kimi_k2 | 50 | 111 | 0 | 111 ok / 0 fail | 111 | 0 |
