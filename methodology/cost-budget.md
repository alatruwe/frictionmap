# cost-budget.md

FrictionMap v2 — judge-run cost budget. Resolves against pre-registration §7 (full-bucket vs subsample). Prices verified 2026-08-15 from public rate trackers; re-verify at freeze.

## Model prices (per MTok, input/output)

| Model | Standard | Batch (50%) | Pinning |
|---|---|---|---|
| Claude Haiku 4.5 | $1 / $5 | $0.50 / $2.50 | dated snapshot (`claude-haiku-4-5-20251001`) |
| Claude Sonnet 4.6 | $3 / $15 | $1.50 / $7.50 | dated snapshot |
| Gemini Flash tiers | — | — | **excluded**: deprecation cadence (2.0 Flash shut down June 2026) incompatible with version-pin rule |

Prompt caching (scaffold cached at ~10% of input rate) stacks with batch per vendor docs; treated as upside, not counted in headline numbers.

## Token assumptions

| Parameter | Value | Basis |
|---|---|---|
| Prompt scaffold (rubric + instructions) | 2,500 tok | drafted prompts, anchors included; exact count at freeze |
| Output (digit + one-line justification) | ~100 tok | justification-then-score ordering |
| Own-corpus block | ~90 tok | median 60–70 words × ~1.3 tok/word |
| SWE-bench block **B** | 100 / 300 / 800 tok | unknown until adapter exists; low/mid/high |
| Units per trajectory **U** | 10 / 40 / 100 | unknown until adapter exists; low/mid/high |
| Trajectories | 9,374 | fixed (bucket) |
| Tasks in bucket | 500 | published constant (SWE-bench Verified) |

Per-call cost formula: `calls × [(S + B)/1e6 × input_rate + 100/1e6 × output_rate]`.
Cost is linear in both U and (S + B), S = scaffold. B is a second unknown the §7 decision must wait on, same as U.

Tables (a)–(c) and the boundary figures are computed at S=500, output=40; recompute at freeze. At S≈2,500 the full-bucket branch likely depends on prompt caching — verify cache-read rate and Haiku 4.5's minimum cacheable prompt length at freeze.

## (a) Validation runs — 500 calls, own corpus

Input ≈ 0.30 MTok, output ≈ 0.02 MTok.

| Model | Cost |
|---|---|
| Haiku 4.5 | **$0.40** |
| Sonnet 4.6 | $1.19 |

Validation cost is a rounding error at every candidate. Model choice is not cost-constrained at this stage; it is constrained by the validation gate.

Per Decision 5, cross-model agreement is future work, not v2 scope. The writeup carries the limitation as one sentence, stated in its specific form: a Claude judge scoring Claude-family agents among the 19 is a potential confound in the agent stratification, unmeasured in v2.

## (b) Full-bucket transfer run — 9,374 trajectories, B = 300 (mid)

| U | Calls | Haiku std | Haiku batch | Sonnet std | Sonnet batch |
|---|---|---|---|---|---|
| 10 | 93,740 | $94 | **$47** | $281 | $141 |
| 40 | 374,960 | $375 | **$188** | $1,125 | $563 |
| 100 | 937,400 | $937 | **$469** | $2,813 | $1,406 |

B sensitivity: B = 800 multiplies input cost ×1.6 vs B = 300 (e.g. U=40 Haiku batch → ~$295). B = 100 → ×0.75 (~$141).

## (c) Subsample scenarios — random by task, all 19 agents per task retained (§7 rule)

U = 40, B = 300, Haiku:

Trajectories scale as (tasks / 500) × 9,374 ≈ 18.7 per task.

| Tasks sampled | Trajectories | Calls | Std | Batch |
|---|---|---|---|---|
| 50 | ~937 | ~37,500 | $37 | **$19** |
| 100 | ~1,875 | ~75,000 | $75 | **$37** |
| 200 | ~3,750 | ~150,000 | $150 | **$75** |

Scale linearly for other U and B.

## §7 decision rule (proposed for freeze)

Freeze a **rule**, not a branch — U and B are unknown by design until the adapter exists, so pre-committing a branch now would be guessing dressed as rigor.

1. Cost ceiling **C = $250** (frozen 2026-08-15).
2. Build the adapter; measure realized U and median B on the bucket.
3. Project full-bucket cost at Haiku batch rates using measured U, B.
4. If projected ≤ C → **full bucket**.
5. Else → **subsample** at the largest task count in {200, 100, 50} whose projection fits C, random by task, all agents per task retained.

Boundary at C = $250, Haiku batch: U × [(500 + B)/2 + 100] ≤ ~26,700. At B = 300 → U ≤ 53 (mid scenario fits with headroom). At B = 800 → U ≤ 36 (mid scenario narrowly fails → subsample at 200 tasks, ~$118). *Correction note: an earlier draft stated the boundary as "U × (500+B) ≤ ~430,000," which was wrong by roughly 10×; the formula above is the operative one.*

## Escalation contingency

If Haiku fails the validation gate, Sonnet 4.6 does not inherit validation. Per §5's own rule, escalation is a **new pre-registered run**: full 500-call validation pass ($1.19), 3-rerun stability check, 2-paraphrase perturbation check — all against the same fixed gate threshold — then transfer. The hand labels are reused; sequential testing against them is declared by the pre-committed escalation order (cheapest first), which is a fixed decision tree, not model selection.

Transfer numbers under Sonnet: every figure ×3. Full bucket at mid-mid → $563 batch, over the $250 ceiling → subsample. At 200 tasks ($225 batch) fits under C = $250; the ceiling rule handles this without amendment.
