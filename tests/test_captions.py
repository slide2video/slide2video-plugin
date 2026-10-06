from lv import captions

T = {"scenes": [
    {"start": 10.0, "words": [{"w": "One.", "s": 0.5, "e": 0.9}, {"w": "Two", "s": 1.0, "e": 1.2}, {"w": "three!", "s": 1.3, "e": 1.6}]},
    {"start": 20.0, "words": [{"w": f"w{i}", "s": i * 0.1, "e": i * 0.1 + 0.05} for i in range(20)]},
]}


def test_segments_split_on_sentences_and_16_words():
    seg = captions.segments(T)
    assert seg[0] == (10.5, 10.9, "One.") and seg[1] == (11.0, 11.6, "Two three!")
    assert len(seg[2][2].split()) == 16 and len(seg[3][2].split()) == 4


def test_stamp_and_vtt():
    assert captions.stamp(3725.5) == "01:02:05.500"
    v = captions.vtt(T)
    assert v.startswith("WEBVTT\n\n1\n00:00:10.500 --> 00:00:11.250\nOne.\n")
