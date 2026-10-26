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


def test_a_clip_is_one_omni_flash_interaction_answered_at_once(tmp_path):
    Image.new("RGB", (1600, 900), "blue").save(tmp_path / "a.png")
    calls = []

    def fake(url, data=None, headers=None, timeout=None, retries=None, **kw):
        calls.append((url, data, headers, retries))
        return {"status": "completed", "usage": {"total_output_tokens": 57920},
                "steps": [{"type": "thought", "content": [{"type": "thought", "text": "..."}]},
                          {"type": "model_output", "content": [{"type": "video", "mime_type": "video/mp4",
                                                                 "data": base64.b64encode(b"MP4DATA").decode()}]}]}
    out = clips.make_clip(tmp_path / "a.png", "kelp swaying", "kelp", tmp_path, request=fake, strip=False)
    assert out.read_bytes() == b"MP4DATA"
    [(url, data, headers, retries)] = calls
    assert url.endswith("/v1beta/interactions") and headers == {"x-goog-api-key": KEY}
    assert data["model"] == "gemini-omni-1.1-flash" and data["generation_config"] == {"video_config": {"task": "image_to_video"}}
    assert data["response_format"] == {"type": "video", "resolution": "720p", "aspect_ratio": "16:9"}
    assert (data["background"], data["store"], data["stream"]) == (False, False, False)
    assert [p["type"] for p in data["input"]] == ["image", "text"] and data["input"][1]["text"] == "kelp swaying"
    assert retries == 0   # a retry after a failed answer could pay for a second clip


@pytest.mark.parametrize("resp, says", [
    ({"status": "completed", "steps": [{"type": "model_output", "content": [{"type": "text", "text": "I can't make that video."}]}]},
     "I can't make that video."),
    ({"status": "failed", "steps": []}, "status: failed"),
    ({}, "status: none"),
], ids=["refused in words", "failed", "empty"])
def test_no_video_says_why(resp, says):
    with pytest.raises(UserError) as e:
        clips.video_of(resp)
    assert "made no clip" in str(e.value) and says in str(e.value)


def test_a_clip_api_error_never_shows_the_key(tmp_path):
    Image.new("RGB", (1600, 900), "blue").save(tmp_path / "a.png")

    def fake(url, **kw):
        raise net.ApiError(429, "RESOURCE_EXHAUSTED: billing " + KEY, url)
    with pytest.raises(UserError) as e:
        clips.make_clip(tmp_path / "a.png", "x", "kelp", tmp_path, request=fake, strip=False)
    assert KEY not in str(e.value)


def test_frames(tmp_path):
    mp4 = tmp_path / "c.mp4"
    subprocess.run([tools.ffmpeg(), "-v", "error", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=24", "-t", "1",
                    "-pix_fmt", "yuv420p", str(mp4)], check=True)
    assert clips.frames(mp4, tmp_path / "clip_c") == 24
    assert clips.frames(mp4, tmp_path / "clip_c", max_frames=10) == 10
    assert (tmp_path / "clip_c/0001.jpg").exists()


def test_clips_are_on_and_priced_from_config(monkeypatch, tmp_path, capsys):
    from lv import cli, config, keys
    monkeypatch.setattr(keys, "get", lambda *a, **k: None)
    assert cli.main(["estimate", str(tmp_path), "--chapters", "2", "--minutes", "3", "--clips", "2", "--music", "--json"]) == 0
    import json
    est = json.loads(capsys.readouterr().out)
    assert est["usd"] == round(2 * config.CLIP_PRICE + config.LYRIA_PRICE, 2)
    assert {"label": "2 short animated clips", "usd": round(2 * config.CLIP_PRICE, 2), "detail": "10 seconds each"} in est["items"]


def test_the_make_skill_offers_clips_again():
    from pathlib import Path
    make = (Path(__file__).parents[1] / "slide2video/skills/make/SKILL.md").read_text(encoding="utf-8")
    assert "AI clips are off" not in make
    assert "LV clip " in make and "--clips <K>" in make and "A clip is 10 seconds" in make
