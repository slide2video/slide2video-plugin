import json

import pytest

from conftest import PLUGIN
from lv import cli, contract

EXAMPLES = PLUGIN / "site-contract" / "examples"


def _ex(name):
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def test_version_is_an_integer():
    assert contract.VERSION == 1


@pytest.mark.parametrize("name", sorted(p.name for p in EXAMPLES.glob("*.json")))
def test_examples_are_valid(name):
    kind = "timing" if name == "timing.json" else name.split("-")[0]
    assert contract.problems(kind, _ex(name)) == []


def test_question_without_options_is_rejected():
    card = _ex("card-questions.json")
    del card["questions"][0]["options"]
    assert any("options" in p for p in contract.problems("card", card))


def test_unknown_card_kind_is_rejected():
    assert contract.problems("card", {"contract": 1, "kind": "chat", "message": "hi"})


def test_wrong_contract_version_is_rejected():
    card = _ex("card-done.json")
    card["contract"] = 2
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
    bad.write_text(json.dumps({"contract": 1, "kind": "plan", "message": "x"}), encoding="utf-8")
    assert cli.main(["card", str(bad)]) == 1
    assert "markdown" in capsys.readouterr().out
