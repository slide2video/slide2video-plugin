import base64

from lv import cli, music, paths
from lv.util import read_text, write_text


def test_init_then_where(tmp_path, capsys):
    assert cli.main(["init", "--path", str(tmp_path / "Media")]) == 0
    out = capsys.readouterr().out
    assert "config.yaml" in out and "lessons" in out
    lesson = tmp_path / "Media" / "lessons" / "biology" / "unit-2"
    assert cli.main(["where", str(lesson)]) == 0
    out = capsys.readouterr().out
    assert "lesson:  biology/unit-2" in out and "videos:" in out and "sources:" in out


def test_init_notes_a_config_without_lessons_dir(tmp_path, capsys):
    write_text(tmp_path / "p/config.yaml", "artist: Someone\n")
    assert cli.main(["init", "--path", str(tmp_path / "p")]) == 0
    out = capsys.readouterr().out
    assert "kept" in out and "lessons_dir: lessons" in out
    assert read_text(tmp_path / "p/config.yaml") == "artist: Someone\n"


def test_where_without_project(tmp_path, capsys):
    assert cli.main(["where", str(tmp_path)]) == 0
    assert "next to the deck" in capsys.readouterr().out


def test_where_reports_missing_project(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LESSON_VIDEOS_PROJECT", str(tmp_path / "gone"))
    assert cli.main(["where", str(tmp_path)]) == 0
    assert "doesn't exist" in capsys.readouterr().out


def test_where_for_a_chapter(lv_project, capsys):
    ch = lv_project.lessons_dir / "biology" / "unit-2" / "ch1"
    write_text(ch / "script.json", "{}")
    assert cli.main(["where", str(ch)]) == 0
    out = capsys.readouterr().out
    assert "assets:" in out and "voice:" in out and "build:" in out


def test_music_and_ingest_use_the_lesson_folders(lv_project, monkeypatch, tmp_path):
    from test_ingest import make_pptx
    unit = lv_project.lessons_dir / "biology" / "unit-2"
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyD-abcdefghijklmnopqrstuvwxyz12345")
    fake = lambda url, **kw: {"steps": [{"content": [{"type": "audio", "data": base64.b64encode(b"ID3").decode()}]}]}
    assert music.make_bed(unit, "calm", request=fake) == paths.lesson(unit).sources / "music" / "bed.mp3"
    deck = tmp_path / "deck folder" / "Deck.pptx"
    deck.parent.mkdir()
    make_pptx(deck)
    assert cli.main(["ingest", str(deck), "--work", str(unit)]) == 0
    assert (paths.lesson(unit).work / "deck" / "slides.md").exists()
    assert not (unit / "deck").exists()


def test_where_outside_the_project(lv_project, tmp_path, capsys):
    assert cli.main(["where", str(tmp_path / "Desktop")]) == 0
    out = capsys.readouterr().out
    assert "not inside" in out and str(lv_project.lessons_dir) in out


def test_where_at_the_project_root(lv_project, capsys):
    assert cli.main(["where", str(lv_project.home)]) == 0
    out = capsys.readouterr().out
    assert "next to the deck" not in out and "<course>/<unit>" in out and str(lv_project.lessons_dir) in out
