# CLAUDE.md

Session protocol for Claude Code working in this repo. Read at the start of every session. If something here seems inconsistent with what Adeline is asking in chat, the live ask wins — name the inconsistency and ask.

## What this project is

**ai-friction-map** — a CLI tool that parses Claude Code session logs and produces an interactive HTML heatmap showing which files in a codebase the model experiences the most friction with. Built for the "Built with Opus 4.7" Claude Code hackathon (April 21–27, 2026).

The signal set: re-evaluation markers ("wait," "actually," "let me reconsider") detected in thinking blocks, plus structural signals (block length, question rate, tool-use coupling, length trend), plus behavioral signals (re-read bursts, edit churn). Every signal is per-file attributed via a co-location rule — a thinking-block file mention counts only if that file is also touched by a tool call in the same session.

Details: the Claude Desktop project this repo is paired with has PROJECT_DESIGN.md, ASSUMPTIONS.md, and IMPLEMENTATION.md. Those are the source of truth for product design, validated assumptions, and phase tracking. They live outside the repo. When Adeline hands off a task, the spec will reference the concepts defined there.

## What's in the repo right now

Check `IMPLEMENTATION.md` (when it lands in the repo) or ask Adeline where the project is. In the first day or two, the scaffolding is all that exists — a CLI that prints stub output. By mid-week, the parser and scoring function land. By weekend, the HTML report and the `/friction` skill.

If you're uncertain what phase the project is in, run:
```bash
ai-friction-map --version
```
and inspect `src/ai_friction_map/`. The code is the ground truth for what exists.

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
- **Package name:** `ai_friction_map` (underscored, Python). **CLI command:** `ai-friction-map` (hyphenated, user-facing). Don't "fix" the inconsistency — Python requires it.
- **No pushed branches yet.** All commits local until Adeline confirms GitHub setup.
- **Commit messages:** conventional-commit style (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`). One concern per commit.

## The north star

The demo succeeds if someone watching says: *"I want this running all the time on my codebase."*

v1 is a static HTML report plus a terminal readout. v2 would be continuous inline coaching. Every scope call serves making the v1 compelling enough that the v2 is obvious.

If a proposed change doesn't advance that — if it's polish on something that isn't demo-critical, or infrastructure for a feature that isn't in scope, or abstraction for a second use case that doesn't exist yet — push back and ask whether it's needed this week.

## Open questions the project knows about

These are named so you don't rediscover them:

- **Skill context discovery.** When `/friction` is invoked as a Claude Code skill, does the skill runtime expose which session invoked it? Investigation task in Phase 2. If the answer is no, the skill takes an explicit identifier argument.
- **Marker lexicon calibration.** The starting lexicon ("wait," "actually," "let me reconsider," etc.) is a committed hypothesis. Thursday hand-tagging validates or revises it. Don't pre-optimize the lexicon in code — it's meant to be swappable.
- **Re-read window size.** Burst re-read detection needs a turn-window parameter. Thursday tuning task. Start with a reasonable default (3 or 5 turns); don't bake the constant into multiple places.
- **Normalization strategy.** Per-file scores divided by file size or LOC to avoid "big file = hot" artifacts. Exact form TBD during Phase 3 scoring work.

## If you're blocked

Ask. Scope is tight, and the cost of asking is small compared to the cost of guessing wrong.

If Adeline isn't available and the block is "I don't know which of two approaches to take," prefer the simpler one and leave a comment explaining the choice. Don't build both.

If the block is "the spec conflicts with the project design," flag the specific conflict and wait. Don't resolve it by reinterpreting the spec.
