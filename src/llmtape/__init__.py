"""Tape: record, replay and diff LLM agent runs.

    import llmtape

    with llmtape.use("tapes/refund.json") as run:
        agent.handle("I want a refund for order A1")
    run.assert_called_before("check_policy", "issue_refund")
"""

from .diff import TapeDiff, diff_tapes
from .recorder import Cassette, RecordedToolError, StreamingNotSupported, TapeDivergence, use
from .tape import Tape, ToolCall
from .tools import tool

__all__ = [
    "Cassette", "RecordedToolError", "StreamingNotSupported", "Tape", "TapeDiff",
    "TapeDivergence", "ToolCall", "diff_tapes", "tool", "use",
]
__version__ = "0.1.0"
