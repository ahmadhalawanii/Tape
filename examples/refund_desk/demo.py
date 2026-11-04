"""Record the refund desk under both prompts and write the diff page.

    python -m examples.refund_desk.demo            # scripted stand-in model, free
    ANTHROPIC_API_KEY=... python -m examples.refund_desk.demo --live   # real Claude

Writes docs/demo/before.json, docs/demo/after.json and docs/index.html.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import llmtape
from llmtape import report
from llmtape.testing import scripted_client

from .agent import SYSTEM_V1, SYSTEM_V2, RefundDesk
from .scripted_model import respond

DOCS = Path(__file__).resolve().parents[2] / "docs"
ENQUIRY = "I'd like a refund for my tent, order N1002."


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="record against the real API")
    args = parser.parse_args()
    if args.live:
        import anthropic
        client, source = anthropic.Anthropic(), "Claude API"
    else:
        client, source = scripted_client(respond), "scripted stand-in model (examples/refund_desk/scripted_model.py)"

    tapes = []
    for label, system in (("before", SYSTEM_V1), ("after", SYSTEM_V2)):
        path = DOCS / "demo" / f"{label}.json"
        with llmtape.use(path, "record", meta={"prompt": label, "recorded_against": source}) as run:
            RefundDesk(client, system=system).handle(ENQUIRY)
        tapes.append(run)

    diff = llmtape.diff_tapes(*tapes)
    (DOCS / "index.html").write_text(report.render(diff=diff, title="Tape: a prompt edit that refunds $489"),
                                     encoding="utf-8")
    print(diff.to_text(color=True))
    print(f"\nwrote {DOCS / 'index.html'}")


if __name__ == "__main__":
    main()
