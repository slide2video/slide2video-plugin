from lv import doctor


def test_doctor_without_keys(browser_ok, capsys):
    assert doctor.run_doctor(no_keys=True, install=False) == 0
    out = capsys.readouterr().out
    for item in ("ffmpeg", "Chromium renderer", "Fonts", "Sound effects", "Test video"):
        assert f"✓ {item}" in out


def test_doctor_reports_missing_key(browser_ok, capsys):
    assert doctor.run_doctor(no_keys=False, install=False) == 1
    assert "✗ ElevenLabs key" in capsys.readouterr().out
