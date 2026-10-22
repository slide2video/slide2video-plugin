import json
import os
import time

from lv import cli, contract, estimate, keys, status
from lv.util import write_json, write_text


def test_plan_estimate():
    assert estimate.plan_chars(5, 5) == 22500
    assert estimate.gemini_usd(2, True) == 0.88
    r = estimate.report(22500, 2, True)
    assert "22,500" in r and "$0.88" in r and "20%" in r
    free = estimate.report(22500, 0, False, paid_voice=False)
    assert "free voice" in free and "$0.00" in free


def test_chars_in_scripts(tmp_path):
    write_json(tmp_path / "ch1/script.json", {"scenes": [{"id": "a", "say": "Hello."}, {"id": "b"}]})
    write_json(tmp_path / "ch2/script.json", {"scenes": [{"id": "a", "say": "Hi"}]})
    assert estimate.chars_in_scripts(tmp_path) == 8


def test_status_stages(tmp_path):
    work = tmp_path / "slide2video" / "_work"
    ch = work / "ch2"
    write_json(ch / "script.json", {"out": "Chapter 2 - X.mp4", "scenes": []})
    assert status.stage(ch) == "script written: run narrate"
    time.sleep(0.01)
    write_text(ch / "build/timing.js", "window.TIMING = {};")
    assert status.stage(ch) == "narrated: write scenes.js"
    write_text(ch / "scenes.js", "")
    assert status.stage(ch) == "scenes written: check stills, then render"
    time.sleep(0.01)
    write_text(tmp_path / "slide2video/Chapter 2 - X.mp4", "x")
    assert status.stage(ch) == "done: Chapter 2 - X.mp4"
    write_json(work / "ch10/script.json", {"scenes": []})
    assert [c.name for c in status.chapters(work)] == ["ch2", "ch10"]
    assert "ch10" in status.report(work)


def test_breakdown_lists_what_report_says():
    b = estimate.breakdown(22500, 2, True)
    assert b["usd"] == estimate.gemini_usd(2, True) == 0.88
    assert [i["label"] for i in b["items"]] == ["Narration (ElevenLabs)", "Background music", "2 short animated clips"]
    assert round(sum(i["usd"] for i in b["items"]), 2) == b["usd"]
    assert "22,500 characters" in b["items"][0]["detail"]
    assert estimate.breakdown(1000, 0, False, paid_voice=False) == {"usd": 0, "items": [{"label": "Narration (free voice)", "usd": 0}]}
    assert estimate.breakdown(1000, 1, False, paid_voice=False)["items"][1]["label"] == "1 short animated clip"


def test_breakdown_fits_the_plan_card():
    card = {"contract": 2, "kind": "plan", "message": "m", "markdown": "x",
            "estimate": {**estimate.breakdown(9000, 3, True), "minutes": 3, "chapters": 2}}
    assert contract.problems("card", card) == []


def test_estimate_json_command(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(keys, "get", lambda *a, **k: None)
    assert cli.main(["estimate", str(tmp_path), "--chapters", "2", "--minutes", "3", "--clips", "0", "--music", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["usd"] == estimate.gemini_usd(0, True)
    assert out["items"][0] == {"label": "Narration (free voice)", "usd": 0}


def test_breakdown_carries_quantities():
    assert estimate.breakdown(5400, 2, True, chapters=3, minutes=2.0)["quantities"] == \
        {"chapters": 3, "minutes": 2.0, "clips": 2, "music": True, "chars": 5400}
    assert "quantities" not in estimate.breakdown(5400, 2, True)


def test_estimate_json_command_prints_quantities(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(keys, "get", lambda *a, **k: None)
    assert cli.main(["estimate", str(tmp_path), "--chapters", "2", "--minutes", "3", "--clips", "0", "--music", "--json"]) == 0
    q = json.loads(capsys.readouterr().out)["quantities"]
    assert (q["chapters"], q["minutes"], q["clips"], q["music"]) == (2, 3, 0, True)
