import asyncio
import json

import pytest

import llmtape
from llmtape import Tape, TapeDivergence

from .conftest import ask


def test_record_then_replay_returns_the_same_message_without_calling_the_model(client, echo, tmp_path):
    path = tmp_path / "t.json"
    with llmtape.use(path) as run:
        first = ask(client, "hello")
    assert path.exists() and echo.calls == 1
    assert run.summary()["model_calls"] == 1

    with llmtape.use(path) as run:          # auto: the tape exists, so it replays
        again = ask(client, "hello")
    assert echo.calls == 1
    assert again.content[0].text == first.content[0].text == "echo hello"
    assert type(again) is type(first)


def test_replay_raises_on_a_changed_request_and_names_the_field(client, tmp_path):
    path = tmp_path / "t.json"
    with llmtape.use(path, "record"):
        ask(client, "hello")
    with pytest.raises(TapeDivergence) as caught:
        with llmtape.use(path, "replay"):
            ask(client, "goodbye")
    assert caught.value.index == 0
    assert [c.path for c in caught.value.changes] == ["messages[0].content"]
    assert "LLMTAPE_MODE=update" in str(caught.value)


def test_divergence_is_not_swallowed_by_an_agents_except_exception(client, tmp_path):
    path = tmp_path / "t.json"
    with llmtape.use(path, "record"):
        ask(client, "hello")

    def agent_with_fallback():
        try:
            return ask(client, "changed")
        except Exception:
            return "fallback reply"

    with pytest.raises(TapeDivergence):
        with llmtape.use(path, "replay"):
            agent_with_fallback()


def test_divergence_is_raised_at_exit_even_if_caught_as_base_exception(client, tmp_path):
    path = tmp_path / "t.json"
    with llmtape.use(path, "record"):
        ask(client, "hello")
    with pytest.raises(TapeDivergence):
        with llmtape.use(path, "replay"):
            try:
                ask(client, "changed")
            except BaseException:
                pass


def test_strict_replay_fails_when_the_run_makes_fewer_calls(client, tmp_path):
    path = tmp_path / "t.json"
    with llmtape.use(path, "record"):
        ask(client, "one")
        ask(client, "two")
    with pytest.raises(TapeDivergence, match="stops earlier"):
        with llmtape.use(path, "replay"):
            ask(client, "one")
    with llmtape.use(path, "replay", strict=False):
        ask(client, "one")


def test_replay_without_a_tape_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        llmtape.use(tmp_path / "missing.json", "replay")


def test_update_replays_the_matching_prefix_and_goes_live_from_the_first_difference(client, echo, tmp_path):
    path = tmp_path / "t.json"
    with llmtape.use(path, "record"):
        ask(client, "one")
        ask(client, "two")
        ask(client, "three")
    assert echo.calls == 3

    with llmtape.use(path, "update"):
        ask(client, "one")
        ask(client, "TWO")
        ask(client, "three")
    assert echo.calls == 5                  # call #0 replayed; #1 and #2 live
    tape = Tape.load(path)
    assert tape.meta["diverged_at"] == 1
    assert [e["response"]["content"][0]["text"] for e in tape.model_events()] == \
        ["echo one", "echo TWO", "echo three"]


def test_scrubbers_ignore_volatile_text(client, tmp_path):
    path = tmp_path / "t.json"
    scrub = [(r"\d{4}-\d{2}-\d{2}", "<date>")]
    with llmtape.use(path, "record", scrub=scrub):
        ask(client, "hi", system="Today is 2026-11-04.")
    with llmtape.use(path, "replay", scrub=scrub):
        ask(client, "hi", system="Today is 2027-01-01.")
    assert "<date>" in path.read_text()


def test_streaming_is_refused_rather_than_silently_unrecorded(client, tmp_path):
    with pytest.raises(llmtape.StreamingNotSupported):
        with llmtape.use(tmp_path / "t.json", "record"):
            client.messages.create(model="m", max_tokens=5, stream=True,
                                   messages=[{"role": "user", "content": "x"}])


def test_messages_stream_is_refused_inside_a_tape(client, tmp_path):
    with pytest.raises(llmtape.StreamingNotSupported):
        with llmtape.use(tmp_path / "t.json", "record"):
            client.messages.stream(model="m", max_tokens=5, messages=[{"role": "user", "content": "x"}])


def test_concurrent_threads_each_use_their_own_tape(client, tmp_path):
    import threading
    barrier = threading.Barrier(2)

    def run(name):
        with llmtape.use(tmp_path / f"{name}.json", "record"):
            barrier.wait()
            ask(client, name)
            barrier.wait()

    threads = [threading.Thread(target=run, args=(n,)) for n in ("left", "right")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    for name in ("left", "right"):
        texts = [e["response"]["content"][0]["text"] for e in Tape.load(tmp_path / f"{name}.json").model_events()]
        assert texts == [f"echo {name}"]


def test_async_client_records_and_replays(aclient, echo, tmp_path):
    path = tmp_path / "t.json"

    async def run():
        return await aclient.messages.create(model="claude-haiku-5-5", max_tokens=5,
                                             messages=[{"role": "user", "content": "async"}])

    with llmtape.use(path, "record"):
        asyncio.run(run())
    with llmtape.use(path, "replay"):
        message = asyncio.run(run())
    assert echo.calls == 1 and message.content[0].text == "echo async"


def test_beta_messages_are_recorded_too(client, echo, tmp_path):
    path = tmp_path / "t.json"
    for mode in ("record", "replay"):
        with llmtape.use(path, mode):
            message = client.beta.messages.create(model="claude-haiku-5-5", max_tokens=5,
                                                  messages=[{"role": "user", "content": "beta"}])
    assert echo.calls == 1
    assert type(message).__name__ == "BetaMessage"
    assert json.loads(path.read_text())["events"][0]["endpoint"] == "beta.messages"


def test_patch_is_removed_after_the_block(client, echo, tmp_path):
    from anthropic.resources.messages import Messages
    original = Messages.create
    with llmtape.use(tmp_path / "t.json", "record"):
        assert Messages.create is not original
    assert Messages.create is original
    ask(client, "untaped")
    assert echo.calls == 1


def test_no_secrets_are_written(client, tmp_path):
    path = tmp_path / "t.json"
    with llmtape.use(path, "record"):
        client.messages.create(model="m", max_tokens=5, extra_headers={"x-api-key": "sk-secret"},
                               messages=[{"role": "user", "content": "x"}])
    assert "sk-secret" not in path.read_text() and "scripted" not in path.read_text()


def test_credentials_in_prompts_and_tool_output_are_redacted(client, tmp_path):
    key = "sk-ant-api03-" + "x" * 40
    path = tmp_path / "t.json"

    @llmtape.tool
    def leaky() -> dict:
        return {"aws": "AKIA" + "A" * 16}

    with llmtape.use(path, "record"):
        ask(client, f"my key is {key}")
        leaky()
    text = path.read_text()
    assert key not in text and "AKIA" not in text and "<redacted>" in text
    with llmtape.use(path, "replay"):           # redaction is applied the same way on replay
        ask(client, f"my key is {key}")
        leaky()
