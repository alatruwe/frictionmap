# Action-encoding ingest — join coverage and spot-check (Phase 2 → Phase 3 handoff)

*2026-09-07. Task 1 (ingest) run by `methodology/scripts/ingest_action_encodings.py`; diagnostic by `methodology/scripts/diag_trae_unjoined.py`. Status: **STOPPED at the Task 1 hard requirement** — one agent joins below 100%. Task 2 (the 20-trajectory reproducibility spot-check) was not started, per the handoff: the stop returns to [A] before any spot-check is drawn. Nothing in this report is a fix; the numbers are as observed.*

## Provenance

The action encoding used as Phase 3's Q2 comparison baseline is the authors' 13-symbol enriched encoding (arXiv 2604.02547; replication package Zenodo 19351830, CC BY 4.0). Both the encoding scheme and the parse are theirs: we consume their shipped `data/enriched_encodings_all.csv` directly and do not reimplement or modify their encoder (`scripts/data_processing/extract_enriched_encoding_all.py`, sha256 `4754346e…5fe`; `scripts/config.py`, sha256 `8f6da96e…76e`, matching the hash vendored in our registry). Our only contribution is the join of their rows to our parsed population and the reproducibility check. **Reproducibility on a 20-trajectory seeded sample is not yet verified** — that check is gated behind the coverage decision below and this paragraph will be completed when it runs.

## Their CSV — structure

`data/enriched_encodings_all.csv` (sha256 `57a15b94…3fb`), 9,874 rows, one per agent-task pair across their 20 submissions. Columns:

| column | role |
|---|---|
| `instance_id` | task id (`<owner>__<repo>-<n>`), the file stem with `.traj`/`.json`/`.traj.json` removed |
| `agent_name`, `llm_name` | submission identity — written by their `main()` verbatim from `SUBMISSION_META[folder]["agent"]` / `["llm"]`; there is **no submission-folder column** |
| `framework` | their format string (not an identity: `openhands` and `trae` each serve several folders) |
| `is_failed` | resolution status: 0 resolved / 1 failed / −1 unknown (from `resolution_status.json`) |
| `enriched_encoding` | the 13-symbol string, space-separated |
| `base_encoding`, `n_raw_steps`, `n_encoded_steps`, `has_lb_lt_distinction` | derived / bookkeeping |

`(agent_name, llm_name)` is unique per submission folder across all 20 entries, and `(agent_name, llm_name, instance_id)` is unique across the CSV (0 duplicates).

## Join

**Key:** `(agent, llm, instance_id)`. `(agent, llm)` comes from our vendored registry entry for the population folder (`swebench_adapter.registry.SUBMISSION_META`, their table verbatim); `instance_id` is the discovery stem (spec §1 rule, `.traj.json` treated as one stem, `preds.json` quarantined). **No normalization of any kind was applied on either side** — no case folding, no extension or prefix handling beyond the discovery stem that Phase 2 already uses.

**Population** = the 6,404 instance-id files that passed parse validation on 2026-09-07 (`adapter-parse-validation.md`), 13 agents.

**Output table:** `methodology/results/action-encodings-joined.csv`, 6,404 rows — one per population file — columns `submission_folder, agent_name, llm_name, instance_id, joined, enriched_encoding, is_failed`. Unjoined rows are present with `joined=0` and blank encoding/status. Note the table carries `is_failed`, which the Phase 2 adapter spec fenced; the fence covered adapter steps, and this table is the Phase 3 input the handoff asked for. `action_encoding/` is a separate package from `swebench_adapter`, which still never reads the CSV.

### Coverage per agent

| submission folder | n population | n joined | n unjoined | coverage |
|---|---|---|---|---|
| 20240402_sweagent_claude3opus | 443 | 443 | 0 | 100.00% |
| 20240402_sweagent_gpt4 | 496 | 496 | 0 | 100.00% |
| 20240620_sweagent_claude3.5sonnet | 500 | 500 | 0 | 100.00% |
| 20240728_sweagent_gpt4o | 465 | 465 | 0 | 100.00% |
| 20250511_sweagent_lm_32b | 500 | 500 | 0 | 100.00% |
| 20250522_sweagent_claude-4-sonnet-20250514 | 500 | 500 | 0 | 100.00% |
| 20250524_openhands_claude_4_sonnet | 500 | 500 | 0 | 100.00% |
| 20250716_openhands_kimi_k2 | 500 | 500 | 0 | 100.00% |
| 20250804_codesweep_sweagent_kimi_k2_instruct | 500 | 500 | 0 | 100.00% |
| 20250804_epam-ai-run-claude-4-sonnet | 500 | 500 | 0 | 100.00% |
| **20250928_trae_doubao_seed_code** | **500** | **483** | **17** | **96.60%** |
| 20251021_SalesforceAIResearch_SAGE_bash_only | 500 | 500 | 0 | 100.00% |
| 20251205_sonar-foundation-agent_claude-opus-4-5 | 500 | 500 | 0 | 100.00% |

Total: 6,404 population, 6,387 joined, 17 unjoined. Reverse gap (CSV rows for a population `(agent, llm)` with no file on disk): 0 for all 13 — the CSV never has *more* than we do. **12/13 agents at 100%; Trae-doubao at 96.60% → stop condition met.**

### The 17 unjoined Trae-doubao trajectories

```
astropy__astropy-7606        django__django-15161          scikit-learn__scikit-learn-14141
django__django-10973         django__django-15569          sympy__sympy-13878
django__django-11276         django__django-16082          sympy__sympy-16886
django__django-12308         django__django-16569          sympy__sympy-17139
django__django-13401         matplotlib__matplotlib-20859  sympy__sympy-19346
django__django-14089         scikit-learn__scikit-learn-13439
```

These are not key mismatches and not a download gap. They are ordinary trajectories (53–191 KB, 29–103 messages, 14–51 assistant turns each carrying `<function=` calls; 15 of 17 are marked resolved in their `resolution_status.json`), and their own script skips them. Diagnostic (`diag_trae_unjoined.py`, their parser and encoder imported unmodified from a byte-identical scratch copy of `scripts/`, hashes printed and matching):

- Their `extract_steps_trae()` reads an assistant message's `tool_calls` list, or failing that the ```` ``` ```` code fences in its text. It never reads `<function=…>` XML (the handoff's second blind spot).
- Trae-doubao has **no `tool_calls` anywhere** (0/500 files) and issues every action as `<function=…>` XML. So their step list for this agent is built only from incidental code fences in assistant prose.
- Exactly 17 of 500 files have zero code fences in assistant messages, and those 17 are exactly the unjoined set. Their parser returns 0 steps → `encode_trajectory` returns `None` → their `main()` counts them as `n_skip` and writes no row. Deterministic, reproduced on all 17.
- The three joined controls checked (astropy-12907, astropy-13033, django-11099) encode to `G G … G` only — 16, 28 and 4 symbols respectively, every one `G`. This is a preview of the degeneracy the handoff expects the Task 2 note to document for Trae-doubao; it is recorded here as a diagnostic observation, not as the spot-check.

Verbatim diagnostic output:

```
UNJOINED astropy__astropy-7606              asst= 22 tool_calls=0 fences=  0 fn_tags= 22 their_steps=  0 encoding=None
UNJOINED django__django-10973               asst= 26 tool_calls=0 fences=  0 fn_tags= 26 their_steps=  0 encoding=None
UNJOINED django__django-11276               asst= 20 tool_calls=0 fences=  0 fn_tags= 20 their_steps=  0 encoding=None
UNJOINED django__django-12308               asst= 43 tool_calls=0 fences=  0 fn_tags= 43 their_steps=  0 encoding=None
UNJOINED django__django-13401               asst= 35 tool_calls=0 fences=  0 fn_tags= 35 their_steps=  0 encoding=None
UNJOINED django__django-14089               asst= 16 tool_calls=0 fences=  0 fn_tags= 16 their_steps=  0 encoding=None
UNJOINED django__django-15161               asst= 51 tool_calls=0 fences=  0 fn_tags= 51 their_steps=  0 encoding=None
UNJOINED django__django-15569               asst= 19 tool_calls=0 fences=  0 fn_tags= 19 their_steps=  0 encoding=None
UNJOINED django__django-16082               asst= 37 tool_calls=0 fences=  0 fn_tags= 37 their_steps=  0 encoding=None
UNJOINED django__django-16569               asst= 23 tool_calls=0 fences=  0 fn_tags= 23 their_steps=  0 encoding=None
UNJOINED matplotlib__matplotlib-20859       asst= 20 tool_calls=0 fences=  0 fn_tags= 20 their_steps=  0 encoding=None
UNJOINED scikit-learn__scikit-learn-13439   asst= 23 tool_calls=0 fences=  0 fn_tags= 23 their_steps=  0 encoding=None
UNJOINED scikit-learn__scikit-learn-14141   asst= 14 tool_calls=0 fences=  0 fn_tags= 14 their_steps=  0 encoding=None
UNJOINED sympy__sympy-13878                 asst= 51 tool_calls=0 fences=  0 fn_tags= 51 their_steps=  0 encoding=None
UNJOINED sympy__sympy-16886                 asst= 14 tool_calls=0 fences=  0 fn_tags= 14 their_steps=  0 encoding=None
UNJOINED sympy__sympy-17139                 asst= 30 tool_calls=0 fences=  0 fn_tags= 30 their_steps=  0 encoding=None
UNJOINED sympy__sympy-19346                 asst= 24 tool_calls=0 fences=  0 fn_tags= 24 their_steps=  0 encoding=None
CONTROL  astropy__astropy-12907             asst= 15 tool_calls=0 fences= 32 fn_tags= 15 their_steps= 16 encoding=G G G G G G G G G G G G G G G G
CONTROL  astropy__astropy-13033             asst= 21 tool_calls=0 fences= 56 fn_tags= 21 their_steps= 28 encoding=G G G G G G G G G G G G G G G G G G G G G G G G G G G G
CONTROL  django__django-11099               asst= 20 tool_calls=0 fences=  8 fn_tags= 20 their_steps=  4 encoding=G G G G
```

Side note on the download: per-folder file counts for the 13 population agents equal the CSV's per-agent row counts exactly for the 12 complete agents (443/496/500/465/…), so their skips are the only source of loss inside the population.

## Decision returned to [A]

The 17 rows cannot be joined because their pipeline produced no encoding for them; there is no key to normalize. Options, none taken here:

1. Keep the population at 500 and carry the 17 as `joined=0` with reason "their parser: zero steps"; Q2's Trae-doubao baseline covers 483, and the writeup states it. Simplest and consistent with "their encoding, their parse".
2. Treat the 17 as outside the Q2 comparison set only (not the friction population).
3. Anything that produces an encoding for the 17 is out of scope by the handoff (no reimplementation, no correction).

Task 2 is untouched and ready to run once the decision is in. Mechanism validated by the diagnostic: their script imports and runs from a byte-identical scratch copy under `uv run --no-project --with pandas --with numpy` (pandas/numpy are not in our environment; nothing is installed into the project). Their package was not modified: file hashes above are unchanged, no file under the package was created or modified today, and no `__pycache__` was written into their `scripts/` tree.

## Acceptance criteria — status

1. Join coverage per agent reported — yes; 12/13 at 100%, **STOPPED** on Trae-doubao (483/500) with the 17 keys listed.
2. Spot-check 20/20 — **not run** (gated by 1).
3. Their script untouched — yes (hashes and mtimes verified).
4. Seed recorded — n/a until Task 2 runs.
5. Provenance paragraph — present, with the reproducibility clause explicitly pending.
