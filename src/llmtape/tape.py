"""The tape file, and questions you can ask of it.

A tape is an ordered list of events. A `model` event is one Messages API call: the
request as sent, the response as received, and how long it took. A `tool` event is one
call to a function wrapped with `@llmtape.tool`: its input and its output or error.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .pricing import cost_usd

FORMAT_VERSION = 1


@dataclass(frozen=True)
class ToolCall:
    """A tool the model asked for, in the order it asked."""

    name: str
    input: dict
    call_index: int     # which model call requested it
    id: str = ""

    def __repr__(self) -> str:
        return f"{self.name}({json.dumps(self.input, ensure_ascii=False)})"


@dataclass
class Tape:
    events: list[dict] = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    path: Path | None = None

    # ---- files ----------------------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path) -> "Tape":
        path = Path(path)
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")), path)

    @classmethod
    def from_dict(cls, data: dict, path: Path | None = None) -> "Tape":
        if not isinstance(data, dict):
            raise ValueError(f"{path or 'tape'}: not a tape file")
        version = data.get("llmtape")
        if version != FORMAT_VERSION:
            raise ValueError(f"{path or 'tape'}: unsupported tape format {version!r}")
        return cls(events=list(data.get("events", [])), meta=dict(data.get("meta", {})), path=path)

    def to_dict(self) -> dict:
        return {"llmtape": FORMAT_VERSION, "meta": self.meta, "events": self.events}

    def save(self, path: str | Path | None = None) -> Path:
        path = Path(path or self.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.meta.setdefault("recorded_at", datetime.now(timezone.utc).isoformat(timespec="seconds"))
        text = json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n"
        path.write_text(text, encoding="utf-8")
        self.path = path
        return path

    @property
    def name(self) -> str:
        """The path for display: relative to the working directory when inside it."""
        if self.path is None:
            return "tape"
        try:
            return self.path.resolve().relative_to(Path.cwd()).as_posix()
        except ValueError:
            return str(self.path)

    # ---- what happened --------------------------------------------------------------

    def model_events(self) -> list[dict]:
        return [e for e in self.events if e["kind"] == "model"]

    def tool_events(self) -> list[dict]:
        return [e for e in self.events if e["kind"] == "tool"]

    def tool_calls(self) -> list[ToolCall]:
        calls = []
        for i, event in enumerate(self.model_events()):
            for block in event["response"].get("content", []):
                if block.get("type") == "tool_use":
                    calls.append(ToolCall(block["name"], block.get("input") or {}, i, block.get("id", "")))
        return calls

    def tool_names(self) -> list[str]:
        return [c.name for c in self.tool_calls()]

    def final_text(self) -> str:
        """Text of the last model response, the agent's answer to the user."""
        models = self.model_events()
        if not models:
            return ""
        return response_text(models[-1]["response"])

    def usage(self) -> dict:
        keys = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
        total = dict.fromkeys(keys, 0)
        for event in self.model_events():
            usage = event["response"].get("usage") or {}
            for key in keys:
                total[key] += usage.get(key) or 0
        return total

    def cost_usd(self) -> float | None:
        costs = [cost_usd(e["response"].get("model") or e["request"].get("model"),
                          e["response"].get("usage")) for e in self.model_events()]
        return None if any(c is None for c in costs) else sum(costs)

    def latency_ms(self) -> int:
        return sum(int(e.get("latency_ms") or 0) for e in self.model_events())

    def summary(self) -> dict:
        return {
            "model_calls": len(self.model_events()),
            "tool_calls": len(self.tool_calls()),
            "models": sorted({e["response"].get("model") or e["request"].get("model", "?")
                              for e in self.model_events()}),
            **self.usage(),
            "cost_usd": self.cost_usd(),
            "latency_ms": self.latency_ms(),
        }

    # ---- assertions -----------------------------------------------------------------
    # Each returns self so they chain, and fails with the whole trajectory in the message,
    # because "expected issue_refund" is useless without seeing what happened instead.

    def assert_called(self, name: str, **expected: Any) -> "Tape":
        calls = [c for c in self.tool_calls() if c.name == name]
        if not calls:
            raise AssertionError(f"{name} was never called. Tool calls: {self._trajectory()}")
        if expected and not any(_matches(c.input, expected) for c in calls):
            got = "; ".join(repr(c) for c in calls)
            raise AssertionError(f"{name} was called, but never with {expected}. Calls: {got}")
        return self

    def assert_not_called(self, name: str) -> "Tape":
        calls = [c for c in self.tool_calls() if c.name == name]
        if calls:
            raise AssertionError(f"{name} was called {len(calls)} time(s): {calls}")
        return self

    def assert_called_before(self, first: str, then: str) -> "Tape":
        names = self.tool_names()
        if then in names and (first not in names or names.index(first) > names.index(then)):
            raise AssertionError(f"{then} ran before {first}. Tool calls: {self._trajectory()}")
        return self

    def assert_order(self, names: Iterable[str]) -> "Tape":
        """The given tools appear in this order (other calls may sit between them)."""
        wanted = list(names)
        it = iter(self.tool_names())
        if not all(any(n == got for got in it) for n in wanted):
            raise AssertionError(f"Expected order {wanted}. Tool calls: {self._trajectory()}")
        return self

    def assert_max_calls(self, n: int) -> "Tape":
        count = len(self.model_events())
        if count > n:
            raise AssertionError(f"{count} model calls, expected at most {n}")
        return self

    def assert_cost_below(self, usd: float) -> "Tape":
        cost = self.cost_usd()
        if cost is None:
            raise AssertionError("Cost unknown: add the model to llmtape.pricing.PRICES")
        if cost >= usd:
            raise AssertionError(f"Cost ${cost:.6f} is not below ${usd:.6f}")
        return self

    def assert_text_contains(self, *needles: str) -> "Tape":
        text = self.final_text()
        missing = [n for n in needles if n.lower() not in text.lower()]
        if missing:
            raise AssertionError(f"Final reply lacks {missing}. Reply: {text!r}")
        return self

    def _trajectory(self) -> str:
        calls = self.tool_calls()
        return " -> ".join(repr(c) for c in calls) if calls else "(none)"


def response_text(response: dict) -> str:
    return "".join(b.get("text", "") for b in response.get("content", []) if b.get("type") == "text")


def _matches(actual: Any, expected: Any) -> bool:
    """Subset match: every expected key is present with an equal (or subset) value."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            k in actual and _matches(actual[k], v) for k, v in expected.items())
    return actual == expected
