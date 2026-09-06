# Judge harness (pre-registration §5)

Scores thinking blocks with the frozen judge prompts in `methodology/judge-prompts/`,
one independent API call per unit, and stores every attempt under `judge-runs/`
(gitignored). Default mode is a dry run over the anchor sessions. The validation
sample is reachable only through the gated `--validation-run` path.

## Setup

```bash
uv sync --extra dev --extra judge      # adds the anthropic SDK; not a CLI runtime dep
export ANTHROPIC_API_KEY=...            # real calls only; tests need no key
```

## Commands

```bash
# dry-run smoke over the anchor sessions (methodology/anchor-sessions.txt)
uv run python methodology/scripts/run_judge.py run \
    --corpus-root ~/Projects/v2-sessions --run-id smoke-anchors --pass v1-pass1
uv run python methodology/scripts/run_judge.py run \
    --corpus-root ~/Projects/v2-sessions --run-id smoke-anchors \
    --pass paraphrase-a --pass paraphrase-b --limit 5

uv run python methodology/scripts/run_judge.py render  judge-runs/smoke-anchors
uv run python methodology/scripts/run_judge.py metrics judge-runs/smoke-anchors
```

Re-running with the same `--run-id` resumes: any attempt already in a pass's
ledger is never re-issued. A run dir is one mode only; dry-run and validation
never share a `--run-id`.

Pass ids: `v1-pass1`, `v1-pass2`, `v1-pass3` (rerun stability, prompt `v1.md`),
`paraphrase-a`, `paraphrase-b` (one pass each).

## Validation mode

```bash
uv run python methodology/scripts/run_judge.py run --validation-run \
    --i-confirm "labels are committed and hashed" \
    --corpus-root ~/Projects/v2-sessions --run-id validation-<date> \
    --pass v1-pass1 --pass v1-pass2 --pass v1-pass3 --pass paraphrase-a --pass paraphrase-b
```

Three gates run before any call, all hard exits: `labels.csv` raw bytes hash to
the value in commit 8900f2e; the corpus matches `corpus-manifest.txt`; the
labeling sheet re-rendered from `sample-manifest.csv` hashes to the value in
`sample-seal.txt` (proves the judge sees byte-identical text to what was labeled).
Nothing in the validation path prints unit contents.

## Bound parameters

Model `claude-haiku-4-5-20251001`, `max_tokens` 300, temperature 0 sent via
`extra_body` (anthropic 1.x removed the typed kwarg; `tests/test_judge_client.py`
asserts the outgoing body), no `thinking` parameter, one user turn per call, no
shared context. Parse rule (D1, frozen 2026-09-06) in `parse.py`; retry-once-then-
missing per `judge-prompts/README.md`.

## Run layout

```
judge-runs/<run_id>/
  run-manifest.json      model/params/SDK, prompt sha256s, scaffold token counts,
                         per-pass timestamps, call/retry/missing/latency stats
  infra.log              transient API errors and backoff (no unit text)
  <pass_id>/ledger.jsonl one line per API attempt; the resume source of truth
  <pass_id>/raw/<pos>-<attempt>.json   full response per attempt
  <pass_id>/scores.csv   pass_id, sheet_position, session_id, block_index, score,
                         justification, raw_response_path, retry_flag, missing_flag
  metrics.json           from `metrics`
```

`scaffold_tokens` is `count_tokens` on the system prompt plus the user template
with an empty substitution; `first_response_usage` is the first live response's
usage in each pass. Both are what `cost-budget.md` asks to record at first run.

## Blindness

Dry-run never opens `sample-manifest.csv` (`tests/test_judge_blindness.py` trips
on any attempt). Anchor-session blocks appear verbatim inside the prompts, so
dry-run scores are not a quality signal: log them, don't read them. Smoke reports
carry operational stats only.
