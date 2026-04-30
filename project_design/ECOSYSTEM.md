# Ecosystem — AI Friction and Legibility

Adjacent-space thinking around the friction map. Not hackathon scope. Captures what the friction map is one point in, so the near-term work stays grounded in a larger picture without committing to it.

Separate from `PROJECT_DESIGN.md` (the product being built), `ASSUMPTIONS.md` (what's been tested), and `TRADEOFFS.md` (decisions in the current build). This file is about where the project could go and the principles that would keep it honest.

---

## Foundational insight

AI cognitive load is observable where human cognitive load wasn't. Thinking blocks, re-reads, edit churn, marker density — all machine-readable in session transcripts. A senior engineer's frustration with a gnarly file is invisible; Claude's is in the transcript.

That's the foundation. Everything downstream — friction maps, legibility scores, PR checks, benchmarks — is a way of exploiting the fact that this signal now exists.

---

## The grid

Two axes: time-mode × scope.

|  | Retrospective | Generalized scoring | Live |
|---|---|---|---|
| **Single codebase** | Friction map (today) | Per-codebase legibility model, PR check | Live session readout, IDE coaching |
| **Cross codebase** | Benchmarking via file-intrinsic proxies (with caveat) | Generalized model (Anthropic-shaped, not independent-product-shaped) | Fleet observability (opt-in required) |

Top row is the independent product. Bottom row is Anthropic-shaped or a long-game extension that requires solving the corpus problem. The ecosystem lives in the top row.

**The scope split matters.** Cross-codebase generalization would average away the thing that matters — conventions, languages, styles, architectural choices all vary. A per-codebase model trained on that codebase's own sessions is more accurate, more tractable, and has no corpus or consent problem.

---

## Use cases

1. **Friction map** — retrospective view of where Claude struggled on this codebase. Today's product.
2. **Per-codebase legibility score** — score any file in this codebase, including new ones, based on features learned from the observed set. Unlocks after enough session data.
3. **PR check** — score file pre-PR and post-PR, report the delta. Gates or warns on merges that reduce legibility.
4. **Live session readout** — mid-work diagnostic on the active session.
5. **IDE coaching** — inline hints when a file shows friction signals in the current session.
6. **Industry benchmark** — percentile ranking against top open-source projects on file-intrinsic features, DX-survey-shaped, with explicit "this is a proxy, we don't have friction data on those projects" caveat.

---

## How the scoring actually works

Classical statistics, not LLMs. A table where rows are files, columns are features (cyclomatic complexity, LOC, fan-out, naming entropy, etc.) plus a final column: observed friction from sessions.

```
File          | Complexity | LOC | Fan-out | ... | Observed friction
storage.py    | 12         | 450 | 8       | ... | 0.87
migrations.py | 6          | 200 | 3       | ... | 0.42
```

Fit a model (linear regression, gradient-boosted tree — doesn't matter much). The fit solves for feature weights that best explain observed friction. Features with near-zero weights are noise; features with large weights carry signal. Scoring a new file is evaluating the formula on its feature values.

Runs in milliseconds on a laptop. Interpretable. Fast. Re-fittable as new sessions accumulate. Zero LLM in the scoring path.

**Attribution falls out of the fit.** "storage.py scored 0.87, where 0.5 comes from cyclomatic complexity and 0.3 comes from fan-out" — decomposable per-file into feature contributions, which points at what to refactor.

---

## Principles

**Counting beats interpretation.** Every signal should be something you count in observed behavior, not something you infer about intent. The moment a score becomes a bag of heuristics untethered from observation, it collapses into SonarQube-with-a-neural-net. This is what distinguishes AI friction tooling from existing code quality tools.

**Observation before generalization.** Path is: observe (friction map) → earn trust → generalize (legibility score) → apply to change (PR check). Don't skip to generalization before there's enough observation. Session threshold enforces this at the product level.

**Single-codebase first.** Conventions and styles vary too much for cross-codebase generalization to work without averaging away the signal. The per-codebase model is both more accurate and more tractable.

**The loop closes through observation.** Generalized scoring makes a claim about a file; subsequent sessions on that file either confirm or contradict it. That's how the model improves and how the product proves itself. Observation isn't just input — it's also validation.

**Generalization, not prediction.** The model scores files it hasn't observed directly, including post-PR file-states that don't yet exist. That's generalization, not forecasting. The PR check is two generalized-scoring operations compared, not a prediction of future friction. Cleaner claim, cleaner validation.

**Attribution is a hypothesis, not a prescription.** Early model: "files with high X tend to have high friction in this codebase." Mature model, after enough validation loops: "reducing X in this codebase has historically reduced friction by roughly Y." Second claim is much stronger and takes real data to earn. Name this distinction in the product; don't let users mistake correlation for causation.

**Honest proxies are fine; unflagged proxies aren't.** The benchmark cell only works if it's explicit that it's a feature-based comparison, not observed friction. Engineers tolerate proxies they can see.

**The moat isn't the algorithm; it's being the tool users run.** Scoring functions are replicable. Observation-first strategy earns the trust that unlocks everything else. The friction map is the wedge.

**Fitting sidesteps argument.** Which features matter is an empirical question, answered by fitting a model on the data and seeing which weights are non-zero. Don't argue which features matter a priori; measure.

**AI legibility is what we're optimizing for, unapologetically.** The transition phase ends with agents executing code. Optimizing for the agent that runs the code is no different from optimizing for the interpreter that runs it. The framing doesn't need to square with human legibility to be defensible.

---

## Product mechanics

**Two user-facing states, one threshold.**

- *Observation-only* — not enough data for legibility scoring yet. Friction map works from session one.
- *Scoring unlocked* — enough session data accumulated. Legibility scoring on any file, PR check on diffs, attribution points at features.

The threshold is empirical, determined by when the per-codebase model's scores stabilize (learning curve, cross-validation stability). Research question, not a product-timing call.

**Under the hood, the model evolves continuously.** Features get added if they earn their fit weight. Refactor-outcome data refines weights over time. Semantic analysis and LLM-in-the-loop become *candidate features* that are evaluated like any other feature — do they add signal after controlling for the cheaper features already in the model. If yes, they earn their way in. If not, they don't. No user-facing tier structure; just a model that gets better.

---

## The closed loop

What makes this ecosystem structurally different from existing code quality tooling: the feedback loop closes.

1. Model predicts file X has high friction, attributed to feature Y.
2. Developer refactors to reduce feature Y.
3. Subsequent sessions on file X either show reduced friction or don't.
4. Features whose refactors produce real friction reduction are causal. Features whose refactors don't move the needle are correlates.
5. Model weights update based on what actually worked.

No existing code quality tool can do this — none of them observe the downstream effect of their recommendations. The closed loop is what turns the product from a dashboard into a tool that gets smarter as it's used, and it's the answer to "how do we validate our causal claims."

---

## Open research questions

- **Session data threshold for scoring unlock.** When does the per-codebase model's predictions stabilize enough to be trustworthy? Measured how — learning curves, cross-validation stability, confidence intervals on feature weights. This is the single gate between the product's two user-facing states.
- **Dependent variable choice.** Fitting against "total friction events on this file" gives one model; "friction per LOC" gives another; "whether this file ever triggered a re-evaluation marker cluster" gives a third. What to score against is itself a design choice, answered empirically.
- **Feature set.** Cyclomatic complexity, Halstead volume, cognitive complexity, naming entropy, identifier length distribution, comment density, import fan-out, inheritance depth, type annotation coverage, git churn, many more. Which earn their keep in the fit, controlling for the cheaper ones. Empirical.
- **Benchmark viability.** Cross-codebase comparison via file-intrinsic proxies is DX-survey-shaped — useful if the caveats are explicit, a rabbit hole if it tries to claim more than it measures. Worth keeping as a nice-to-have, not core.

---

## Discipline

This is a think file, not a plan file. Entries belong here when the thinking is worth preserving past the chat that generated it — principles, mental models, strategic questions, framings that would otherwise have to be rebuilt from scratch next time.

Not a commitment to build any of this. The friction map is the commitment. This file is the context the friction map sits inside.