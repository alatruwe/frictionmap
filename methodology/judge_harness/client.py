"""One judge call = one independent API request. No state between calls.

Judge parameters are bound by pre-registration §5 and judge-prompts/README.md:
Claude Haiku 4.5 dated snapshot, temperature 0, extended thinking off (the
`thinking` parameter is omitted). max_tokens 300 is headroom over the ~100-token
expected output, not a knob.

anthropic 1.x dropped `temperature` from the typed messages.create signature;
the API still honours it on Haiku 4.5, and the SDK's documented route is
extra_body, which is merged into the request JSON as-is. The mock-transport
test asserts the outgoing body carries "temperature": 0 — that assertion, not
the SDK version, is the guarantee.
"""
from __future__ import annotations

import platform
from dataclasses import dataclass
from typing import Any

import anthropic

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 300
TEMPERATURE = 0
JUDGE_PARAMS: dict[str, Any] = {
    "model": MODEL,
    "max_tokens": MAX_TOKENS,
    "temperature": TEMPERATURE,
    "temperature_mechanism": "extra_body (anthropic 1.x removed the typed kwarg)",
    "thinking": "off (parameter omitted)",
    "sdk": f"anthropic {anthropic.__version__}",
    "python": platform.python_version(),
}
# Statuses the SDK does not retry itself but which are still infrastructure.
_INFRA_STATUSES = {408, 409, 429, 529}


@dataclass(frozen=True)
class CallResult:
    text: str
    stop_reason: str | None
    request_id: str | None
    input_tokens: int | None
    output_tokens: int | None
    model: str | None
    response: dict          # full Message as a dict, stored raw


def is_infra_error(exc: BaseException) -> bool:
    """Transient API failure: retry with backoff, log, never count as a parse attempt."""
    if isinstance(exc, anthropic.APIConnectionError):   # includes APITimeoutError
        return True
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code >= 500 or exc.status_code in _INFRA_STATUSES
    return False


class JudgeClient:
    def __init__(self, client: anthropic.Anthropic | None = None,
                 max_retries: int = 5, timeout: float = 60.0) -> None:
        self._client = client or anthropic.Anthropic(max_retries=max_retries, timeout=timeout)

    def judge(self, system: str, user: str) -> CallResult:
        raw = self._client.messages.with_raw_response.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
            extra_body={"temperature": TEMPERATURE},
        )
        message = raw.parse()
        text = "".join(block.text for block in message.content if block.type == "text")
        return CallResult(
            text=text,
            stop_reason=message.stop_reason,
            request_id=raw.headers.get("request-id"),
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            model=message.model,
            response=message.to_dict(),
        )

    def count_tokens(self, system: str, user: str) -> int:
        result = self._client.messages.count_tokens(
            model=MODEL, system=system,
            messages=[{"role": "user", "content": user}],
        )
        return result.input_tokens
