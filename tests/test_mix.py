from lv import mix, narrate, sfx, tools
from lv.util import write_json


def test_mix_groups_sfx_and_skips_unknown(make_chapter, fake_speak, capsys):
    sfx.build()
    ch = make_chapter([{"id": "a", "min": 3}])
    T = narrate.narrate(ch, speak_fn=fake_speak)
    write_json(ch / "build/sfx.json", [{"t": 0.5, "name": "pop0", "gain": -12}, {"t": 1.0, "name": "pop0"},
                                       {"t": 1.5, "name": "sparkle1"}, {"t": 2.0, "name": "k_question_001"}])
    out = mix.mix_audio(ch, T, {"music": "../music/missing.mp3"})
    assert abs(tools.duration(out) - 3) < 0.2
    said = capsys.readouterr().out
    assert "k_question_001" in said and "missing.mp3" in said
