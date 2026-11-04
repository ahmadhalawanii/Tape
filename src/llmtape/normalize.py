"""Turning SDK objects into plain JSON, and comparing two JSON values.

Everything Tape stores goes through `to_jsonable` first, so a tape file is ordinary JSON
that diffs cleanly in git and can be read without this library.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable

# Request keys that change between runs without changing what the model is asked.
VOLATILE_KEYS = frozenset({"extra_headers", "extra_query", "extra_body", "timeout"})

_SENTINELS = frozenset({"NotGiven", "Omit"})


def _is_sentinel(value: Any) -> bool:
    return type(value).__name__ in _SENTINELS


def to_jsonable(value: Any) -> Any:
    """Convert pydantic models, dataclasses, tuples and SDK sentinels to plain JSON."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items() if not _is_sentinel(v)}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value if not _is_sentinel(v)]
    if hasattr(value, "model_dump"):
        return to_jsonable(value.model_dump(mode="json", exclude_none=True))
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return to_jsonable(dataclasses.asdict(value))
    if isinstance(value, (set, frozenset)):
        return sorted(to_jsonable(v) for v in value)
    return repr(value)


Scrubber = tuple[str, str]  # (regex, replacement)


def scrub(value: Any, scrubbers: Iterable[Scrubber]) -> Any:
    """Apply regex replacements to every string in a JSON value."""
    compiled = [(re.compile(p) if isinstance(p, str) else p, r) for p, r in scrubbers]
    if not compiled:
        return value

    def walk(v: Any) -> Any:
        if isinstance(v, str):
            for pattern, repl in compiled:
                v = pattern.sub(repl, v)
            return v
        if isinstance(v, dict):
            return {k: walk(x) for k, x in v.items()}
        if isinstance(v, list):
            return [walk(x) for x in v]
        return v

    return walk(value)


def normalize_request(kwargs: dict, scrubbers: Iterable[Scrubber] = ()) -> dict:
    data = {k: v for k, v in kwargs.items() if k not in VOLATILE_KEYS}
    return scrub(to_jsonable(data), scrubbers)


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()[:16]


@dataclass(frozen=True)
class Change:
    path: str
    old: Any
    new: Any

    MISSING = "<missing>"

    def __str__(self) -> str:
        old, new = self.old, self.new
        if isinstance(old, str) and isinstance(new, str) and max(len(old), len(new)) > 80:
            old, new = _around_first_difference(old, new)
        return f"{self.path or '<root>'}: {_short(old)} -> {_short(new)}"


def json_diff(old: Any, new: Any, path: str = "", limit: int = 50) -> list[Change]:
    """Structural differences between two JSON values, as dotted paths."""
    out: list[Change] = []

    def walk(a: Any, b: Any, p: str) -> None:
        if len(out) >= limit:
            return
        if isinstance(a, dict) and isinstance(b, dict):
            for key in sorted(set(a) | set(b)):
                sub = f"{p}.{key}" if p else key
                walk(a.get(key, Change.MISSING), b.get(key, Change.MISSING), sub)
        elif isinstance(a, list) and isinstance(b, list):
            for i in range(max(len(a), len(b))):
                walk(a[i] if i < len(a) else Change.MISSING,
                     b[i] if i < len(b) else Change.MISSING, f"{p}[{i}]")
        elif a != b:
            out.append(Change(p, a, b))

    walk(old, new, path)
    return out


def _short(value: Any, width: int = 80) -> str:
    text = value if isinstance(value, str) and value == Change.MISSING else canonical(value)
    return text if len(text) <= width else text[: width - 3] + "..."


def _around_first_difference(a: str, b: str, context: int = 30) -> tuple[str, str]:
    """Long strings that share a prefix: show the part where they start to differ."""
    i = next((k for k, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    start = max(0, i - context)
    lead = "..." if start else ""
    return lead + a[start:i + 40], lead + b[start:i + 40]
