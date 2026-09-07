# Adapter structural audit report (spec §5)

*Generated 2026-09-07 by `methodology/scripts/run_adapter_audit.py` against `/Users/adelinelatruwe/Projects/replication-package/dataset/trajectories/verified`, on the §5 audit sample (647 files, 13 agents; every ⌈n/50⌉-th discovery-passing file from index 0, bytewise order), after the extractors. Descriptive only: no unit-definition change, no outcome join, no ranking. Structure only: no resolution contact, no marker counts, no signal values, no v1 code over trajectories. Words = whitespace-split tokens.*

Rule versions: SAGE `sage-1`, Trae `trae-b-1` (spec rev 3 §4). Harness-string rule §2.4 (D3): prefix `Exit due to`, SWE-agent family only. Build-level note: unit text excludes the boundary delimiters (SAGE `THOUGHT:` label, Trae `<think>` opener and final `</think>`); interior content is verbatim.

## 1. Emission-per-anchor multiplicity (fragment_count) per family

| family | units | fragment_count = 1 | > 1 | > 1 rate | max | distribution |
|---|---|---|---|---|---|---|
| `thought` field | 11105 | 11104 | 1 | 0.0% | 2 | 1: 11104; 2: 1 |
| `Thoughts` entries | 1749 | 1749 | 0 | 0.0% | 1 | 1: 1749 |
| `THOUGHT:` prefix | 1879 | 1879 | 0 | 0.0% | 1 | 1: 1879 |
| thinking blocks | 3076 | 3076 | 0 | 0.0% | 1 | 1: 3076 |
| `<think>` tags | 1540 | 1533 | 7 | 0.5% | 2 | 1: 1533; 2: 7 |
| think-tool args | 258 | 258 | 0 | 0.0% | 1 | 1: 258 |

## 2. Unit length distribution (words) per agent

Non-terminal and terminal units separately (§2.3 stratification). Feeds the pre-registration §5 length-shift limitation; reported next to κ context in the writeup.

| submission folder | stratum | n | min | p25 | median | p75 | p90 | max | mean |
|---|---|---|---|---|---|---|---|---|---|
| 20240402_sweagent_claude3opus | non-terminal | 923 | 6 | 18 | 27 | 46 | 80 | 287 | 39 |
|  | terminal | 0 | — | — | — | — | — | — | — |
| 20240402_sweagent_gpt4 | non-terminal | 923 | 14 | 39 | 58 | 85 | 127 | 388 | 69 |
|  | terminal | 0 | — | — | — | — | — | — | — |
| 20240620_sweagent_claude3.5sonnet | non-terminal | 1733 | 5 | 22 | 33 | 49 | 69 | 233 | 40 |
|  | terminal | 0 | — | — | — | — | — | — | — |
| 20240728_sweagent_gpt4o | non-terminal | 2003 | 8 | 23 | 30 | 42 | 57 | 118 | 34 |
|  | terminal | 0 | — | — | — | — | — | — | — |
| 20250511_sweagent_lm_32b | non-terminal | 2014 | 3 | 7 | 10 | 20 | 45 | 335 | 20 |
|  | terminal | 1 | 1151 | 1151 | 1151 | 1151 | 1151 | 1151 | 1151 |
| 20250522_sweagent_claude-4-sonnet-20250514 | non-terminal | 2199 | 3 | 12 | 18 | 36 | 86 | 525 | 39 |
|  | terminal | 0 | — | — | — | — | — | — | — |
| 20250524_openhands_claude_4_sonnet | non-terminal | 144 | 52 | 180 | 216 | 253 | 290 | 820 | 226 |
|  | terminal | 3 | 220 | 220 | 226 | 233 | 233 | 233 | 226 |
| 20250716_openhands_kimi_k2 | non-terminal | 108 | 71 | 115 | 152 | 215 | 247 | 411 | 168 |
|  | terminal | 3 | 199 | 199 | 249 | 267 | 267 | 267 | 238 |
| 20250804_codesweep_sweagent_kimi_k2_instruct | non-terminal | 1309 | 3 | 7 | 11 | 24 | 53 | 369 | 23 |
|  | terminal | 0 | — | — | — | — | — | — | — |
| 20250804_epam-ai-run-claude-4-sonnet | non-terminal | 1701 | 3 | 12 | 20 | 37 | 77 | 511 | 33 |
|  | terminal | 48 | 96 | 323 | 345 | 377 | 388 | 521 | 346 |
| 20250928_trae_doubao_seed_code | non-terminal | 1540 | 1 | 7 | 13 | 88 | 220 | 3587 | 95 |
|  | terminal | 0 | — | — | — | — | — | — | — |
| 20251021_SalesforceAIResearch_SAGE_bash_only | non-terminal | 1879 | 2 | 14 | 22 | 35 | 68 | 464 | 32 |
|  | terminal | 0 | — | — | — | — | — | — | — |
| 20251205_sonar-foundation-agent_claude-opus-4-5 | non-terminal | 3026 | 4 | 12 | 18 | 39 | 106 | 1134 | 47 |
|  | terminal | 50 | 7 | 60 | 134 | 183 | 201 | 334 | 131 |

## 3. Presence per trajectory

Fraction of trajectories with ≥1 unit, per agent. Agent behaviour under §6, not a failure threshold.

| submission folder | trajectories | with ≥1 unit | presence | units | mean units/traj | median units/traj |
|---|---|---|---|---|---|---|
| 20240402_sweagent_claude3opus | 50 | 50 | 100.0% | 923 | 18.5 | 20 |
| 20240402_sweagent_gpt4 | 50 | 50 | 100.0% | 923 | 18.5 | 15 |
| 20240620_sweagent_claude3.5sonnet | 50 | 50 | 100.0% | 1733 | 34.7 | 28 |
| 20240728_sweagent_gpt4o | 47 | 47 | 100.0% | 2003 | 42.6 | 48 |
| 20250511_sweagent_lm_32b | 50 | 50 | 100.0% | 2015 | 40.3 | 34 |
| 20250522_sweagent_claude-4-sonnet-20250514 | 50 | 50 | 100.0% | 2199 | 44.0 | 40 |
| 20250524_openhands_claude_4_sonnet | 50 | 50 | 100.0% | 147 | 2.9 | 3 |
| 20250716_openhands_kimi_k2 | 50 | 50 | 100.0% | 111 | 2.2 | 2 |
| 20250804_codesweep_sweagent_kimi_k2_instruct | 50 | 50 | 100.0% | 1309 | 26.2 | 18 |
| 20250804_epam-ai-run-claude-4-sonnet | 50 | 50 | 100.0% | 1749 | 35.0 | 34 |
| 20250928_trae_doubao_seed_code | 50 | 50 | 100.0% | 1540 | 30.8 | 31 |
| 20251021_SalesforceAIResearch_SAGE_bash_only | 50 | 50 | 100.0% | 1879 | 37.6 | 34 |
| 20251205_sonar-foundation-agent_claude-opus-4-5 | 50 | 50 | 100.0% | 3076 | 61.5 | 57 |

## 4. Terminal-unit and empty-anchor rates

Terminal units are stratified as a genre (wrap-up summaries, §2.3); the stratification carries to the writeup. Empty anchors = action steps with no preceding reasoning (§2.4). Empty emissions = designated slots that were empty / whitespace-only (no emission).

| submission folder | units | terminal | terminal rate | trajectories ending in a terminal unit | action steps | empty anchors | empty-anchor rate | empty emissions / designated slots | free-standing units | free-standing rate |
|---|---|---|---|---|---|---|---|---|---|---|
| 20240402_sweagent_claude3opus | 923 | 0 | 0.0% | 0/50 | 951 | 28 | 2.9% | 2 / 925 | 0 | 0.0% |
| 20240402_sweagent_gpt4 | 923 | 0 | 0.0% | 0/50 | 933 | 10 | 1.1% | 0 / 923 | 0 | 0.0% |
| 20240620_sweagent_claude3.5sonnet | 1733 | 0 | 0.0% | 0/50 | 1743 | 10 | 0.6% | 0 / 1733 | 0 | 0.0% |
| 20240728_sweagent_gpt4o | 2003 | 0 | 0.0% | 0/47 | 2028 | 25 | 1.2% | 0 / 2003 | 0 | 0.0% |
| 20250511_sweagent_lm_32b | 2015 | 1 | 0.0% | 1/50 | 2102 | 88 | 4.2% | 88 / 2103 | 0 | 0.0% |
| 20250522_sweagent_claude-4-sonnet-20250514 | 2199 | 0 | 0.0% | 0/50 | 3130 | 931 | 29.7% | 954 / 3153 | 20 | 0.9% |
| 20250524_openhands_claude_4_sonnet | 147 | 3 | 2.0% | 3/50 | 3538 | 3394 | 95.9% | 0 / 147 | 144 | 98.0% |
| 20250716_openhands_kimi_k2 | 111 | 3 | 2.7% | 3/50 | 2726 | 2618 | 96.0% | 0 / 111 | 108 | 97.3% |
| 20250804_codesweep_sweagent_kimi_k2_instruct | 1309 | 0 | 0.0% | 0/50 | 1440 | 131 | 9.1% | 133 / 1443 | 2 | 0.2% |
| 20250804_epam-ai-run-claude-4-sonnet | 1749 | 48 | 2.7% | 48/50 | 2350 | 649 | 27.6% | 649 / 2398 | 1701 | 97.3% |
| 20250928_trae_doubao_seed_code | 1540 | 0 | 0.0% | 0/50 | 1720 | 180 | 10.5% | 180 / 1727 | 7 | 0.5% |
| 20251021_SalesforceAIResearch_SAGE_bash_only | 1879 | 0 | 0.0% | 0/50 | 1880 | 1 | 0.1% | 0 / 1879 | 0 | 0.0% |
| 20251205_sonar-foundation-agent_claude-opus-4-5 | 3076 | 50 | 1.6% | 50/50 | 3026 | 0 | 0.0% | 0 / 3076 | 0 | 0.0% |

## 5. SAGE boundary rule (`sage-1`) validation counts and anomaly rates

Audit-sample files minus the §4.1 inspection files ['astropy__astropy-12907', 'astropy__astropy-13033'] (disjoint).

| check | count | rate |
|---|---|---|
| files (disjoint) | 49 |  |
| assistant messages | 1852 |  |
| units produced | 1851 | 99.9% |
| `THOUGHT:` absent (no emission) | 1 | 0.1% |
| `THOUGHT:` at offset ≠ 0 (prose before it excluded) | 3 | 0.2% |
| non-bash fences before the bash fence (rev-1 template's cut class) | 10 | 0.5% |
| missing bash fence (emission runs to end of message) | 0 | 0.0% |

## 6. Trae stray-closer rate (option-B-affected, `trae-b-1`)

Audit-sample files minus the §4.2 inspection files ['astropy__astropy-12907', 'astropy__astropy-13033'] (disjoint).

| check | count | rate |
|---|---|---|
| files (disjoint) | 49 |  |
| assistant messages | 1712 |  |
| units produced | 1525 | 89.1% |
| messages with > 1 `</think>` (option-B-affected) | 162 | 9.5% |
| units containing an affected fragment | 161 | 10.6% |
| `<think>` with no closer (emission runs to end of message) | 0 | 0.0% |

## 7. Harness-string census (§2.4, D3)

`n_harness_strings` = designated slots excluded by the documented-prefix rule (`Exit due to`, SWE-agent family only). The duplicate census lists the top exact-duplicate designated strings on action-less containers (text-only steps and their analogues in other families), per agent — to surface any further harness template structurally for a documented addition. Strings are shown truncated; counts are of exact duplicates. In old-format SWE-agent files the exit string sits on a step whose action is `exit_cost` / `exit_context` (an action-bearing step), so it counts under `n_harness_strings` — the anchor then has no emission — but never enters the action-less census; the split is shown.

| submission folder | n_harness_strings |   on action-less steps |   on action-bearing steps | action-less designated strings | top exact duplicates (≥2) |
|---|---|---|---|---|---|
| 20240402_sweagent_claude3opus | 26 | 0 | 26 | 0 | — |
| 20240402_sweagent_gpt4 | 10 | 0 | 10 | 0 | — |
| 20240620_sweagent_claude3.5sonnet | 10 | 0 | 10 | 0 | — |
| 20240728_sweagent_gpt4o | 25 | 0 | 25 | 0 | — |
| 20250511_sweagent_lm_32b | 19 | 19 | 0 | 20 | `'Exit due to cost limit'` ×17; `'Exit due to context window'` ×2 |
| 20250522_sweagent_claude-4-sonnet-20250514 | 3 | 3 | 0 | 23 | `'Exit due to cost limit'` ×2 |
| 20250524_openhands_claude_4_sonnet | 0 | 0 | 0 | 147 | — |
| 20250716_openhands_kimi_k2 | 0 | 0 | 0 | 111 | — |
| 20250804_codesweep_sweagent_kimi_k2_instruct | 5 | 5 | 0 | 7 | `'Exit due to cost limit'` ×3 |
| 20250804_epam-ai-run-claude-4-sonnet | 0 | 0 | 0 | 1749 | `"Now let's test our fix:"` ×35; `"Now let's test the fix:"` ×9; `'Let me explore the Django source code structure:'` ×8; `"Let me try running the tests using Django's test runner:"` ×7; `'Let me use the Django test runner instead:'` ×6 |
| 20250928_trae_doubao_seed_code | 0 | 0 | 0 | 7 | — |
| 20251021_SalesforceAIResearch_SAGE_bash_only | 0 | 0 | 0 | 0 | — |
| 20251205_sonar-foundation-agent_claude-opus-4-5 | 0 | 0 | 0 | 50 | — |

## Supplementary (descriptive): path-layer and mention coverage

Fraction of actions with ≥1 extracted path (feeds Phase 3's ability to compute reread_bursts / edit_churn), and fraction of units with a tier-1/2 mention attribution against the trajectory's touched-path set. Old-format `edit` resolves to the currently open file (documented stateful rule in paths.py).

| submission folder | actions | with ≥1 path | args unparsed | old `edit` w/o open file | units | tier 1 (exact_path) | tier 2 (unique_basename) |
|---|---|---|---|---|---|---|---|
| 20240402_sweagent_claude3opus | 951 | 71.5% | 0 | 0 | 923 | 8.7% | 24.2% |
| 20240402_sweagent_gpt4 | 933 | 65.7% | 0 | 0 | 923 | 6.9% | 47.5% |
| 20240620_sweagent_claude3.5sonnet | 1743 | 76.0% | 0 | 2 | 1733 | 6.4% | 20.3% |
| 20240728_sweagent_gpt4o | 2028 | 84.1% | 0 | 0 | 2003 | 8.8% | 36.5% |
| 20250511_sweagent_lm_32b | 2102 | 85.7% | 0 | 0 | 2015 | 2.6% | 5.9% |
| 20250522_sweagent_claude-4-sonnet-20250514 | 3130 | 76.7% | 0 | 0 | 2199 | 2.9% | 2.2% |
| 20250524_openhands_claude_4_sonnet | 3538 | 76.0% | 0 | 0 | 147 | 44.9% | 1.4% |
| 20250716_openhands_kimi_k2 | 2726 | 80.1% | 0 | 0 | 111 | 39.6% | 0.0% |
| 20250804_codesweep_sweagent_kimi_k2_instruct | 1440 | 80.6% | 0 | 0 | 1309 | 2.6% | 4.5% |
| 20250804_epam-ai-run-claude-4-sonnet | 2350 | 86.9% | 0 | 0 | 1749 | 4.3% | 4.1% |
| 20250928_trae_doubao_seed_code | 1720 | 65.5% | 0 | 0 | 1540 | 4.0% | 8.4% |
| 20251021_SalesforceAIResearch_SAGE_bash_only | 1880 | 70.0% | 0 | 0 | 1879 | 4.7% | 3.7% |
| 20251205_sonar-foundation-agent_claude-opus-4-5 | 3030 | 48.7% | 0 | 0 | 3076 | 3.5% | 4.4% |
