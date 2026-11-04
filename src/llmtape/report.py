"""A self-contained HTML page for one or more tapes, or for a diff between two.

No server, no build step and no external requests: the tape data is embedded as JSON and
rendered with textContent only, so model output in a tape can never inject markup.
"""

from __future__ import annotations

import json
from importlib import resources

from .diff import TapeDiff
from .pricing import cost_usd
from .tape import Tape


def transcript(tape: Tape) -> list[dict]:
    """The conversation as a reader sees it: each message once, in order."""
    items: list[dict] = []
    models = tape.model_events()
    if not models:
        return items
    system = models[0]["request"].get("system")
    if system:
        items.append({"role": "system", "blocks": [{"type": "text", "text": _system_text(system)}]})
    seen = 0
    for i, event in enumerate(models):
        messages = event["request"].get("messages", [])
        new = messages[seen:] if len(messages) >= seen else messages
        if i > 0 and new and new[0].get("role") == "assistant":
            new = new[1:]          # the previous response, already shown
        for message in new:
            items.append({"role": message.get("role", "user"), "blocks": _blocks(message.get("content"))})
        seen = len(messages)
        response = event["response"]
        model = response.get("model") or event["request"].get("model")
        items.append({
            "role": "assistant",
            "call": i,
            "blocks": _blocks(response.get("content")),
            "meta": {
                "model": model,
                "stop_reason": response.get("stop_reason"),
                "usage": response.get("usage") or {},
                "latency_ms": event.get("latency_ms"),
                "cost_usd": cost_usd(model, response.get("usage")),
            },
        })
    return items


def _system_text(system) -> str:
    if isinstance(system, str):
        return system
    return "\n\n".join(b.get("text", "") for b in system if isinstance(b, dict))


def _blocks(content) -> list[dict]:
    if content is None:
        return []
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    out = []
    for block in content:
        kind = block.get("type")
        if kind == "text":
            out.append({"type": "text", "text": block.get("text", "")})
        elif kind == "tool_use":
            out.append({"type": "tool_use", "name": block.get("name"), "input": block.get("input")})
        elif kind == "tool_result":
            body = block.get("content")
            if isinstance(body, list):
                body = "\n".join(b.get("text", json.dumps(b)) for b in body if isinstance(b, dict))
            out.append({"type": "tool_result", "text": str(body or ""), "is_error": bool(block.get("is_error"))})
        elif kind == "thinking":
            if block.get("thinking"):
                out.append({"type": "thinking", "text": block["thinking"]})
        else:
            out.append({"type": "other", "text": json.dumps(block, ensure_ascii=False)})
    return out


def _tape_payload(tape: Tape) -> dict:
    return {"name": tape.name, "summary": tape.summary(),
            "meta": tape.meta, "transcript": transcript(tape)}


def render(tapes: list[Tape] | None = None, diff: TapeDiff | None = None, title: str = "Tape") -> str:
    if diff is not None:
        payload = {"kind": "diff", "diff": diff.to_dict(),
                   "tapes": [_tape_payload(diff.a), _tape_payload(diff.b)]}
    else:
        payload = {"kind": "tapes", "tapes": [_tape_payload(t) for t in tapes or []]}
    # Escaping every "<" keeps "</script>" and "<!--" in model output from ending the block.
    data = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    template = resources.files("llmtape").joinpath("report.html").read_text(encoding="utf-8")
    return template.replace("{{TITLE}}", _escape(title)).replace("{{DATA}}", data)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
