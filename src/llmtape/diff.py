"""What changed in an agent's behaviour between two tapes.

Not a text diff of the JSON: the questions a reviewer asks are which tools the agent now
calls or skips, with what arguments, what it finally told the user, and what it cost.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field

from .normalize import Change, json_diff
from .tape import Tape, ToolCall


@dataclass
class Step:
    op: str                    # same | changed | added | removed
    a: ToolCall | None = None
    b: ToolCall | None = None
    changes: list[Change] = field(default_factory=list)


@dataclass
class TapeDiff:
    a: Tape
    b: Tape
    first_divergence: int | None
    request_changes: list[Change]
    trajectory: list[Step]
    text_a: str
    text_b: str

    @property
    def behaviour_changed(self) -> bool:
        return any(s.op != "same" for s in self.trajectory) or self.text_a != self.text_b

    def metrics(self) -> list[tuple[str, float | None, float | None]]:
        sa, sb = self.a.summary(), self.b.summary()
        keys = ["model_calls", "tool_calls", "input_tokens", "output_tokens", "cost_usd", "latency_ms"]
        return [(k, sa[k], sb[k]) for k in keys]

    def headline(self) -> list[str]:
        """One line per behaviour change, most important first."""
        lines = []
        for s in self.trajectory:
            if s.op == "added":
                lines.append(f"now calls {s.b!r}")
            elif s.op == "removed":
                lines.append(f"no longer calls {s.a!r}")
            elif s.op == "changed":
                args = ", ".join(str(c) for c in s.changes[:3])
                lines.append(f"{s.b.name} called with different input: {args}")
        if self.text_a != self.text_b:
            lines.append("final reply changed")
        return lines

    def to_dict(self) -> dict:
        def call(c: ToolCall | None):
            return None if c is None else {"name": c.name, "input": c.input, "call_index": c.call_index}

        return {
            "a": self.a.name,
            "b": self.b.name,
            "behaviour_changed": self.behaviour_changed,
            "headline": self.headline(),
            "first_divergence": self.first_divergence,
            "request_changes": [str(c) for c in self.request_changes],
            "trajectory": [{"op": s.op, "a": call(s.a), "b": call(s.b),
                            "changes": [str(c) for c in s.changes]} for s in self.trajectory],
            "text_a": self.text_a,
            "text_b": self.text_b,
            "metrics": [{"name": n, "a": a, "b": b} for n, a, b in self.metrics()],
        }

    # ---- rendering ------------------------------------------------------------------

    def to_text(self, color: bool = False) -> str:
        red, green, yellow, dim, reset = (("\033[31m", "\033[32m", "\033[33m", "\033[2m", "\033[0m")
                                          if color else ("",) * 5)
        out = [f"tape diff  {self.a.name}  ->  {self.b.name}", ""]
        if not self.behaviour_changed and self.first_divergence is None:
            out.append(f"{green}No change in behaviour.{reset}")
        for line in self.headline():
            out.append(f"{yellow}* {line}{reset}")
        if self.first_divergence is not None:
            out += ["", f"First differing request: model call #{self.first_divergence}"]
            out += [f"{dim}  {c}{reset}" for c in self.request_changes[:8]]
        out += ["", "Tool calls:"]
        for s in self.trajectory:
            if s.op == "same":
                out.append(f"    {s.a!r}")
            elif s.op == "removed":
                out.append(f"{red}  - {s.a!r}{reset}")
            elif s.op == "added":
                out.append(f"{green}  + {s.b!r}{reset}")
            else:
                out.append(f"{red}  - {s.a!r}{reset}")
                out.append(f"{green}  + {s.b!r}{reset}")
        if not self.trajectory:
            out.append("    (none)")
        if self.text_a != self.text_b:
            out += ["", "Final reply:"]
            for line in difflib.unified_diff(self.text_a.splitlines(), self.text_b.splitlines(),
                                             lineterm="", n=1):
                if line.startswith(("---", "+++", "@@")):
                    continue
                tint = red if line.startswith("-") else green if line.startswith("+") else ""
                out.append(f"{tint}  {line}{reset}")
        out += ["", f"{'':16}{'before':>12}{'after':>12}{'change':>20}"]
        for name, a, b in self.metrics():
            out.append(f"  {name:14}{_fmt(a):>12}{_fmt(b):>12}{_delta(a, b):>20}")
        return "\n".join(out)

    def to_markdown(self) -> str:
        """For a CI job summary or a pull request comment."""
        title = "Agent behaviour changed" if self.behaviour_changed else "No change in agent behaviour"
        out = [f"### {title}: `{self.b.name}`", ""]
        out += [f"- {line}" for line in self.headline()]
        out += ["", "| | before | after | change |", "|---|---:|---:|---:|"]
        out += [f"| {n} | {_fmt(a)} | {_fmt(b)} | {_delta(a, b)} |" for n, a, b in self.metrics()]
        out += ["", "<details><summary>Tool calls</summary>", "", "```diff"]
        for s in self.trajectory:
            if s.op == "same":
                out.append(f"  {s.a!r}")
            if s.op in ("removed", "changed"):
                out.append(f"- {s.a!r}")
            if s.op in ("added", "changed"):
                out.append(f"+ {s.b!r}")
        out += ["```", "", "</details>"]
        return "\n".join(out)


def diff_tapes(a: Tape, b: Tape) -> TapeDiff:
    first, changes = _first_divergence(a, b)
    return TapeDiff(a, b, first, changes, _align(a.tool_calls(), b.tool_calls()),
                    a.final_text(), b.final_text())


def _first_divergence(a: Tape, b: Tape) -> tuple[int | None, list[Change]]:
    ma, mb = a.model_events(), b.model_events()
    for i, (x, y) in enumerate(zip(ma, mb)):
        if x["request"] != y["request"]:
            return i, json_diff(x["request"], y["request"], limit=20)
    if len(ma) != len(mb):
        return min(len(ma), len(mb)), []
    return None, []


def _align(a: list[ToolCall], b: list[ToolCall]) -> list[Step]:
    steps: list[Step] = []
    matcher = difflib.SequenceMatcher(a=[c.name for c in a], b=[c.name for c in b], autojunk=False)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            for x, y in zip(a[i1:i2], b[j1:j2]):
                changes = json_diff(x.input, y.input)
                steps.append(Step("changed" if changes else "same", x, y, changes))
        else:
            steps += [Step("removed", a=x) for x in a[i1:i2]]
            steps += [Step("added", b=y) for y in b[j1:j2]]
    return steps


def _fmt(v) -> str:
    if v is None:
        return "?"
    if isinstance(v, float):
        return f"${v:.5f}"
    return f"{v:,}"


def _delta(a, b) -> str:
    if a is None or b is None:
        return ""
    d = b - a
    if not d:
        return "0"
    if isinstance(d, float):
        pct = f" ({d / a:+.0%})" if a else ""
        return f"{'+' if d > 0 else '-'}${abs(d):.5f}{pct}"
    return f"{d:+,}"
