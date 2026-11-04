"""Recording and replaying Messages API calls.

    with llmtape.use("tapes/refund.json") as tape:
        run_my_agent()
    tape.assert_called("lookup_order")

Modes:
    record  call the API, write a new tape
    replay  never call the API; a request that differs from the tape raises TapeDivergence
    auto    replay if the tape exists, otherwise record (the default)
    update  replay while requests match; from the first difference call the API for real
            and rewrite the tape. You pay only for the part of the run that changed.

The patch sits on the SDK's `messages.create` (sync, async, and beta), so any client
instance, including one built deep inside your code, is captured.
"""

from __future__ import annotations

import os
import re
import threading
from contextvars import ContextVar
import time
from pathlib import Path
from typing import Any, Iterable

from .normalize import Change, Scrubber, fingerprint, json_diff, normalize_request, to_jsonable
from .tape import Tape

MODES = ("record", "replay", "auto", "update")
ENV_MODE = "LLMTAPE_MODE"


class TapeDivergence(BaseException):
    """The run asked for something the tape does not hold.

    A BaseException, like pytest's own failures, so an agent's `except Exception`
    fallback cannot swallow it and quietly carry on against the real API.
    """

    def __init__(self, message: str, *, index: int | None = None,
                 changes: list[Change] | None = None, path: Path | None = None) -> None:
        super().__init__(message)
        self.index = index
        self.changes = changes or []
        self.path = path


class RecordedToolError(Exception):
    """A tool raised when the tape was recorded; replay raises this in its place."""


class StreamingNotSupported(Exception):
    pass


class Cassette:
    """One recording session over one tape file. Use through `llmtape.use(...)`."""

    def __init__(self, path: str | Path, mode: str | None = None,
                 scrub: Iterable[Scrubber] = (), strict: bool = True,
                 meta: dict | None = None) -> None:
        mode = mode or os.environ.get(ENV_MODE) or "auto"
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, not {mode!r}")
        self.path = Path(path)
        self.requested_mode = mode
        self.scrubbers = [(re.compile(p), r) for p, r in scrub]
        self.strict = strict
        self.meta = meta or {}

        exists = self.path.exists()
        if mode == "replay" and not exists:
            raise FileNotFoundError(f"No tape at {self.path}. Record one with {ENV_MODE}=record")
        self.mode = "replay" if mode == "auto" and exists else ("record" if mode == "auto" else mode)
        self.recorded = Tape.load(self.path) if exists and self.mode in ("replay", "update") else Tape()
        self.tape = Tape(meta={**self.meta}, path=self.path)   # what this run did

        self.live = self.mode == "record"     # update flips this at the first difference
        self._model_cursor = 0
        self._used_tools: set[int] = set()
        self._divergence: TapeDivergence | None = None
        self._lock = threading.Lock()

    # ---- context --------------------------------------------------------------------

    def __enter__(self) -> "Cassette":
        _push(self)
        return self

    async def __aenter__(self) -> "Cassette":
        return self.__enter__()

    def __exit__(self, exc_type, exc, tb) -> None:
        _pop(self)
        if self._divergence is not None and exc is not self._divergence:
            raise self._divergence      # an agent caught it; surface it anyway
        if exc_type is not None:
            return
        if self.mode == "replay" and self.strict:
            left = len(self.recorded.model_events()) - self._model_cursor
            if left > 0:
                raise TapeDivergence(
                    f"Run finished after {self._model_cursor} model call(s) but the tape at "
                    f"{self.path} holds {left} more. The agent stops earlier than when recorded.",
                    index=self._model_cursor, path=self.path)
        if self.mode in ("record", "update"):
            self.tape.meta.setdefault("mode", self.mode)
            self.tape.save(self.path)

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.__exit__(exc_type, exc, tb)

    # Assertions read what *this* run did.
    def __getattr__(self, name: str) -> Any:
        if name.startswith(("assert_", "tool_", "final_", "model_", "usage", "cost", "summary", "latency")):
            return getattr(self.tape, name)
        raise AttributeError(name)

    # ---- model calls ----------------------------------------------------------------

    def _next_model(self, endpoint: str, kwargs: dict) -> tuple[dict, dict | None]:
        """Return (normalized request, recorded event to replay, or None to go live)."""
        __tracebackhide__ = True
        if kwargs.get("stream"):
            raise StreamingNotSupported("llmtape does not record stream=True calls yet; "
                                        "call messages.create without stream inside a tape")
        request = normalize_request(kwargs, self.scrubbers)
        with self._lock:
            if self.live:
                return request, None
            recorded = self.recorded.model_events()
            index = self._model_cursor
            if index < len(recorded):
                old = recorded[index]
                if old.get("fingerprint") == fingerprint(request) or old["request"] == request:
                    self._model_cursor += 1
                    return request, old
                changes = json_diff(old["request"], request)
            else:
                changes = []
            if self.mode == "update":
                self.live = True
                self.tape.meta["diverged_at"] = index
                return request, None
            self._divergence = _divergence(self.path, index, len(recorded), changes)
            raise self._divergence

    def _record_model(self, endpoint: str, request: dict, response: Any, latency_ms: int) -> None:
        self.tape.events.append({
            "kind": "model",
            "endpoint": endpoint,
            "fingerprint": fingerprint(request),
            "request": request,
            "response": to_jsonable(response),
            "latency_ms": latency_ms,
        })

    # ---- tool calls -----------------------------------------------------------------

    def _tool(self, name: str, tool_input: dict) -> tuple[bool, Any]:
        """(True, recorded output) to replay, or (False, None) to run the tool for real."""
        __tracebackhide__ = True
        with self._lock:
            if self.live:
                return False, None
            for i, event in enumerate(self.recorded.events):
                if (i not in self._used_tools and event["kind"] == "tool"
                        and event["name"] == name and event["input"] == tool_input):
                    self._used_tools.add(i)
                    self.tape.events.append(event)
                    return True, event
            if self.mode == "update":
                return False, None     # a new tool call; run it, the model calls will follow
            self._divergence = TapeDivergence(
                f"Tool {name}({tool_input}) is not on the tape at {self.path}. "
                f"Re-record with {ENV_MODE}=update.", path=self.path)
            raise self._divergence

    def _record_tool(self, name: str, tool_input: dict, output: Any, error: BaseException | None) -> None:
        event = {"kind": "tool", "name": name, "input": tool_input}
        if error is None:
            event["output"] = to_jsonable(output)
        else:
            event["error"] = {"type": type(error).__name__, "message": str(error)}
        self.tape.events.append(event)


def _divergence(path: Path, index: int, recorded: int, changes: list[Change]) -> TapeDivergence:
    if changes:
        lines = "\n".join(f"  {c}" for c in changes[:12])
        more = f"\n  ... {len(changes) - 12} more" if len(changes) > 12 else ""
        detail = f"Request differs from the recording:\n{lines}{more}"
    else:
        detail = f"The tape holds only {recorded} model call(s); this run made another."
    return TapeDivergence(
        f"Run diverged from {path} at model call #{index}.\n{detail}\n"
        f"If the change is intended, re-record with {ENV_MODE}=update: it replays the matching "
        f"prefix and calls the API only from this point.",
        index=index, changes=changes, path=path)


# ---- the patch ----------------------------------------------------------------------

# Which cassette is open is per thread and per asyncio task; the SDK patch is shared, so it
# stays installed while any cassette anywhere is open.
_active: ContextVar[tuple[Cassette, ...]] = ContextVar("llmtape_active", default=())
_open = 0
_originals: dict[tuple[type, str], Any] = {}
_patch_lock = threading.Lock()


def active() -> Cassette | None:
    stack = _active.get()
    return stack[-1] if stack else None


def _push(cassette: Cassette) -> None:
    global _open
    with _patch_lock:
        if _open == 0:
            _install()
        _open += 1
    cassette._token = _active.set(_active.get() + (cassette,))


def _pop(cassette: Cassette) -> None:
    global _open
    try:
        _active.reset(cassette._token)
    except ValueError:      # exited in a different context than it was entered
        _active.set(tuple(c for c in _active.get() if c is not cassette))
    with _patch_lock:
        _open -= 1
        if _open == 0:
            _uninstall()


def _targets() -> list[tuple[type, str, bool]]:
    from anthropic.resources.messages import AsyncMessages, Messages

    targets = [(Messages, "messages", False), (AsyncMessages, "messages", True)]
    try:
        from anthropic.resources.beta.messages import AsyncMessages as BetaAsync
        from anthropic.resources.beta.messages import Messages as Beta
        targets += [(Beta, "beta.messages", False), (BetaAsync, "beta.messages", True)]
    except ImportError:  # pragma: no cover - older SDKs
        pass
    return targets


def _response_type(endpoint: str):
    if endpoint == "beta.messages":
        from anthropic.types.beta import BetaMessage
        return BetaMessage
    from anthropic.types import Message
    return Message


def _install() -> None:
    for cls, endpoint, is_async in _targets():
        original = cls.create
        _originals[(cls, "create")] = original
        cls.create = _async_wrapper(original, endpoint) if is_async else _sync_wrapper(original, endpoint)
        if hasattr(cls, "stream"):
            _originals[(cls, "stream")] = cls.stream
            cls.stream = _refuse_stream(cls.stream)


def _refuse_stream(original):
    """messages.stream() is not recorded yet; inside a tape it must not reach the API quietly."""
    def stream(self, *args, **kwargs):
        if active() is not None:
            raise StreamingNotSupported("llmtape does not record messages.stream() yet; "
                                        "use messages.create inside a tape")
        return original(self, *args, **kwargs)
    return stream


def _uninstall() -> None:
    for (cls, attr), original in _originals.items():
        setattr(cls, attr, original)
    _originals.clear()


def _sync_wrapper(original, endpoint: str):
    def create(self, *args, **kwargs):
        __tracebackhide__ = True
        cassette = active()
        if cassette is None:
            return original(self, *args, **kwargs)
        request, replay = cassette._next_model(endpoint, kwargs)
        if replay is not None:
            cassette.tape.events.append(replay)
            return _response_type(endpoint).model_validate(replay["response"])
        started = time.monotonic()
        response = original(self, *args, **kwargs)
        cassette._record_model(endpoint, request, response, int((time.monotonic() - started) * 1000))
        return response

    create.__wrapped__ = original
    return create


def _async_wrapper(original, endpoint: str):
    async def create(self, *args, **kwargs):
        __tracebackhide__ = True
        cassette = active()
        if cassette is None:
            return await original(self, *args, **kwargs)
        request, replay = cassette._next_model(endpoint, kwargs)
        if replay is not None:
            cassette.tape.events.append(replay)
            return _response_type(endpoint).model_validate(replay["response"])
        started = time.monotonic()
        response = await original(self, *args, **kwargs)
        cassette._record_model(endpoint, request, response, int((time.monotonic() - started) * 1000))
        return response

    create.__wrapped__ = original
    return create


def use(path: str | Path, mode: str | None = None, *, scrub: Iterable[Scrubber] = (),
        strict: bool = True, meta: dict | None = None) -> Cassette:
    """Record or replay every Messages API call made inside the `with` block."""
    return Cassette(path, mode, scrub=scrub, strict=strict, meta=meta)
