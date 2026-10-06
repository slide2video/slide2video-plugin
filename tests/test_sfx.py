import wave

from lv import sfx


def test_build_makes_every_name_once(lv_home):
    d = sfx.build()
    assert d == lv_home / "sfx"
    for name in sfx.NAMES:
        with wave.open(str(d / f"{name}.wav")) as w:
            assert (w.getnchannels(), w.getframerate()) == (2, 48000) and w.getnframes() > 1000
    stamp = (d / "pop0.wav").stat().st_mtime_ns
    sfx.build()
    assert (d / "pop0.wav").stat().st_mtime_ns == stamp
