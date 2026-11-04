"""`@llmtape.tool`: record a tool's result so replay needs no database, API or network.

    @llmtape.tool
    def lookup_order(order_id: str) -> dict:
        return db.fetch(order_id)

Outside a tape the function runs normally. Inside one, its input and output are recorded,
and on replay the recorded output is returned without running it. Outputs must be JSON
serializable (dicts, lists, dataclasses, pydantic models); replay returns the JSON form.
"""

from __future__ import annotations

import functools
import inspect
from typing import Callable

from .normalize import redact, to_jsonable
from .recorder import RecordedToolError, active

_LIVE = object()   # sentinel: run the real function


def tool(fn: Callable | None = None, *, name: str | None = None):
    def decorate(func: Callable) -> Callable:
        tool_name = name or func.__name__
        signature = inspect.signature(func)

        def bound_input(args, kwargs) -> dict:
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            return redact(to_jsonable(dict(bound.arguments)))

        def taped(args, kwargs):
            """(cassette, input, recorded output or _LIVE). No cassette means run normally."""
            cassette = active()
            if cassette is None:
                return None, None, _LIVE
            tool_input = bound_input(args, kwargs)
            hit, event = cassette._tool(tool_name, tool_input)
            if not hit:
                return cassette, tool_input, _LIVE
            if "error" in event:
                raise RecordedToolError(f"{event['error']['type']}: {event['error']['message']}")
            return cassette, tool_input, event.get("output")

        def record(cassette, tool_input, result, error):
            if cassette is not None:
                cassette._record_tool(tool_name, tool_input, result, error)

        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                cassette, tool_input, output = taped(args, kwargs)
                if output is not _LIVE:
                    return output
                try:
                    result = await func(*args, **kwargs)
                except Exception as error:
                    record(cassette, tool_input, None, error)
                    raise
                record(cassette, tool_input, result, None)
                return result

            return async_wrapper

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cassette, tool_input, output = taped(args, kwargs)
            if output is not _LIVE:
                return output
            try:
                result = func(*args, **kwargs)
            except Exception as error:
                record(cassette, tool_input, None, error)
                raise
            record(cassette, tool_input, result, None)
            return result

        return wrapper

    return decorate(fn) if fn is not None else decorate
