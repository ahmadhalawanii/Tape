"""Behaviour tests for the refund desk. They replay from tapes/, so CI needs no API key."""

from .agent import RefundDesk


def test_refunds_a_recent_order(client, tape):
    reply = RefundDesk(client).handle("Hi, my trail shoes from order N1001 fell apart. Refund please?")

    tape.assert_order(["lookup_order", "check_policy", "issue_refund"])
    tape.assert_called("issue_refund", order_id="N1001", amount=129.0)
    tape.assert_cost_below(0.01)
    assert "RF-N1001" in reply


def test_declines_an_order_outside_the_window(client, tape):
    reply = RefundDesk(client).handle("I'd like a refund for my tent, order N1002.")

    tape.assert_called("check_policy", order_id="N1002")
    tape.assert_not_called("issue_refund")
    tape.assert_text_contains("store credit")
    assert "can't be refunded" in reply


def test_asks_for_the_order_number(client, tape):
    RefundDesk(client).handle("My jacket zip broke, can I get my money back?")

    tape.assert_max_calls(1)
    tape.assert_not_called("lookup_order")
    tape.assert_text_contains("order number")
