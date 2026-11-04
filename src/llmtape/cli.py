"""`tape` command line.

    tape show tapes/x.json                 the conversation, in the terminal
    tape diff before.json after.json       what changed in the agent's behaviour
    tape diff tapes/x.json --git HEAD      working copy against the committed tape
    tape report tapes/ -o report.html      HTML page for every tape under a folder
    tape stats tapes/                      calls, tokens and cost per tape
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from . import report
from .diff import diff_tapes
from .tape import Tape


def _tapes(paths: list[str]) -> list[Tape]:
    out = []
    for p in map(Path, paths):
        files = sorted(p.rglob("*.json")) if p.is_dir() else [p]
        for f in files:
            try:
                out.append(Tape.load(f))
            except (ValueError, KeyError, AttributeError, TypeError):
                if not p.is_dir():
                    raise
    return out


def _from_git(rev: str, path: str) -> Tape:
    if rev.startswith("-"):
        raise SystemExit(f"tape: {rev!r} is not a git revision")
    file = Path(path).resolve()
    root = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=file.parent,
                               capture_output=True, text=True, check=True).stdout.strip())
    rel = file.relative_to(root).as_posix()
    shown = subprocess.run(["git", "show", f"{rev}:{rel}"], cwd=root, capture_output=True, text=True)
    if shown.returncode != 0:
        raise SystemExit(f"tape: {rel} does not exist at {rev}")
    return Tape.from_dict(json.loads(shown.stdout), Path(f"{rev}:{rel}"))


def cmd_show(args) -> int:
    for t in _tapes(args.paths):
        print(f"== {t.name}")
        for item in report.transcript(t):
            who = "agent" if item["role"] == "assistant" else item["role"]
            meta = item.get("meta")
            if meta:
                u = meta["usage"]
                who += f"  #{item['call']} {meta['model']} {u.get('input_tokens', 0)}->{u.get('output_tokens', 0)} tok"
            print(f"\n[{who}]")
            for b in item["blocks"]:
                if b["type"] == "tool_use":
                    print(f"  -> {b['name']}({json.dumps(b['input'], ensure_ascii=False)})")
                elif b["type"] == "tool_result":
                    print(f"  <- {b['text'][:300]}")
                else:
                    text = b["text"] if item["role"] != "system" else b["text"][:400]
                    print("  " + text.replace("\n", "\n  "))
        print()
    return 0


def cmd_diff(args) -> int:
    if args.git:
        before, after = _from_git(args.git, args.before), Tape.load(args.before)
    else:
        if not args.after:
            raise SystemExit("tape diff: give two tapes, or one tape and --git REV")
        before, after = Tape.load(args.before), Tape.load(args.after)
    d = diff_tapes(before, after)
    if args.format == "json":
        print(json.dumps(d.to_dict(), indent=2, ensure_ascii=False))
    elif args.format == "markdown":
        print(d.to_markdown())
    else:
        print(d.to_text(color=sys.stdout.isatty()))
    if args.html:
        Path(args.html).write_text(report.render(diff=d, title="Tape diff"), encoding="utf-8")
        print(f"\nwrote {args.html}", file=sys.stderr)
    return 1 if args.exit_code and d.behaviour_changed else 0


def cmd_report(args) -> int:
    tapes = _tapes(args.paths)
    Path(args.output).write_text(report.render(tapes=tapes, title="Tape report"), encoding="utf-8")
    print(f"wrote {args.output} ({len(tapes)} tapes)")
    return 0


def cmd_stats(args) -> int:
    rows = [(t.name, t.summary()) for t in _tapes(args.paths)]
    width = max([len(r[0]) for r in rows] + [4])
    print(f"{'tape':{width}}  {'calls':>5}  {'tools':>5}  {'in tok':>8}  {'out tok':>8}  {'cost':>10}")
    total = 0.0
    for name, s in rows:
        cost = s["cost_usd"]
        total += cost or 0
        shown = "?" if cost is None else f"${cost:.5f}"
        print(f"{name:{width}}  {s['model_calls']:>5}  {s['tool_calls']:>5}  "
              f"{s['input_tokens']:>8,}  {s['output_tokens']:>8,}  {shown:>10}")
    print(f"{'':{width}}  {'':>5}  {'':>5}  {'':>8}  {'total':>8}  ${total:>9.5f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tape", description="Record, replay and diff LLM agent runs.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("show", help="print the conversation in a tape")
    p.add_argument("paths", nargs="+")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("diff", help="compare agent behaviour between two tapes")
    p.add_argument("before")
    p.add_argument("after", nargs="?")
    p.add_argument("--git", metavar="REV", help="compare BEFORE as committed at REV with the working copy")
    p.add_argument("--format", choices=("text", "markdown", "json"), default="text")
    p.add_argument("--html", metavar="FILE", help="also write an HTML diff page")
    p.add_argument("--exit-code", action="store_true", help="exit 1 when behaviour changed")
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("report", help="write an HTML page for tapes")
    p.add_argument("paths", nargs="+")
    p.add_argument("-o", "--output", default="tape-report.html")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("stats", help="calls, tokens and cost per tape")
    p.add_argument("paths", nargs="+")
    p.set_defaults(func=cmd_stats)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
