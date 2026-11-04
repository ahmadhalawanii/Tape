"""Cost of a model call, from the usage block the API returns.

USD per million tokens: input, output, cache read, cache write (5 minute TTL).
Check against https://platform.claude.com/docs/en/about-claude/pricing when it changes.
Add or override entries with `llmtape.pricing.PRICES[model] = (...)`.
"""

from __future__ import annotations

PRICES: dict[str, tuple[float, float, float, float]] = {
    "claude-fable-5-1": (10.00, 50.00, 0.25, 12.50),
    "claude-opus-5-5": (4.00, 20.00, 0.20, 5.00),
    "claude-opus-5": (5.00, 25.00, 0.50, 6.25),
    "claude-opus-4-8": (5.00, 25.00, 0.50, 6.25),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20, 2.50),
    "claude-sonnet-5": (2.00, 10.00, 0.20, 2.50),
    "claude-sonnet-4-6": (3.00, 15.00, 0.30, 3.75),
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),
    "claude-haiku-4-5": (1.00, 5.00, 0.10, 1.25),
}


def price_for(model: str) -> tuple[float, float, float, float] | None:
    if model in PRICES:
        return PRICES[model]
    # Dated snapshots such as claude-haiku-4-5-20251001: longest matching prefix wins.
    matches = [m for m in PRICES if model.startswith(m)]
    return PRICES[max(matches, key=len)] if matches else None


def cost_usd(model: str, usage: dict | None) -> float | None:
    """None when the model is unknown, so a missing price never reads as free."""
    prices = price_for(model or "")
    if prices is None or not usage:
        return None
    p_in, p_out, p_read, p_write = prices
    return (
        (usage.get("input_tokens") or 0) * p_in
        + (usage.get("output_tokens") or 0) * p_out
        + (usage.get("cache_read_input_tokens") or 0) * p_read
        + (usage.get("cache_creation_input_tokens") or 0) * p_write
    ) / 1e6
