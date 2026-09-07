# Adapter parse-validation report (spec §6)

*Generated 2026-09-07 by `methodology/scripts/run_adapter_validation.py` against `/Users/adelinelatruwe/Projects/replication-package/dataset/trajectories/verified`. Every instance-id file of every population agent was loaded and extracted; nothing was skipped silently. Rates go back to [A] verbatim; the >10% disposition is not made here (pre-reg §6).*

- **File-level failure:** JSON unreadable, or top-level shape does not match the family's §1 expectation.
- **Unit-level failure:** file parses but the family's designated structure is absent (no `thought` keys / no `Thoughts` entries / no thinking block / no `THOUGHT:` / no `<think>`; n/a for think-tool).
- **Denominator:** deduped instance-id-stem files; `non_trajectory` files sit outside both numerator and denominator.
- **Rate:** (file + unit) / denominator; `>10%` strict. Zero units with structure present, and zero action steps, are agent behaviour, not failures (reported descriptively; see the audit report).

## Per-agent rates

| submission folder | family | instance-id files | file-level failures | unit-level failures | rate | over 10% (strict) | units | trajectories with ≥1 unit | zero-action trajectories | non_trajectory quarantined |
|---|---|---|---|---|---|---|---|---|---|---|
| 20240402_sweagent_claude3opus | thought | 443 | 0 | 0 | 0.00% | no | 8078 | 443/443 | 0 | 0 |
| 20240402_sweagent_gpt4 | thought | 496 | 0 | 0 | 0.00% | no | 10174 | 496/496 | 0 | 0 |
| 20240620_sweagent_claude3.5sonnet | thought | 500 | 0 | 0 | 0.00% | no | 16725 | 500/500 | 0 | 0 |
| 20240728_sweagent_gpt4o | thought | 465 | 0 | 0 | 0.00% | no | 17846 | 465/465 | 0 | 0 |
| 20250511_sweagent_lm_32b | thought | 500 | 0 | 0 | 0.00% | no | 19967 | 500/500 | 0 | 0 |
| 20250522_sweagent_claude-4-sonnet-20250514 | thought | 500 | 0 | 0 | 0.00% | no | 21799 | 500/500 | 0 | 1 |
| 20250524_openhands_claude_4_sonnet | think_tool | 500 | 0 | 0 | 0.00% | no | 1407 | 500/500 | 0 | 0 |
| 20250716_openhands_kimi_k2 | think_tool | 500 | 0 | 0 | 0.00% | no | 1202 | 500/500 | 0 | 0 |
| 20250804_codesweep_sweagent_kimi_k2_instruct | thought | 500 | 0 | 0 | 0.00% | no | 13632 | 500/500 | 0 | 0 |
| 20250804_epam-ai-run-claude-4-sonnet | epam | 500 | 0 | 0 | 0.00% | no | 17660 | 500/500 | 0 | 0 |
| 20250928_trae_doubao_seed_code | trae | 500 | 0 | 0 | 0.00% | no | 15364 | 500/500 | 0 | 0 |
| 20251021_SalesforceAIResearch_SAGE_bash_only | sage | 500 | 0 | 0 | 0.00% | no | 18900 | 500/500 | 0 | 0 |
| 20251205_sonar-foundation-agent_claude-opus-4-5 | sonar | 500 | 0 | 0 | 0.00% | no | 30757 | 500/500 | 0 | 0 |

## Quarantine listing

Also written per agent under `methodology/adapter-quarantine/<folder>.txt` (class ∈ `file`, `unit`, `non_trajectory`).

| submission folder | file | class | detail |
|---|---|---|---|
| 20250522_sweagent_claude-4-sonnet-20250514 | `preds.json` | `non_trajectory` | stem does not match <owner>__<repo>-<n> |
