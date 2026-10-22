import io

import pytest
from PIL import Image

from lv import ingest
from lv.util import UserError, read_json, read_text


def png(color, size=(400, 300)):
    b = io.BytesIO()
    Image.new("RGB", size, color).save(b, "PNG")
    b.seek(0)
    return b


def make_pptx(path):
    from pptx import Presentation
    from pptx.util import Inches
    prs = Presentation()
    s1 = prs.slides.add_slide(prs.slide_layouts[1])
    s1.shapes.title.text = "Osmosis – ¿qué es?"
    s1.placeholders[1].text = "Water follows salt 🌊 “always”"
    s1.shapes.add_picture(png("red"), Inches(5), Inches(2))
    s1.notes_slide.notes_text_frame.text = "Ask: which way does water move?"
    s2 = prs.slides.add_slide(prs.slide_layouts[5])
    s2.shapes.title.text = "Data"
    rows = s2.shapes.add_table(2, 2, Inches(1), Inches(2), Inches(4), Inches(1)).table
    rows.cell(0, 0).text, rows.cell(0, 1).text = "Before", "After"
    rows.cell(1, 0).text, rows.cell(1, 1).text = "39 g", "43 g"
    s2.shapes.add_picture(png("red"), Inches(5), Inches(2))      # same image again: deduplicated
    s2.shapes.add_picture(png("blue"), Inches(1), Inches(4))
    prs.save(str(path))


def test_ingest_unicode_text(tmp_path):
    deck = tmp_path / "deck.pptx"
    make_pptx(deck)
    out = ingest.ingest(deck, tmp_path / "work")
    md = read_text(out / "slides.md")
    assert "## Slide 1: Osmosis – ¿qué es?" in md and "🌊 “always”" in md
    assert "Speaker notes: Ask: which way does water move?" in md
    assert "Before | After" in md and "39 g | 43 g" in md
    assert len(list((out / "media").iterdir())) == 2
    assert "Images: s001-1.png" in md and "Images: s001-1.png, s002-2.png" in md
    assert (out / "contact-01.jpg").exists()


def test_ingest_path_with_spaces_and_accents(tmp_path):
    folder = tmp_path / "Unidad 1 – Biología"
    folder.mkdir()
    deck = folder / "Clase 1 – Ósmosis.pptx"
    make_pptx(deck)
    out = ingest.ingest(deck, ingest.default_work(deck))
    assert out == folder / "slide2video" / "_work" / "deck" and (out / "slides.md").exists()


def test_ingest_pdf(tmp_path):
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Photosynthesis\nProducers make glucose")
    page.insert_image(pymupdf.Rect(72, 120, 272, 270), stream=png("green").getvalue())
    deck = tmp_path / "deck.pdf"
    doc.save(str(deck))
    out = ingest.ingest(deck, tmp_path / "work")
    md = read_text(out / "slides.md")
    assert "## Slide 1: Photosynthesis" in md and "Producers make glucose" in md
    assert (out / "pages" / "p001.png").exists() and len(list((out / "media").iterdir())) == 1


@pytest.mark.parametrize("ext", [".key", ".ppt", ".odp"])
def test_unsupported_formats_explain_export(tmp_path, ext):
    deck = tmp_path / f"deck{ext}"
    deck.write_bytes(b"x")
    with pytest.raises(UserError) as e:
        ingest.ingest(deck, tmp_path / "work")
    assert "PowerPoint (.pptx)" in str(e.value)


def test_contact_sheet_survives_unreadable_image(tmp_path):
    (tmp_path / "a.emf").write_bytes(b"not an image at all")
    Image.new("RGB", (50, 50), "red").save(tmp_path / "b.png")
    sheets = ingest.contact_sheets(sorted(tmp_path.iterdir()), tmp_path)
    assert len(sheets) == 1 and sheets[0].exists()


def _replace_media(pptx, member_suffix, data):
    import zipfile
    src = zipfile.ZipFile(pptx)
    items = [(i, src.read(i.filename)) for i in src.infolist()]
    src.close()
    with zipfile.ZipFile(pptx, "w", zipfile.ZIP_DEFLATED) as z:
        for info, blob in items:
            z.writestr(info, data if info.filename.startswith("ppt/media/") and info.filename.endswith(member_suffix) else blob)


def test_ingest_survives_corrupt_and_mpo_images(tmp_path):
    from pptx import Presentation
    from pptx.util import Inches
    jpg = io.BytesIO()
    Image.new("RGB", (300, 200), "green").save(jpg, "JPEG")
    jpg.seek(0)
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[5])
    s.shapes.title.text = "Phone photos"
    s.shapes.add_picture(png("red"), Inches(1), Inches(2))
    s.shapes.add_picture(jpg, Inches(5), Inches(2))
    deck = tmp_path / "deck.pptx"
    prs.save(str(deck))
    mpo = io.BytesIO()
    Image.new("RGB", (300, 200), "blue").save(mpo, "MPO", save_all=True, append_images=[Image.new("RGB", (300, 200), "navy")])
    _replace_media(deck, ".png", b"\x00not an image")
    _replace_media(deck, ".jpg", mpo.getvalue())
    out = ingest.ingest(deck, tmp_path / "work")
    md = read_text(out / "slides.md")
    assert "Images: s001-1.png, s001-2.jpg" in md
    assert (out / "contact-01.jpg").exists()


def test_ingest_reads_chart_and_marks_it(tmp_path):
    from pptx import Presentation
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE
    from pptx.util import Inches
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[5])
    s.shapes.title.text = "Potato mass"
    data = CategoryChartData()
    data.categories = ["Before", "After"]
    data.add_series("Salt water", (39, 43))
    s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(1), Inches(2), Inches(6), Inches(4), data)
    deck = tmp_path / "deck.pptx"
    prs.save(str(deck))
    md = read_text(ingest.ingest(deck, tmp_path / "work") / "slides.md")
    assert "[Chart: column clustered]" in md
    assert "- Salt water: Before = 39, After = 43" in md


def _chart_deck(tmp_path, kind, categories, series, number_format="General", label_format=None):
    from pptx import Presentation
    from pptx.chart.data import CategoryChartData
    from pptx.util import Inches
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[5])
    s.shapes.title.text = "Chart"
    data = CategoryChartData(number_format=number_format)
    data.categories = categories
    for name, values in series:
        data.add_series(name, values)
    chart = s.shapes.add_chart(kind, Inches(1), Inches(2), Inches(6), Inches(4), data).chart
    if label_format:
        chart.plots[0].has_data_labels = True
        labels = chart.plots[0].data_labels
        labels.number_format, labels.number_format_is_linked = label_format, False
    deck = tmp_path / "deck.pptx"
    prs.save(str(deck))
    return read_text(ingest.ingest(deck, tmp_path / "work") / "slides.md")


def test_ingest_gives_every_value_of_every_series_in_the_deck_format(tmp_path):
    from pptx.enum.chart import XL_CHART_TYPE
    md = _chart_deck(tmp_path, XL_CHART_TYPE.COLUMN_CLUSTERED, ["Q3 26", "Q4 26", "Q1 27", "Q2 27", "Q3 27"],
                     [("Revenue", (43.0, 47.1, 41.8, 45.6, 48.2)), ("Costs", (30.0, 31.5, None, 32.0, 33.25))],
                     number_format="0.0")
    assert "- Revenue: Q3 26 = 43.0, Q4 26 = 47.1, Q1 27 = 41.8, Q2 27 = 45.6, Q3 27 = 48.2" in md
    assert "- Costs: Q3 26 = 30.0, Q4 26 = 31.5, Q1 27 = (blank), Q2 27 = 32.0, Q3 27 = 33.3" in md


def test_ingest_shows_a_pie_in_percent_when_the_deck_does(tmp_path):
    from pptx.enum.chart import XL_CHART_TYPE
    md = _chart_deck(tmp_path, XL_CHART_TYPE.PIE, ["Cafés", "Grocery", "Online", "Wholesale"],
                     [("Share", (0.58, 0.21, 0.13, 0.08))], number_format="0%")
    assert "[Chart: pie]" in md
    assert "- Share: Cafés = 58%, Grocery = 21%, Online = 13%, Wholesale = 8%" in md


def test_smartart_text_from_data_part():
    xml = (b'<dgm:dataModel xmlns:dgm="http://schemas.openxmlformats.org/drawingml/2006/diagram" '
           b'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><dgm:ptLst>'
           b'<dgm:pt><dgm:t><a:p><a:r><a:t>Evaporation</a:t></a:r></a:p></dgm:t></dgm:pt>'
           b'<dgm:pt><dgm:t><a:p><a:r><a:t>Condensation</a:t></a:r></a:p></dgm:t></dgm:pt>'
           b'</dgm:ptLst></dgm:dataModel>')
    assert ingest._smartart_text(xml) == "Evaporation / Condensation"


def test_ingest_writes_the_slide_count(tmp_path):
    deck = tmp_path / "deck.pptx"
    make_pptx(deck)
    out = ingest.ingest(deck, tmp_path / "work")
    assert read_json(out / "deck.json") == {"slides": 2}


def test_ingest_uses_the_data_labels_format_the_deck_shows(tmp_path):
    from pptx.enum.chart import XL_CHART_TYPE
    md = _chart_deck(tmp_path, XL_CHART_TYPE.PIE, ["Cafés", "Grocery"], [("Share", (0.58, 0.42))], label_format="0.0%")
    assert "- Share: Cafés = 58.0%, Grocery = 42.0%" in md
