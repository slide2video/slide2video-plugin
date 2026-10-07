from lv import doctor


def test_doctor_without_keys(browser_ok, capsys):
    assert doctor.run_doctor(no_keys=True, install=False) == 0
    out = capsys.readouterr().out
    for item in ("ffmpeg", "Chromium renderer", "Fonts", "Sound effects", "Test video"):
        assert f"✓ {item}" in out


def test_doctor_passes_with_no_keys_at_all(browser_ok, capsys, monkeypatch):
    from lv import voices
    monkeypatch.setitem(voices.SPEAKERS, "edge", lambda *a: (_ for _ in ()).throw(voices.VoiceUnavailable("offline")))
    assert doctor.run_doctor(no_keys=False, install=False) == 0
    out = capsys.readouterr().out
    assert "✓ ElevenLabs key: not set (optional)" in out and "✓ Narration:" in out and "captions" in out
