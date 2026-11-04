import json
import subprocess

from llmtape import Tape
from llmtape.cli import main
from llmtape.report import render, transcript


def write(path, final_text, tools=("lookup",)):
    events = [{"kind": "model", "request": {"model": "claude-haiku-5-5", "system": "sys",
                                            "messages": [{"role": "user", "content": "hi"}]},
               "response": {"model": "claude-haiku-5-5",
                            "content": [{"type": "tool_use", "id": "t", "name": n, "input": {}} for n in tools],
                            "usage": {"input_tokens": 10, "output_tokens": 5}}},
              {"kind": "model", "request": {"model": "claude-haiku-5-5", "system": "sys", "messages": [
                  {"role": "user", "content": "hi"},
                  {"role": "assistant", "content": []},
                  {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t", "content": "ok"}]}]},
               "response": {"model": "claude-haiku-5-5", "content": [{"type": "text", "text": final_text}],
                            "usage": {"input_tokens": 10, "output_tokens": 5}}}]
    Tape(events=events).save(path)
    return path


def test_transcript_shows_each_message_once(tmp_path):
    t = Tape.load(write(tmp_path / "a.json", "bye"))
    roles = [i["role"] for i in transcript(t)]
    assert roles == ["system", "user", "assistant", "user", "assistant"]


def test_report_cannot_be_broken_out_of_by_model_output(tmp_path):
    evil = "<!--<script></script><script>alert(1)</script>"
    html = render(tapes=[Tape.load(write(tmp_path / "a.json", evil))])
    data = html.split('id="tape-data" type="application/json">')[1].split("</script>")[0]
    assert "<" not in data
    assert json.loads(data)["tapes"][0]["transcript"][-1]["blocks"][0]["text"] == evil


def test_cli_diff_exit_code_and_formats(tmp_path, capsys):
    a = write(tmp_path / "a.json", "same")
    b = write(tmp_path / "b.json", "different", tools=("lookup", "refund"))
    assert main(["diff", str(a), str(a), "--exit-code"]) == 0
    assert main(["diff", str(a), str(b), "--exit-code", "--html", str(tmp_path / "d.html")]) == 1
    assert "now calls refund" in capsys.readouterr().out
    assert (tmp_path / "d.html").exists()
    main(["diff", str(a), str(b), "--format", "json"])
    assert json.loads(capsys.readouterr().out)["behaviour_changed"] is True


def test_cli_show_stats_report(tmp_path, capsys):
    write(tmp_path / "tapes" / "a.json", "hello there")
    (tmp_path / "tapes" / "notes.json").write_text("{}")       # not tapes: skipped in folders
    (tmp_path / "tapes" / "list.json").write_text("[1, 2]")
    assert main(["show", str(tmp_path / "tapes")]) == 0
    assert "hello there" in capsys.readouterr().out
    assert main(["stats", str(tmp_path / "tapes")]) == 0
    assert "total" in capsys.readouterr().out
    assert main(["report", str(tmp_path / "tapes"), "-o", str(tmp_path / "r.html")]) == 0


def test_cli_diff_against_git(tmp_path, capsys):
    run = lambda *a: subprocess.run(a, cwd=tmp_path, check=True, capture_output=True)
    run("git", "init", "-q")
    path = write(tmp_path / "t.json", "old reply")
    run("git", "add", ".")
    run("git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "commit", "-qm", "x")
    write(path, "new reply")
    assert main(["diff", str(path), "--git", "HEAD", "--exit-code"]) == 1
    assert "final reply changed" in capsys.readouterr().out
