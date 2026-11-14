"""A website turn's `clips` (contract 2.8.0): the most AI clips the video project may have, chosen on the website."""
import base64
import json
from pathlib import Path

import pytest
from PIL import Image

from lv import cli, clips, contract, keys, net, worker
from lv.util import UserError, write_json

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


def test_clips_are_counted_in_the_private_folder_never_in_the_lesson(monkeypatch, tmp_path):
    lesson, private = tmp_path / "lesson", tmp_path / "private"
    monkeypatch.setenv("LV_SITE_CLIP_LEDGER", str(lesson / "planted"))  # never one from the worker's own environment
    assert "LV_SITE_CLIP_LEDGER" not in worker._site_env(private, root=lesson)
    write_json(lesson / "site" / "turn.json", {**TURN, "clips": 2})
    ledger = Path(worker._site_env(private, root=lesson)["LV_SITE_CLIP_LEDGER"])
    assert ledger.parent == private and lesson not in ledger.parents


def _estimate(tmp_path, n: int) -> int:
    return cli.main(["estimate", str(tmp_path), "--chapters", "2", "--minutes", "3", "--clips", str(n), "--json"])


def test_site_mode_plans_no_more_clips_than_allowed(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(keys, "get", lambda *a, **k: None)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LV_SITE_MODE", "1")
    monkeypatch.setenv("LV_SITE_CLIPS", "0")
    assert _estimate(tmp_path, 1) == 1
    assert "No AI clips are left" in capsys.readouterr().err
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


def _photo(folder: Path) -> Path:
    Image.new("RGB", (1600, 900), "blue").save(folder / "photo.png")
    return folder / "photo.png"


def _video(*a, **k):
    return {"steps": [{"type": "model_output", "content": [{"type": "video", "data": base64.b64encode(b"MP4").decode()}]}]}


def _site(monkeypatch, tmp_path, limit: str | None, ledger: bool = True) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LV_SITE_MODE", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    for name, value in (("LV_SITE_CLIPS", limit), ("LV_SITE_CLIP_LEDGER", str(tmp_path.parent / "private") if ledger else None)):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    return tmp_path.parent / "private"


def test_site_mode_makes_no_more_clips_than_allowed_whatever_happens_to_the_lesson_folder(monkeypatch, tmp_path, capsys):
    """The count is the step's places in the private ledger: deleting or renaming clips, or another work folder, frees
    nothing."""
    lesson = tmp_path / "lesson"
    lesson.mkdir()
    photo = _photo(lesson)
    asked = []
    monkeypatch.setattr(clips, "omni", lambda png, prompt, request=None: asked.append(prompt) or b"MP4")
    monkeypatch.setattr(clips, "run", lambda *a, **k: None)  # no ffmpeg strip

    def clip(name: str, work: str = "w") -> int:
        return cli.main(["clip", str(photo), "--work", str(lesson / work), "--name", name, "--prompt", name])
    _site(monkeypatch, lesson, "0")
    assert clip("river") == 1
    assert "No AI clips are left" in capsys.readouterr().err
    _site(monkeypatch, lesson, "2")
    assert clip("river") == 0
    assert clip("kelp") == 0
    for mp4 in (lesson / "w").rglob("*.mp4"):
        mp4.unlink()  # deleting (or renaming) the clips gives nothing back
    assert clip("fish") == 1
    assert clip("fish", work="other") == 1  # nor does another work folder
    assert "at most 2 AI clips" in capsys.readouterr().err
    assert asked == ["river", "kelp"]
    # no ledger with a limit (never so from the worker): refused; no limit (a computer's turn): as before
    _site(monkeypatch, lesson, "2", ledger=False)
    assert clip("eel") == 1
    _site(monkeypatch, lesson, None, ledger=False)
    assert clip("eel") == 0
    assert asked == ["river", "kelp", "eel"]


def test_clip_commands_started_together_never_share_a_place(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    def take(_):
        try:
            return clips.reserve_place(tmp_path / "ledger", 3).name
        except UserError:
            return None
    with ThreadPoolExecutor(max_workers=12) as pool:
        got = list(pool.map(take, range(24)))
    assert sorted(g for g in got if g) == ["clip-1", "clip-2", "clip-3"]


@pytest.mark.parametrize("fails, given_back", [
    ("error answer", True),        # the service refused the call (4xx): nothing billed
    ("server error", False),       # a 5xx may come after the work was done
    ("no answer", False),          # a timeout or a dropped connection may have been billed
    ("no video", False),           # the service answered: billed
    ("bad photo", True),           # never sent
    ("no key", True),              # never sent
    (None, False),                 # a clip made
])
def test_a_place_is_given_back_only_when_the_clip_cant_have_been_billed(monkeypatch, tmp_path, fails, given_back):
    photo = _photo(tmp_path)
    if fails == "no key":
        monkeypatch.setattr(keys, "get", lambda var, required=True: (_ for _ in ()).throw(keys.MissingKey("no key")))
    else:
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    if fails == "bad photo":
        photo.write_bytes(b"not a picture")

    def request(url, **kw):
        if fails == "error answer":
            raise net.ApiError(400, "INVALID_ARGUMENT", url)
        if fails == "server error":
            raise net.ApiError(500, "INTERNAL", url)
        if fails == "no answer":
            raise net.ApiError(0, "timed out", url)
        return {"status": "completed", "steps": []} if fails == "no video" else _video()
    place = clips.reserve_place(tmp_path / "ledger", 1)
    if fails:
        with pytest.raises(Exception):
            clips.make_clip(photo, "p", "kelp", tmp_path, request=request, strip=False, place=place)
    else:
        clips.make_clip(photo, "p", "kelp", tmp_path, request=request, strip=False, place=place)
    assert place.exists() is not given_back



def test_site_mode_never_asks_about_clips_and_follows_the_turn():
    from pathlib import Path
    make = (Path(__file__).parents[1] / "slide2video/skills/make/SKILL.md").read_text(encoding="utf-8")
    site = make.split("## Site mode", 1)[1]
    rule = " ".join(site.split("- **Clips:**", 1)[1].split("\n- **", 1)[0].split())
    for needed in ("`clips`", "never ask about clips", "`mode` but no `clips`", "plan at most that many", "`estimate --clips`",
                   "neither `clips` nor `mode`"):
        assert needed in rule, needed
