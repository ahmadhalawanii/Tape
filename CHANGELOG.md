# Changelog

## 0.1.0 (2026-11-04)

First release.

- **Record and replay** Anthropic `messages.create` calls (sync, async and beta) to a JSON tape, matched in order. Replay returns the SDK's own response types and never calls the API.
- **Divergence errors** that name the changed request field and the model call where the run stopped matching. They can't be swallowed by an agent's `except Exception`.
- **Modes:** `auto`, `record`, `replay`, and `update`, which replays the matching prefix and calls the API only from the first difference.
- **`@llmtape.tool`** records tool results and errors, so replays need no database or third-party API.
- **Assertions** on a run: `assert_called`, `assert_not_called`, `assert_called_before`, `assert_order`, `assert_max_calls`, `assert_cost_below`, `assert_text_contains`.
- **Cost and token totals** per run from the response usage and a model price table.
- **`tape` CLI:** `show`, `diff` (text, markdown, JSON or HTML, and `--git REV`), `report` and `stats`.
- **pytest plugin** with a `tape` fixture and `--tape-mode` / `--tape-dir` options.
- **Redaction** of Anthropic, OpenAI, AWS, GitHub, Stripe and Slack keys before anything is written.
- **CI workflow** that replays tests and posts a behaviour diff for every changed tape.

Known limits: Anthropic SDK only; streaming isn't recorded yet; concurrent calls must happen in a stable order.
