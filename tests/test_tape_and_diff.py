import pytest

from llmtape import Tape, diff_tapes
from llmtape.pricing import cost_usd


def model(tool_uses=(), text="", model="claude-haiku-5-5", system="s", inp=100, out=20):
    content = [{"type": "tool_use", "id": f"t{i}", "name": n, "input": a} for i, (n, a) in enumerate(tool_uses)]
    if text:
        content.append({"type": "text", "text": text})
    return {"kind": "model", "request": {"model": model, "system": system, "messages": []},
            "response": {"model": model, "content": content,
                         "usage": {"input_tokens": inp, "output_tokens": out}}, "latency_ms": 5}


@pytest.fixture
def refund_tape():
    return Tape(events=[
        model([("lookup_order", {"order_id": "A1"})]),
        model([("check_policy", {"order_id": "A1"})]),
        model([("issue_refund", {"order_id": "A1", "amount": 40})]),
        model(text="Refunded $40."),
    ])


def test_queries(refund_tape):
    assert refund_tape.tool_names() == ["lookup_order", "check_policy", "issue_refund"]
    assert refund_tape.final_text() == "Refunded $40."
    s = refund_tape.summary()
    assert s["model_calls"] == 4 and s["tool_calls"] == 3 and s["input_tokens"] == 400


def test_passing_assertions_chain(refund_tape):
    (refund_tape.assert_called("issue_refund", amount=40)
     .assert_called_before("check_policy", "issue_refund")
     .assert_order(["lookup_order", "issue_refund"])
     .assert_not_called("cancel_order")
     .assert_max_calls(4)
     .assert_cost_below(0.01)
     .assert_text_contains("refunded"))


@pytest.mark.parametrize("check, message", [
    (lambda t: t.assert_called("cancel_order"), "never called"),
    (lambda t: t.assert_called("issue_refund", amount=99), "never with"),
    (lambda t: t.assert_not_called("issue_refund"), "called 1 time"),
    (lambda t: t.assert_called_before("issue_refund", "check_policy"), "ran before"),
    (lambda t: t.assert_order(["issue_refund", "lookup_order"]), "Expected order"),
    (lambda t: t.assert_max_calls(2), "4 model calls"),
    (lambda t: t.assert_cost_below(0.0000001), "not below"),
    (lambda t: t.assert_text_contains("sorry"), "lacks"),
])
def test_failing_assertions_explain_what_happened(refund_tape, check, message):
    with pytest.raises(AssertionError, match=message):
        check(refund_tape)


def test_pricing_handles_dated_snapshots_and_unknown_models():
    usage = {"input_tokens": 1_000_000, "output_tokens": 1_000_000}
    assert cost_usd("claude-haiku-4-5-20251001", usage) == pytest.approx(6.0)
    assert cost_usd("claude-opus-5-5", usage) == pytest.approx(24.0)
    assert cost_usd("some-other-model", usage) is None
    assert Tape(events=[model(model="unknown")]).cost_usd() is None


def test_diff_finds_skipped_new_and_changed_tool_calls(refund_tape):
    after = Tape(events=[
        model([("lookup_order", {"order_id": "A1"})], system="s2"),
        model([("issue_refund", {"order_id": "A1", "amount": 400})], system="s2"),
        model(text="Refunded $400.", system="s2"),
    ])
    d = diff_tapes(refund_tape, after)
    assert [s.op for s in d.trajectory] == ["same", "removed", "changed"]
    assert d.trajectory[2].changes[0].path == "amount"
    assert d.first_divergence == 0 and d.request_changes[0].path == "system"
    assert d.behaviour_changed
    assert any("no longer calls check_policy" in h for h in d.headline())
    text = d.to_text()
    assert "- check_policy" in text and "Refunded $400." in text
    md = d.to_markdown()
    assert md.startswith("### Agent behaviour changed") and "| model_calls | 4 | 3 | -1 |" in md


def test_diff_of_identical_tapes(refund_tape):
    d = diff_tapes(refund_tape, refund_tape)
    assert not d.behaviour_changed and d.first_divergence is None
    assert "No change" in d.to_text()


def test_tape_file_roundtrip_and_version_check(refund_tape, tmp_path):
    path = refund_tape.save(tmp_path / "x" / "t.json")
    loaded = Tape.load(path)
    assert loaded.events == refund_tape.events and "recorded_at" in loaded.meta
    path.write_text('{"llmtape": 99, "events": []}')
    with pytest.raises(ValueError, match="unsupported"):
        Tape.load(path)
