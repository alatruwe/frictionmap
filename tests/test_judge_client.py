"""The real SDK client against an in-process mock transport: asserts the exact
request body the judge sends. This is the temperature-0 guarantee."""
from __future__ import annotations

import json

import anthropic
import httpx2 as httpx
from anthropic import DefaultHttpxClient

from judge_harness.client import MAX_TOKENS, MODEL, JudgeClient, is_infra_error

MESSAGE = {
    "id": "msg_test", "type": "message", "role": "assistant", "model": MODEL,
    "content": [{"type": "text", "text": '{"justification": "q", "score": 2}'}],
    "stop_reason": "end_turn", "stop_sequence": None,
    "usage": {"input_tokens": 3010, "output_tokens": 88},
}


def _client(captured: list) -> JudgeClient:
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        if request.url.path.endswith("/count_tokens"):
            return httpx.Response(200, json={"input_tokens": 2950})
        return httpx.Response(200, json=MESSAGE, headers={"request-id": "req_abc"})
    sdk = anthropic.Anthropic(api_key="test-key", max_retries=0,
                              http_client=DefaultHttpxClient(transport=httpx.MockTransport(handler)))
    return _wrap(sdk)


def _wrap(sdk):
    return JudgeClient(sdk)


def test_request_body_is_exactly_the_bound_parameters():
    captured: list[httpx.Request] = []
    result = _client(captured).judge("SYSTEM TEXT", "USER TEXT")
    body = json.loads(captured[0].content)
    assert body["temperature"] == 0
    assert body["model"] == MODEL == "claude-haiku-4-5-20251001"
    assert body["max_tokens"] == MAX_TOKENS == 300
    assert "thinking" not in body
    assert body["system"] == "SYSTEM TEXT"
    assert body["messages"] == [{"role": "user", "content": "USER TEXT"}]   # one user turn, no history
    assert set(body) == {"temperature", "model", "max_tokens", "system", "messages"}
    assert result.text == '{"justification": "q", "score": 2}'
    assert result.stop_reason == "end_turn"
    assert result.request_id == "req_abc"
    assert (result.input_tokens, result.output_tokens) == (3010, 88)
    assert result.response["usage"]["input_tokens"] == 3010


def test_count_tokens_uses_same_system_and_user():
    captured: list[httpx.Request] = []
    assert _client(captured).count_tokens("S", "U") == 2950
    body = json.loads(captured[0].content)
    assert body["system"] == "S" and body["messages"] == [{"role": "user", "content": "U"}]
    assert body["model"] == MODEL


def test_infra_error_classification():
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    def status(code):
        return anthropic.APIStatusError("x", response=httpx.Response(code, request=req), body=None)
    assert is_infra_error(anthropic.APIConnectionError(request=req))
    assert is_infra_error(anthropic.APITimeoutError(request=req))
    assert is_infra_error(status(500)) and is_infra_error(status(529)) and is_infra_error(status(429))
    assert not is_infra_error(status(400)) and not is_infra_error(status(401))
    assert not is_infra_error(ValueError("nope"))
