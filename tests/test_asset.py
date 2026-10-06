import pytest
from PIL import Image

from lv import ingest
from lv.util import UserError


def test_asset_converts_rgba_png_to_jpg_and_downscales(tmp_path):
    Image.new("RGBA", (3200, 1600), (255, 0, 0, 128)).save(tmp_path / "in.png")
    out = ingest.prepare_asset(tmp_path / "in.png", tmp_path / "assets" / "o'brien photo.jpg")
    with Image.open(out) as im:
        assert im.mode == "RGB" and im.size == (1600, 800)


def test_asset_explains_unreadable_formats(tmp_path):
    (tmp_path / "diagram.emf").write_bytes(b"\x01\x00\x00\x00 not really")
    with pytest.raises(UserError) as e:
        ingest.prepare_asset(tmp_path / "diagram.emf", tmp_path / "assets" / "diagram.png")
    assert "PNG" in str(e.value)
