import json

import pytest

from conftest import PLUGIN
from lv import cli, styles
from lv.util import UserError, write_json, write_text

SCHOOL = json.loads((PLUGIN / "styles/school/style.json").read_text(encoding="utf-8")) if (PLUGIN / "styles/school/style.json").is_file() else None


def run(capsys, *argv):
    code = cli.main(list(argv))
    return code, capsys.readouterr()


def a_style(root, sid="business", **over):
    data = {**SCHOOL, "id": sid, "name": sid.title(), "public": False, **over}
    write_json(root / sid / "style.json", data)
    write_text(root / sid / "guide.md", f"# {sid}\n")
    return data


def test_every_plugin_style_is_valid_and_named_after_its_folder():
    found = styles.installed()
    assert set(found) == {p.name for p in (PLUGIN / "styles").iterdir() if p.is_dir()}
    assert all(s.origin == "plugin" and s.guide.is_file() for s in found.values())


def test_school_asks_exactly_what_lesson_videos_asked(capsys):
    code, out = run(capsys, "style", "school")
    assert code == 0
    s = json.loads(out.out)
    assert s["questions"][0]["id"] == "grade"
    assert s["questions"][0]["text"] == "What grade are the students?"
    assert s["check"] == {"id": "students", "file": "student-info.md",
                          "looks_for": "names of students, class photos, graded student work",
                          "remove": "Remove these slides", "keep": "They're not students",
                          "keep_decision": "not students"}
    assert s["public"] is True and s["guide"].endswith("guide.md")


def test_styles_lists_school_alone_by_default(capsys, monkeypatch):
    monkeypatch.delenv("LV_STYLES_DIR", raising=False)
    code, out = run(capsys, "styles", "--json")
    assert code == 0 and [s["id"] for s in json.loads(out.out)] == ["school"]


def test_styles_dir_adds_styles(capsys, monkeypatch, tmp_path):
    a_style(tmp_path / "private styles")
    monkeypatch.setenv("LV_STYLES_DIR", str(tmp_path / "private styles"))
    code, out = run(capsys, "styles")
    assert code == 0 and "school" in out.out and "business" in out.out and "private styles" in out.out


@pytest.mark.parametrize("problem, expected", [
    ("duplicate", "Two styles have the id 'school'"),
    ("schema", "questions"),
    ("folder", "must equal the folder name"),
    ("guide", "guide.md is missing"),
])
def test_bad_styles_are_named(monkeypatch, tmp_path, problem, expected):
    root = tmp_path / "extra"
    if problem == "duplicate":
        a_style(root, "school")
    elif problem == "schema":
        a_style(root, questions="not a list")
    elif problem == "folder":
        data = a_style(root)
        write_json(root / "business" / "style.json", {**data, "id": "other"})
    else:
        a_style(root)
        (root / "business" / "guide.md").unlink()
    monkeypatch.setenv("LV_STYLES_DIR", str(root))
    with pytest.raises(UserError, match=expected):
        styles.installed()


def test_reserved_question_ids_are_refused(monkeypatch, tmp_path):
    for i, qid in enumerate(("chapters", "voice", "issue-1", "problem")):
        root = tmp_path / f"r{i}"
        a_style(root, questions=[{"id": qid, "text": "?", "options": "from-deck"}])
        monkeypatch.setenv("LV_STYLES_DIR", str(root))
        with pytest.raises(UserError):
            styles.installed()


def test_unknown_style_lists_the_installed_ones(capsys, monkeypatch):
    monkeypatch.delenv("LV_STYLES_DIR", raising=False)
    code, out = run(capsys, "style", "travel")
    assert code == 1 and "No style 'travel'" in out.err and "school" in out.err


def test_missing_styles_dir_is_a_clear_error(monkeypatch, tmp_path):
    monkeypatch.setenv("LV_STYLES_DIR", str(tmp_path / "nope"))
    with pytest.raises(UserError, match="isn't a folder"):
        styles.installed()
