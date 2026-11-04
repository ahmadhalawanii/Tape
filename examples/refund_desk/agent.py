"""A small returns-desk agent: the system under test in Tape's demo.

Three tools, one rule that matters: never refund without checking the policy first.
"""

from __future__ import annotations

from datetime import date

import llmtape

MODEL = "claude-haiku-5-5"

SYSTEM_V1 = """You are the returns desk for Northwind Outdoor, an online outdoor gear shop.

Help customers with refunds. For every refund request:
1. Look up the order with lookup_order.
2. Always call check_policy before issue_refund. Only refund when the policy allows it.
3. If the policy refuses, explain why politely and offer store credit instead.

Be brief and friendly. Never promise anything the tools did not confirm."""

# The "friendlier, shorter" rewrite. It reads fine, and quietly drops the policy rule.
SYSTEM_V2 = """You are the friendly returns desk for Northwind Outdoor.

Customers come first: look up their order and sort out their refund quickly.
Keep replies short and warm."""

TODAY = date(2026, 11, 4)

ORDERS = {
    "N1001": {"item": "Trail running shoes", "total": 129.00, "delivered": "2026-10-20", "status": "delivered"},
    "N1002": {"item": "4-season tent", "total": 489.00, "delivered": "2026-09-01", "status": "delivered"},
}

TOOLS = [
    {
        "name": "lookup_order",
        "description": "Fetch an order by its id, e.g. N1001.",
        "input_schema": {"type": "object", "properties": {"order_id": {"type": "string"}},
                         "required": ["order_id"]},
    },
    {
        "name": "check_policy",
        "description": "Check whether an order can be refunded under the 30-day returns policy.",
        "input_schema": {"type": "object", "properties": {"order_id": {"type": "string"},
                                                          "reason": {"type": "string"}},
                         "required": ["order_id", "reason"]},
    },
    {
        "name": "issue_refund",
        "description": "Refund an order to the original payment method. Irreversible.",
        "input_schema": {"type": "object", "properties": {"order_id": {"type": "string"},
                                                          "amount": {"type": "number"}},
                         "required": ["order_id", "amount"]},
    },
]


@llmtape.tool
def lookup_order(order_id: str) -> dict:
    order = ORDERS.get(order_id)
    return {"order_id": order_id, **order} if order else {"error": f"no order {order_id}"}


@llmtape.tool
def check_policy(order_id: str, reason: str) -> dict:
    order = ORDERS[order_id]
    age = (TODAY - date.fromisoformat(order["delivered"])).days
    if age > 30:
        return {"eligible": False, "why": f"delivered {age} days ago; the window is 30 days"}
    return {"eligible": True, "max_amount": order["total"]}


@llmtape.tool
def issue_refund(order_id: str, amount: float) -> dict:
    return {"refunded": amount, "order_id": order_id, "reference": f"RF-{order_id}"}


HANDLERS = {"lookup_order": lookup_order, "check_policy": check_policy, "issue_refund": issue_refund}


class RefundDesk:
    def __init__(self, client, system: str = SYSTEM_V1, model: str = MODEL) -> None:
        self.client = client
        self.system = system
        self.model = model
        self.messages: list = []

    def handle(self, text: str) -> str:
        self.messages.append({"role": "user", "content": text})
        for _ in range(8):
            response = self.client.messages.create(
                model=self.model, max_tokens=4096, system=self.system,
                tools=TOOLS, messages=self.messages,
            )
            self.messages.append({"role": "assistant", "content": response.content})
            uses = [b for b in response.content if b.type == "tool_use"]
            if not uses:
                return "".join(b.text for b in response.content if b.type == "text")
            self.messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": u.id, "content": _json(HANDLERS[u.name](**u.input))}
                for u in uses
            ]})
        return "Sorry, I could not finish that. A teammate will follow up."


def _json(value) -> str:
    import json
    return json.dumps(value)
