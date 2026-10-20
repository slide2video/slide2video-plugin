import json
import os
import signal

import pytest

from lv import worker
from lv.util import read_json, write_json
from test_worker import (DECK, PRJ, QUESTIONS, REVIEW, _chapter, _claude_writing, _turn,  # noqa: F401
                         lessons)

pytestmark = pytest.mark.skipif(not hasattr(signal, "SIGTERM"), reason="no SIGTERM")


def _turn_file(tmp_path, **kw):
    f = tmp_path / "turn.json"
    write_json(f, _turn(**kw))
    return f


def test_given_turn_runs_and_writes_the_card_without_finishing(paired, lessons, tmp_path):
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    out = tmp_path / "card.json"
    assert worker.run_given(_turn_file(tmp_path, kind="approve"), out,
                            claude=_claude_writing(REVIEW, also=_chapter), out=lambda *_: None) == 0
    assert paired.finished == [] and paired.next_queries == []
    assert paired.uploads["out/ch1/v1/Chapter 1 - Water.mp4"] == ("video/mp4", b"mp4")
    card = read_json(out)
    assert card["kind"] == "review" and card["video"] == "out/ch1/v1/Chapter 1 - Water.mp4"


def test_given_turn_error_card_returns_one(paired, lessons, tmp_path):
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    out = tmp_path / "card.json"
    assert worker.run_given(_turn_file(tmp_path), out, claude=_claude_writing(None, code=1),
                            out=lambda *_: None) == 1
    assert read_json(out)["kind"] == "error" and paired.finished == []


def test_invalid_given_turn_writes_an_error_card(paired, lessons, tmp_path):
    f = tmp_path / "turn.json"
    f.write_text(json.dumps({"contract": 2}), encoding="utf-8")
    out = tmp_path / "card.json"
    assert worker.run_given(f, out, claude=_claude_writing(QUESTIONS), out=lambda *_: None) == 1
    assert read_json(out)["kind"] == "error"
    assert paired.finished == [] and paired.next_queries == [] and paired.heartbeats == []


def test_sigterm_during_given_turn_writes_a_hand_back_card(paired, lessons, tmp_path):
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    out = tmp_path / "card.json"
    before = signal.getsignal(signal.SIGTERM)

    def claude(cmd, cwd, log):
        os.kill(os.getpid(), signal.SIGTERM)
        raise AssertionError("not reached")
    with pytest.raises(KeyboardInterrupt):
        worker.run_given(_turn_file(tmp_path), out, claude=claude, out=lambda *_: None)
    card = read_json(out)
    assert card["kind"] == "error" and card["message"] == worker.STOPPED and card["retry_after"]
    assert paired.finished == []
    assert signal.getsignal(signal.SIGTERM) == before


def test_given_turn_with_api_key_passes_the_key_to_claude(paired, lessons, tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-0123")
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    seen = {}
    monkeypatch.setattr(worker.subprocess, "run",
                        lambda cmd, **kw: seen.update(kw) or type("R", (), {"returncode": 0})())
    out = tmp_path / "card.json"
    worker.run_given(_turn_file(tmp_path), out, api_key=True, out=lambda *_: None)
    assert seen["env"]["ANTHROPIC_API_KEY"] == "sk-ant-test-0123"
    assert read_json(out)["kind"] == "error"  # the fake claude wrote no card


def test_given_turn_needs_the_key_up_front(lessons, tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(worker.UserError):
        worker.run_given(_turn_file(tmp_path), tmp_path / "c.json", api_key=True)


@pytest.mark.parametrize("argv", [["worker", "--turn", "t.json"], ["worker", "--card-out", "c.json"],
                                  ["worker", "--turn", "t.json", "--card-out", "c.json", "--once"]])
def test_turn_and_card_out_go_together_and_exclude_other_modes(argv):
    from lv import cli
    with pytest.raises(SystemExit) as e:
        cli.main(argv)
    assert e.value.code == 2
