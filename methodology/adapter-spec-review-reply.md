# Reply: Adapter Spec Review — All Questions Resolved

*Adeline, 2026-09-06. Responds to `methodology/adapter-spec-review.md` (PR #17). Decisions below are final for this cycle; they will be integrated into spec rev 2 by Desktop — do not edit the spec. Build handoff follows rev 2.*

## Answers Q1–Q11

**Q1 — `thought` container:** Confirmed. `trajectory[]` only, key `thought`, both format versions. `history` is never read for reasoning. The `is_demo` catch is noted as the review's most valuable finding — demo text in judged units would have been silent construct contamination.

**Q2 — Reasoning turn with no action:** Forward-attach to the next action step when one exists; terminal unit when none does. Rule 1's "own anchor with no action" reading is rejected. Adopt your family-agnostic phrasing of rule 2: any designated emission whose container carries no action forward-attaches.

**Q3 — Empty designated text:** Confirmed. Empty or whitespace-only designated text = no emission; anchor is empty; zero-length units never exist.

**Q4 — Trae stray closers:** Option B — `<think>` opener through the *last* `</think>` in the message. Rider: store the first-closer offset per affected unit so option A is recoverable from metadata (same reversibility pattern as fragment offsets). Audit reports the affected-message rate. Rationale for the record: truncating at the first closer would cut deliberation arcs on a format artifact — the same segmentation confound the unit definition was chosen to avoid; supporting structure: no `<function=` occurs before the last closer in any sampled message. Boundary rule gets `rule_version` provenance like SAGE's.

**Q5 — SAGE template:** Confirmed. First `THOUGHT:` occurrence through the first ```` ```bash ```` opener; no `THOUGHT:` → no emission; no bash fence → end of message. The two recon files are logged as the inspection sample; derivation and validation samples must be disjoint from them.

**Q6 — Unit-level failure:** Neither the spec's threshold nor the review's zero-units version. New definition: unit-level failure = file parses but the family's designated **structure is absent** (no `thought` keys / no `Thoughts`-authored entries / no `blocks[]` with thinking / no `THOUGHT:` occurrence / no `<think>` tag / n.a. for think-tool). Zero units with structure present is agent behavior, not extraction failure — reported descriptively by the audit. No numeric threshold exists; the rule is computable now.

**Q7 — Denominator:** Confirmed. Per-agent rates computed over deduped files whose stem matches the instance-id pattern; everything else quarantined `non_trajectory`, excluded from numerator and denominator.

**Q8 — Registry:** Confirmed. Vendor the 20-entry table into the registry module; record `config.py`'s sha256 alongside; never import their `config.py` at runtime.

**Q9 — Fence:** Confirmed. `enriched_encodings_all.csv` joins the Phase 2 hard fence (it carries `is_failed` per row). Phase 3's spot-check will use a column-stripped view, defined then.

**Q10 — Attribution reuse:** Tiers 1–2 reimplemented on unit text + touched-path set from the path layer; fixture test comparing against v1 tier-1–2 output on own-corpus blocks; tier 3 not rebuilt — superseded, since the unit's anchor already *is* the adjacency tier 3 inferred; ship `anchor_files` metadata on every unit instead. Logged deviation wording for the writeup: "mention tiers reimplemented on adapter output, fixture-verified against the pin; proximity tier superseded by step-anchored units."

**Q11 — Environment:** On me, before the build session. Assume the dataset is readable and its root is passed to the adapter as an explicit argument (per your 9.7 note — no default path resolution, no `config.py` import).

## Review items accepted without a question attached

- **EPAM gate rewrite (§7.1):** accepted as you redefined it — alternation-regularity check plus next-vs-previous path-resolution check on the audit sample, and a build rule that the loader never sorts keys. Spec rev 2 adds one limitation line: chronological insertion order is an unverifiable assumption supported by two consistency checks, stated once in the limitation set.
- **Build resequencing:** all three changes adopted — blindness tripwires first (task 1), anchoring engine before family extractors, audit after extractors. 9.6 acceptance criterion adopted as proposed (fixture tests + table-driven bash rule table). 9.7 mechanism adopted (monkeypatch tripwire mirroring `test_judge_blindness.py`, now covering all three fenced files + `results/`).
- **Provenance fields** on units: `family`, `rule_version`, `container`, `emission_kind` — adopted, plus Q4's first-closer offset.
- **Phase 3 spot-check note:** Trae-doubao (their parser never reads `<function=` XML for it) joins the SAGE `Pr`-undercount; both agents oversampled in the ~20-trajectory spot-check. Goes to the tracker, not this spec.
- **§0 addition:** blindness note names `enriched_encodings_all.csv` explicitly (per Q9).
- **EPAM multiplicity:** the spec's "multiple entries per anchor expected" claim was wrong — sample shows strict 1:1. Rev 2 corrects the sentence; the unit decision stands on its recorded rationale (segmentation confound), and B degrades to A when multiplicity is 1. Reversibility rider stays.

## Disposition

- PR #17: merge as-is. The review doc is the durable record; no edits requested.
- Spec rev 2: Desktop integrates everything above; lands as a commit touching only `swe-bench-adapter-spec.md`.
- Build handoff: separate document after rev 2, following your task 0–7 plan (est. 2.8 blocks; SAGE and Trae rule derivations are [A] work outside the envelope).