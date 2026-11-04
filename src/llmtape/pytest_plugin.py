"""pytest integration: a `tape` fixture with one tape file per test.

    def test_refund(tape):
        agent.handle("refund order A1")
        tape.assert_called("lookup_order", order_id="A1")

Tapes live next to the test file: tests/tapes/<module>/<test name>.json.
Pick the mode with --tape-mode or LLMTAPE_MODE. Use `replay` in CI, so a missing or
stale tape fails the build instead of quietly calling the API.
Options per test: @pytest.mark.tape(name="...", scrub=[(regex, replacement)]).
"""

from __future__ import annotations

import os
import re

import pytest

from .recorder import ENV_MODE, MODES, Cassette


def pytest_addoption(parser):
    group = parser.getgroup("llmtape")
    group.addoption("--tape-mode", choices=MODES, default=None,
                    help=f"record | replay | auto | update (default: ${ENV_MODE} or auto)")
    group.addoption("--tape-dir", default=None, help="directory for tapes (default: tapes/ beside each test file)")


def pytest_configure(config):
    config.addinivalue_line("markers", "tape(name=None, scrub=None): options for the tape fixture")


def _file_name(nodename: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", nodename).strip("_") + ".json"


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    report = yield
    if report.when == "call":
        item._llmtape_failed = report.failed
    return report


@pytest.fixture
def tape(request):
    marker = request.node.get_closest_marker("tape")
    options = dict(marker.kwargs) if marker else {}
    mode = request.config.getoption("--tape-mode") or os.environ.get(ENV_MODE) or "auto"
    base = request.config.getoption("--tape-dir")
    if base:
        # Keep the test's package path, so tests/a/test_x.py and tests/b/test_x.py don't share tapes.
        try:
            module = request.path.relative_to(request.config.rootpath).with_suffix("")
        except ValueError:
            module = request.path.with_suffix("").relative_to(request.path.anchor)
        folder = request.config.rootpath / base / module
    else:
        folder = request.path.parent / "tapes" / request.path.stem
    path = folder / _file_name(options.get("name") or request.node.name)
    cassette = Cassette(path, mode, scrub=options.get("scrub") or (),
                        meta={"test": request.node.nodeid})
    with cassette:
        yield cassette
        if getattr(request.node, "_llmtape_failed", False):
            cassette.strict = False    # the test's own failure explains a short run
