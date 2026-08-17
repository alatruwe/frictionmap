# FrictionMap v2 — Labeling Rubric

Status: DRAFT — frozen at the `v2-prereg-freeze` tag. Until that tag exists, edits
are permitted; after it, changes only via amendment logged in pre-registration §9.

This rubric is the pre-registration §4 **step-1 artifact**: it must be written and
frozen before the validation sample is drawn (§4 step 2) and before any label is
assigned (§4 step 3). The judge prompt (§5, `judge-prompts/`) must encode the *same
construct* as this rubric — the 0–3 scale below, with the same level definitions and
the same input condition. A judge scoring a different construct than the human labeler
makes the §5 κ uninterpretable.

---

## 1. Construct

Verbatim from pre-registration §2:

> **Friction (construct):** observable evidence that the model's reasoning is not
> proceeding smoothly — backtracking, re-evaluation, contradiction of its own prior
> statements, repeated failed approaches to the same target — as distinct from
> ordinary sequential planning. The construct is domain-general; validation (§5) is
> domain-specific to this corpus. Cross-domain transfer (non-coding reasoning text)
> is future work, not a v2 claim.

## 2. Input condition

The labeler sees **the thinking text of the unit, and nothing else** — no signal
values, no judge outputs, no file rankings, no session metadata beyond the text
itself. This is the identical input condition given to the judge (pre-registration
§2, §4 step 3). Judgments are made from the text alone; nothing about the session it
came from, the files it touched, or how any signal scored it may enter the decision.

## 3. The scale

The judged unit is the attributed thinking block (§2). One score per unit, ordinal,
0–3.

### 3.0 — smooth

**Definition:** `0 = smooth` (pre-registration §2).

**Decision criteria:**
[ADELINE: 2–4 bullets]

**Boundary vs level 1:**
[ADELINE: prose]

**Anchor example:**

```text
[ADELINE: paste block text]
```

- Session ID: `[ADELINE: session id]`
- Why this is a 0: [ADELINE: one-line justification]

### 3.1 — minor re-evaluation

**Definition:** `1 = minor re-evaluation` (pre-registration §2).

**Decision criteria:**
[ADELINE: 2–4 bullets]

**Boundary vs levels 0 and 2:**
[ADELINE: prose]

**Anchor example:**

```text
[ADELINE: paste block text]
```

- Session ID: `[ADELINE: session id]`
- Why this is a 1: [ADELINE: one-line justification]

### 3.2 — substantive backtracking

**Definition:** `2 = substantive backtracking` (pre-registration §2).

**Decision criteria:**
[ADELINE: 2–4 bullets]

**Boundary vs levels 1 and 3:**
[ADELINE: prose]

**Anchor example:**

```text
[ADELINE: paste block text]
```

- Session ID: `[ADELINE: session id]`
- Why this is a 2: [ADELINE: one-line justification]

### 3.3 — thrashing

**Definition:** `3 = thrashing` (pre-registration §2).

**Decision criteria:**
[ADELINE: 2–4 bullets]

**Boundary vs level 2:**
[ADELINE: prose]

**Anchor example:**

```text
[ADELINE: paste block text]
```

- Session ID: `[ADELINE: session id]`
- Why this is a 3: [ADELINE: one-line justification]

## 4. Negative cases — score 0 even when verbose

[ADELINE: sequential planning, exploration, narrated tool intent — score 0 even when
verbose. One short paragraph or a bulleted list per case, with the discriminating
question for each.]

## 5. Anchor provenance

- Anchors are drawn from the **attune corpus only**. Brownfield blocks are excluded
  from anchor text for privacy; this is noted as a limitation — the rubric's worked
  examples come from one of the two corpora in the validation pool, so anchor
  calibration is attune-shaped even though labeling is pooled across both.
- Candidate sessions are located via **session-level marker density** (marker-positive
  thinking blocks ÷ total thinking blocks per session), by
  `methodology/scripts/dump_anchor_candidates.py`. Density selects *sessions to read*,
  not blocks to anchor; the anchor choice within a session is made by reading the text.
- **All sessions displayed during anchor selection are excluded from the validation
  sampling pool**, whether or not an anchor was ultimately chosen from them. The
  exclusion list is `methodology/anchor-sessions.txt` and the sampling script (§3) must
  honour it. This is contamination containment per §4: the pre-registration requires
  anchor examples to come from sessions *outside* the validation sample, and reading a
  session's blocks during anchor hunting is exposure regardless of what was selected.

## 6. Procedure

Verbatim from pre-registration §4:

> Order is binding:
>
> 1. Labeling rubric written and frozen (the 0–3 scale above, with one anchor example
>    per level — examples drawn from sessions *outside* the validation sample).
> 2. Sample drawn by committed script.
> 3. I hand-label all N units seeing only the thinking text — no signal values, no
>    judge outputs, no file rankings, no session metadata beyond the text itself.
>    (Identical input condition to the judge, per §2.)
> 4. Labels committed (hash) before the judge runs on the validation sample.
>
> Contamination rule: if I see judge output or signal values for a unit before
> labeling it, that unit is discarded and replaced from a reserve list, and the event
> is logged in Section 9.
