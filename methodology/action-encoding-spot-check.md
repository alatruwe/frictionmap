# Action-encoding reproducibility spot-check (Task 2)

*Generated 2026-09-07 by `methodology/scripts/spot_check_action_encodings.py`. Seed **20260907** (`action_encoding.spotcheck.SEED`). Replication package: `/Users/adelinelatruwe/Projects/replication-package`. Scratch mirror: `/private/tmp/claude-502/-Users-adelinelatruwe-Projects-ai-friction-map/52ec26b1-b330-4d8c-afbd-a9539ce73f24/scratchpad/spotcheck` (not committed).*

## Result

- `enriched_encoding` exact match: **20/20**
- full-row match (all 10 CSV columns: instance_id, agent_name, framework, llm_name, is_failed, n_raw_steps, n_encoded_steps, enriched_encoding, base_encoding, has_lb_lt_distinction): **20/20**
- their script exit code: 0

## Sample

Rule: 5 × SAGE, 5 × Trae-doubao, 10 × uniform across the remaining 11 agents — implemented as 10 distinct agents drawn uniformly from the 11, one trajectory drawn uniformly from each. All draws are from the **joined** population only; an unjoined trajectory has no CSV row to compare against. For Trae-doubao that universe is the joined 483 of 500 population files (the 17 their parser skipped are out of the spot-check universe by construction; see `action-encoding-ingest.md`).

| # | submission folder | instance_id | encoding match | full-row match |
|---|---|---|---|---|
| 1 | 20251021_SalesforceAIResearch_SAGE_bash_only | sympy__sympy-20428 | yes | yes |
| 2 | 20251021_SalesforceAIResearch_SAGE_bash_only | django__django-13410 | yes | yes |
| 3 | 20251021_SalesforceAIResearch_SAGE_bash_only | sympy__sympy-18698 | yes | yes |
| 4 | 20251021_SalesforceAIResearch_SAGE_bash_only | django__django-13089 | yes | yes |
| 5 | 20251021_SalesforceAIResearch_SAGE_bash_only | django__django-15930 | yes | yes |
| 6 | 20250928_trae_doubao_seed_code | django__django-13363 | yes | yes |
| 7 | 20250928_trae_doubao_seed_code | sphinx-doc__sphinx-9673 | yes | yes |
| 8 | 20250928_trae_doubao_seed_code | sphinx-doc__sphinx-10614 | yes | yes |
| 9 | 20250928_trae_doubao_seed_code | pylint-dev__pylint-4970 | yes | yes |
| 10 | 20250928_trae_doubao_seed_code | sympy__sympy-22456 | yes | yes |
| 11 | 20240402_sweagent_gpt4 | astropy__astropy-14096 | yes | yes |
| 12 | 20240620_sweagent_claude3.5sonnet | django__django-13590 | yes | yes |
| 13 | 20240728_sweagent_gpt4o | django__django-15382 | yes | yes |
| 14 | 20250511_sweagent_lm_32b | sphinx-doc__sphinx-8621 | yes | yes |
| 15 | 20250522_sweagent_claude-4-sonnet-20250514 | scikit-learn__scikit-learn-13496 | yes | yes |
| 16 | 20250524_openhands_claude_4_sonnet | sympy__sympy-13372 | yes | yes |
| 17 | 20250716_openhands_kimi_k2 | sympy__sympy-23413 | yes | yes |
| 18 | 20250804_codesweep_sweagent_kimi_k2_instruct | sympy__sympy-12419 | yes | yes |
| 19 | 20250804_epam-ai-run-claude-4-sonnet | scikit-learn__scikit-learn-25747 | yes | yes |
| 20 | 20251205_sonar-foundation-agent_claude-opus-4-5 | django__django-11066 | yes | yes |

## Their script, unmodified

Run end to end (`main()`), inside the mirror, as: `uv run --no-project --with pandas --with numpy python scripts/data_processing/extract_enriched_encoding_all.py`. The mirror holds byte-identical copies (sha256 verified against the package before the run) of their script, their `config.py` (matches the registry-vendored hash), their `resolution_status.json`, and only the 20 sampled trajectory files, so `main()` encodes exactly these and writes its own `data/enriched_encodings_all.csv` in the mirror. Their package is not written to or imported from.

| copied file | sha256 |
|---|---|
| `scripts/data_processing/extract_enriched_encoding_all.py` | `4754346e67f7391c167186ac4e82cc5a09e81ec4270208a6a76f53f93875a0fe` |
| `scripts/config.py` | `8f6da96e829eb6b492e55a1f5569258c129987e3d988177a2ce9b3a8822e276e` |
| `data/resolution_status.json` | `ff8aab49365f902b34b3e79dff4be3aba0f9c72f46a5b01568bb4af91333214b` |

<details><summary>sha256 of the 20 copied trajectory files</summary>

- `20251021_SalesforceAIResearch_SAGE_bash_only/sympy__sympy-20428.traj.json` `ffc83289b07415ddfd3a73d45c9a9b06a0a3e23731fab03b63e4bf72319452e0`
- `20251021_SalesforceAIResearch_SAGE_bash_only/django__django-13410.traj.json` `65513bd6002f8e11fe7a02a60c94fc4fe0b269563ede02076015239197b552e6`
- `20251021_SalesforceAIResearch_SAGE_bash_only/sympy__sympy-18698.traj.json` `f081d48aab4603abd0deaef08cfd359ab6a2eb685d7669095bcfc354ec7cd540`
- `20251021_SalesforceAIResearch_SAGE_bash_only/django__django-13089.traj.json` `71594e427defc9158b5cf79c2b8e13c86b42766bc07746085f92ed61cdd4594b`
- `20251021_SalesforceAIResearch_SAGE_bash_only/django__django-15930.traj.json` `f43d1213737be1334ff1594f1bb3b9a443849b1c68f7945e5b33d8317cd490df`
- `20250928_trae_doubao_seed_code/django__django-13363.json` `2478027b05007c86bb686e049964377ce6c83cb82f422d1b4cf0728b3a35d545`
- `20250928_trae_doubao_seed_code/sphinx-doc__sphinx-9673.json` `0affc2c8c827a9611070fad6a3a705de3b026c74c32b553085205fee73ba3067`
- `20250928_trae_doubao_seed_code/sphinx-doc__sphinx-10614.json` `43524165213bdcceeda6836f7c06a822e4d22ac6350f73c150c3a6923c72db8e`
- `20250928_trae_doubao_seed_code/pylint-dev__pylint-4970.json` `ee94610fdffe09421c89e63a7fb91095f1622f7580eaf6cba26f4db75a813681`
- `20250928_trae_doubao_seed_code/sympy__sympy-22456.json` `85ce1af7309c145dd87279cfee03582d8f523a41e58fb4510f7a9a9b6f625ade`
- `20240402_sweagent_gpt4/astropy__astropy-14096.traj` `81b18d7218c97c9792d9987c40052db4f76f17daf468dde6ff6950dae8d50d76`
- `20240620_sweagent_claude3.5sonnet/django__django-13590.traj` `f8f3eaf96b2bbfe0ddd3631fed014827493317f520f0c0e43380816b375ddcbe`
- `20240728_sweagent_gpt4o/django__django-15382.traj` `a7015f88202091fce07e16af11e7ed29ccc9e0f9517b5567fed563097384ca6c`
- `20250511_sweagent_lm_32b/sphinx-doc__sphinx-8621.traj` `15ffad20a99d365125a40eb8c4100666b5ec43e23fa706692424bce7cad3bde2`
- `20250522_sweagent_claude-4-sonnet-20250514/scikit-learn__scikit-learn-13496.traj` `226ee60badaa917c06513a0b806c8807a224affa8e09f36aadbcfad2614fea48`
- `20250524_openhands_claude_4_sonnet/sympy__sympy-13372.json` `526a5b9048702f067863fcc3e1c58c057124e30efce0b015a8a8064488b61f90`
- `20250716_openhands_kimi_k2/sympy__sympy-23413.json` `117d727beb48fdfcb526272986afe76b7af21f23b6806ab898bbcec691161b4d`
- `20250804_codesweep_sweagent_kimi_k2_instruct/sympy__sympy-12419.traj` `a12cca34b5ca4f5d96d96966c40893af916ee443330008ce6614c10254a87195`
- `20250804_epam-ai-run-claude-4-sonnet/scikit-learn__scikit-learn-25747.traj` `bd53544bdeb349fe82d70e518b06346dfa38f4f17e42b5bf272e2e95fcb91f29`
- `20251205_sonar-foundation-agent_claude-opus-4-5/django__django-11066.json` `945159453ef3e293b71585ac7a24723c6bb30346792d44ea8beaeccb08d2fdc4`

</details>

<details><summary>their stdout (tail)</summary>

```

  Symbol Res_frac Fail_frac     Diff    Direction
  ------------------------------------------------
  G        0.3310    0.1008  +0.2301  -> resolved
  Ps       0.0107    0.1471  -0.1365    -> failed
  Pr       0.0071    0.1253  -0.1182    -> failed
  Vr       0.0142    0.0708  -0.0566    -> failed
  Ls       0.0961    0.0572  +0.0389  -> resolved
  Vp       0.1601    0.1226  +0.0375  -> resolved
  L        0.0996    0.0627  +0.0370  -> resolved
  Ve       0.0249    0.0599  -0.0350    -> failed
  Vf       0.0000    0.0054  -0.0054    -> failed
  E        0.0071    0.0027  +0.0044  -> resolved
  Lb       0.0356    0.0327  +0.0029  -> resolved
  Pi       0.0000    0.0027  -0.0027    -> failed
  P        0.1708    0.1689  +0.0019  -> resolved
  Lt       0.0427    0.0409  +0.0018  -> resolved

======================================================================
  PER-LLM SUMMARY
======================================================================

  Agent           LLM                        N   Res% MedSteps
  ------------------------------------------------------------
  EPAM-AI         claude-4-sonnet            1   0.0%       23
  OpenHands       kimi-k2                    1   0.0%       80
  SWE-agent       gpt-4                      1   0.0%       35
  SWE-agent       gpt-4o                     1   0.0%       66
  SWE-agent       lm-32b                     1   0.0%       75
  SAGE            claude-4.5+gpt-5           5  60.0%       27
  Trae            doubao-seed-code           5  80.0%       20
  CodeSweep       kimi-k2                    1 100.0%       21
  OpenHands       claude-4-sonnet            1 100.0%       36
  SWE-agent       claude-3.5-sonnet          1 100.0%       26
  SWE-agent       claude-4-sonnet            1 100.0%       42
  Sonar           claude-opus-4.5            1 100.0%       23

======================================================================
  DONE
======================================================================
```

</details>

## Diffs

None — every compared column of every sampled row is identical between their shipped CSV and the rerun.

## SAGE and Trae-doubao — observed symbol distribution (descriptive only)

Their parser is action-channel-only with two known blind spots: `Pr` cannot fire on bash-mediated edits (SAGE is bash-fence), and it never reads Trae's `<function=` XML. Both agents are in their no-`Lb`/`Lt` group, so those two symbols cannot fire by construction. Per sampled trajectory, the rerun's encoding (identical to their CSV row wherever the table above says match):

### SAGE — 5 sampled trajectories

| instance_id | n symbols | distinct symbols | share `G` | encoding |
|---|---|---|---|---|
| sympy__sympy-20428 | 28 | Ls:5, L:2, P:6, Vp:6, Vr:2, G:7 | 25% | `Ls Ls G G Ls Ls Ls L G P P G G Vr P P P Vp Vp Vp Vp Vp Vp Vr P G L G` |
| django__django-13410 | 22 | Ls:1, L:7, P:8, Ve:2, G:4 | 18% | `Ls L P Ve P L L G L P L Ve P P G P L L P G P G` |
| sympy__sympy-18698 | 35 | Ls:4, L:11, P:11, Vp:5, Vr:2, G:2 | 6% | `L L P Vr Ls L Ls L L P L P P L Ls L Ls Vp P L Vr P Vp Vp Vp Vp P P P L L P G P G` |
| django__django-13089 | 27 | Ls:3, P:8, Vp:5, G:11 | 41% | `Ls G G Ls G P Vp P G P P Vp Vp P G P Ls G G Vp Vp P G P G G G` |
| django__django-15930 | 24 | Ls:7, L:1, P:7, Vp:3, Vr:1, G:5 | 21% | `Ls Ls G P Ls Ls P Ls Ls Vr P P Vp Vp Vp G P G P L Ls G P G` |

Aggregate over the 5: 136 symbols; `Ls` 20 (14.7%), `L` 21 (15.4%), `P` 40 (29.4%), `Vp` 19 (14.0%), `Ve` 2 (1.5%), `Vr` 5 (3.7%), `G` 29 (21.3%). Never fire in the sample: `Lb`, `Lt`, `Ps`, `Pi`, `Pr`, `Vf`, `E`.

Context, all 500 joined rows of this agent in their CSV: 19302 symbols; `Ls` 13.2%, `L` 17.8%, `P` 26.7%, `Ps` 0.1%, `Pi` 0.1%, `Vp` 19.3%, `Vf` 1.5%, `Ve` 2.1%, `Vr` 2.8%, `E` 0.3%, `G` 15.9%. Never fire agent-wide: `Lb`, `Lt`, `Pr`. Median symbols per row: 36.

### Trae-doubao — 5 sampled trajectories

| instance_id | n symbols | distinct symbols | share `G` | encoding |
|---|---|---|---|---|
| django__django-13363 | 8 | G:8 | 100% | `G G G G G G G G` |
| sphinx-doc__sphinx-9673 | 20 | G:20 | 100% | `G G G G G G G G G G G G G G G G G G G G` |
| sphinx-doc__sphinx-10614 | 25 | G:25 | 100% | `G G G G G G G G G G G G G G G G G G G G G G G G G` |
| pylint-dev__pylint-4970 | 24 | G:24 | 100% | `G G G G G G G G G G G G G G G G G G G G G G G G` |
| sympy__sympy-22456 | 8 | G:8 | 100% | `G G G G G G G G` |

Aggregate over the 5: 85 symbols; `G` 85 (100.0%). Never fire in the sample: `Lb`, `Lt`, `Ls`, `L`, `P`, `Ps`, `Pi`, `Pr`, `Vp`, `Vf`, `Ve`, `Vr`, `E`.

Context, all 483 joined rows of this agent in their CSV: 13175 symbols; `P` 0.0%, `Vp` 0.1%, `Ve` 0.0%, `E` 0.1%, `G` 99.7%. Never fire agent-wide: `Lb`, `Lt`, `Ls`, `L`, `Ps`, `Pi`, `Pr`, `Vf`, `Vr`. Median symbols per row: 18.

