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
from typing import Any, Callable

from .normalize import to_jsonable
from .recorder import RecordedToolError, active


def tool(fn: Callable | None = None, *, name: str | None = None):
    def decorate(func: Callable) -> Callable:
        tool_name = name or func.__name__
        signature = inspect.signature(func)

        def bound_input(args, kwargs) -> dict:
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            return to_jsonable(dict(bound.arguments))

        def replayed(event: dict) -> Any:
            if "error" in event:
                err = event["error"]
                raise RecordedToolError(f"{err['type']}: {err['message']}")
            return event.get("output")

        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                cassette = active()
                if cassette is None:
                    return await func(*args, **kwargs)
                tool_input = bound_input(args, kwargs)
                hit, event = cassette._tool(tool_name, tool_input)
                if hit:
                    return replayed(event)
                try:
                    result = await func(*args, **kwargs)
                except Exception as error:
                    cassette._record_tool(tool_name, tool_input, None, error)
                    raise
                cassette._record_tool(tool_name, tool_input, result, None)
                return result

            return async_wrapper

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cassette = active()
            if cassette is None:
                return func(*args, **kwargs)
            tool_input = bound_input(args, kwargs)
            hit, event = cassette._tool(tool_name, tool_input)
            if hit:
                return replayed(event)
            try:
                result = func(*args, **kwargs)
            except Exception as error:
                cassette._record_tool(tool_name, tool_input, None, error)
                raise
            cassette._record_tool(tool_name, tool_input, result, None)
            return result

        return wrapper

    return decorate(fn) if fn is not None else decorate
