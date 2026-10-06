import base64
import subprocess

import pytest
from PIL import Image

from lv import clips, music, net, tools
from lv.util import UserError

KEY = "AIzaSyD-abcdefghijklmnopqrstuvwxyz12345"


@pytest.fixture(autouse=True)
def gemini_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", KEY)


def test_make_bed_writes_mp3(tmp_path):
    def fake(url, data=None, headers=None, timeout=None, **kw):
        assert url.endswith("/interactions") and data["model"] == "lyria-3.5"
        return {"steps": [{"content": [{"type": "audio", "data": base64.b64encode(b"ID3fake").decode()}]}]}
    out = music.make_bed(tmp_path, "calm lo-fi study music", request=fake)
    assert out == tmp_path / "music/bed.mp3" and out.read_bytes() == b"ID3fake"


def test_make_bed_billing_error(tmp_path):
    def fake(url, **kw):
        raise net.ApiError(429, "RESOURCE_EXHAUSTED: billing", url)
    with pytest.raises(UserError) as e:
        music.make_bed(tmp_path, "x", request=fake)
    assert "billing" in str(e.value) and KEY not in str(e.value)


def test_prep_crops_to_720p(tmp_path):
    Image.new("RGB", (1000, 1000), "red").save(tmp_path / "a.png")
    import io
    with Image.open(io.BytesIO(clips.prep(tmp_path / "a.png"))) as im:
        assert im.size == (1280, 720)


def test_veo_polls_then_downloads(tmp_path):
    Image.new("RGB", (1600, 900), "blue").save(tmp_path / "a.png")
    calls = []
    def fake(url, data=None, headers=None, timeout=None, raw=False, **kw):
        calls.append(url)
        if url.endswith(":predictLongRunning"):
            assert data["parameters"]["resolution"] == "720p"
            return {"name": "operations/abc"}
        if url.endswith("operations/abc"):
            return {"done": len(calls) > 2, "response": {"generateVideoResponse": {"generatedSamples": [{"video": {"uri": "https://dl.test/v.mp4"}}]}}}
        assert raw
        return b"MP4DATA"
    out = clips.make_clip(tmp_path / "a.png", "kelp swaying", "kelp", tmp_path, request=fake, sleep=lambda s: None, strip=False)
    assert out.read_bytes() == b"MP4DATA" and calls[-1] == "https://dl.test/v.mp4"


def test_veo_safety_filter_message():
    op = {"done": True, "response": {"generateVideoResponse": {"raiMediaFilteredCount": 1, "raiMediaFilteredReasons": ["person"]}}}
    with pytest.raises(UserError) as e:
        clips.result_uri(op)
    assert "safety filter" in str(e.value)


def test_frames(tmp_path):
    mp4 = tmp_path / "c.mp4"
    subprocess.run([tools.ffmpeg(), "-v", "error", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=24", "-t", "1",
                    "-pix_fmt", "yuv420p", str(mp4)], check=True)
    assert clips.frames(mp4, tmp_path / "clip_c") == 24
    assert clips.frames(mp4, tmp_path / "clip_c", max_frames=10) == 10
    assert (tmp_path / "clip_c/0001.jpg").exists()
