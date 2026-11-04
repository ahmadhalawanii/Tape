"""A deterministic stand-in for the model, so the demo runs without an API key.

It follows the system prompt the way a model would: it checks the refund policy only
when the prompt tells it to. Record against Claude instead with ANTHROPIC_API_KEY set
and LLMTAPE_MODE=record; the tests and the diff work the same either way.
"""

from __future__ import annotations

import json
import re


def respond(request: dict) -> list[dict]:
    system = request.get("system") or ""
    messages = request["messages"]
    asked = next(m["content"] for m in messages if m["role"] == "user" and isinstance(m["content"], str))
    order_id = (re.search(r"N\d{4}", asked) or [None])[0]

    calls, results = {}, {}
    for m in messages:
        for b in m["content"] if isinstance(m["content"], list) else []:
            if b.get("type") == "tool_use":
                calls[b["id"]] = b
            if b.get("type") == "tool_result":
                results[calls[b["tool_use_id"]]["name"]] = json.loads(b["content"])

    def use(name, **args):
        return [{"type": "tool_use", "name": name, "input": args}]

    if not order_id:
        return [{"type": "text", "text": "Happy to help. What is your order number? It starts with N."}]
    if "lookup_order" not in results:
        return [{"type": "text", "text": "Let me pull up that order."}] + use("lookup_order", order_id=order_id)
    order = results["lookup_order"]
    if "check_policy before issue_refund" in system and "check_policy" not in results:
        return use("check_policy", order_id=order_id, reason=asked[:80])
    policy = results.get("check_policy", {"eligible": True})
    if not policy["eligible"]:
        return [{"type": "text", "text":
                 f"I'm sorry, the {order['item'].lower()} can't be refunded: it was {policy['why']}. "
                 f"I can offer ${order['total']:.2f} in store credit instead. Would that help?"}]
    if "issue_refund" not in results:
        return use("issue_refund", order_id=order_id, amount=order["total"])
    return [{"type": "text", "text":
             f"Done. ${order['total']:.2f} is on its way back to your card "
             f"(reference {results['issue_refund']['reference']}). It usually lands in 3 to 5 days."}]
