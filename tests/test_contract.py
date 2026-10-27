import json

import pytest

from conftest import PLUGIN
from lv import cli, contract

EXAMPLES = PLUGIN / "site-contract" / "examples"


def _ex(name):
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def test_contract_version_is_the_plugin_major():
    assert contract.PLUGIN == "2.5.1"
    assert contract.VERSION == 2


@pytest.mark.parametrize("name", sorted(p.name for p in EXAMPLES.glob("*.json")))
def test_examples_are_valid(name):
    kind = "timing" if name == "timing.json" else name.split("-")[0]
    assert contract.problems(kind, _ex(name)) == []


def test_question_without_options_is_rejected():
    card = _ex("card-questions.json")
    del card["questions"][0]["options"]
    assert any("options" in p for p in contract.problems("card", card))


def test_unknown_card_kind_is_rejected():
    assert contract.problems("card", {"contract": 2, "kind": "chat", "message": "hi"})


def test_turn_needs_a_project_with_a_style():
    no_style = _ex("turn-start.json")
    del no_style["project"]["style"]
    assert any("style" in p for p in contract.problems("turn", no_style))
    old = _ex("turn-start.json")
    old["lesson"] = old.pop("project")
    assert contract.problems("turn", old)
    bad_id = _ex("turn-start.json")
    bad_id["project"]["id"] = "les_0123456789abcdefghijkl"
    assert contract.problems("turn", bad_id)


def test_wrong_contract_version_is_rejected():
    card = _ex("card-done.json")
    card["contract"] = 1
    assert contract.problems("card", card)


@pytest.mark.parametrize("path", ["in/../x.pptx", "in/.hidden", "/etc/passwd", "in/a/b.pptx", "out/x.pptx", "in/a\\b"])
def test_turn_file_paths_must_be_plain_names_in_in(path):
    turn = _ex("turn-start.json")
    turn["files"][0]["path"] = path
    assert contract.problems("turn", turn)


def test_card_command(tmp_path, capsys):
    good = tmp_path / "card.json"
    good.write_text(json.dumps(_ex("card-plan.json")), encoding="utf-8")
    assert cli.main(["card", str(good)]) == 0
    assert "card ok" in capsys.readouterr().out
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"contract": 2, "kind": "plan", "message": "x"}), encoding="utf-8")
    assert cli.main(["card", str(bad)]) == 1
    assert "markdown" in capsys.readouterr().out


def test_new_optional_fields_are_checked():
    plan = _ex("card-plan.json")
    plan["estimate"]["items"] = [{"label": "", "usd": 1}]
    assert any("items" in p for p in contract.problems("card", plan))
    plan["estimate"]["items"] = [{"label": "Music", "usd": -1}]
    assert any("items" in p for p in contract.problems("card", plan))
    q = _ex("card-questions.json")
    q["slides"] = 0
    assert any("slides" in p for p in contract.problems("card", q))
    q = _ex("card-questions.json")
    q["questions"][0]["options"][0]["recommended"] = "yes"
    assert any("recommended" in p for p in contract.problems("card", q))


def test_cards_without_the_new_fields_stay_valid():
    plan = _ex("card-plan.json")
    plan["estimate"].pop("items")
    q = _ex("card-questions.json")
    q.pop("slides")
    for question in q["questions"]:
        for o in question["options"]:
            o.pop("recommended", None)
    assert contract.problems("card", plan) == []
    assert contract.problems("card", q) == []


def test_plan_card_quantities_validate():
    card = {"contract": 2, "kind": "plan", "message": "m", "markdown": "x",
            "estimate": {"usd": 0, "minutes": 2, "chapters": 3,
                         "quantities": {"chapters": 3, "minutes": 2, "clips": 0, "music": False, "chars": 5400}}}
    assert contract.problems("card", card) == []
    card["estimate"]["quantities"]["chapters"] = 0
    assert contract.problems("card", card)


def test_error_card_reason_is_a_short_string():
    base = {"contract": 2, "kind": "error", "message": "m"}
    assert contract.problems("card", {**base, "reason": "busy"}) == []
    assert contract.problems("card", {**base, "reason": "x" * 41})


# --- review fixes (slide2video-site#7) -----------------------------------------------------------------------------------

def test_a_card_without_a_kind_gets_one_plain_problem():
    card = _ex("card-questions.json")
    del card["kind"]
    found = contract.problems("card", card)
    assert any("'kind' is a required property" in p for p in found)
    assert not any("questions" in p for p in found)   # no noise from the kind-specific rules


@pytest.mark.parametrize("value", ["tomorrow", "2026-10-24", "2026-10-24T15:00:00", "2026-13-40T25:00:00Z", "2026-10-24 15:00:00Z"])
def test_retry_after_must_be_an_rfc3339_date_time(value):
    card = _ex("card-error.json")
    card["retry_after"] = value
    assert any("retry_after" in p for p in contract.problems("card", card)), value


@pytest.mark.parametrize("value", [None, "2026-10-24T15:00:00Z", "2026-10-24T15:00:00.5-07:00"])
def test_retry_after_takes_a_date_time_or_null(value):
    card = _ex("card-error.json")
    card["retry_after"] = value
    assert contract.problems("card", card) == []


@pytest.mark.parametrize("kind", ["chat", "", "START", None])
def test_turn_kind_must_be_one_the_plugin_knows(kind):
    turn = _ex("turn-start.json")
    turn["turn"]["kind"] = kind
    assert any("kind" in p for p in contract.problems("turn", turn))


@pytest.mark.parametrize("change", [
    lambda t: t.pop("scenes"), lambda t: t.update(duration=-1), lambda t: t["scenes"][0].pop("start"),
    lambda t: t["scenes"][0].update(dur="5"), lambda t: t["scenes"][0].update(slide=0),
], ids=["no scenes", "negative duration", "scene without start", "string dur", "slide 0"])
def test_a_malformed_timing_is_refused(change):
    timing = _ex("timing.json")
    change(timing)
    assert contract.problems("timing", timing)


def test_card_command_checks_a_review_cards_files_as_the_worker_will(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("LV_SITE_ROOT", str(tmp_path))
    (tmp_path / "lesson-videos").mkdir()
    (tmp_path / "lesson-videos" / "Chapter 1.mp4").write_bytes(b"mp4")
    (tmp_path / "elsewhere.mp4").write_bytes(b"mp4")
    card = {**_ex("card-review.json"), "video": "lesson-videos/Chapter 1.mp4"}
    card.pop("captions", None)
    card.pop("stills", None)
    f = tmp_path / "card.json"
    f.write_text(json.dumps(card), encoding="utf-8")
    assert cli.main(["card", str(f)]) == 0
    capsys.readouterr()
    f.write_text(json.dumps({**card, "video": "elsewhere.mp4"}), encoding="utf-8")
    assert cli.main(["card", str(f)]) == 1
    out = capsys.readouterr().out
    assert "video:" in out and "lesson-videos" in out and "render" in out
