import json
import os
import signal
import sys

import pytest

from lv import contract, worker
from lv.util import read_json, write_json
from test_worker import (DECK, PRJ, QUESTIONS, REVIEW, _chapter, _claude_writing, _turn,  # noqa: F401
                         lessons)


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
    assert contract.problems("card", card) == []


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


@pytest.mark.skipif(sys.platform == "win32", reason="no SIGTERM to send to oneself on Windows")
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


def test_interrupt_during_given_turn_writes_a_hand_back_card(paired, lessons, tmp_path):
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    out = tmp_path / "card.json"

    def claude(cmd, cwd, log):
        raise KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        worker.run_given(_turn_file(tmp_path), out, claude=claude, out=lambda *_: None)
    card = read_json(out)
    assert card["kind"] == "error" and card["message"] == worker.STOPPED and card["retry_after"]
    assert paired.finished == []


def test_given_turn_with_api_key_passes_the_key_to_claude(paired, lessons, tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-0123")
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    seen = {}
    monkeypatch.setattr(worker, "_run_in_group",
                        lambda cmd, **kw: seen.update(kw) or type("R", (), {"returncode": 0})())
    out = tmp_path / "card.json"
    worker.run_given(_turn_file(tmp_path), out, api_key=True, out=lambda *_: None)
    assert seen["env"]["ANTHROPIC_API_KEY"] == "sk-ant-test-0123"
    assert read_json(out)["kind"] == "error"  # the fake claude wrote no card


def test_given_turn_without_the_key_writes_an_error_card(paired, lessons, tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = tmp_path / "c.json"
    assert worker.run_given(_turn_file(tmp_path), out, api_key=True, out=lambda *_: None) == 1
    card = read_json(out)
    assert card["kind"] == "error" and card["message"] == worker.NEEDS_API_KEY
    assert contract.problems("card", card) == []
    assert paired.heartbeats == []


@pytest.mark.skipif(sys.platform == "win32", reason="no SIGTERM to send to oneself on Windows")
def test_sigterm_before_the_turn_starts_writes_a_hand_back_card(paired, lessons, tmp_path, monkeypatch):
    out = tmp_path / "card.json"
    before = signal.getsignal(signal.SIGTERM)

    def lock(root):
        os.kill(os.getpid(), signal.SIGTERM)
        raise AssertionError("not reached")
    monkeypatch.setattr(worker, "_lock", lock)
    with pytest.raises(KeyboardInterrupt):
        worker.run_given(_turn_file(tmp_path), out, claude=_claude_writing(QUESTIONS), out=lambda *_: None)
    card = read_json(out)
    assert card["kind"] == "error" and card["message"] == worker.STOPPED and card["retry_after"]
    assert contract.problems("card", card) == []
    assert signal.getsignal(signal.SIGTERM) == before


def test_sigterm_handler_is_installed_before_anything_else(lessons, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(worker, "_sigterm_as_interrupt", lambda: calls.append("sigterm"))
    monkeypatch.setattr(worker, "read_json", lambda f: calls.append("read") or {})
    monkeypatch.setattr(worker, "_claude_runner", lambda claude, api_key: calls.append("runner") or claude)
    worker.run_given(_turn_file(tmp_path), tmp_path / "card.json", out=lambda *_: None)
    assert calls[0] == "sigterm"


def test_unusable_lessons_folder_writes_an_error_card(paired, lessons, tmp_path, monkeypatch):
    out = tmp_path / "card.json"

    def lock(root):
        raise PermissionError(13, "Permission denied", str(root))
    monkeypatch.setattr(worker, "_lock", lock)
    assert worker.run_given(_turn_file(tmp_path), out, claude=_claude_writing(QUESTIONS), out=lambda *_: None) == 1
    card = read_json(out)
    assert card["kind"] == "error" and "Permission denied" in card["message"]
    assert contract.problems("card", card) == []


def test_card_is_replaced_whole_or_not_at_all(tmp_path, monkeypatch):
    out = tmp_path / "card.json"
    out.write_text("previous\n", encoding="utf-8")

    def replace(src, dst):
        raise KeyboardInterrupt
    monkeypatch.setattr(worker.os, "replace", replace)
    with pytest.raises(KeyboardInterrupt):
        worker._write_card(out, worker.error_card("new", ""))
    assert out.read_text(encoding="utf-8") == "previous\n"
    assert [f.name for f in tmp_path.iterdir()] == ["card.json"]


def test_interrupt_while_writing_the_result_writes_a_hand_back_card(paired, lessons, tmp_path, monkeypatch):
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    out = tmp_path / "card.json"
    real = os.replace
    seen = []

    def replace(src, dst):
        if str(dst) == str(out) and not seen:  # the first write of the result is interrupted
            seen.append(dst)
            raise KeyboardInterrupt
        return real(src, dst)
    monkeypatch.setattr(worker.os, "replace", replace)
    with pytest.raises(KeyboardInterrupt):
        worker.run_given(_turn_file(tmp_path, kind="approve"), out, claude=_claude_writing(REVIEW, also=_chapter),
                         out=lambda *_: None)
    card = read_json(out)
    assert card["kind"] == "error" and card["message"] == worker.STOPPED and card["retry_after"]


def test_an_old_card_file_is_removed_before_the_turn_runs(paired, lessons, tmp_path):
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    out = tmp_path / "card.json"
    out.write_text("an old card\n", encoding="utf-8")
    seen = []

    def claude(cmd, cwd, log):
        seen.append(out.exists())
        return 1
    assert worker.run_given(_turn_file(tmp_path), out, claude=claude, out=lambda *_: None) == 1
    assert seen == [False] and read_json(out)["kind"] == "error"


@pytest.mark.parametrize("argv", [["worker", "--turn", "t.json"], ["worker", "--card-out", "c.json"],
                                  ["worker", "--turn", "t.json", "--card-out", "c.json", "--once"]])
def test_turn_and_card_out_go_together_and_exclude_other_modes(argv):
    from lv import cli
    with pytest.raises(SystemExit) as e:
        cli.main(argv)
    assert e.value.code == 2
