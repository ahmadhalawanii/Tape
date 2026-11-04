"""A real `anthropic.Anthropic` client wired to a Python function instead of the network.

    def respond(request: dict) -> list[dict]:
        return [{"type": "text", "text": "hello"}]

    client = llmtape.testing.scripted_client(respond)

The SDK's own request building, response parsing and types all run, so code under test
cannot tell the difference. Used by Tape's tests and demo; handy for yours.
"""

from __future__ import annotations

import itertools
import json
from typing import Callable

import anthropic
import httpx2

Responder = Callable[[dict], "list[dict] | dict"]
_ids = itertools.count(1)


def _tokens(value) -> int:
    return max(1, len(json.dumps(value, ensure_ascii=False)) // 4)


def _message(request: dict, result) -> dict:
    if isinstance(result, dict) and "content" in result:
        content, stop = result["content"], result.get("stop_reason")
    else:
        content, stop = result, None
    for block in content:
        if block.get("type") == "tool_use":
            block.setdefault("id", f"toolu_{next(_ids):04d}")
    if stop is None:
        stop = "tool_use" if any(b.get("type") == "tool_use" for b in content) else "end_turn"
    return {
        "id": f"msg_{next(_ids):06d}",
        "type": "message",
        "role": "assistant",
        "model": request.get("model", "scripted"),
        "content": content,
        "stop_reason": stop,
        "stop_sequence": None,
        "usage": {
            "input_tokens": _tokens([request.get("system"), request.get("tools"), request.get("messages")]),
            "output_tokens": _tokens(content),
        },
    }


def _handler(respond: Responder):
    def handle(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        return httpx2.Response(200, json=_message(body, respond(body)))
    return handle


def scripted_client(respond: Responder) -> anthropic.Anthropic:
    transport = httpx2.MockTransport(_handler(respond))
    return anthropic.Anthropic(api_key="scripted", max_retries=0,
                               http_client=anthropic.DefaultHttpxClient(transport=transport))


def scripted_async_client(respond: Responder) -> anthropic.AsyncAnthropic:
    transport = httpx2.MockTransport(_handler(respond))
    return anthropic.AsyncAnthropic(api_key="scripted", max_retries=0,
                                    http_client=anthropic.DefaultAsyncHttpxClient(transport=transport))
