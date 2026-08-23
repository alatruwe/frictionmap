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

The judged unit is the attributed thinking block (§2). One score per unit, ordinal, 0–3.
Boundary fragments are constructed illustrations, not corpus text; they nest —
each level's fragment is the previous level's fragment plus added reasoning, and
the added text is the move that earns the higher score. Anchors are verbatim
corpus blocks.

### 3.0 — smooth

**Definition:** `0 = smooth` (pre-registration §2).

**Decision criteria:**
- No contradiction is detected throughout the block.
- Intent and progress are linear and explicit throughout the block.
- A marker-like word scores 0 when nothing changes around it: no judgment is
  re-checked, no step revised, no direction shifted. The word functions as
  emphasis or confirmation, not correction.

**Boundary level 0 vs level 1:**
The discriminating question: does the model revisit a judgment or assumption
it already made, or only move forward? 
Forward motion — planning, observing, evaluating, concluding — is 0, however long or opinionated. 
"After running the tests, this approach is actually faster" is 0: an evaluation, but nothing is questioned. 
"I need to add a validation check here for the user_id string. Actually, the team migrated that column to a string type last week. I'll now add the string validation" is 1: an assumption is corrected and the step continues,
adjusted. 
The bar for 1 is low: any revisiting of prior reasoning crosses it.
What does NOT cross it: new evaluations or conclusions, even strong ones,
that build forward without questioning anything already established.

**Anchor example:**

```text
It seems the settings.json change isn't actually in any commit on this branch. Let me check the main branch vs this branch for settings.json.
```

- Session ID: `9eb36936-b91d-494e-9858-eea64edc529d`
- Why this is a 0: no judgment revised, no step changed, vocabulary in confirmatory function.

### 3.1 — minor re-evaluation

**Definition:** `1 = minor re-evaluation` (pre-registration §2).

**Decision criteria:**
- The model questions or re-checks a judgment, assumption, or step it
  just made.
- The check resolves: the original work is confirmed or locally adjusted, 
  nothing is discarded, direction does not change.
- The block continues from where it was; the re-evaluation is contained.

**Boundary level 1 vs level 2:**
The discriminating question: Was the previous approach or objective completely abandoned and discarded?
"I need to add a validation check here for the user_id string. Actually, the team migrated that column to a string type last week. I'll now add the string validation" is 1: an assumption is corrected and the step continues,
adjusted. 
"I need to add a validation check here for the user_id string. Actually, the team migrated that column to a string type last week. I'll now add the string validation. Wait, the database already enforces this type at the schema level. I'll discard this check entirely to avoid duplicating logic and rely on the schema constraint instead. Now I'll move to the next step and run the test suite" is 2.
The bar for 2: a stated step or approach is discarded, not adjusted.
Mixture rule: one clear abandonment in an otherwise smooth block scores 2 —
the block is scored on its worst move, not its average.
An announced abandonment scores 2 even if the block ends before the new
direction proceeds — "this won't work, I should discard this check" is the
move itself; enactment is not required.
What does NOT cross into 2: re-evaluation that adjusts and retains — the
level-1 fragment above is the near-miss: an assumption is corrected, but the
step survives, modified.

**Anchor example:**

```text
Still waiting on the 8192 token test. Given it started after 8000 tokens (309s), and 8192 is only 2.4% more tokens than 8000, the time should be comparable. Let me wait a bit more.
Actually, I think there might be a non-linear scaling issue. If the model is taking 309s for 8000 tokens, the 8192-token test might take around 325-330s. It's been running for a bit, so maybe it's close to done.
Let me check the results now.
```

- Session ID: `3ec85b0a-3b67-48da-abe7-023125456cb3`
- Why this is a 1: re-evaluates and adjusts an assumption without changing the core plan

### 3.2 — substantive backtracking

**Definition:** `2 = substantive backtracking` (pre-registration §2).

**Decision criteria:**
- A stated next step or approach is abandoned and replaced by a
  different one.
- Abandonment may be explicit ("that won't work, instead…") — the announcement alone suffices, even if the block ends before the new direction proceeds — or silent, where the new direction proceeding as if the earlier plan never existed is itself the evidence. Both score 2.
- Work or planning done under the abandoned approach is discarded, not built on.
- There is a linear forward chain of thoughts.

**Boundary level 2 vs level 3:**
The discriminating question: Does the block loop back to a previously abandoned idea, or remain unresolved without establishing a stable direction?
"I need to add a validation check here for the user_id string. Actually, the team migrated that column to a string type last week. I'll now add the string validation. Wait, the database already enforces this type at the schema level. I'll discard this check entirely to avoid duplicating logic and rely on the schema constraint instead. Now I'll move to the next step and run the test suite" is 2
"I need to add a validation check here for the user_id string. Actually, the team migrated that column to a string type last week. I'll now add the string validation. Wait, the database already enforces this type at the schema level. I'll discard this check entirely to avoid duplicating logic and rely on the schema constraint instead. Now I'll move to the next step and run the test suite. Actually, wait, catching a database constraint failure throws an unhandled raw SQL error back to the user, which breaks API spec. Right, so I do need the validation here to catch it early and return a clean 400 response. But if I validate it here, I’m duplicating database schema logic again and maintaining two sources of truth... Wait, so should I push it to the database or validate it here?" is 3
The bar for 3: the block returns — an abandoned approach is picked up again,
or the same unresolved re-evaluation recurs. Resolution at the end does not
rescue the block: if the pattern circled before resolving, it is a 3.
What does NOT cross into 3: a linear chain of abandonments — even several —
where each move advances to a new approach and none returns to a discarded
one. Such a chain is a 2, however long.


**Anchor example:**

```text
The user seems to be sharing the stop hook feedback with me. This is feedback from a hook that runs at the end of a session. The hook is reviewing the conversation and determining whether any tasks from IMPLEMENTATION.md were completed. In both cases, the hook correctly determined that no tasks were completed (just technical Q&A) and did nothing.
The user might be sharing this to show me the hook is working, or they might have a question about it. Let me wait to see if they have a follow-up question or if they're just showing me the output.
Actually, looking at this more carefully - the user sent the stop hook feedback as their message. They might be asking about the hook behavior or just showing me the output. I should respond briefly.
Looking at the second message more carefully, it's just the stop hook feedback with no additional content after it - the user might be sharing this to demonstrate the hook is functioning, or they could have accidentally pasted it without a follow-up question. me the hook ran, or they might want to discuss it.
I think the user is just sharing the hook output to show me it ran. I should acknowledge it briefly, or they might want something specific. Let me ask.
Actually, wait - looking at the conversation structure again:
Message 1 (user): "how do I do that: confirm that the tokenizer Ollama loads..."
Message 2 (assistant): answer
Message 3 (user): "Stop hook feedback: [...] can I do this: [code]"
Message 4 (assistant): answer about the code
Message 5 (user): "Stop hook feedback: [...]\n\n[nothing else]"
So the last message from the user is just the stop hook feedback with no additional question. This seems like they might have accidentally sent just the hook feedback, or they want to discuss something about the hook behavior. I should probably ask what they're looking for, since the message appears to be incomplete or they might need clarification on something.
```

- Session ID: `9eb36936-b91d-494e-9858-eea64edc529d`
- Why this is a 2: multiple assumptions are abandoned in sequence, but the
  progression is linear — each "actually" advances to a new reading; no
  abandoned interpretation is returned to, and the final re-check confirms
  rather than reopens. Definitive conclusion reached without circling.

### 3.3 — thrashing

**Definition:** `3 = thrashing` (pre-registration §2).

**Decision criteria:**
- Repeated switching between approaches at the same target — the block circles rather than progresses.
- At least one return: an approach previously abandoned is picked up again, or the same re-evaluation recurs without resolving.
- The pattern circles before any resolution: either no stable direction is
  established, or direction arrives only after the block has already returned
  to abandoned ground. Linearity, not resolution, is what separates 2 from 3.

**Anchor example:**

```text
Good progress! The ceiling check is running. Here's what we know so far:
- 200 tokens: OK, 0.33s
- 1500 tokens: OK, 0.45s
- 6000 tokens: OK, 201.59s (!!! that's very slow - over 3 minutes!)
- 8000 tokens: OK, 309.33s (!!! that's over 5 minutes!)
- 8192 tokens: currently running
The inference times are EXTREMELY slow on M3 Mac.
These times are way too slow - something's definitely off. Even though MPS is available on the system, the sentence-transformers library might not be using it properly, especially with the custom NomicBert architecture that nomic-embed-text-v1.5 uses.
Looking at the projected timeline, this is a serious problem. Just the ceiling check alone would take over 10 minutes, and the full benchmark with multiple runs per token count would stretch into hours. At 201 seconds for 6000 tokens, I'm looking at a completely impractical runtime. = ~603s
- 8000: 3 × ~309s = ~927s
That's over 25 minutes just for the single-input benchmark. Plus the batch of 10 conversations...
This is clearly a very important finding. The script is currently stuck on the 8192-token test. Let me kill this and modify the script to:
1. Limit the repetitions for slow benchmarks
2. Or actually, let me let it run and just note the timing as a finding
Actually, the spec says there's a "soft budget of 60 minutes." The ceiling check itself is already going to take much longer than that. The script has been running for:
- 200: 0.33s
- 1500: 0.45s
- 6000: 201.59s (~3.4 min)
- 8000: 309.33s (~5.2 min)
- 8192: currently running (probably similar time)
- 8500: will take similar time
So the ceiling check alone will take ~15-20 minutes, which is fine within the 60-minute budget. But the single-input benchmark with 3 runs each at 6000 and 8000 tokens would add another ~30 minutes, pushing the total well over the limit. The spec anticipated much faster inference speeds than what we're seeing here. I should let the ceiling check finish since that's the primary finding, then decide whether to skip or reduce the remaining benchmarks to stay within the time constraint. ceiling check and report partial results
Actually, wait - maybe the slow times are because the model is using CPU despite MPS being available. If the script uses device='cpu' or falls back, that would explain the extreme slowness.
Looking at the timings, there's a clear pattern: 200 and 1500 tokens run in under a second, but 6000 tokens jumps to 201 seconds - that's a 400x slowdown for only 4x the input. Even accounting for the O(n²) attention complexity in transformers, which would predict a 16x increase, something else must be happening. The NomicBert model might have issues with MPS at larger sequence lengths, or there's memory pressure causing thrashing on the 8GB system, or the MPS backend is falling back to CPU for specific operations on large attention matrices.
I should let the ceiling check finish since that's the primary finding, then adjust the remaining benchmarks - reducing the single-input runs to just one iteration for large sizes and potentially skipping or cutting back the batch benchmark given how long this is taking. The spec allows reporting partial numbers if we exceed 60 minutes, so I'll prioritize getting the ceiling data and see what time remains.
```

- Session ID: `3ec85b0a-3b67-48da-abe7-023125456cb3`
- Why this is a 3: the block circles — kill-the-script vs. let-it-run flips, the "let the ceiling check finish" plan is stated, abandoned for renewed diagnosis, then returned to. Direction arrives only after the pattern has already returned to abandoned ground; the eventual resolution does not rescue it (see level-3 criteria).

## 4. Negative cases — score 0 even when verbose

- **Sequential planning.** Forward motion — planning, observing, evaluating,
  concluding — scores 0, however long or opinionated. No judgment or
  assumption already made is revisited.
- **Exploration / investigation narration.** Reading files, tracing code,
  gathering context, narrating findings. Discovering new information is not
  revisiting a judgment — "oh, this is structured differently than typical"
  is observation, not re-evaluation, when no prior assumption of the model's
  own gets corrected. Exploration that overturns a stated premise crosses
  into 1.
- **Narrated tool intent.** "I'll run the tests, then check the output" —
  announced actions, no judgment revisited.
- **Affirmative marker use.** Marker vocabulary in emphatic or confirmatory
  function: see level-0 criteria. Words count only when a friction move
  occurs around them.
- **Verbosity.** Length, thoroughness, and hedged phrasing are not friction
  evidence. A 400-word meticulous plan is a 0.

## 5. Anchor provenance

- Anchors are drawn from the **attune corpus only**. Brownfield blocks are excluded
  from anchor text for privacy; this is noted as a limitation — the rubric's worked
  examples come from one of the two corpora in the validation pool, so anchor
  calibration is attune-shaped even though labeling is pooled across both.
- Candidate sessions are located via **session-level marker density** (marker-positive
  thinking blocks ÷ total thinking blocks per session), by
  `methodology/scripts/dump_anchor_candidates.py`; the thinking text actually read for
  anchor selection was rendered one session at a time by
  `methodology/scripts/dump_session.py`, which also appends every session it displays to
  the exclusion list. Density selects *sessions to read*, not blocks to anchor; the
  anchor choice within a session is made by reading the text.
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
