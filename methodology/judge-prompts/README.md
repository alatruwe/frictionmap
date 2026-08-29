# Judge prompts

Three frozen prompt artifacts for pre-registration §5. Each file is sent verbatim:
text above `=== USER TURN ===` is the system prompt; the harness substitutes
`{{THINKING_TEXT}}` into the template below it.

- `v1.md` — rubric §1–4 as committed, minus cuts listed below
- `v1-paraphrase-a.md`, `v1-paraphrase-b.md` — semantically equivalent rewrites of v1

Judge: Claude Haiku 4.5 (pinned snapshot per pre-registration §5), temperature 0,
extended thinking off (incompatible with temperature 0). Output ordering is
justification-then-score so the deciding quote precedes the number.

## v1 provenance
v1 is the labeling rubric's own text. Cuts: rubric header, §5 (anchor provenance),
§6 (procedure), per-line pre-registration cross-references, definition lines,
anchor session IDs, "no judge outputs" (meaningless to the judge), construct
domain-generality tail. Adaptation: "The labeler sees" → "You see". Additions:
role line, data-not-instructions sentence, output block, user-turn template.

## Paraphrase rule (pre-committed)
Held fixed across all three: input condition, scale intro, output block, user-turn
template, the four constructed fragments (verbatim), the four anchor blocks
(verbatim), level headings, construct terms (revisit, abandoned, discarded, return,
linear, circles, smooth).
Reworded in A and B: construct sentence, all four level criteria, the three
boundary questions and surrounding prose, all five negative cases, fragment
annotations, anchor rationales.
All three pairwise comparisons (v1↔A, v1↔B, A↔B) are tested; A and B were written
to differ from each other, not only from v1.

## Deviations log
- A's construct phrase "doesn't move forward cleanly" originated in review
  (Claude); kept by decision. All other paraphrase wording author-written;
  review was equivalence-checking only (flag, not fix).

## Parse-failure rule (pre-committed)
Unparseable or refused judge output: one retry at temperature 0. If still
unparseable: recorded as missing, excluded from κ, count reported alongside
results.
