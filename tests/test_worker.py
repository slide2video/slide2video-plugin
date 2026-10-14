import datetime as dt
import hashlib
import json
import os

import pytest

from lv import worker
from lv.util import read_json, write_json, write_text

DECK = b"pretend pptx bytes"
LES = "les_0123456789abcdefghijkl"


def _turn(kind="start", tid="trn_0123456789abcdefghijkl", path="in/water-cycle.pptx", **extra):
    return {"contract": 1, "lesson": {"id": LES, "title": "Unit 3: Water/Cycle"},
            "turn": {"id": tid, "seq": 1, "kind": kind, "lease_seconds": 1800},
            "files": [{"id": "fil_0123456789abcdefghijkl", "name": "water-cycle.pptx", "kind": "deck",
                       "sha256": hashlib.sha256(DECK).hexdigest(), "size": len(DECK), "path": path}], **extra}


@pytest.fixture
def lessons(tmp_path, monkeypatch):
    root = tmp_path / "Lesson Videos"
    monkeypatch.setenv("LV_LESSONS_DIR", str(root))
    return root


def _claude_writing(card, also=None, code=0, log="ok\n"):
    calls = []

    def fake(cmd, cwd, logfile):
        calls.append((cmd, cwd))
        logfile.write_text(log, encoding="utf-8")
        if also:
            also(cwd)
        if card is not None:
            write_json(cwd / "site" / "card.json", card)
        return code
    fake.calls = calls
    return fake


QUESTIONS = {"contract": 1, "kind": "questions", "message": "Questions",
             "questions": [{"id": "grade", "text": "Grade?", "options": [{"label": "6–8"}]}]}


def test_no_turn_is_quiet(paired, lessons):
    assert worker.run_once(claude=_claude_writing(QUESTIONS)) == 0
    assert paired.finished == []


def test_start_turn_downloads_runs_claude_and_sends_card(paired, lessons):
    paired.turns.append(_turn())
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    fake = _claude_writing(QUESTIONS)
    assert worker.run_once(claude=fake) == 0
    folder = worker.lesson_dir({"id": LES, "title": "x"})
    assert folder.name == f"Unit 3- Water-Cycle ({LES})"
    assert (folder / "in" / "water-cycle.pptx").read_bytes() == DECK
    assert read_json(folder / "site" / "turn.json")["turn"]["kind"] == "start"
    assert (folder / "site" / "lv.txt").read_text(encoding="utf-8").strip() == worker.lv_command()
    assert fake.calls[0][1] == folder
    assert paired.finished == [("trn_0123456789abcdefghijkl", QUESTIONS)]


def test_existing_deck_with_same_hash_is_not_downloaded_again(paired, lessons):
    folder = worker.lesson_dir({"id": LES, "title": "Unit 3: Water/Cycle"})
    write_text(folder / "in" / "keep.txt", "")
    (folder / "in" / "water-cycle.pptx").write_bytes(DECK)
    paired.turns.append(_turn())  # paired.files is empty: a download would 404
    assert worker.run_once(claude=_claude_writing(QUESTIONS)) == 0
    assert paired.finished[0][1]["kind"] == "questions"


def test_damaged_download_becomes_error(paired, lessons):
    paired.turns.append(_turn())
    paired.files["fil_0123456789abcdefghijkl"] = b"something else"
    assert worker.run_once(claude=_claude_writing(QUESTIONS)) == 1
    assert paired.finished[0][1]["kind"] == "error" and "damaged" in paired.finished[0][1]["message"]


@pytest.mark.parametrize("path", ["in/../x.pptx", "/etc/passwd", "in/.hidden"])
def test_bad_turn_paths_are_refused_before_writing(paired, lessons, path):
    paired.turns.append(_turn(path=path))
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    fake = _claude_writing(QUESTIONS)
    assert worker.run_once(claude=fake) == 1
    assert fake.calls == [] and paired.finished[0][1]["kind"] == "error"
    assert not (lessons.parent / "x.pptx").exists()


def _chapter(folder):
    ch = folder / "lesson-videos" / "_work" / "ch1"
    write_json(ch / "script.json", {"chapter": "1", "title": "Water", "scenes": [
        {"id": "hook", "say": "Where does rain come from? Let us find out today together."},
        {"id": "condensation", "say": "When warm, moist air rises it cools."}]})
    write_text(ch / "build" / "timing.js", "window.TIMING = " + json.dumps(
        {"duration": 20.0, "scenes": [{"id": "hook", "start": 0, "dur": 8.0}, {"id": "condensation", "start": 8.0, "dur": 12.0}]}) + ";\n")
    out = folder / "lesson-videos"
    (out / "Chapter 1 - Water.mp4").write_bytes(b"mp4")
    (out / "Chapter 1 - Water.vtt").write_bytes(b"WEBVTT")
    (ch / "build" / "final.jpg").write_bytes(b"jpg")


REVIEW = {"contract": 1, "kind": "review", "message": "Chapter 1 is ready.", "chapter": 1,
          "video": "lesson-videos/Chapter 1 - Water.mp4", "captions": "lesson-videos/Chapter 1 - Water.vtt",
          "stills": "lesson-videos/_work/ch1/build/final.jpg"}


def test_review_card_uploads_video_captions_stills_and_timing(paired, lessons):
    paired.turns += [_turn("approve"), _turn("feedback", tid="trn_1123456789abcdefghijkl")]
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    assert worker.run_once(claude=_claude_writing(REVIEW, also=_chapter)) == 0
    sent = paired.finished[0][1]
    assert sent["version"] == 1
    assert sent["video"] == "out/ch1/v1/Chapter 1 - Water.mp4"
    assert paired.uploads["out/ch1/v1/Chapter 1 - Water.mp4"] == ("video/mp4", b"mp4")
    assert paired.uploads["out/ch1/v1/Chapter 1 - Water.vtt"][0] == "text/vtt"
    timing = json.loads(paired.uploads["out/ch1/v1/timing.json"][1])
    assert timing["scenes"][1] == {"id": "condensation", "start": 8.0, "dur": 12.0, "label": "Condensation",
                                   "first_words": "When warm, moist air rises it cools."}
    assert worker.run_once(claude=_claude_writing(REVIEW, also=_chapter)) == 0
    assert paired.finished[1][1]["video"] == "out/ch1/v2/Chapter 1 - Water.mp4"


def test_card_path_outside_the_lesson_is_an_error(paired, lessons, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("private", encoding="utf-8")
    paired.turns.append(_turn("approve"))
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    card = {**REVIEW, "video": "../../secret.txt"}
    assert worker.run_once(claude=_claude_writing(card)) == 1
    assert paired.uploads == {} and paired.finished[0][1]["kind"] == "error"


def test_claude_failure_sends_redacted_log(paired, lessons):
    paired.turns.append(_turn())
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    log = "starting\nkey was sk_0123456789abcdef0123456789abcdef\ncrashed\n"
    assert worker.run_once(claude=_claude_writing(None, code=1, log=log)) == 1
    card = paired.finished[0][1]
    assert card["kind"] == "error" and "sk_0123" not in card["log_tail"] and "crashed" in card["log_tail"]


def test_invalid_card_is_an_error(paired, lessons):
    paired.turns.append(_turn())
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    assert worker.run_once(claude=_claude_writing({"contract": 1, "kind": "plan", "message": "x"})) == 1
    assert "couldn't be read" in paired.finished[0][1]["message"]


def test_usage_limit_sets_retry_after():
    now = dt.datetime(2026, 10, 14, 10, 0, tzinfo=dt.timezone(dt.timedelta(hours=-7)))
    card = worker.error_card("Claude stopped.", "5-hour limit reached ∙ resets 3pm\n", now=now, detect_limit=True)
    assert card["retry_after"] == "2026-10-14T15:00:00-07:00" and "usage limit" in card["message"]
    later = now.replace(hour=16)
    assert worker.error_card("x", "5-hour limit reached ∙ resets 3pm", now=later, detect_limit=True)["retry_after"].startswith("2026-10-15T15:00")
    assert worker.error_card("x", "some other failure", now=now, detect_limit=True)["retry_after"] is None


def test_delete_turn_removes_the_folder_without_claude(paired, lessons):
    folder = worker.lesson_dir({"id": LES, "title": "Unit 3: Water/Cycle"})
    write_text(folder / "in" / "x.txt", "x")
    paired.turns.append(_turn("delete", delete=True))
    fake = _claude_writing(QUESTIONS)
    assert worker.run_once(claude=fake) == 0
    assert not folder.exists() and fake.calls == []
    assert paired.finished[0][1]["kind"] == "done"


def test_live_lock_makes_a_second_run_exit(paired, lessons):
    lessons.mkdir(parents=True)
    (lessons / ".worker.lock").write_text(str(os.getpid()), encoding="utf-8")
    paired.turns.append(_turn())
    assert worker.run_once(claude=_claude_writing(QUESTIONS)) == 0
    assert paired.finished == [] and len(paired.turns) == 1


def test_stale_lock_is_taken_over(paired, lessons):
    lessons.mkdir(parents=True)
    (lessons / ".worker.lock").write_text("999999999", encoding="utf-8")
    paired.turns.append(_turn())
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    assert worker.run_once(claude=_claude_writing(QUESTIONS)) == 0
    assert len(paired.finished) == 1 and not (lessons / ".worker.lock").exists()


def test_heartbeat_sends_the_progress_line(paired, lessons, monkeypatch):
    monkeypatch.setattr(worker, "HEARTBEAT", 0.05)
    paired.turns.append(_turn())
    paired.files["fil_0123456789abcdefghijkl"] = DECK

    def slow(cwd):
        import time
        write_text(cwd / "site" / "progress.txt", "Reading the deck\nNarrating 3 of 12 scenes\n")
        time.sleep(0.3)
    assert worker.run_once(claude=_claude_writing(QUESTIONS, also=slow)) == 0
    assert ("trn_0123456789abcdefghijkl", "Narrating 3 of 12 scenes") in paired.heartbeats


def test_claude_command_limits_tools(monkeypatch):
    monkeypatch.setattr(worker.shutil, "which", lambda n: f"/usr/local/bin/{n}")
    cmd = worker.claude_command('"/usr/bin/uv" run "/p/lesson-videos.py"')
    assert cmd[1:3] == ["-p", worker.PROMPT]
    assert 'Bash("/usr/bin/uv" run "/p/lesson-videos.py":*)' in cmd
    i = cmd.index("--disallowedTools")
    assert cmd[i + 1:] == ["WebFetch", "WebSearch"]
    assert not any(t.startswith("Bash") and t != 'Bash("/usr/bin/uv" run "/p/lesson-videos.py":*)' for t in cmd)
    for bare in ("Read", "Write", "Edit"):
        assert bare not in cmd
    assert {"Read(./**)", "Edit(./**)", "Write(./**)", "Glob", "Grep"} <= set(cmd)
    plugin = str(worker.config.PLUGIN_ROOT).lstrip("/")
    assert f"Read(//{plugin}/**)" in cmd


def test_site_mode_env_is_set_for_claude(monkeypatch, tmp_path):
    seen = {}

    def fake_run(cmd, **kw):
        seen.update(kw)
        return type("R", (), {"returncode": 0})()
    monkeypatch.setattr(worker.subprocess, "run", fake_run)
    worker.run_claude(["claude"], tmp_path, tmp_path / "log")
    assert seen["env"]["LV_SITE_MODE"] == "1"


def test_missing_deck_download_still_finishes_with_error(paired, lessons):
    paired.turns.append(_turn())  # no file on the site, no local copy
    assert worker.run_once(claude=_claude_writing(QUESTIONS)) == 1
    assert paired.finished[0][1]["kind"] == "error"


def test_upload_failure_still_finishes_with_error(paired, lessons):
    paired.fail_uploads = True
    paired.turns.append(_turn("approve"))
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    assert worker.run_once(claude=_claude_writing(REVIEW, also=_chapter)) == 1
    assert paired.finished[0][1]["kind"] == "error"


def test_invalid_card_error_is_valid_and_short(paired, lessons):
    from lv import contract
    paired.turns.append(_turn())
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    card = {"contract": 1, "kind": "plan", "message": "x", "markdown": "m" * 20001}
    assert worker.run_once(claude=_claude_writing(card)) == 1
    sent = paired.finished[0][1]
    assert contract.problems("card", sent) == [] and "problems at" in sent["message"]


def test_other_service_limit_is_not_a_claude_usage_limit(paired, lessons):
    paired.turns.append(_turn())
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    bad = {"contract": 1, "kind": "plan", "message": "x"}
    assert worker.run_once(claude=_claude_writing(bad, log="ElevenLabs character limit reached\n")) == 1
    sent = paired.finished[0][1]
    assert sent["retry_after"] is None and "usage limit" not in sent["message"]


def test_claude_stopped_with_limit_keeps_original_message():
    card = worker.error_card("Claude stopped.", "5-hour limit reached ∙ resets 3pm", detect_limit=True)
    assert "usage limit" in card["message"] and card["message"].endswith("Claude stopped.")


def test_card_naming_the_log_is_an_error(paired, lessons):
    paired.turns.append(_turn("approve"))
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    card = {**REVIEW, "video": "site/claude.log"}
    assert worker.run_once(claude=_claude_writing(card, also=_chapter)) == 1
    assert paired.uploads == {} and paired.finished[0][1]["kind"] == "error"


def test_outgoing_card_is_redacted(paired, lessons):
    paired.turns.append(_turn())
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    card = {**QUESTIONS, "message": "key sk_0123456789abcdef0123456789abcdef here"}
    assert worker.run_once(claude=_claude_writing(card)) == 0
    assert "sk_0123456789abcdef" not in paired.finished[0][1]["message"]
