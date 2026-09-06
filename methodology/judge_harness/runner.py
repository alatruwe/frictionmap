"""Run one pass: every unit judged in its own API call, retry-once on parse
failure, then missing. Resumable from the ledger; a killed pass re-issues no
call for any attempt already recorded.

Infrastructure errors (connection, timeout, 429, 5xx, overloaded) are not parse
attempts: the SDK retries them first; after that, this loop backs off and
retries the same unit up to `infra_max` more times, logging each to infra.log.
If they keep failing the pass aborts with the ledger intact for resume.
"""
from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

from judge_harness.client import CallResult, is_infra_error
from judge_harness.parse import parse_response
from judge_harness.prompts import Prompt, assemble
from judge_harness.store import (
    MAX_ATTEMPTS,
    Attempt,
    append_ledger,
    load_ledger,
    log_infra,
    unit_complete,
    write_raw,
)
from judge_harness.units import Unit


class Judge(Protocol):
    def judge(self, system: str, user: str) -> CallResult: ...


class PassAborted(RuntimeError):
    """Infrastructure kept failing. Ledger is intact; rerun to resume."""


@dataclass
class PassSummary:
    pass_id: str
    units_total: int = 0
    units_skipped_resume: int = 0
    units_completed: int = 0
    calls: int = 0
    retried: int = 0
    missing: int = 0
    infra_retries: int = 0
    latencies_s: list[float] = field(default_factory=list)
    first_response_usage: dict | None = None
    started_at: str = ""
    ended_at: str = ""

    def latency_stats(self) -> dict:
        if not self.latencies_s:
            return {}
        return {
            "min_s": round(min(self.latencies_s), 3),
            "median_s": round(statistics.median(self.latencies_s), 3),
            "max_s": round(max(self.latencies_s), 3),
        }

    def as_manifest(self) -> dict:
        return {
            "units_total": self.units_total,
            "units_skipped_resume": self.units_skipped_resume,
            "units_completed": self.units_completed,
            "calls": self.calls,
            "retried": self.retried,
            "missing": self.missing,
            "infra_retries": self.infra_retries,
            "latency": self.latency_stats(),
            "first_response_usage": self.first_response_usage,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def call_with_infra_retry(client: Judge, system: str, user: str, *, run_dir: Path,
                          label: str, infra_max: int, sleep: Callable[[float], None],
                          base_delay: float) -> tuple[CallResult, int, float]:
    """(result, infra retries used, latency of the successful call)."""
    retries = 0
    while True:
        started = time.monotonic()
        try:
            return client.judge(system, user), retries, time.monotonic() - started
        except Exception as exc:  # noqa: BLE001 - classified below
            if not is_infra_error(exc):
                raise
            log_infra(run_dir, f"{_now()} {label} infra error #{retries + 1}: {type(exc).__name__}: {exc}")
            if retries >= infra_max:
                raise PassAborted(f"{label}: {infra_max} infra retries exhausted ({type(exc).__name__})") from exc
            sleep(base_delay * (2 ** retries))
            retries += 1


def run_pass(run_dir: Path, pass_id: str, prompt: Prompt, units: list[Unit], client: Judge, *,
             infra_max: int = 3, sleep: Callable[[float], None] = time.sleep,
             base_delay: float = 5.0, progress: Callable[[str], None] | None = None) -> PassSummary:
    summary = PassSummary(pass_id=pass_id, units_total=len(units), started_at=_now())
    ledger = load_ledger(run_dir, pass_id)

    for unit in units:
        attempts = list(ledger.get(unit.position, []))
        if unit_complete(attempts):
            summary.units_skipped_resume += 1
            continue
        system, user = assemble(prompt, unit.text)
        label = f"{pass_id} unit {unit.position:03d}"
        while not unit_complete(attempts):
            attempt_no = len(attempts) + 1
            result, infra_retries, latency = call_with_infra_retry(
                client, system, user, run_dir=run_dir, label=f"{label} attempt {attempt_no}",
                infra_max=infra_max, sleep=sleep, base_delay=base_delay)
            summary.calls += 1
            summary.infra_retries += infra_retries
            summary.latencies_s.append(latency)
            if summary.first_response_usage is None:
                summary.first_response_usage = {
                    "input_tokens": result.input_tokens, "output_tokens": result.output_tokens,
                    "model": result.model, "request_id": result.request_id,
                }
            parsed = parse_response(result.text, result.stop_reason)
            raw_rel = write_raw(run_dir, pass_id, unit.position, attempt_no, {
                "request_id": result.request_id, "attempt": attempt_no,
                "parse": {"valid": parsed.valid, "reason": parsed.reason},
                "response": result.response,
            })
            attempt = Attempt(
                pass_id=pass_id, sheet_position=unit.position, session_id=unit.session_id,
                block_index=unit.block_index, attempt=attempt_no, valid=parsed.valid,
                score=parsed.score, justification=parsed.justification, reason=parsed.reason,
                raw_response_path=raw_rel, request_id=result.request_id,
                stop_reason=result.stop_reason, input_tokens=result.input_tokens,
                output_tokens=result.output_tokens, infra_retries=infra_retries,
                latency_s=round(latency, 3), timestamp=_now(),
            )
            append_ledger(run_dir, attempt)
            attempts.append(attempt)
        summary.units_completed += 1
        if len(attempts) > 1:
            summary.retried += 1
        if not any(a.valid for a in attempts):
            summary.missing += 1
        if progress:
            progress(f"{label}: done ({summary.units_completed}/{len(units) - summary.units_skipped_resume})")

    summary.ended_at = _now()
    return summary


__all__ = ["Judge", "PassAborted", "PassSummary", "run_pass", "call_with_infra_retry", "MAX_ATTEMPTS"]
