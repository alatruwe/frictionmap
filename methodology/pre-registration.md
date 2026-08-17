# FrictionMap v2 — Pre-Registration

Status: DRAFT — pre-freeze. This document becomes binding at git tag v2-prereg-freeze. Until that tag exists, edits are permitted; after it, changes only via amendment noted in §9.
**Freeze rule:** after freeze, no edits to Sections 2–8. Deviations during the study are logged in Section 9 as deviations, with rationale, not absorbed silently.
**Scope gate (fixed in advance):** v2 is done when (a) the judge is validated or fails validation on my own corpus per Section 5, and (b) the stratification study produces a result in either direction per Section 7. Null results close the project successfully.

Remaining before freeze (checklist in §10): recon step (§6), corpus hash manifest (§3), labeling rubric + anchors (§4), sampling script (§3), judge prompt v1 + paraphrases (§5).

---

## 1. Background and claim under test

FrictionMap v1 ranks codebase files by friction using three deterministic signals: re-evaluation marker rate in extended-thinking text (`markers_per_100w`), reread bursts, and edit churn. All are counting operations; none involve LLM judgment.

v2 tests two things:

**H1 (judge validity).** An LLM judge scoring reasoning-level friction agrees with (i) blind human labels and (ii) v1 deterministic signals on the same corpus, at pre-committed thresholds.

**H2 (transfer).** v1 signals, built on interactive Claude Code sessions, behave as predicted (Section 6) on autonomous SWE-bench Verified trajectories, and friction measures stratify the leaderboard bucket in ways the prior 13-symbol action encoding (arXiv 2604.02547) does not capture.

Prior-art positioning is in `prior-art-map.md`. Their construct-validity section names chain-of-thought quality as the layer their encoding abstracts away; H1 targets exactly that layer.

## 2. Operational definitions

**Friction (construct):** observable evidence that the model's reasoning is not proceeding smoothly — backtracking, re-evaluation, contradiction of its own prior statements, repeated failed approaches to the same target — as distinct from ordinary sequential planning. The construct is domain-general; validation (§5) is domain-specific to this corpus. Cross-domain transfer (non-coding reasoning text) is future work, not a v2 claim.

**Judged unit:** the *attributed thinking block* — matches the v1 signal substrate and the attribution key.

**Judge input:** the thinking text of the unit, and nothing else — no signal values, no session metadata, no surrounding events. Judge and human labeler see identical input (§4). This is load-bearing for the layer claim (§1) and for the §5 cross-signal prediction; context-enriched judging is a different study.

**Judge output:** ordinal 0–3 friction score per unit (0 = smooth, 1 = minor re-evaluation, 2 = substantive backtracking, 3 = thrashing), plus a one-line quoted justification. Ordinal, not continuous — humans can't reliably hand-label continuous values, and the validation target is human labels.

**v1 artifact freeze:** the judge and transfer studies run against v1 exactly as shipped at commit `e2d6db2f59d189ce4deb7d756ba65b73617f5bdd` (HEAD of main, verified against remote 2026-08-16). If a v1 change becomes necessary before data collection (e.g., the C1 disposition below fires its fix branch), the pin moves by explicit amendment logged in §9 — never silently.

**Marker regex disposition (internal issue C1) — pre-committed decision rule:** the regex lacks a trailing `\b` ("waiting" matches "wait", "hmmm" matches "hmm"). Disposition is decided by measurement, with the rule committed here before the measurement runs:

1. *Measure:* diagnostic script computes the inflection-only share of marker hits on my own corpus — hits matched by the current regex but not by a boundary-corrected variant (per-marker trailing `\b` for alphanumeric-final markers; `"no,"` and `"now I'm realizing"` stay literal). Script committed; ~1 hour; touches no calibration.
2. *Rule:* if inflection-only share ≤ **5%** of total marker hits → **freeze as-is**; the leak stands as a documented, quantified limitation inherited by all marker-based results. If > 5% → **fix + re-validate** (hand-tag the diff set, re-run corpus-scale lexicon precision, re-run canonical-session sanity check) before any transfer-study work; est. 2–3 focused blocks, absorbed as a pre-registered consequence.
3. *Either way:* the same diagnostic runs per-model on leaderboard trajectories during the transfer study — inflection frequency may vary by LLM narration style, making an unquantified leak a potential cross-model confound in the primary stratification cut. Reported per-model in the writeup.

The threshold is committed before the script runs. Whichever branch fires, the number and the branch taken are reported.

## 3. Corpora and sampling

- **Own corpus:** The corpus is all sessions in the two v1 calibration corpora (attune, brownfield); no session-level selection. Session files are not part of this repository. Corpus identity is fixed by a committed hash manifest (methodology/corpus-manifest.txt: relative path + SHA-256 per session file) generated at freeze; no sessions are added, removed, or modified during the study — any change is detectable against the manifest. Unit count reported before labeling begins (same bash pass as the manifest; the count is descriptive, not a selection criterion). Known pool at drafting time: ~645 attributed thinking blocks (attune) + ~466 (brownfield) ≈ 1,100, of which ~375 marker-positive. Terminology note: v1's tier-3 attribution attaches to every thinking block (empty file_paths when no nearby tool_use carries paths), so 'attributed thinking block' names a pipeline stage, not a filter — the validation pool is all thinking blocks (1,111 at manifest time; 378 marker-positive). File-attachment (868/1,111 non-empty file_paths) is recorded per sampled block and reported as a descriptive split in the H1 results; it is not a sampling criterion.
- **Validation sample:** N = 100 units for hand-labeling, stratified: 50 sampled uniformly at random, 50 oversampled from units with `markers_per_100w > 0` (a purely random sample of a calm corpus risks labeling 95 smooth blocks and starving the agreement statistic). Sampled pooled across both corpora; **corpus identity recorded per unit**. Sampling script committed before labels are assigned.
- **Leaderboard bucket:** SWE-bench Verified public trajectory bucket (~9,374 trajectories, 19 agents, 14 LLMs, 500 tasks), same dataset as arXiv 2604.02547.

## 4. Blind-labeling protocol

Order is binding:

1. Labeling rubric written and frozen (the 0–3 scale above, with one anchor example per level — examples drawn from sessions *outside* the validation sample).
2. Sample drawn by committed script.
3. I hand-label all N units seeing only the thinking text — no signal values, no judge outputs, no file rankings, no session metadata beyond the text itself. (Identical input condition to the judge, per §2.)
4. Labels committed (hash) before the judge runs on the validation sample.

Contamination rule: if I see judge output or signal values for a unit before labeling it, that unit is discarded and replaced from a reserve list, and the event is logged in Section 9.

## 5. Judge validation — metrics and thresholds

All thresholds committed here, before any judge run.

**Judge-vs-human agreement (primary):** quadratic-weighted Cohen's κ on the 0–3 labels.
- κ ≥ 0.6 → **validated**; 0.4 ≤ κ < 0.6 → **partially validated**; κ < 0.4 → **judge fails validation**. (Landis–Koch conventional bands.)
- **Band consequences:** validated → judge scores enter Q1/Q2 (§7) as a friction measure. Partially validated → judge results reported as characterization only, **excluded from Q1/Q2 hypothesis tests**; deterministic signals carry the transfer study alone. Failed → judge dropped; §8 null-result path with failure-mode analysis.
- The **point estimate decides the band** — no CI adjustment in either direction. The CI is reported.
- **Secondary views reported:** κ on the random half of the sample alone (guards against the marker-oversampling half inflating agreement by construction), and per-corpus κ (guards against a corpus-dependent judge failure hiding in the pooled number).

**Judge-vs-deterministic agreement (secondary):** Spearman ρ between mean judge score per file and v1 per-file signal values, per signal, restricted to files with `n_blocks_attributed ≥ 3` (small-N floor; thin-evidence files are established attribution noise). No pass threshold — this is characterization, not gating. **Predictions:** ρ > 0 vs `markers_per_100w` (same substrate, overlapping construct); weaker or null vs reread bursts and edit churn (they measure action-level friction the judge cannot see from thinking text alone, except where the model narrates its actions). **Anticipated surprise, named in advance:** if judge-vs-churn ρ matched or exceeded judge-vs-markers, that would indicate models narrate action struggles thoroughly enough that text carries the action layer — an interesting result, not a failure.

**Stability checks (all must pass for "validated"):**
- *Rerun consistency:* judge runs 3× on the validation sample at **temperature 0**; exact-score agreement across runs **≥ 95%**. (At temp 0 the check targets residual/structural instability — borderline-block flapping, API-level nondeterminism — not sampling noise; the bar is correspondingly higher than it would be for a sampling regime.) Pre-committed contingency: if agreement lands near the bar (~93–96%), escalate to 5 runs on the disagreement blocks; logged in §9.
- *Prompt perturbation:* 2 semantically-equivalent paraphrases of the judge prompt, **written and committed to `judge-prompts/` before any judge run**; **pairwise κ across all three prompt versions ≥ 0.7, all pairs** (no averaging). Each variant runs once over the sample. The per-block disagreement pattern is reported; disagreement concentrating on blocks where hand labels were hesitant is confirmatory and stated as such.
- *Ordering/position effects:* eliminated by construction — each unit is judged in an independent single API call; no presentation order or shared context exists across units, so no positional check is required.

**Judge model:** **Claude Haiku 4.5, pinned dated snapshot (`claude-haiku-4-5-20251001`), temperature 0.** Model version change = new pre-registered run. Deployment is single-run per unit; the 3× reruns are validation-only scaffolding.

**Contingency (escalation rule):** escalation fires on any outcome below *validated* — κ < 0.6 or any stability-check miss. Sonnet 4.6 becomes the judge and does not inherit Haiku's validation: switching models triggers a **new pre-registered validation run** (full 500-call pass + stability + perturbation, same fixed thresholds) before any transfer work. The §5 bands and their consequences apply to the **final model in the escalation sequence**; the partially-validated and failed paths (§8) fire only after Sonnet's run. The 100 hand labels are reused across the escalation sequence; sequential testing against them is declared by the pre-committed escalation order (cheapest first), a fixed decision tree, not model selection on the labels.

**Self-preference caveat:** a Claude judge scoring thinking text from Claude-family agents among the 19 is a potential confound in the primary agent stratification (§7), not merely a generic bias risk; stated as a limitation in the writeup, unmeasured in v2. Cross-model agreement checks test a claim v2 does not make; future work.

**Cost:** est. tokens/unit and total run cost live in `cost-budget.md`. Judge prompts are frozen artifacts (`judge-prompts/`) — v1 of each prompt committed before the first validation run; later prompt versions are new pre-registered runs, not silent replacements. **Validation-vs-deployment length shift, named:** validation runs on ~90-token own-corpus blocks; leaderboard blocks may be substantially longer. κ validated at one input-length distribution and applied at another is a stated limitation.

## 6. Transfer-prediction table

Committed before any leaderboard trajectory is parsed. **Pre-freeze recon step:** before this table freezes, a format recon (~2 trajectories per agent) records, per agent format: presence/absence of read actions, edit actions, and reasoning/thinking text. Recon findings are recorded in this section. This checks whether the substrate exists — it does not compute signal values, and is not contamination. The adapter is specced against the formats the recon shows are parseable and reasoning-bearing, not all 8 frameworks; "transfers only to formats exposing X" is a finding.

Format per signal: prediction (transfers / degrades / cannot transfer), mechanism, and what result would falsify the prediction.

| Signal | Prediction (confirmed) | Mechanism | Falsifier |
|---|---|---|---|
| markers_per_100w | Transfers if trajectories expose thinking/reasoning text; **cannot transfer** for agents whose .traj format omits reasoning | Language-level; substrate-dependent | Reasoning text present but marker rates degenerate (zero everywhere, or non-comparable to own corpus) |
| reread_bursts | Transfers with adapter mapping of read actions | Action-level; their Locate symbols prove the substrate exists | **Saturation** — autonomous agents reread as policy at rates flattening per-file variance (documented prior: tool_use_coupling saturated at 97–99% on own corpora) |
| edit_churn | Transfers with adapter mapping of edit actions | Action-level; ≈ their Pr symbol | **Saturation**, same mechanism as reread_bursts |
| complexity normalization | **Cannot transfer** — reads on-disk file content; no local checkout for leaderboard repos | Known (C7) | — |
| 8 parked signals | Out of scope for v2; remain parked | — | — |

**Recon findings (recorded 2026-08-16, corrected same day after raw-event verification; full record incl. correction log in `swe-bench-recon-stage3-findings.md`):** 2 trajectories per agent inspected, 19/19 agents, cross-file format consistency verified. Read/edit action substrate present 19/19 (15 structured tool calls; 2 pseudo-XML regex; 1 bash-fence regex; 1 inferable from labeled tool results). An initial five-class reasoning taxonomy (A–E) was falsified in three cells by raw-event inspection and rebuilt on two properties: whether text is **designated as reasoning** by the agent's format (extraction = counting, not interpretation) and whether the channel is **private or public narration**:

| Substrate | Agents | Count |
|---|---|---|
| Private designated (thinking blocks: Sonar; `<think>` tags: Trae-doubao; think-tool arguments: OpenHands-claude-4-sonnet, OpenHands-kimi-k2 — sparse, ~2–3 calls/trajectory) | 4 | 4 |
| Public designated (labeled narration — `thought` field: 6 SWE-agent + CodeSweep; `Thoughts` entries: EPAM; `THOUGHT:` prefix: SAGE) | 9 | 13 |
| Undesignated narration (OpenHands-CodeAct-2.1, Trae-claude [declared `reasoning` key never populated], Skywork, devstral) | 4 | 17 |
| None (OpenHands-gpt5: reasoning tokens withheld; OpenHands-opus-4.5: think-tool arguments severed in export) | 2 | 19 |

Verified facts behind the rebuild: SWE-agent `thought` is derived from the public response in all format versions (new format: byte-identical to `content`, 53/53 and 74/74 events; old format: extracted prose segment) — no SWE-agent variant has a private channel. Trae-claude's `reasoning` key: 35 events, 0 populated (file 2: key absent). Think-tool census across all agents: exactly 2 agents use it.

**BINDING — H2 analysis population:** the **13 designated-substrate agents**. Inclusion principle: extraction of judged text must be counting (designer-drawn boundary), never interpretation (our judgment about which prose spans are reasoning). Undesignated-narration and no-substrate agents carry no H2 claims; they may appear in a descriptive appendix only. Consequences, all binding:
1. Q1's contested-task definition and all cross-agent analyses operate within the 13-agent population.
2. **Channel-type stratification:** all marker-rate and judge-score results are reported split private-designated vs. public-designated. Rationale: marker base rates plausibly differ between private reasoning and audience-directed narration; pooling would hide this. Stratification is descriptive, not a hypothesis test.
3. v1's behavioral gating requires marker substrate; on excluded agents it cannot run as designed — a second, independent reason they carry no H2 claims.
4. **Parse-validation fallback:** recon verified structure on 2 files/agent. If at adapter time designated-reasoning extraction fails on >10% of an agent's files, that agent drops from the population with a documented handoff (measure-then-dispose, same shape as C1).
5. **Density caveat:** think-tool agents contribute few designated blocks per trajectory; sampling and per-agent aggregation must not assume comparable block density across the 13.

Confound notes carried to §7: substrate type correlates with framework (all SWE-agent formats are public-designated; OpenHands spans private/undesignated/none). Reasoning absence is an export/API artifact, not a model-family artifact (one GPT, one Claude). ~9 of the 13 are Claude-family — the Claude-judge confound stands as written.

**Length-confound classification (adopted from 2604.02547):** before analysis, each transferring signal is classified as difficulty-proxy vs. strategy-signal by its **Spearman** correlation with trajectory length, computed per-signal per-transferring-format on the study sample, **before any outcome variable is examined**; any signal with |ρ| > **0.5** vs. length gets within-task analysis only (Approach B), never pooled cross-task claims. Note: the primary analyses (Q1, Q2) are within-task / length-controlled by construction; this cutoff fences the exploratory perimeter only, and no primary result depends on it.

## 7. Stratification study design

- **Primary cut:** by LLM, not framework (their RQ3: LLM identity dominates behavior). Framework is the secondary cut.
- **Comparisons:** within-task (fix task, vary agents) wherever the agent×task matrix permits; Wilcoxon signed-rank, two-sided. Cross-task within-agent comparisons use Mann-Whitney U with Cliff's δ, reported with the difficulty caveat.
- **Questions of record, ranked before data (rank is binding):**
  - *Q1 (primary — validity):* do friction measures (transferred v1 signals; judge scores if validated per §5 and if reasoning text exists in the trajectories) separate resolved from failed trajectories within-task, and does that separation add information beyond their 13-symbol encoding? **Operationalized: Q1 passes iff friction measures show a significant within-task effect (α = 0.05) after controlling for their three structural dimensions (context gathering, opening patch intensity, validation effort), on the held-out half of contested tasks.** A contested task = one whose agent×task cell contains both resolved and failed trajectories (uncontested tasks carry zero within-task outcome signal). Split: 50/50 random by task, seed committed in the sampling script; exploration permitted on the first half; the confirmatory test runs **once** on the held-out half — no peeking, no re-splits; misfires logged in §9. **The uncontrolled within-task effect is reported as a descriptive result regardless of Q1's verdict** — it is the operationally relevant number (friction measures alone separating outcomes), distinct from the controlled research claim. Q1 determines which claim is earned: "measures a layer beyond the action encoding" vs "makes a known layer deployable"; both are reportable, only the first requires the control.
  - *Q2 (secondary — operational value):* among *resolved* trajectories on the same task, does friction predict cost (tokens where available, else step count) **beyond trajectory length**? Guard against mechanical correlation: count-based signals (reread bursts, edit churn) enter as rates or via partial correlation controlling for step count. A raw friction↔cost correlation without the length control is not a result under this registration.
    *Purpose:* diagnostic, not just predictive. The billing meter reports total spend; it cannot distinguish productive spend from struggle or localize where struggle concentrated. Q2 tests whether friction measures — with file/locus attribution where the trajectory format permits — discriminate friction-cost from productive cost. *Scope fence:* v2 is observational. A positive Q2 result establishes that cost concentrates where friction concentrates; it does not establish that addressing friction reduces cost. That is a causal claim requiring an intervention study, out of scope for v2 and stated in the writeup as motivated future work, not a finding.
- **Sample:** decided by pre-committed cost rule, not by branch. **Cost ceiling C = $250, frozen here** (committed before adapter measurements exist — the branch condition is fixed before the data that could game it). Rule: (1) build the adapter; measure realized units-per-trajectory U and median block tokens B on the bucket; (2) project full-bucket judge cost at the **validated judge model's** batch rates (Haiku 4.5 by default; Sonnet 4.6 if the §5 escalation fired); (3) projected ≤ $250 → **full bucket**; (4) else → **subsample** at the largest task count in {200, 100, 50} whose projection fits C — random by task, all 19 agents per task retained (the matrix structure is the method). Reference: at mid-mid assumptions (U=40, B=300) full bucket projects ~$188 at Haiku batch rates and fits with headroom; full bucket is the default outcome under Haiku. Details in `cost-budget.md`.

## 8. Null results — what counts, and what gets published

Each is a finding, published as stated:

- The escalation sequence terminates below *validated* (Sonnet κ < 0.4 or stability failure) → "an LLM judge could not be validated for reasoning-level friction against blind human labels on this corpus" — plus the failure mode analysis across both models in the sequence.
- Marker signal cannot transfer (no reasoning text in trajectory formats) → substrate finding; the transfer table predicted the dependency.
- Friction measures add nothing beyond the 13-symbol encoding within-task → "the deterministic action layer captures what my measures capture" — a direct, honest answer to the same-dataset question in the prior-art map. (Per §7, the deployability framing of that same result — a known layer made runnable on any session log — is reported alongside.)

## 9. Deviations log

| Date | Section | What changed | Why | Impact on claims |
|---|---|---|---|---|
| — | — | — | — | — |

## 10. Artifacts and freeze checklist

- [x] All DECISION items resolved (session 2026-08-15; judge model + cost via budget handoff)
- [x] Escalation rule, band composition, self-preference specificity, label-reuse clause reconciled (session 2026-08-15)
- [x] Cost-rule model reference fixed (§7: validated judge model's rates, not Haiku unconditionally); ordering check replaced with by-construction note (§5)
- [x] Recon step run; findings recorded in §6 (2026-08-16; initial taxonomy corrected same day via raw-event verification; BINDING 13-agent designated-substrate population; full record in `swe-bench-recon-stage3-findings.md`)
- [x] v1 commit hash pinned (§2) — `e2d6db2`, 2026-08-16
- [x] Corpus hash manifest generated + committed (§3) — `corpus-manifest.txt`, 147 session files (66 attune + 81 brownfield), 2026-08-16
- [ ] Labeling rubric + anchor examples written (§4.1)
- [ ] Sampling script committed (§3, includes Q1 split seed per §7)
- [ ] Judge prompt v1 + 2 paraphrases committed to `judge-prompts/` (§5)
- [x] cost-budget.md reconciled (Luna row cut; task count = 500; escalation math restated at C = $250 incl. Sonnet re-validation; boundary formula corrected; decision-rule step 3 references the validated judge model's rates) (§5, §7)
- [ ] cost-budget.md committed to public repo
- [ ] This doc committed to public repo; freeze = the commit flipping DRAFT → FROZEN; that commit hash is the freeze timestamp
