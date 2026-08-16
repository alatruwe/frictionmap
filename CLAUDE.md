# CLAUDE.md

Session protocol for Claude Code working in this repo. Read at the start of every session. If something here seems inconsistent with what Adeline is asking in chat, the live ask wins — name the inconsistency and ask.

## What this project is

**FrictionMap** — a CLI tool that parses Claude Code session logs and produces an interactive HTML heatmap showing which files in a codebase the model experiences the most friction with.

The signal set: re-evaluation markers ("wait," "actually," "let me reconsider") detected in thinking blocks, plus structural signals (block length, question rate, tool-use coupling, length trend), plus behavioral signals (re-read bursts, edit churn). Every signal is per-file attributed via a co-location rule — a thinking-block file mention counts only if that file is also touched by a tool call in the same session.

Details: `project_design/` in this repo holds PROJECT_DESIGN.md, ASSUMPTIONS.md, HOW_IT_WORKS.md, TRADEOFFS.md, ECOSYSTEM.md, and schema.md — the source of truth for product design, validated assumptions, and the parked-signal rationale. Phase tracking (IMPLEMENTATION.md) lives outside the repo in the paired Claude Desktop project. When Adeline hands off a task, the spec will reference the concepts defined there.

Note that the design docs are a point-in-time record, not a current plan. PROJECT_DESIGN.md carries a status note explaining what it now over-describes: of the three milestones it sequences, only Milestone 1 shipped. Milestone 2 (the per-session debugger HTML) and Milestone 3 (the `/friction` skill) were both cut. Neither is coming back in v1 — don't pick up work that assumes them.

## What's in the repo right now

v1 has shipped: `frictionmap scan` (corpus HTML report), `frictionmap session <id>` (terminal summary), and `frictionmap active-sessions`. Nothing is sequenced after Phase 5b in v1; future work is the v2 validation study, tracked separately. Ask Adeline before starting anything that isn't a fix to shipped behavior.

If you're uncertain what phase the project is in, run:
```bash
frictionmap --version
```
and inspect `src/frictionmap/`. The code is the ground truth for what exists.

## How Adeline works

**Handoffs, not freeform collaboration.** Adeline writes specs; you implement. Specs are tight, usually include acceptance tests, and name their scope explicitly. Don't widen scope — if a task says "add three tests," add three tests, not a test harness.

**Ugly version first.** The order is always: `works → works on real data → readable → pretty`. Don't skip ahead. If you find yourself refactoring something that's "a bit awkward" before the feature ships, stop and ask whether that refactor is in scope.

**Fast agreement is a smell.** If Adeline approves something quickly that you had concerns about, raise the concern anyway. Silent consent on a bad design is worse than pushback.

**Specs have time estimates.** If a new task doesn't have one, ask before engaging. A bad estimate is better than no estimate.

**Tests for real logic only.** Don't test argparse. Don't test trivial getters. Test the functions where correctness actually matters — path resolution, parser state machines, scoring functions. The scaffolding has one testable helper (`resolve_sessions_dir`); future phases will add more.

## Working with Claude Code (meta)

This project is itself about analyzing Claude Code's behavior. That has two implications worth naming:

**Your sessions become the demo data.** Every Claude Code session spent building this tool lands in `~/.claude/projects/-<path-to-repo>/` as a JSONL file. By Friday, Adeline will run the tool on these sessions. That means:
- Your thinking blocks will be parsed and scored.
- Files you struggle with during the build will show up in the friction heatmap.
- The hero shot of the demo might literally be you getting confused about something.

This is fine and expected. Don't behave differently because of it — behave normally. Confusion is useful signal; papered-over confusion is useless signal.

**Respect the data you're generating.** Don't add commits just to generate activity. Don't artificially expand thinking blocks. The corpus should reflect real work.

## Repo conventions

- **Python 3.11+.** Modern type hints (`dict[str, int]`, `Path | None`).
- **Standard library first.** No runtime dependencies added without a concrete reason. If you want to reach for a library, check whether stdlib covers it.
- **Hatchling build backend.** Don't convert to setuptools unless there's a real incompatibility.
- **Naming:** package `frictionmap` (`src/frictionmap/`), CLI command `frictionmap`, product name FrictionMap. Renamed from `ai_friction_map`/`ai-friction-map` on April 29, 2026; the repo directory is still `ai-friction-map` and that's fine — don't "fix" it.
- **Remote:** `origin` is `github.com/alatruwe/frictionmap`.
- **Branch + PR for everything.** All changes go on a new branch and ship as a pull request for review — never commit or push directly to `main`. Name the branch for the work (`fix-...`, `docs-...`, etc.), commit there, push, and open a PR against `main`. This holds even for small or doc-only changes.
- **Commit messages:** conventional-commit style (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`). One concern per commit.

## The north star

The demo succeeds if someone watching says: *"I want this running all the time on my codebase."*

v1 is a static HTML report plus a terminal readout. v2 would be continuous inline coaching. Every scope call serves making the v1 compelling enough that the v2 is obvious.

If a proposed change doesn't advance that — if it's polish on something that isn't demo-critical, or infrastructure for a feature that isn't in scope, or abstraction for a second use case that doesn't exist yet — push back and ask whether it's needed this week.

## Settled design questions

Marker lexicon calibration, re-read window size, and score normalization were all open
during the build and are now resolved. Don't reopen them from first principles — the
answers and their rationale live in `project_design/HOW_IT_WORKS.md` and
`project_design/TRADEOFFS.md`. Read those before changing the lexicon, the window
parameter, or the normalization form.

## Parked scoring signals

Several entries in `WEIGHTS` (in `src/frictionmap/scoring.py`) are intentionally `0.0` — `reasoning_to_output_ratio`, `question_rate_per_100w`, `tool_use_coupling`, `block_length_words`, plus the leakage cluster (`edit_failures`, `grep_reformulations`, `bash_retries`, `read_after_edit`). They still compute and emit in `ScoreComponents`, and `corpus.leakage_by_file` is still populated. Don't "fix" them by assigning weight without checking `project_design/HOW_IT_WORKS.md` (parking rationale) first — each was parked after a specific diagnostic showed the signal was wrong-shape at the per-file level.

## If you're blocked

Ask. Scope is tight, and the cost of asking is small compared to the cost of guessing wrong.

If Adeline isn't available and the block is "I don't know which of two approaches to take," prefer the simpler one and leave a comment explaining the choice. Don't build both.

If the block is "the spec conflicts with the project design," flag the specific conflict and wait. Don't resolve it by reinterpreting the spec.
