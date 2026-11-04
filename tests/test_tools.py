import pytest

import llmtape


def make_tools():
    runs = {"lookup": 0, "boom": 0}

    @llmtape.tool
    def lookup(order_id: str, verbose: bool = False) -> dict:
        runs["lookup"] += 1
        return {"order_id": order_id, "total": 10.0}

    @llmtape.tool(name="explode")
    def boom(x: int) -> int:
        runs["boom"] += 1
        raise ValueError(f"bad {x}")

    return lookup, boom, runs


def test_tool_runs_normally_outside_a_tape():
    lookup, _, runs = make_tools()
    assert lookup("A1") == {"order_id": "A1", "total": 10.0}
    assert runs["lookup"] == 1


def test_tool_output_is_replayed_without_running(tmp_path):
    lookup, _, runs = make_tools()
    path = tmp_path / "t.json"
    with llmtape.use(path, "record"):
        lookup("A1")
    with llmtape.use(path, "replay") as run:
        assert lookup(order_id="A1") == {"order_id": "A1", "total": 10.0}
    assert runs["lookup"] == 1
    assert run.tool_events()[0]["input"] == {"order_id": "A1", "verbose": False}


def test_tool_errors_are_recorded_and_raised_on_replay(tmp_path):
    _, boom, runs = make_tools()
    path = tmp_path / "t.json"
    with pytest.raises(ValueError):
        with llmtape.use(path, "record") as run:
            boom(3)
    run.save(path)     # an exception skips the automatic save
    with llmtape.use(path, "replay"):
        with pytest.raises(llmtape.RecordedToolError, match="ValueError: bad 3"):
            boom(3)
    assert runs["boom"] == 1


def test_unrecorded_tool_input_diverges(tmp_path):
    lookup, _, _ = make_tools()
    path = tmp_path / "t.json"
    with llmtape.use(path, "record"):
        lookup("A1")
    with pytest.raises(llmtape.TapeDivergence, match="lookup"):
        with llmtape.use(path, "replay"):
            lookup("B2")


def test_async_tool(tmp_path):
    import asyncio
    runs = []

    @llmtape.tool
    async def fetch(url: str) -> str:
        runs.append(url)
        return "page"

    path = tmp_path / "t.json"
    for mode in ("record", "replay"):
        with llmtape.use(path, mode):
            assert asyncio.run(fetch("https://x")) == "page"
    assert runs == ["https://x"]
