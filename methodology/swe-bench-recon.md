# SWE-bench Trajectory Recon — Full Record

*FrictionMap v2, pre-registration §6 recon step. Run 2026-08-16, single session.*
*Supersedes: `swe-bench-recon-checklist.md`, `swe-bench-recon-stage1-findings.md`, `swe-bench-recon-stage3-findings.md`.*

## Purpose and scope fence

Before freezing the v2 pre-registration, verify that the SWE-bench Verified trajectory corpus (arXiv 2604.02547; ~9,374 trajectories, 19 agents, 500 tasks) contains the substrate v1's signals need: read actions, edit actions, and reasoning/thinking text, per agent format.

Scope fence (pre-committed in §6): recon records **substrate presence only**. No signal values computed, no marker counting, no realized cost measurement. The fence is what keeps recon out of contamination territory — the transfer-prediction table freezes against structure, not against peeked results.

## Stage 1 — Sourcing

**Source located:** trajectories live in a public S3 bucket (`swe-bench-submissions`), not in the `swe-bench/experiments` git repo. Download per submission via `python -m analysis.download_logs evaluation/verified/<folder>`. **Access is anonymous** — the script uses `signature_version=UNSIGNED`; the repo README's claim that an AWS account is required is stale.

**Bucket identity:** the repo holds 134 Verified submissions (full leaderboard history). The paper's Table 6 defines the 19-agent subset with framework, LLM, and resolution rate per agent. Three agents have 443–499 trajectories instead of 500 (timeouts/infra failures), giving 9,374.

**Folder mapping:** 16 of 19 mapped unambiguously by name. Three resolved from in-repo metadata:

| Agent | Resolved to | Evidence |
|---|---|---|
| Skywork / qwen-32b | `20250616_Skywork-SWE-32B` | 190 resolved = 38.0% ≈ Table 6's 38.1%; TTS_Bo8 variant is 47.0% |
| SAGE / claude-4.5+gpt-5 | `20251021_SalesforceAIResearch_SAGE_bash_only` | 365 = 73.0% exact; OpenHands variant is 73.8% |
| Trae / claude-4-sonnet+opus | `20250612_trae` | metadata lists claude-4-sonnet + claude-4-opus; sibling folder is model-undisclosed. Medium-high confidence; raw-rate gap vs Table 6 consistent with gap-agent denominator |

Full 19-row mapping table: see appendix A.

**Size finding:** one full submission's `trajs/` = 5.0 GB → full corpus ≈ 50–95 GB. Recon proceeded on a deterministic sample instead: first 2 alphabetical trajectory files per agent (both astropy tasks), pulled by `scripts/recon_pull.py`. Full-corpus storage is a post-recon, pre-adapter logistics item.

## Stage 2 — Sample pull

38+ files, 19 agents, ~7 MB. One agent (`20250522_sweagent_claude-4-sonnet`) stores config/patch files alongside trajectories and needed a targeted re-pull filtering to `.traj`. Cross-file format consistency verified for all 19 agents (2 files each, identical top-level shape).

## Stage 3 — Format inspection

### Action substrate: present 19/19

Four parsing shapes: structured tool calls (15 agents — tool name + JSON args with file paths; read vs edit distinguished by tool + command arg); inline pseudo-XML `<function=...>` tags (Skywork, devstral — regex); inline bash fences (SAGE — command-class regex, same approach as the prior-art paper); labeled tool results only (OH-opus-4.5 — action class inferable, degraded).

### Reasoning substrate: initial taxonomy, falsified and rebuilt

Structural key-scanning (4 inspection passes) produced a five-class taxonomy (A: dedicated thought field; B: thinking blocks; C: inline-tagged; D: narration-only; E: none). **Raw-event inspection falsified three cells:**

1. **SWE-agent `thought` is not a separate channel.** New format: byte-identical to `content` (verified 53/53, 74/74 events). Old format: differs only because old `content` bundles thought+action and `thought` is the extracted prose segment. Every version derives `thought` from the single public response — a labeled copy of narration.
2. **Trae-claude's `reasoning` key is never populated.** 35 events with the key, 0 non-null; second file lacks the key. Declared channel, empty.
3. **Two OpenHands agents hide a designated reasoning channel in tool-call arguments** — a tool named `think` whose `thought` argument carries genuine reasoning (OH-claude-4-sonnet: 3/36 calls; OH-kimi-k2: 2/40). The key-scan read only content blocks and misfiled both as narration-only. This also reframes OH-opus-4.5: same think-tool pattern, but its export kept the tool result ("Your thought has been logged.") and severed the arguments — reasoning existed in-channel; the release dropped it.

**Process note:** the falsified cells were caught by dumping whole raw events with structure intact (`scripts/show_class_examples.py` → `substrate_class_examples.md`) instead of trusting pre-extracted fields, then confirmed by a targeted scan (`scripts/verify_classes.py`). Summary-level inspection produced a plausible, wrong table.

### Corrected taxonomy (authoritative)

Two properties, not a class ladder: **is the text designated as reasoning by the format** (extraction = counting, not interpretation), and **is the channel private or public narration**:

| Substrate | Agents | Count |
|---|---|---|
| **Private designated** — thinking blocks (Sonar); `<think>` tags (Trae-doubao); think-tool arguments (OH-claude-4-sonnet, OH-kimi-k2; sparse, ~2–3/trajectory) | 4 | 4 |
| **Public designated** — labeled narration: `thought` field (SWE-agent ×6, CodeSweep); `Thoughts` entries (EPAM); `THOUGHT:` prefix (SAGE) | 9 | 13 |
| **Undesignated narration** — OH-CodeAct-2.1, Trae-claude, Skywork, devstral | 4 | 17 |
| **None** — OH-gpt5 (reasoning tokens withheld by API), OH-opus-4.5 (think-tool arguments severed in export) | 2 | 19 |

## Binding population decision

Recorded in pre-registration §6, which is authoritative; summary:

**H2 analysis population = the 13 designated-substrate agents.** Inclusion principle: extraction of judged text must be counting (designer-drawn boundary), never interpretation (our judgment about which prose spans are reasoning). Binding consequences: Q1 and all cross-agent analyses operate within the 13; channel type (private vs. public designated) is a pre-registered descriptive stratification; excluded agents appear in a descriptive appendix only; parse-validation fallback (>10% extraction failure per agent at adapter time → agent drops with documented handoff); block-density caveat for think-tool agents (few designated blocks per trajectory — sampling and per-agent aggregation must not assume comparable density).

Confounds carried to §7: substrate type correlates with framework (all SWE-agent formats public-designated; OpenHands spans private/undesignated/none); ~9 of 13 are Claude-family (Claude-judge confound stands); reasoning absence is an export/API artifact, not a model-family artifact (one GPT, one Claude).

## Caveats

- Sample: 2 trajectories per agent, both astropy tasks. Format variation across repos/tasks unverified beyond these; the adapter needs per-file format validation with a quarantine path.
- Trae folder mapping is medium-high confidence; Zenodo supplement (record 19351830) is the optional definitive check.
- Sonar thinking blocks carry a `num_tokens` field — noted as structure only.

## Artifacts

- `scripts/recon_pull.py` — deterministic sample pull (first-2-alphabetical per agent)
- `scripts/show_class_examples.py` → `substrate_class_examples.md` — raw-event examples per substrate type
- `scripts/verify_classes.py` — falsification scan (thought/content identity, reasoning-key population, think-tool census)
- `recon_samples.zip` — the 40-file sample corpus (not committed; regenerable via recon_pull.py)

## Appendix A — 19-agent folder mapping

| # | Framework / LLM | Res. rate | Submission folder |
|---|---|---|---|
| 1 | Sonar / claude-opus-4.5 | 79.2% | `20251205_sonar-foundation-agent_claude-opus-4-5` |
| 2 | Trae / doubao-seed-code | 78.5% | `20250928_trae_doubao_seed_code` |
| 3 | OpenHands / claude-opus-4.5 | 78.3% | `20251127_openhands_claude-opus-4-5` |
| 4 | EPAM-AI / claude-4-sonnet | 76.8% | `20250804_epam-ai-run-claude-4-sonnet` |
| 5 | Trae / claude-4-sonnet+opus | 75.4% | `20250612_trae` |
| 6 | SAGE / claude-4.5+gpt-5 | 73.0% | `20251021_SalesforceAIResearch_SAGE_bash_only` |
| 7 | OpenHands / gpt-5 | 71.8% | `20250807_openhands_gpt5` |
| 8 | OpenHands / claude-4-sonnet | 70.4% | `20250524_openhands_claude_4_sonnet` |
| 9 | SWE-agent / claude-4-sonnet | 66.6% | `20250522_sweagent_claude-4-sonnet-20250514` |
| 10 | OpenHands / kimi-k2 | 65.4% | `20250716_openhands_kimi_k2` |
| 11 | CodeSweep / kimi-k2 | 53.4% | `20250804_codesweep_sweagent_kimi_k2_instruct` |
| 12 | OpenHands / claude-3.5-sonnet | 53.0% | `20241029_OpenHands-CodeAct-2.1-sonnet-20241022` |
| 13 | OpenHands / devstral-small | 46.8% | `20250520_openhands_devstral_small` |
| 14 | SWE-agent / lm-32b | 40.2% | `20250511_sweagent_lm_32b` |
| 15 | Skywork / qwen-32b | 38.1% | `20250616_Skywork-SWE-32B` |
| 16 | SWE-agent / claude-3.5-sonnet | 33.6% | `20240620_sweagent_claude3.5sonnet` |
| 17 | SWE-agent / gpt-4o | 24.9% | `20240728_sweagent_gpt4o` |
| 18 | SWE-agent / gpt-4 | 22.6% | `20240402_sweagent_gpt4` |
| 19 | SWE-agent / claude-3-opus | 15.1% | `20240402_sweagent_claude3opus` |
