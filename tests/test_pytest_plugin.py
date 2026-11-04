def test_fixture_records_then_replays_in_ci_mode(pytester):
    pytester.makeconftest("""
import pytest
from llmtape.testing import scripted_client

@pytest.fixture
def client():
    return scripted_client(lambda r: [{"type": "text", "text": "hi"}])
""")
    pytester.makepyfile(test_agent="""
def test_greets(client, tape):
    client.messages.create(model="claude-haiku-5-5", max_tokens=5,
                           messages=[{"role": "user", "content": "hello"}])
    tape.assert_text_contains("hi").assert_max_calls(1)
""")
    pytester.runpytest().assert_outcomes(passed=1)
    assert (pytester.path / "tapes" / "test_agent" / "test_greets.json").exists()
    pytester.runpytest("--tape-mode=replay").assert_outcomes(passed=1)


def test_missing_tape_fails_in_replay_mode(pytester):
    pytester.makepyfile(test_x="""
def test_new(tape):
    pass
""")
    result = pytester.runpytest("--tape-mode=replay")
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*No tape at*"])


def test_a_failing_test_is_not_reported_twice(pytester, monkeypatch):
    pytester.makeconftest("""
import pytest
from llmtape.testing import scripted_client

@pytest.fixture
def client():
    return scripted_client(lambda r: [{"type": "text", "text": "hi"}])
""")
    pytester.makepyfile(test_agent="""
import os
def test_two_calls(client, tape):
    ask = lambda t: client.messages.create(model="m", max_tokens=5, messages=[{"role": "user", "content": t}])
    ask("one")
    if os.environ.get("BREAK"):
        raise KeyError("agent bug")
    ask("two")
""")
    pytester.runpytest().assert_outcomes(passed=1)
    monkeypatch.setenv("BREAK", "1")
    result = pytester.runpytest("--tape-mode=replay")
    result.assert_outcomes(failed=1)        # the KeyError, and no teardown error on top


def test_tape_dir_keeps_the_package_path(pytester):
    pytester.mkpydir("a").joinpath("test_same.py").write_text("def test_t(tape): pass")
    pytester.mkpydir("b").joinpath("test_same.py").write_text("def test_t(tape): pass")
    pytester.runpytest("--tape-dir=tapes", "--import-mode=importlib").assert_outcomes(passed=2)
    assert (pytester.path / "tapes" / "a" / "test_same" / "test_t.json").exists()
    assert (pytester.path / "tapes" / "b" / "test_same" / "test_t.json").exists()
