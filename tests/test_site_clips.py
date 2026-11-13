"""A website turn's `clips` (contract 2.8.0): the most AI clips the video project may have, chosen on the website."""
import json

import pytest

from lv import cli, clips, contract, keys, worker
from lv.util import write_json

TURN = {"contract": 2, "project": {"id": "prj_0123456789abcdefghijkl", "title": "Unit 3", "style": "school"},
        "turn": {"id": "trn_0123456789abcdefghijkl", "seq": 1, "kind": "start", "lease_seconds": 1800}, "files": []}


def test_the_contract_takes_an_optional_clip_count():
    assert contract.problems("turn", TURN) == []
    for n in (0, 1, 6, 50):
        assert contract.problems("turn", {**TURN, "clips": n}) == [], n
    for bad in (-1, 51, 2.5, "2", True, None):
        assert contract.problems("turn", {**TURN, "clips": bad}) != [], bad


@pytest.mark.parametrize("extra, allowed", [
    ({}, None),                                  # a computer's turn: the plugin plans clips as it always has
    ({"clips": 0}, 0),
    ({"clips": 4}, 4),
    ({"clips": 4, "mode": "normal"}, 4),
    ({"mode": "premium"}, 0),                     # the website's processing, from before `clips`: nobody chose clips
    ({"clips": -2}, 0), ({"clips": "3"}, 0), ({"clips": True}, 0), ({"clips": None}, 0),  # anything else: none
])
def test_clips_allowed(extra, allowed):
    assert worker.clips_allowed({**TURN, **extra}) == allowed


def test_the_limit_reaches_claudes_commands_from_the_turn_written_before_it_starts(monkeypatch, tmp_path):
    monkeypatch.setenv("LV_SITE_CLIPS", "9")  # never one from the worker's own environment
    assert "LV_SITE_CLIPS" not in worker._site_env(tmp_path, root=tmp_path)
    write_json(tmp_path / "site" / "turn.json", {**TURN, "clips": 2})
    assert worker._site_env(tmp_path, root=tmp_path)["LV_SITE_CLIPS"] == "2"
    write_json(tmp_path / "site" / "turn.json", {**TURN, "mode": "normal"})
    assert worker._site_env(tmp_path, root=tmp_path)["LV_SITE_CLIPS"] == "0"
    write_json(tmp_path / "site" / "turn.json", TURN)
    assert "LV_SITE_CLIPS" not in worker._site_env(tmp_path, root=tmp_path)
    (tmp_path / "site" / "turn.json").write_text("{not json", encoding="utf-8")
    assert "LV_SITE_CLIPS" not in worker._site_env(tmp_path, root=tmp_path)


def _estimate(tmp_path, n: int) -> int:
    return cli.main(["estimate", str(tmp_path), "--chapters", "2", "--minutes", "3", "--clips", str(n), "--json"])


def test_site_mode_plans_no_more_clips_than_allowed(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(keys, "get", lambda *a, **k: None)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LV_SITE_MODE", "1")
    monkeypatch.setenv("LV_SITE_CLIPS", "0")
    assert _estimate(tmp_path, 1) == 1
    assert "AI clips are off" in capsys.readouterr().err
    assert _estimate(tmp_path, 0) == 0
    assert json.loads(capsys.readouterr().out)["quantities"]["clips"] == 0
    monkeypatch.setenv("LV_SITE_CLIPS", "2")
    assert _estimate(tmp_path, 3) == 1
    assert "at most 2 AI clips" in capsys.readouterr().err
    assert _estimate(tmp_path, 2) == 0
    assert json.loads(capsys.readouterr().out)["quantities"]["clips"] == 2
    # without a limit (a computer's turn, or no site mode): as before
    monkeypatch.delenv("LV_SITE_CLIPS")
    assert _estimate(tmp_path, 7) == 0
    capsys.readouterr()
    monkeypatch.setenv("LV_SITE_CLIPS", "0")
    monkeypatch.delenv("LV_SITE_MODE")
    assert _estimate(tmp_path, 7) == 0


def test_site_mode_makes_no_more_clips_than_allowed(monkeypatch, tmp_path, capsys):
    made = []
    monkeypatch.setattr(clips, "make_clip", lambda image, prompt, name, work, frac: made.append(name))
    monkeypatch.chdir(tmp_path)
    (tmp_path / "photo.jpg").write_bytes(b"x")
    folder = tmp_path / "w" / "clips"

    def clip(name: str) -> int:
        return cli.main(["clip", str(tmp_path / "photo.jpg"), "--work", str(tmp_path / "w"), "--name", name, "--prompt", "p"])
    monkeypatch.setenv("LV_SITE_MODE", "1")
    monkeypatch.setenv("LV_SITE_CLIPS", "0")
    assert clip("river") == 1
    assert "AI clips are off" in capsys.readouterr().err
    monkeypatch.setenv("LV_SITE_CLIPS", "2")
    folder.mkdir(parents=True)
    (folder / "river.mp4").write_bytes(b"v")
    assert clip("river") == 0       # making one again replaces it
    assert clip("kelp") == 0
    (folder / "kelp.mp4").write_bytes(b"v")
    assert clip("fish") == 1
    assert "already has the 2 AI clips" in capsys.readouterr().err
    assert made == ["river", "kelp"]
    monkeypatch.delenv("LV_SITE_CLIPS")
    assert clip("fish") == 0
    assert made == ["river", "kelp", "fish"]


def test_site_mode_never_asks_about_clips_and_follows_the_turn():
    from pathlib import Path
    make = (Path(__file__).parents[1] / "slide2video/skills/make/SKILL.md").read_text(encoding="utf-8")
    site = make.split("## Site mode", 1)[1]
    rule = " ".join(site.split("- **Clips:**", 1)[1].split("\n- **", 1)[0].split())
    for needed in ("`clips`", "never ask about clips", "`mode` but no `clips`", "plan at most that many", "`estimate --clips`",
                   "neither `clips` nor `mode`"):
        assert needed in rule, needed
