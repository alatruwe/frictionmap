# cost-budget.md

FrictionMap v2 — judge-run cost budget. Resolves against pre-registration §7 (full-bucket vs subsample). Prices verified 2026-08-15 and re-verified 2026-08-29 (platform pricing table). Frozen with the pre-registration.

## Model prices (per MTok, input/output)

| Model | Standard | Batch (50%) | ID |
|---|---|---|---|
| Claude Haiku 4.5 | $1 / $5 | $0.50 / $2.50 | `claude-haiku-4-5-20251001` (dated snapshot) |
| Claude Sonnet 5 (escalation) | $2 / $10 | $1 / $5 | `claude-sonnet-5` (dateless, pinned per Anthropic model-versioning doc) |
| Gemini Flash tiers | — | — | **excluded**: deprecation cadence incompatible with version-pin rule |

Escalation model changed from Sonnet 4.6 to Sonnet 5 on 2026-08-29: Sonnet 4.6 is a legacy model with a retirement date inside the plausible life of the writeup; a legacy escalation judge is a reproducibility liability. Price was not the reason; it happens to be lower.

**Prompt caching is not counted, and not used.** Haiku 4.5's minimum cacheable prompt length is 4,096 tokens; the judge scaffold is ~3,000 and does not qualify. Independently, batch requests are processed asynchronously against a 5-minute cache TTL, so hit rate is not controllable. All figures below are uncached.

## Token assumptions

| Parameter | Value | Basis |
|---|---|---|
| Prompt scaffold **S** (system prompt incl. anchors) | 3,000 tok | v1.md lines above `=== USER TURN ===` = 2,327 words by `wc -w` (whole file 2,334) × ~1.3 tok/word; estimate, exact count recorded at first judge run |
| Output (justification + score) | 100 tok | justification-then-score ordering |
| Own-corpus block | ~90 tok | median 60–70 words × ~1.3 tok/word |
| SWE-bench block **B** | 100 / 300 / 800 tok | unknown until adapter exists; low/mid/high |
| Units per trajectory **U** | 10 / 40 / 100 | unknown until adapter exists; low/mid/high |
| Trajectories (13-agent population) | ~6,500 | 13 × 500; three agents have 443–499, so this is a conservative ceiling |
| Tasks in bucket | 500 | published constant (SWE-bench Verified) |
| Trajectories per sampled task | 13 | all population agents retained per task (§7) |

Per-call cost: `(S + B)/1e6 × input_rate + 100/1e6 × output_rate`. Total = calls × per-call.
S dominates input: at S = 3,000, B moves per-call cost by <15% across its full range. **U is the decisive unknown.**

## (a) Validation runs — own corpus, 500 calls per pass, standard rates

Input per call ≈ 3,090 tok. Passes: 3 reruns + 2 paraphrases = 5 × 500 = 2,500 calls.

| Model | Per pass | Full validation (5 passes) |
|---|---|---|
| Haiku 4.5 | $1.80 | $9.00 |
| Sonnet 5 | $3.59 | $17.95 |

Validation cost is a rounding error at either model. Model choice is constrained by the validation gate, not cost.

Per Decision 5, cross-model agreement is future work. The writeup carries the limitation in its specific form: a Claude judge scoring Claude-family agents among the 13 is a potential confound in the agent stratification, unmeasured in v2.

## (b) Full-population transfer run — ~6,500 trajectories, 13 agents, B = 300

| U | Calls | Haiku std | Haiku batch | Sonnet 5 std | Sonnet 5 batch |
|---|---|---|---|---|---|
| 10 | 65,000 | $247 | **$124** | $494 | $247 |
| 40 | 260,000 | $988 | **$494** | $1,976 | $988 |
| 100 | 650,000 | $2,470 | **$1,235** | $4,940 | $2,470 |

B sensitivity at U=40, Haiku batch: B = 100 → $468; B = 800 → $559.

## (c) Subsample scenarios — random by task, 13 agents per task (§7 rule)

U = 40, B = 300, Haiku:

| Tasks sampled | Trajectories | Calls | Std | Batch |
|---|---|---|---|---|
| 50 | 650 | 26,000 | $99 | **$49** |
| 100 | 1,300 | 52,000 | $198 | **$99** |
| 200 | 2,600 | 104,000 | $395 | **$198** |

Scale linearly in U and calls.

## §7 decision rule (frozen)

Freeze a **rule**, not a branch — U and B are unknown by design until the adapter exists.

1. Cost ceiling **C = $250** (frozen 2026-08-15).
2. Build the adapter; measure realized U and median B on the 13-agent population.
3. Project full-population cost at the validated judge model's batch rates using measured U, B, and the measured scaffold token count.
4. If projected ≤ C → **full population**.
5. Else → **subsample** at the largest task count in {200, 100, 50} whose projection fits C, random by task, all 13 population agents per task retained.

Boundary at C = $250, Haiku batch, ~6,500 trajectories: `U × [(S + B)/2 + 250] ≤ ~38,500`. At S = 3,000: B = 300 → U ≤ 20; B = 800 → U ≤ 17. **Expected outcome at mid-mid (U=40, B=300): subsample at 200 tasks (~$198).** Full population fits only at low U. Subsample-at-200 holds up to U ≈ 50.

*Correction note: an earlier draft stated the boundary as "U × (500+B) ≤ ~430,000," which was wrong by roughly 10×; the formula above is the operative one.*

Task count has a floor as well as a ceiling (pre-registration §7). The floor is a power requirement fixed from Phase 1 labeler self-consistency; C yields to it. Under the rule, C is the amount spent by default, not the amount refused above.

## Escalation contingency

If Haiku fails the validation gate, Sonnet 5 does not inherit validation. Per §5: new pre-registered run — full validation pass ($17.95 for all five passes), 3-rerun stability, 2-paraphrase perturbation, same thresholds — then transfer.

Transfer numbers under Sonnet 5: every Haiku figure ×2. Full population at mid-mid → $988 batch, over C → subsample. 200 tasks → $395, over C. **100 tasks → $198, fits.** The escalation path at mid-mid therefore runs on half the task count of the Haiku path; the ceiling rule handles this without amendment, and the task-count difference is reported alongside results.
